---
phase: 21A-chat-eq-real-spectrum-fft
verified: 2026-05-18T00:00:00Z
status: passed
score: 32/32 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
plans_verified:
  - 21A-01-PLAN.md
  - 21A-02-PLAN.md
  - 21A-03-PLAN.md
  - 21A-04-PLAN.md
  - 21A-05-PLAN.md
  - 21A-06-PLAN.md
  - 21A-07-PLAN.md
  - 21A-08-PLAN.md
requirements_verified:
  - UI-EQ-01
  - UI-EQ-02
  - UI-EQ-03
  - UI-EQ-04
  - UI-EQ-05
  - UI-EQ-06
  - UI-EQ-RESILIENCE
test_evidence:
  focused: "16 passed (tests/test_mic_reader_spectrum.py + tests/test_mic_reader_watchdog.py)"
  full: "89 passed (tests/ excluding test_memory.py — pre-existing failure documented in deferred-items.md)"
---

# Phase 21A: Chat EQ Real Spectrum FFT — Verification Report

**Phase Goal (ROADMAP.md):** Заменить «иллюзию спектра» в виджете эквалайзера на странице чата (`wakeMeter.js`) на реальный частотный спектр FFT, посчитанный на сервере поверх того же аудио-потока, который слышат OWW/ASR. Сохранить отображение OWW score (голубая линия) и threshold (оранжевый пунктир) без изменений.

**Verified:** 2026-05-18
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement — Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Server-side FFT computes real spectrum over same audio buffer feeding RMS/OWW/ASR | ✓ VERIFIED | `System/adam/mic_reader.py:700` `_compute_bands` (numpy rfft over mono_chunk); called from `_emit_audio_level` line 694 |
| 2 | `audio_level` SSE payload carries `bands: list[float]` length 24, values in [0..1] | ✓ VERIFIED | mic_reader.py lines 694-696 (`if bands is not None: payload["bands"] = bands`); test_payload_shape asserts shape 24 floats ∈ [0,1] |
| 3 | Real audio_level fires at 25 Hz; synthetic backfill omits `bands` | ✓ VERIFIED | `_audio_level_emit_every_n` derived from `spectrum_cadence_hz` (line 176); synthetic `_level_emit_loop` does not call `_compute_bands` (does not write `bands`) |
| 4 | `apply_config` hot-reloads all 8 spectrum_* keys + rebuilds band table when geometry changes | ✓ VERIFIED | mic_reader.py lines 531-573: dirty-flag check + `_build_log_band_table()` rebuild on bands/min_hz/max_hz change |
| 5 | 8 spectrum_* keys exist in Config.json under media.audio with reference defaults | ✓ VERIFIED | Config.json lines 58-65: 24, 80.0, 8000.0, -60.0, 0.0, 25.0, 0.6, 0.85 (exact match to RESEARCH §9) |
| 6 | 8 spectrum_* keys documented in Config.schema.json | ✓ VERIFIED | Config.schema.json lines 256-310 (all 8 keys with non-empty descriptions) |
| 7 | `events_jsonl_sample_audio_level` writing-side sampler reduces disk pressure without affecting SSE | ✓ VERIFIED | events.py line 62-66 (conditional write); `_recent.append()` + `_broadcast()` unconditional (lines 73-75); Config.json line 66 default = 5 |
| 8 | wakeMeter renders 24 bars directly from `bands[]` — no peak-hold, no decay, no EQ_SHAPE/wobble | ✓ VERIFIED | wakeMeter.js: `N_BANDS = 24` (line 23), bars[] Float32Array (line 69), draw loop lines 166-181; grep for forbidden tokens (`EQ_SHAPE`, `audioLevel * 4`, `peaks[i] * 0.87`, `Date.now() * 0.0015`) returns **zero matches** |
| 9 | Per-bar color from green→yellow→red gradient using configurable thresholds | ✓ VERIFIED | wakeMeter.js line 40 `function colorForLevel(v, yAt, rAt)`, applied per-bar at line 181 |
| 10 | OWW score (cyan) and threshold (orange dashed) rendering UNCHANGED | ✓ VERIFIED | wakeMeter.js: oww_score handler (line 301-307) + wake_sensitivity_updated (line 308-312) preserved; cyan/orange render paths untouched in draw() |
| 11 | `dispose()` is idempotent — second call no-ops | ✓ VERIFIED | wakeMeter.js lines 316-318: `if (disposed) return; disposed = true;`; draw() also guards via `if (disposed) return` (line 137) |
| 12 | Missing/invalid bands in audio_level keeps last snapshot — bars do not flash to zero | ✓ VERIFIED | wakeMeter.js lines 273-275: `if (Array.isArray(p.bands) && p.bands.length === N_BANDS)` — assignment only when valid |
| 13 | chat.js hint mentions real FFT spectrum | ✓ VERIFIED | chat.js line 457: «Эквалайзер: реальный спектр микрофона (FFT, 24 полосы 80–8000 Гц)…» |
| 14 | settings.js draggable variant wired with `wrapper._dispose → meter.dispose()` + audit marker | ✓ VERIFIED | settings.js line 623 (`draggable: true`), line 700 audit marker «Phase 21A: idempotent dispose…», line 701 `wrapper._dispose = …` |
| 15 | Auto-restart watchdog (Plan 08): after N consecutive `:81/audio` open failures, sends `POST :80/api/system/stream/restart` automatically | ✓ VERIFIED | mic_reader.py: `_should_trigger_stream_restart` (line 830), `_trigger_stream_restart` (line 848) |
| 16 | Watchdog threshold + cooldown are Config-driven | ✓ VERIFIED | Config.json lines 119-120: `esp_stream_restart_after_fails: 5`, `esp_stream_restart_cooldown_sec: 120.0`; schema lines 560-567 |
| 17 | Pytest test scaffold present and passing — 16 tests across spectrum + watchdog suites | ✓ VERIFIED | `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py tests/test_mic_reader_watchdog.py -q` → **16 passed in 0.15s** |
| 18 | Synthetic mono-chunk fixtures available | ✓ VERIFIED | tests/conftest.py: `mono_chunk_silence` (line 32), `mono_chunk_sine` (line 38), `mono_chunk_white_noise` (line 62) |
| 19 | Smoke verdict PASS recorded | ✓ VERIFIED | 21A-SMOKE-RESULTS.md line 87: `## Smoke Verdict: PASS` |
| 20 | Full test suite (89 tests) passes | ✓ VERIFIED | `./.venv/bin/python -m pytest tests/ -q --ignore=tests/test_memory.py` → **89 passed in 0.88s** |

**Score: 20/20 phase-level truths verified.** Adding plan-level truths below (per must_haves frontmatter): 32/32 cumulative — all PASS.

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/test_mic_reader_spectrum.py` | 7 spectrum tests | ✓ VERIFIED | 7 test functions present (`test_sine_localised`, `test_silence_floor`, `test_noise_distributed`, `test_payload_shape`, `test_cadence_constant`, `test_spectrum_keys_in_schema`, `test_hot_reload`); 293 lines |
| `tests/conftest.py` | Synthetic fixtures | ✓ VERIFIED | All 3 fixtures present; 79 lines |
| `tests/test_mic_reader_watchdog.py` | 9 watchdog tests | ✓ VERIFIED | 9 test functions present (gate predicate + trigger helper + disabled state); 194 lines; all pass |
| `System/Config.json` | 8 spectrum_* + sampler + 2 ASR watchdog keys | ✓ VERIFIED | Lines 58-65 (spectrum), 66 (sampler), 119-120 (ASR watchdog) |
| `System/Config.schema.json` | Schema for all new keys | ✓ VERIFIED | Lines 256-311 (9 media.audio keys), 560-567 (2 ASR keys) |
| `System/adam/mic_reader.py` | `_compute_bands`, `_build_log_band_table`, `_should_trigger_stream_restart`, `_trigger_stream_restart` | ✓ VERIFIED | All 4 symbols present at lines 700, 62, 830, 848 |
| `System/adam/events.py` | Writing-side sampler | ✓ VERIFIED | `_jsonl_sample_audio_level` + per-type counter; SSE/_recent unconditional |
| `System/WebUI/static/js/widgets/wakeMeter.js` | `colorForLevel`, `disposed` flag, no legacy tokens | ✓ VERIFIED | Lines 40, 134; zero forbidden-token matches |
| `System/WebUI/static/js/panels/chat.js` | Updated hint | ✓ VERIFIED | Line 457 explicit FFT mention |
| `System/WebUI/static/js/panels/settings.js` | Audit marker + wrapper._dispose | ✓ VERIFIED | Lines 700-701 |
| `21A-SMOKE-RESULTS.md` | Smoke verdict PASS | ✓ VERIFIED | Line 87 |

## Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `MicReader._emit_audio_level` | `_compute_bands` | direct method call (line 694) | ✓ WIRED — payload["bands"] assignment guarded by `if bands is not None` |
| `MicReader.apply_config` | `_build_log_band_table` rebuild | dirty-flag check on bands/min_hz/max_hz (line 550) | ✓ WIRED |
| `EventLog.append` | `events.jsonl` | conditional write counter (line 62-66) | ✓ WIRED — SSE/_recent unconditional |
| `wakeMeter.js` audio_level handler | `bands[]` state | `Array.isArray(p.bands) && p.bands.length === N_BANDS` (line 273) | ✓ WIRED |
| `wakeMeter.js` dispose() | unsub + cancelAnimationFrame | `disposed` boolean flag (line 318) | ✓ WIRED — idempotent |
| `chat.js` cleanup | `wakeMeter.dispose()` | typeof guard (line 663) | ✓ WIRED |
| `settings.js` wrapper._dispose | `meter.dispose()` | captured closure (line 701) | ✓ WIRED |
| `MicReader._run` | `_trigger_stream_restart` | gate when fails ≥ threshold + cooldown OK | ✓ WIRED |
| `MicReader._trigger_stream_restart` | `Device.stream_restart` (POST :80) | mcu client call | ✓ WIRED |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Flows Real Data | Status |
|---|---|---|---|---|
| `wakeMeter.js` bars render | `bands[N_BANDS]` | SSE `audio_level.bands` ← `MicReader._compute_bands(mono_chunk)` ← ESP32 mic chunk | ✓ YES — numpy rfft over real PCM int16 chunks | ✓ FLOWING |
| `chat.js` panel | `wakeMeter.canvas` mounted into DOM | `createWakeMeter` returns live widget | ✓ YES — widget bound to SSE EventBus | ✓ FLOWING |
| `events.py` _recent deque + SSE | every event unconditionally | append() before sampler skip-check | ✓ YES — SSE cadence unchanged | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused tests pass | `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py tests/test_mic_reader_watchdog.py -q` | **16 passed in 0.15s** | ✓ PASS |
| Full test suite passes (minus pre-existing) | `./.venv/bin/python -m pytest tests/ -q --ignore=tests/test_memory.py` | **89 passed in 0.88s** | ✓ PASS |
| Forbidden legacy tokens absent from wakeMeter.js | `grep -nE "EQ_SHAPE|audioLevel \* 4|peaks\[i\] \* 0\.87|Date\.now\(\) \* 0\.0015" System/WebUI/static/js/widgets/wakeMeter.js` | empty output | ✓ PASS |
| Config defaults match RESEARCH §9 spec | grep `media.audio.spectrum_*` in Config.json | 24, 80.0, 8000.0, -60.0, 0.0, 25.0, 0.6, 0.85 (exact) | ✓ PASS |

## Requirements Coverage

UI-EQ-* requirement IDs are declared in plan frontmatter + ROADMAP §Phase 21A but are NOT currently registered as formal entries in `.planning/REQUIREMENTS.md` (no `**UI-EQ-XX**: description` line). Coverage is therefore verified against the ROADMAP description of each requirement:

| Requirement | Source | Description (per ROADMAP line 767) | Status | Evidence |
|---|---|---|---|---|
| UI-EQ-01 | 21A-01/03/07 | FFT backend over same audio buffer as RMS/OWW | ✓ SATISFIED | `_compute_bands` + numpy.fft.rfft over mono_chunk |
| UI-EQ-02 | 21A-01/03/04/07 | New SSE event / audio_level extended with bands[] | ✓ SATISFIED | `audio_level` payload now contains `bands` field |
| UI-EQ-03 | 21A-05/06/07 | Render without smoothing/peak-hold | ✓ SATISFIED | wakeMeter.js draws `bands[i]` directly each frame; chat.js hint updated |
| UI-EQ-04 | 21A-05/07 | Color gradient green→yellow→red by level | ✓ SATISFIED | `colorForLevel` piecewise RGB; thresholds Config-driven |
| UI-EQ-05 | 21A-05/07 | Fix potential SSE leak — `dispose()` idempotent | ✓ SATISFIED | `disposed` flag; draw() and dispose() both guard |
| UI-EQ-06 | 21A-01/02/03/07 | Config-First — 8 spectrum_* keys in Config.json + schema | ✓ SATISFIED | All 8 keys + 1 sampler key present with schema descriptions |
| UI-EQ-RESILIENCE | 21A-08 (hotfix) | Auto-restart watchdog when ESP :81 deadlocks | ✓ SATISFIED | `_should_trigger_stream_restart` + `_trigger_stream_restart`; 9 watchdog tests pass |

**Note for ROADMAP maintainer:** Consider backfilling UI-EQ-01..06 + UI-EQ-RESILIENCE as formal `**UI-EQ-XX**: …` entries in REQUIREMENTS.md so that requirement IDs round-trip cleanly between plans and the central registry. This is a documentation hygiene gap, not a phase-goal gap.

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | None detected in phase-modified files | — | — |

A grep for `TBD|FIXME|XXX` in the 21A-modified files (`System/adam/mic_reader.py`, `System/adam/events.py`, `System/Config.json`, `System/Config.schema.json`, `System/WebUI/static/js/widgets/wakeMeter.js`, `System/WebUI/static/js/panels/chat.js`, `System/WebUI/static/js/panels/settings.js`) shows no unreferenced debt markers introduced by this phase. The `_compute_bands` exception path emits a diagnostic `spectrum_error` event rather than a `# TODO` comment — clean.

## Probe Execution

No formal `scripts/*/tests/probe-*.sh` probes are declared by Phase 21A. Phase verification relies on the pytest suite (run above) and the recorded manual smoke test (21A-SMOKE-RESULTS.md, verdict PASS).

## Human Verification Required

None — the live browser checks (M-1..M-4, RESEARCH §11 Steps 1-5) were already executed and recorded as PASS in `21A-SMOKE-RESULTS.md`. Re-running them is unnecessary for this verification pass.

## Gaps Summary

**No blocking gaps.** All 32 must_have truths across plans 21A-01..08 are verified in the codebase. Test suite is green (16 focused + 89 broad). Smoke verdict is PASS. The single pre-existing test failure (`tests/test_memory.py::test_semantic_roundtrip`) is documented as out-of-scope in `deferred-items.md` and confirmed unrelated to Phase 21A (verified against baseline via `git stash` by the executor).

**Minor documentation hygiene observation (non-blocking):** UI-EQ-01..06 + UI-EQ-RESILIENCE are not yet formal entries in `.planning/REQUIREMENTS.md`. They are well-documented in the ROADMAP §Phase 21A description and in each plan's frontmatter, so traceability is maintained — but the central REQUIREMENTS.md registry is the canonical source of truth and would benefit from a backfill. Recommend adding this to a backlog plan or addressing as part of ROADMAP closure for Phase 21A.

**Recommendation:** Phase 21A goal is achieved. Ready for ROADMAP closure (set 21A-07-PLAN.md `[x]` since smoke is recorded, and update `Plans: 8/8 plans executed`).

---

*Verified: 2026-05-18*
*Verifier: Claude (gsd-verifier)*
