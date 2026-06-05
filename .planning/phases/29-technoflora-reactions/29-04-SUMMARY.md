---
phase: 29-technoflora-reactions
plan: "04"
subsystem: flora
tags: [flora, rms, speech-sync, tts, light, vibro, orchestrator]
dependency_graph:
  requires: [29-03]
  provides: [FLORA-04]
  affects:
    - System/adam/flora.py
    - System/Orchestrator.py
tech_stack:
  added: []
  patterns:
    - "RMS envelope from WAV via stdlib wave+audioop (no numpy), per-chunk single-timer sync (D-07)"
    - "asyncio.create_task per chunk for non-blocking frame streaming"
    - "Barge-in cancel: CancelledError swallowed, asyncio task lifecycle respected"
    - "Best-effort guard in Orchestrator: try/except wraps feed_speech_wav (Action-failure-≠-silence)"
key_files:
  created: []
  modified:
    - System/adam/flora.py
    - System/Orchestrator.py
decisions:
  - "Per-chunk single timer (not per-reply): each chunk's envelope starts at dispatch, keeping D-07 sync with chunked playback. Per-reply accumulation would desync."
  - "feed_speech_wav is synchronous fast (kicks asyncio task, no await): safe to call from async _consumer without blocking the pipeline."
  - "Degraded /speak path: Silero plays internally, WAV never exposed; _on_answer_start puts lights on attentive plateau as fallback. Only one degraded path."
  - "_cancel_rms_task awaits the task to ensure clean teardown before transitioning to next preset."
metrics:
  duration: "~30 min"
  completed: "2026-06-05"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 29 Plan 04: RMS Speech Sync Summary

RMS speech light sync (FLORA-04): per-chunk WAV envelope drives PCA9685 light channels 0-10 in lockstep with TTS playback, with sparks on peaks, vibro subtlety, and instant barge-in cancel.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | WAV->RMS envelope (prior session) | 43689f4 | System/adam/flora.py |
| 2 | feed_speech_wav + RMS streamer + barge-in | 458652d | System/adam/flora.py |
| 3 | Wire feed_speech_wav into Orchestrator._consumer | 46a07ef | System/Orchestrator.py |

## What Was Built

### Task 2 — feed_speech_wav + RMS frame streamer (flora.py)

`feed_speech_wav(wav_bytes)` is the public per-chunk WAV intake called by the Orchestrator
consumer. It computes `_rms_envelope` + `_envelope_to_duties` for the chunk, then calls
`_start_rms_stream(duties)` which creates an `asyncio.create_task(_rms_stream(duties))`.

`_rms_stream(duties)` implements D-07:
- `t0 = perf_counter()` at task start (same instant as playback dispatch)
- Per frame `i`: `await asyncio.sleep(t0 + hdmi_latency_offset_ms/1000 + i*interval_s - now)`
- `await mcu_client.set_channels(updates)` for all light channels 0-10
- Sparks (D-08): near-peak frames boost a random channel subset to full `peak_duty` at `spark_probability`
- Vibro (ch 11-14): scaled to `vibro_intensity_pct` alongside light (D-12); NOT silent in answer state
- Frame rate capped at ~12.5 fps by `frame_interval_ms=80` default (T-29-10)

`_on_answer_start` now sets `_answer_active = True` and transitions to `attentive` plateau
(waits for the first `feed_speech_wav` chunk). `_on_answer_end` calls `_stop_rms_stream` and
transitions to `breathe`.

Barge-in (D-09): `_handle` cancels `_rms_task` immediately on `voice_state_change→listening`,
`voice_state_change→standby`, and `wake_word_detected`. `stop()` also cancels `_rms_task`.

### Task 3 — Orchestrator._consumer wiring

Three `to_thread(_play_wav_bytes_sync, pending_wav)` dispatch sites each received:

```python
try:
    flora_controller.feed_speech_wav(pending_wav)
except Exception as _flora_exc:
    event_log.append("flora_feed_error", {"error": str(_flora_exc)})
```

Placed immediately **before** each `to_thread` call so the RMS timer starts together with
playback. The try/except guard ensures flora errors are logged but never break TTS
(Action-failure-≠-silence invariant, T-29-13, CLAUDE.md).

Sites:
1. Final pending flush (`chunk is None` branch)
2. Synth-fail flush (`wav is None` + `pending_wav is not None` branch)
3. Steady-state pipelined playback

## Degraded Path

The non-streaming `/speak` endpoint (Silero plays internally, WAV bytes never exposed) is the
ONLY path where `feed_speech_wav` is never called. In that case `_on_answer_start` already
placed lights on the `attentive` plateau — a static brightness fallback rather than real RMS
modulation. Documented in `feed_speech_wav` docstring (RESEARCH Open Q2 RESOLVED).

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

```
PYTHONPATH=System pytest tests/test_flora.py -x
5 passed, 0 skipped, 1 warning (audioop deprecation Python 3.13 — expected, stdlib only)
```

Acceptance checks:
- `feed_speech_wav`, `set_channels`, `hdmi_latency_offset` all present in FloraController source
- `Orchestrator.py` contains `feed_speech_wav` exactly 3 times; `ast.parse` succeeds

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced beyond the plan's threat model.
All threats mitigated as designed:
- T-29-10: frame_interval_ms=80 caps rate at ~12.5 fps
- T-29-11: set_channels clamps duty 0-4095 and channel 0-15
- T-29-12: barge-in cancel + stop() cancel _rms_task; envelope bounded by WAV duration
- T-29-13: try/except in all 3 Orchestrator feed sites

## Self-Check: PASSED

- `System/adam/flora.py` exists and contains `feed_speech_wav`, `_rms_stream`, `_cancel_rms_task`
- `System/Orchestrator.py` exists and contains `feed_speech_wav` x3
- Commits 458652d and 46a07ef verified in git log
- 5/5 tests passing
