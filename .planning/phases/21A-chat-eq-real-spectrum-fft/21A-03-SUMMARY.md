---
phase: 21A
plan: 03
subsystem: System/adam/mic_reader / Wave 2 (backend FFT)
tags: [fft, spectrum, equaliser, hot-reload, audio_level, numpy]
dependency_graph:
  requires:
    - "21A-01 (Wave 0): tests/test_mic_reader_spectrum.py contract"
    - "21A-02 (Wave 1): 8 spectrum_* keys in Config.json + Config.schema.json"
  provides:
    - "MicReader._compute_bands(mono_chunk) → list[float]|None — 24 log-band dBFS-normalised FFT"
    - "audio_level event payload extended with bands: list[float] length 24"
    - "Per-instance _audio_level_emit_every_n derived from spectrum_cadence_hz (25 Hz @ prod defaults)"
    - "apply_config hot-reload for all 8 spectrum_* keys with lazy band-table rebuild"
  affects:
    - "21A-05 (frontend wakeMeter.js) — consumes payload['bands'] for chat-panel EQ widget"
    - "events.jsonl growth ~2.5× (10 Hz → 25 Hz audio_level cadence; documented cost per D-04)"
tech_stack:
  added:
    - "numpy (already in venv, no new install) — np.fft.rfft + np.hanning for per-frame spectrum"
    - "stdlib math.log10 / math.exp for dBFS + log-frequency band edges"
  patterns:
    - "Precomputed log-frequency binning table built once at __init__, rebuilt only when bands/min/max/sample_rate/frame_ms change (RESEARCH §1 Pattern 1)"
    - "Stateless dBFS mapper: band_mag → 20*log10(mag/ref) → clamp(floor_db, ceiling_db) → linear [0,1] (RESEARCH §3 Pattern 2)"
    - "DC bin 0 skipped (lo = max(1, …)) to suppress INMP441 DC-offset artefact (Pitfall 1)"
    - "Hann window stored as float32 once at __init__ (avoids float64 promotion per frame, Pitfall 2)"
    - "mag_ref = 0.5 × INT16_MAX × sum(Hann) — full-scale rfft peak reference (Pitfall 3)"
    - "Synthetic _level_emit_loop OMITS bands by design — no fresh PCM → no honest spectrum (RESEARCH §12)"
    - "FFT exceptions swallowed via try/except → emit spectrum_error event and return None; audio_level path never stalls"
key_files:
  created:
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/21A-03-SUMMARY.md"
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/deferred-items.md"
  modified:
    - "System/adam/mic_reader.py"
decisions:
  - "FFT computed on Jetson backend (D-01) — same mono_chunk that already drives RMS/OWW/ASR; truth-by-construction"
  - "_compute_bands lives on MicReader as a method (not module-level) so it has direct access to per-instance state (_spec_hann, _spec_band_table, _spec_mag_ref)"
  - "Cadence bumped from 10 Hz (every 5th frame) to 25 Hz (every 2nd frame) via instance attribute, not module constant — enables hot-reload (D-04, D-16)"
  - "Module constant _AUDIO_LEVEL_EMIT_EVERY_N_FRAMES=5 retained as DEPRECATED alias for backwards-compat readers but no longer referenced by _drain_loop"
  - "FFT exceptions logged as 'spectrum_error' event and swallowed — never breaks the UI VU-meter (precedent: B-1 fix that keeps audio_level live during mute)"
  - "table_dirty in apply_config also fires when restart_needed is already True — covers sample_rate/frame_ms/profile changes that affect n_fft"
metrics:
  duration: "single session"
  completed: 2026-05-18
  tasks_total: 3
  tasks_completed: 3
  files_created: 2
  files_modified: 1
---

# Phase 21A Plan 03: Wave 2 — Backend FFT Integration Summary

Wave 2 of Phase 21A — server-side 24-band log-frequency FFT spectrum wired into `MicReader._emit_audio_level`. The chat-panel equaliser widget on the frontend (Plan 05) will now receive a real per-frame spectrum at 25 Hz instead of the legacy synthetic shape.

## What Shipped

| Artifact | Purpose |
| --- | --- |
| `_build_log_band_table(n_fft, sample_rate, n_bands, min_hz, max_hz)` | Module-level helper that returns 24 `(lo_bin, hi_bin)` inclusive ranges into the rfft output. Log-spaced edges via `exp(linspace(log(min_hz), log(max_hz), n_bands+1))`. DC bin 0 skipped. |
| `MicReader._compute_bands(mono_chunk) → list[float]\|None` | Per-frame FFT pipeline: int16 → float32 → Hann → rfft → per-band magnitude sum → dBFS → clamp(floor, ceiling) → linear [0,1] → round(3 decimals). Returns None on short chunk; emits `spectrum_error` on exceptions. |
| Spectrum state on `MicReader` | 13 new attributes set in `__init__`: 8 config-mirror (`_spec_n_bands`, `_spec_min_hz`, `_spec_max_hz`, `_spec_floor_db`, `_spec_ceiling_db`, `_spec_cadence_hz`, `_spec_color_yellow_at`, `_spec_color_red_at`) + 5 derived (`_spec_n_fft`, `_spec_hann`, `_spec_mag_ref`, `_spec_band_table`, `_audio_level_emit_every_n`). |
| `audio_level` payload extension | `payload["bands"] = list[float]` length 24 appended in `_emit_audio_level` when `_compute_bands` returns non-None. Other fields untouched (backwards-compat). |
| Per-instance cadence gate | `_drain_loop` now compares `_level_tick` against `self._audio_level_emit_every_n` (was module constant `_AUDIO_LEVEL_EMIT_EVERY_N_FRAMES`). At prod defaults: 16000 Hz / 20 ms / 25 Hz cadence → every 2nd frame. |
| `apply_config` hot-reload | Re-reads all 8 spectrum_* keys; rebuilds band table on bands/min/max/sample_rate/frame_ms delta; recomputes emit cadence on cadence_hz/frame_ms delta; emits `spectrum_band_table_rebuilt` diagnostic event. Spectrum_* deltas do NOT force `restart_needed=True`. |

## Tasks Executed

| Task | Name | Commit | Outcome |
| --- | --- | --- | --- |
| 1 | numpy import, `_build_log_band_table`, MicReader spectrum state in `__init__` | `07eab2f` | `test_cadence_constant` flipped green; band table verified (`band 0: (1,2) → 50-100 Hz`, `band 23: (132,160) → 6600-8000 Hz`). |
| 2 | `_compute_bands` method, wire into `_emit_audio_level`, switch cadence gate to instance attribute | `759e639` | `test_sine_localised`, `test_silence_floor`, `test_noise_distributed`, `test_payload_shape` all green. _level_emit_loop marked with `Phase 21A: synthetic events OMIT bands by design` comment. |
| 3 | Extend `apply_config` with 8 spectrum_* keys + lazy table/cadence rebuild | `f9483f3` | `test_hot_reload` green. All 7 spectrum tests pass; 104 of 105 tests in full suite green (1 pre-existing unrelated failure deselected). |

## Verification

```bash
$ ./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -x -q
.......                                                                  [100%]
7 passed in 0.07s

$ ./.venv/bin/python -m pytest tests/ --deselect tests/test_memory.py::EpisodicMemoryTests::test_semantic_roundtrip -q
104 passed, 1 deselected in 1.01s

$ ./.venv/bin/python -c "from System.adam.mic_reader import _build_log_band_table; \
    t=_build_log_band_table(320,16000,24,80.0,8000.0); \
    assert len(t)==24; assert all(1<=l<=h<=160 for l,h in t)"
# (exit 0)

$ grep -nE "self\._audio_level_emit_every_n" System/adam/mic_reader.py
176:        self._audio_level_emit_every_n = max(
615:            self._audio_level_emit_every_n = max(
847:                if self._level_tick >= self._audio_level_emit_every_n:
```

All `<acceptance_criteria>` and `<verification>` items from the PLAN satisfied.

## Decisions Made

- **FFT exceptions emit `spectrum_error` and return None, never raise.** The `_emit_audio_level` path is shared with the UI VU-meter; an FFT failure must not break the meter cadence. Mirrors the same defensive posture as the B-1 fix that keeps `audio_level` live during TTS mute.
- **`_compute_bands` lives on `MicReader` (method), not as a module-level function.** Direct access to per-instance state (`_spec_hann`, `_spec_band_table`, `_spec_mag_ref`) avoids passing 4 arrays through every call. The free function `_build_log_band_table` is at module level because it has no per-instance state.
- **`_AUDIO_LEVEL_EMIT_EVERY_N_FRAMES = 5` retained as DEPRECATED.** Removing it would touch backwards-compat readers; keeping the constant with a `DEPRECATED Phase 21A:` comment is cheaper and clearer than deletion. The drain loop no longer references it.
- **`table_dirty` ORed with `restart_needed`.** When sample_rate or frame_ms changes (which already flag `restart_needed`), `n_fft` changes too — so the band table must be rebuilt even if `spectrum_bands/min/max` are unchanged. Same logic for `cadence_dirty` on frame_ms.
- **Synthetic `_level_emit_loop` event keeps the legacy shape.** No `bands` key. The frontend (Plan 05) handler must use `if (Array.isArray(p.bands) && p.bands.length === 24)` to distinguish "new spectrum" from "no fresh PCM, keep last snapshot" (RESEARCH §12, Pitfall 4).
- **Linked floor/ceiling guard `span_db <= 0`.** If a user patches `floor_db = 0` and `ceiling_db = 0` via /api/config, the division by zero would NaN every band. Falls back to `span_db = 1.0` to keep the meter visible. This is a defence-in-depth choice — the schema's `floor_db.maximum: 0` and `ceiling_db.minimum: -20` are the primary gate.

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Issues

- `tests/test_memory.py::EpisodicMemoryTests::test_semantic_roundtrip` — pre-existing `AttributeError: 'EpisodicMemory' object has no attribute 'write_semantic'`. Confirmed failing pre-21A-03 (verified via `git stash` round-trip before edits). Out of scope for FFT spectrum work; logged in `deferred-items.md` for a future memory-subsystem phase.

## Self-Check: PASSED

- `System/adam/mic_reader.py` modified — FOUND
- Commit `07eab2f` — FOUND in `git log`
- Commit `759e639` — FOUND in `git log`
- Commit `f9483f3` — FOUND in `git log`
- `import numpy as np` at top of mic_reader.py — FOUND (line 38)
- `def _build_log_band_table(` at module level — FOUND (line 62)
- `def _compute_bands(` method on MicReader — FOUND (line 619)
- `self._audio_level_emit_every_n` referenced in `__init__`, `apply_config`, `_drain_loop` — FOUND (3 hits)
- `Phase 21A: synthetic events OMIT 'bands'` comment in `_level_emit_loop` — FOUND
- `spectrum_band_table_rebuilt` event in `apply_config` — FOUND
- All 7 tests in `tests/test_mic_reader_spectrum.py` PASS
- Full suite PASS (excluding 1 pre-existing unrelated failure)
