---
phase: 21A
plan: 01
subsystem: tests / Wave 0 (NYQUIST gate)
tags: [tdd, scaffold, fft, spectrum, equaliser]
dependency_graph:
  requires: []
  provides:
    - "tests/test_mic_reader_spectrum.py — RED contract for UI-EQ-01/02/06"
    - "tests/conftest.py — synthetic mono-chunk fixtures (sine, silence, white noise)"
  affects:
    - "21A-02 (Wave 1) consumes _compute_bands / _spec_floor_db / _audio_level_emit_every_n contracts"
    - "21A-03 (Wave 2) consumes payload-shape + hot-reload contracts"
tech_stack:
  added:
    - "pytest fixtures producing raw int16 PCM (16 kHz, 20 ms, mono → 320 samples = 640 bytes)"
    - "numpy.random.default_rng for deterministic seeded white noise"
  patterns:
    - "Lazy import of System.adam.mic_reader inside _make_mic_reader so the test file imports clean pre-Wave-1"
    - "Factory-style fixtures (callable returning bytes) for parameterised sine/noise inputs"
    - "Hann-windowed sine to keep FFT peak sharply localised (1-bin slop budget in test_sine_localised)"
key_files:
  created:
    - "tests/conftest.py"
    - "tests/test_mic_reader_spectrum.py"
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/21A-01-SUMMARY.md"
  modified: []
decisions:
  - "Sine fixture uses Hann window upfront so the 1 kHz test allows only ±1 band of spectral slop"
  - "white_noise fixture seeds numpy.random.default_rng — byte-stable across CI runs"
  - "test_spectrum_keys_in_schema does NOT skip — schema file exists today, the test is the contract Plan 02 must satisfy"
  - "_make_mic_reader passes None for mcu/voice_loop and stub callables for on_event/stereo_reader_factory; never .start()s the reader (no asyncio loop / ESP32 socket required)"
metrics:
  duration: "single session"
  completed: 2026-05-18
  tasks_total: 2
  tasks_completed: 2
  files_created: 3
  files_modified: 0
---

# Phase 21A Plan 01: Wave 0 — FFT Spectrum Stub Tests Summary

Wave 0 NYQUIST gate for Phase 21A — pytest scaffold of seven RED tests (5 SKIP + 2 FAIL) plus three synthetic mono-chunk fixtures, locking the contract Wave 1 and Wave 2 implementations must satisfy.

## What Shipped

| Artifact | Purpose |
| --- | --- |
| `tests/conftest.py` | Three pytest fixtures (`mono_chunk_silence`, `mono_chunk_sine`, `mono_chunk_white_noise`) producing raw little-endian int16 PCM at 16 kHz / 20 ms / mono — exact match for what `MicReader._emit_audio_level` consumes. |
| `tests/test_mic_reader_spectrum.py` | Seven named tests (`test_sine_localised`, `test_silence_floor`, `test_noise_distributed`, `test_payload_shape`, `test_cadence_constant`, `test_spectrum_keys_in_schema`, `test_hot_reload`) covering UI-EQ-01 / UI-EQ-02 / UI-EQ-06 ahead of Wave 1+2. Module-level `WAVE_0_NYQUIST_STUB = True` marker is the grep target reviewers use to confirm the gate is in place. |

## Tasks Executed

| Task | Name | Commit | Outcome |
| --- | --- | --- | --- |
| 1 | Synthetic mono-chunk fixtures | `986ad50` | `tests/conftest.py` created with 3 fixtures; numpy 1.26.4 confirmed; pytest collects without import errors. |
| 2 | Spectrum stub tests | `8305af7` | `tests/test_mic_reader_spectrum.py` created with 7 tests. Local `pytest tests/test_mic_reader_spectrum.py -q` → `2 failed, 5 skipped` — exactly the expected RED. |

## Expected RED State (verified locally)

```
tests/test_mic_reader_spectrum.py::test_sine_localised                SKIPPED (WAVE-1: MicReader._compute_bands)
tests/test_mic_reader_spectrum.py::test_silence_floor                 SKIPPED (WAVE-1: MicReader._compute_bands)
tests/test_mic_reader_spectrum.py::test_noise_distributed             SKIPPED (WAVE-1: MicReader._compute_bands)
tests/test_mic_reader_spectrum.py::test_payload_shape                 FAILED   (audio_level payload missing 'bands' key)
tests/test_mic_reader_spectrum.py::test_cadence_constant              SKIPPED (WAVE-1: MicReader._audio_level_emit_every_n)
tests/test_mic_reader_spectrum.py::test_spectrum_keys_in_schema       FAILED   (Config.schema.json missing 8 spectrum_* keys)
tests/test_mic_reader_spectrum.py::test_hot_reload                    SKIPPED (WAVE-1: _compute_bands / _spec_floor_db / apply_config)
```

This is the contract Wave 1 (21A-02) and Wave 2 (21A-03) must turn green:

1. **`test_spectrum_keys_in_schema`** — first to flip green; 21A-02 Plan adds the 8 schema keys.
2. **`test_payload_shape`** — flips when `_compute_bands` is wired into `_emit_audio_level` (21A-02).
3. The 5 SKIP cases convert to direct assertions once Wave 1 lands the underlying attributes — no further test changes required.

## Verification Run (final)

```bash
$ .venv/bin/python -m pytest tests/ --collect-only -q | tail -2
105 tests collected in 0.27s

$ .venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -q | tail -3
FAILED tests/test_mic_reader_spectrum.py::test_payload_shape
FAILED tests/test_mic_reader_spectrum.py::test_spectrum_keys_in_schema
2 failed, 5 skipped in 0.12s

$ grep -c "^def test_" tests/test_mic_reader_spectrum.py
7

$ grep -c "@pytest.fixture" tests/conftest.py
3
```

All four PLAN `<verification>` items satisfied. `WAVE_0_NYQUIST_STUB = True` constant in place at module level.

## Decisions Made

- **Hann window inside the sine fixture, not the test.** Tests already operate at the FFT-result level; windowing the input keeps the assertion budget tight (±1 band) and matches the same Hann window the production `_compute_bands` will apply internally — the fixture is "pre-conditioned" mic audio, mirroring real ESP32 INMP441 capture.
- **Factory fixtures for sine/noise.** Each test picks its own freq / amplitude / seed without juggling pytest `parametrize`. The `mono_chunk_silence` fixture is a plain value (no params needed), which is fine — the test contract specifies the call style per fixture.
- **`test_spectrum_keys_in_schema` does not skip.** The schema file exists today, so this test is a hard fail until 21A-02 lands the keys. This is by design: it forces the schema edit to happen *first* in the Wave 1 plan, before any code reads the new keys.
- **`_make_mic_reader` never starts the reader.** Passing `mcu=None, voice_loop=None, on_event=noop, stereo_reader_factory=None` and never awaiting `.start()` means tests run without an asyncio loop, ESP32 socket, or stereo factory wiring — keeps the file < 5 s runtime per PLAN success criterion.

## Deviations from Plan

None — plan executed exactly as written.

Worktree note: the executor created a `.venv` symlink → main-repo `.venv` (already in `.gitignore`) so the planned `./.venv/bin/python -m pytest` command line works inside the worktree. No `.venv` artefact is committed.

## Self-Check: PASSED

- `tests/conftest.py` — FOUND
- `tests/test_mic_reader_spectrum.py` — FOUND
- Commit `986ad50` — FOUND in `git log`
- Commit `8305af7` — FOUND in `git log`
- 7 test functions, 3 fixtures, WAVE_0_NYQUIST_STUB marker — all present
- Pytest collection exit 0; targeted run shows 2 fail / 5 skip (expected RED)
