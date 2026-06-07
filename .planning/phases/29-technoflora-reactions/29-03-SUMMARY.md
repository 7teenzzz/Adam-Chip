---
phase: 29-technoflora-reactions
plan: 03
subsystem: inference
tags: [flora, technoflora, event-bus, eventlog, vibro, pca9685, asyncio, config-first, no-proxy, pytest, tdd]

# Dependency graph
requires:
  - phase: 29-technoflora-reactions (plan 01)
    provides: firmware POST /api/flora/state {state, params} -> 200/400 contract on :80 (floraStateHandler)
  - phase: 29-technoflora-reactions (plan 02)
    provides: flora Config section (settings.section("flora")) — channel masks, gamma, crossfade, state presets, vibro silent_states
provides:
  - MCUClient.set_flora_state(state, params) — thin POST /api/flora/state via _NO_PROXY_OPENER, flat-key payload, *_duty/*_channel clamp
  - FloraController — EventLog queue consumer + event->preset mapping + start/stop lifecycle
  - Jetson event->preset mapping (FLORA-03): wake_word->accent, boot_warmup-exit->wake_bloom(once), listening->attentive, standby->breathe, llm_thinking_started->think_pulse
  - Vibro-silent-in-attentive enforced Jetson-side (FLORA-06): vibro_enabled=false for silent_states
  - flora_controller lifespan wiring in Orchestrator (start/stop next to mic_reader)
affects: [29-04 (RMS speech sync — fills the tts_started/finished answer-boundary stubs)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "EventLog pub-sub queue consumer (subscribe()->asyncio.Queue, unsubscribe in finally) — copied from api_runtime SSE generator"
    - "start()/stop() long-lived task lifecycle mirrored from mic_reader"
    - "ESP HTTP only via MCUClient (_NO_PROXY_OPENER), never a fresh urllib/httpx client"

key-files:
  created:
    - System/adam/flora.py
  modified:
    - System/adam/device.py
    - System/Orchestrator.py
    - tests/test_flora.py

key-decisions:
  - "wake_bloom fires once on first voice_state_change OUT of boot_warmup (RESEARCH Open Q1 RESOLVED) — _booted flag guards re-fire"
  - "tts_started/tts_finished are STUBBED to a generic accent/breathe answer boundary; plan 04 replaces _on_answer_start with the RMS streamer"
  - "vibro silenced on BOTH _build_params and _set_state (belt-and-suspenders mirror of firmware, D-11)"
  - "set_flora_state uses suffix-based clamp (*_duty -> value range, *_channel -> channel range) so flat-key params are defended without a param schema"

requirements-completed: [FLORA-03, FLORA-06]

# Metrics
duration: ~15min
completed: 2026-06-05
---

# Phase 29 Plan 03: Jetson Flora Event Layer Summary

**`FloraController` (System/adam/flora.py) consumes the real EventLog pub-sub queue and maps VERIFIED pipeline events to flora presets — wake_word->accent, the first boot_warmup-exit->wake_bloom (once), listening->attentive (vibro OFF, D-11), standby->breathe, thinking->think_pulse — pushing each transition to the ESP via a new thin `MCUClient.set_flora_state` (_NO_PROXY_OPENER, /api/flora/state), wired into the Orchestrator lifespan next to mic_reader.**

## Performance
- **Duration:** ~15 min
- **Completed:** 2026-06-05
- **Tasks:** 3
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- **Task 1 — MCUClient.set_flora_state (FLORA-03):** added `async def set_flora_state(state, params)` to device.py. Builds a flat-key payload `{state, **params}` (firmware parser is flat-key), clamps `*_duty` params to value_min..value_max and `*_channel` params to channel_min..channel_max (defence-in-depth, T-29-07), and routes through `asyncio.to_thread(self._request, "POST", "/api/flora/state", payload)` so it reuses `_NO_PROXY_OPENER` — no fresh HTTP client (v2ray socket-leak gotcha).
- **Task 2 — FloraController (FLORA-03/06, TDD):** new System/adam/flora.py. Subscribes to `event_log.subscribe()` (asyncio.Queue, NOT a callback bus), consumer loop dispatches on `event["type"]`, `start()`/`stop()` lifecycle mirrors mic_reader (cancel task + unsubscribe in finally). Event mapping per RESEARCH §Pattern 4. `_set_state` reads per-preset params from `settings.section("flora")` (Config-First, no hardcoded duty/period literals) and forces `vibro_enabled=False` for any preset in `silent_states` (D-11). Filled `test_event_mapping`, `test_wake_bloom_on_boot_exit`, `test_vibro_silent_listening` with a fake MCU recording `(state, params)` — RED→GREEN.
- **Task 3 — Orchestrator wiring (FLORA-03):** imported FloraController, constructed `flora_controller = FloraController(settings.section("flora"), mcu, event_log)` alongside mic_reader/scene_worker, `await flora_controller.start()` next to mic_reader.start(), `await flora_controller.stop()` in the lifespan finally.

## Task Commits
1. **Task 1: MCUClient.set_flora_state** — `eee9551` (feat)
2. **Task 2 RED: failing FloraController tests** — `a6a93a4` (test)
3. **Task 2 GREEN: FloraController** — `719e7d7` (feat)
4. **Task 3: Orchestrator lifespan wiring** — `b8fc02b` (feat)

## Files Created/Modified
- `System/adam/flora.py` (created) — FloraController: event consumer, event->preset mapping, _set_state/_build_params, start/stop lifecycle, answer-boundary stubs.
- `System/adam/device.py` — added MCUClient.set_flora_state (flat-key POST, suffix clamp, _NO_PROXY_OPENER).
- `System/Orchestrator.py` — import + construct flora_controller + start/stop in lifespan.
- `tests/test_flora.py` — filled test_event_mapping / test_wake_bloom_on_boot_exit / test_vibro_silent_listening (dropped skip markers), added _FakeMCU + helpers.

## Decisions Made
- **wake_bloom = boot-exit, once:** the first `voice_state_change` with `from == "boot_warmup"` triggers wake_bloom; a `_booted` flag prevents re-firing, after which standby maps to breathe normally (RESEARCH Open Q1 RESOLVED).
- **Answer boundary stubbed:** `tts_started -> _on_answer_start` (generic accent) and `tts_finished -> _on_answer_end` (breathe) are intentional stubs; plan 04 replaces `_on_answer_start` with the feed_speech_wav RMS streamer. Documented under Known Stubs.
- **Double vibro enforcement:** `_build_params` and `_set_state` both zero vibro for silent_states — belt-and-suspenders mirror of the firmware (D-11) protecting ASR from motor->mic coupling.
- **Suffix-based clamp in set_flora_state:** flat-key params have no schema, so `*_duty`/`*_channel` suffix heuristics drive the clamp; firmware re-clamps regardless.

## Deviations from Plan
None — plan executed exactly as written.

## TDD Gate Compliance
Task 2 carried `tdd="true"` and is behavior-adding (adam.flora source + behavior block). Gate sequence satisfied in git history: RED `test(29-03)` commit `a6a93a4` (tests fail — ModuleNotFoundError: adam.flora) → GREEN `feat(29-03)` commit `719e7d7` (4 passed, 1 skipped). No REFACTOR needed. No gate violation.

## Known Stubs
| Stub | File | Reason |
|------|------|--------|
| `_on_answer_start` generic accent pulse | System/adam/flora.py | Intentional — plan 04 (FLORA-04) replaces with the RMS speech-sync streamer driven by per-chunk feed_speech_wav. The ambient layer is complete without it; this is the documented hand-off to plan 04. |

## Verification
- `tests/test_flora.py`: 4 passed, 1 skipped (test_rms_envelope reserved for plan 04). Includes test_flora_config (plan 02) + the 3 new mapping/vibro tests.
- Orchestrator: `ast.parse` OK; `flora_controller.start()`, `flora_controller.stop()`, `FloraController(` all present.
- set_flora_state: posts `/api/flora/state` and routes through `_request` (no new client).

## Next Phase Readiness
- Plan 04 (FLORA-04, RMS speech sync) fills `_on_answer_start` with the WAV->RMS envelope streamer and adds the per-chunk feed_speech_wav call in Orchestrator's consumer; `test_rms_envelope` + `_make_sine_wav` are ready. `flora.speech.*` config (frame_interval_ms, hdmi_latency_offset_ms, base/peak duties, spark_probability) is available.

## Self-Check: PASSED
All created/modified files exist on disk; all four task commits (`eee9551`, `a6a93a4`, `719e7d7`, `b8fc02b`) present in git history.

---
*Phase: 29-technoflora-reactions*
*Completed: 2026-06-05*
