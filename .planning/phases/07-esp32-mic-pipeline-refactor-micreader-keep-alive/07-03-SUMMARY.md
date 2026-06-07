---
phase: 07-esp32-mic-pipeline-refactor-micreader-keep-alive
plan: 03
subsystem: Voice Pipeline
tags:
  - orchestrator
  - mic-pipeline
  - boot-sequence
  - refactor
requires:
  - 07-01
  - 07-02
provides:
  - MicReader wired into Orchestrator boot sequence and voice_loop
  - boot_warmup voice_state with explicit standby transition
  - Single audio_level emitter (MicReader); _audio_level_monitor removed
  - VoiceLoopController is pure VAD/OWW/endpointing consumer (no socket I/O)
affects:
  - WebUI chat.js pipelineReady gate (handled in plan 07-04)
tech_stack:
  patterns:
    - producer/consumer split (MicReader -> asyncio.Queue -> VoiceLoopController)
    - lifespan-managed long-lived task (CameraReader-style)
key_files:
  modified:
    - System/Orchestrator.py
decisions:
  - "MicReader is the single emitter of audio_level events (D-10); _audio_level_monitor deleted"
  - "_run dispatch routes by mic_source only — disable_local_fallback never affects routing (W-5)"
  - "_make_stereo_reader promoted from VoiceLoopController method to module-level free function (W-borderline)"
  - "voice_loop.start() emits boot_warmup state BEFORE spawning the run task"
  - "MicReader.start() runs at lifespan-entry; _orchestrated_startup only awaits wait_active() (W-3)"
metrics:
  duration: 1h 6min
  completed: 2026-05-16
  loc_before: 3407
  loc_after: 3312
  loc_delta: -95
  churn: "+200 / -295"
requirements:
  - REQ-ESP-OPEN-BEFORE-WARMUP
  - REQ-NO-ESP-ERRORS-AT-BOOT
  - REQ-RECOVERY-UNDER-5SEC
  - REQ-NO-LOCAL-FALLBACK
---

# Phase 7 Plan 03: Integrate MicReader into Orchestrator — Summary

**One-liner:** Wires MicReader (07-02) into Orchestrator, replaces VoiceLoopController's
ESP32 stream-open logic with a queue consumer, introduces the boot_warmup voice state,
and deletes ~180 lines of legacy stream-management code.

## Overview

This plan delivers the integration half of Phase 7. Plan 07-02 created `System/adam/mic_reader.py`
as a long-lived producer task; this plan rewires `System/Orchestrator.py` to consume it,
removes the now-obsolete stream-management code paths from `VoiceLoopController`, and
introduces the `boot_warmup` voice state so the UI can distinguish "starting up" from
"ready in standby".

Net result:
- `Orchestrator.py`: **3407 → 3312 lines (-95 net)**, churn +200/-295.
- One commit: `0c358a8 feat(07-03): integrate MicReader into Orchestrator`.

## Task execution

### Task 1 — MicReader instantiation + lifespan wiring + _audio_level_monitor deletion

Implemented exactly per plan:

1. `from adam.mic_reader import MicReader` added next to `CameraReader` import.
2. Module-scope `mic_reader = MicReader(asr_cfg, audio_cfg, mcu, voice_loop, on_event)`
   inserted immediately after `voice_loop = VoiceLoopController(...)`.
3. `voice_loop.mic_reader = mic_reader` back-reference set at module scope (resolves
   the chicken-and-egg between VoiceLoopController and MicReader without changing
   either constructor signature).
4. `_audio_level_monitor` function (~47 lines) deleted entirely. Its `level_monitor`
   task creation + `level_monitor.cancel() / asyncio.gather(...)` cleanup blocks in
   `lifespan` are gone.
5. `lifespan` now calls `await mic_reader.start()` after `scene_worker.start()` /
   `session_watcher.start()` / `esp_audio_health.start()` and `await mic_reader.stop()`
   in the `finally:` block AFTER `await voice_loop.stop()` (consumer releases
   `get_chunk()` awaits before producer cancels).
6. `_rebuild_clients` propagates `services.asr` and `media.audio` patches into
   MicReader via `mic_reader.apply_config(asr_cfg, audio_cfg)`; on `mcu` change,
   `mic_reader._mcu = mcu` is refreshed in-place. Each branch appends `"mic_reader"`
   to the restarted list.
7. `mic_reader.status()` exposed in both `/api/agent/status` payload sites (the
   compact and the full `_status_payload()` builders).

### Task 2 — VoiceLoopController consumer refactor + boot_warmup state + deletions

The big surgical refactor:

1. **`VALID_VOICE_STATES = ("boot_warmup", "standby", "listening", "reply")`** added as
   a class constant; `_set_voice_state` now emits a `voice_state_invalid` event for
   unknown values (defensive — does not raise, D-14).
2. **Initial voice_state** changed from `"standby"` to `"boot_warmup"` in `__init__`.
3. **`start()`** sets `self._voice_state = "boot_warmup"` and emits
   `_set_voice_state("boot_warmup", "voice_loop_started")` BEFORE creating the run
   task so the SSE arrives before any `audio_level` event (UI ordering contract
   for plan 07-04).
4. **`_run` rewritten (W-5):**
   ```python
   if self.mic_source == "esp32":
       await self._run_via_mic_reader(frame_bytes)
   else:
       await self._run_local(frame_bytes)
   ```
   No reference to `disable_local_fallback` in dispatch code. The ESP boot-wait
   gating that lived inline in `_run` is now MicReader's responsibility.
5. **`_run_via_mic_reader`** added — thin wrapper that calls `_vad_loop(read_fn=None,
   frame_bytes)`. _vad_loop branches on `self.mic_reader is not None`.
6. **`_vad_loop` modified:**
   - Signature: `read_fn: Callable[[int], bytes] | None`.
   - Chunk read: `if self.mic_reader is not None: chunk = await
     self.mic_reader.get_chunk(timeout=1.0); if chunk is None: continue` else legacy
     `to_thread(_reader[0], frame_bytes)` path.
   - **`boot_warmup` branch:** placed AFTER RMS/VAD compute but BEFORE the
     standby/listening/reply branches. Sets `self.vad_state = "boot_warmup"` and
     `continue`. Drains the queue (so MicReader's drop_oldest stays idle) but skips
     OWW + endpointing entirely.
   - **`audio_level` emission DELETED** — entire block including `level_tick`
     counter (D-10). MicReader is now the sole emitter; per W-1 it includes
     `utterance_id` in its payload by reading `voice_loop._utterance_id`.
   - **B-2 fix:** `_drainer_task` creation block at mute-entry and the
     `try/finally: _drainer_task.cancel(); await _drainer_task` cleanup block at
     mute-exit BOTH deleted. Replaced with `spoke = await
     self._transcribe_and_dispatch(pcm)` — MicReader continuously drains the socket
     in its own task, so the per-turn drainer is no longer needed.
7. **Deletions** (3 functions removed):
   - `VoiceLoopController._run_esp32` (~93 lines)
   - `VoiceLoopController._esp32_drain_during_mute` (~43 lines)
   - `VoiceLoopController._make_stereo_reader` method (~18 lines)
8. **`_make_stereo_reader` free function** added at module scope (above
   `class VoiceLoopController:`). Algorithm preserved verbatim; takes
   `(read_fn, normalize_factor, level_setter)` so callers (MicReader) inject their
   own per-channel RMS sink. Wired into MicReader via
   `mic_reader.set_stereo_reader_factory(_make_stereo_reader)` at module scope.
9. **`_active_audio_source_label`** updated to delegate to
   `self.mic_reader.active_source` when wired; legacy branch retained for tests /
   `mic_source != "esp32"`.
10. **`status()` `mic_stream_state`** prefers `self.mic_reader.status()["stream_state"]`
    when wired, falls back to legacy `self._mic_stream_state` field.
11. **`_orchestrated_startup` reordered:**
    - After `_ensure_crossover_link` + service-readiness gate + `_play_success_sound`
      + `_prewarm_filler`, BEFORE `_warmup_wakeup`: `active = await
      mic_reader.wait_active(timeout=90.0)`. On timeout emits
      `mic_reader_active_timeout` but does NOT abort startup (warmup TTS still proceeds).
    - After `voice_loop.start()` succeeds in the retry loop: calls
      `voice_loop._set_voice_state("standby", "warmup_done")` and resets
      `voice_loop._standby_entry_time = time.perf_counter()` to arm the OWW guard
      window — this is the D-14 boot_warmup → standby transition.
12. **`_wait_for_esp_ready`, `_background_esp_retry`, `_start_background_esp_retry`,
    `force_esp_retry`, `_run_local`, `_esp_mic_fallback`** all retained per W-5 /
    D-16. They are reachable only when `mic_source != "esp32"` (legacy local-mic
    path).

## Verification

All acceptance criteria from the executor context were satisfied:

| # | Check | Result |
|---|-------|--------|
| 1 | `python3 -m py_compile System/Orchestrator.py` | OK |
| 2 | Import-time smoke (`PYTHONPATH=System python3 -c "import Orchestrator; ..."`) | `OK MicReader`; `voice_loop.mic_reader is mic_reader: True`; `voice_loop._voice_state: boot_warmup`; `stereo_reader_factory wired: True` |
| 3 | `grep -c "def _run_esp32\|def _esp32_drain_during_mute\|async def _audio_level_monitor"` | 0 |
| 4 | `grep -c "_drainer_task\|adam_esp32_drainer"` | 0 |
| 5 | `grep -c '"boot_warmup"'` | 6 (>= 2) |
| 6 | `grep -cE 'mic_reader\.wait_active\|mic_reader\.start\(\)\|mic_reader\.stop\(\)\|mic_reader\.get_chunk'` | 5 (>= 4) |
| 7 | `grep -nE "^def _make_stereo_reader"` (module-level) | line 309: `def _make_stereo_reader(` |
| 8 | `grep -c 'if self.mic_source == "esp32":'` | 3 (>= 1; covers `_run`, retained legacy guards) |
| 9 | `grep -c 'event_log.append("audio_level"'` | 0 |

Additionally the AST-walk verification from both Task 1's and Task 2's `<verify>` blocks
passes (`_run_esp32`, `_esp32_drain_during_mute`, `_audio_level_monitor` all gone from
the AST funcs set; `_run_via_mic_reader` present; `_make_stereo_reader` only at module
scope not as a class method; `VALID_VOICE_STATES` present; `_run_local`,
`_wait_for_esp_ready`, `force_esp_retry` all retained).

## Deviations from Plan

**None substantive.** Two minor implementation notes:

1. **Stereo factory wiring location.** Plan Task 2 step 9 mentions adding stereo
   factory injection inside `VoiceLoopController.__init__`. I instead wired it at
   module scope right after `voice_loop.mic_reader = mic_reader` (same code block,
   one line below) because the module-level `_make_stereo_reader` free function is
   not visible inside `__init__` without a forward reference dance. The end state
   is identical (MicReader receives the factory before `start()` runs), but the
   wiring sits at module scope rather than inside the constructor. The plan
   explicitly states the construction-time vs post-construction choice is left to
   the executor for the chicken-and-egg case.

2. **`_orchestrated_startup` standby transition placed inside the retry loop's `if
   result.get("ok"):` branch.** The plan suggested adding it "after the
   `voice_loop.start()` succeeds (inside the for-retry loop, in the `if
   result.get("ok"):` branch right after `event_log.append("voice_loop_boot_ready",
   ...)`)". I did exactly this; the `_standby_entry_time` reset is included in the
   same code block so the OWW guard arms together with the state transition.

No Rule 1/2/3 auto-fixes were needed — the plan was precise and the surgical edits
landed cleanly without side issues. The CLAUDE.md invariants (LLM-only-Russian-text,
`_NO_PROXY_OPENER`, `half_duplex_mute`, ESP32 socket discipline) were not in scope of
this refactor — `_NO_PROXY_OPENER` lives in MicReader (Plan 07-02), and
`half_duplex_mute` continues to work via the unchanged `mic_muted`/`mic_unmuted`
event flow in `_vad_loop`.

## Authentication Gates

None. This plan is a pure code refactor — no external API calls, no auth required.

## Files

- **Modified:** `System/Orchestrator.py` (3407 → 3312 lines)

## Commits

- `0c358a8` — `feat(07-03): integrate MicReader into Orchestrator`

## Self-Check: PASSED

- `System/Orchestrator.py` — exists, 3312 lines.
- Commit `0c358a8` — found in `git log`.
- `.planning/phases/07-esp32-mic-pipeline-refactor-micreader-keep-alive/07-03-PLAN.md` — exists.
- `.planning/phases/07-esp32-mic-pipeline-refactor-micreader-keep-alive/07-03-SUMMARY.md` — this file.
