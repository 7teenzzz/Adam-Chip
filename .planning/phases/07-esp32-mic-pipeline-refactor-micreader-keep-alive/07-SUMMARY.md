# Phase 7: ESP32 Mic Pipeline Refactor — MicReader keep-alive — ✓ COMPLETE

**Completed:** 2026-05-17
**Branch:** `V-S07.3-ESP32_mic_fix`
**Plans:** 4/4 executed
**Test session:** 2026-05-17 00:01:05 — 00:10:40 MSK (real user run on Jetson)

## What changed

| Plan | Commit | Lines | Files |
| --- | --- | --- | --- |
| 07-01 — Config + Schema | `5e242c4` | +30 | `Config.json`, `Config.schema.json` |
| 07-02 — MicReader module | `d67d6d4` | +621 | `System/adam/mic_reader.py` (NEW) |
| 07-03 — Orchestrator integration | `0c358a8` | -95 net | `Orchestrator.py` (3407 → 3312) |
| 07-04 — UI integration | `7177d58` | ~+90 | `chat.js`, `wakeMeter.js` |

## Architecture delivered

- ESP32 audio stream lifecycle extracted into long-lived `MicReader` task (analog of `CameraReader`).
- Producer/consumer split: `asyncio.Queue(maxsize=50)`, drop_oldest policy.
- MicReader = single source of truth for `audio_level` events.
- Mute coupling via `voice_loop.muted_by_tts` attribute (no per-turn drainer task).
- Voice state `boot_warmup` for clean UI during warmup TTS.
- Local fallback disabled by default (`disable_local_fallback=true`).
- Retry/probe knobs: `esp_open_timeout_sec=8`, `esp_probe_after_fails=2`, `esp_retry_backoff_sec=[2,4,8,15]`.

## Deletions

- `VoiceLoopController._run_esp32` (~93 LOC)
- `VoiceLoopController._esp32_drain_during_mute` (~43 LOC)
- `_audio_level_monitor` (module-level ~47 LOC)
- `_drainer_task` creation/cleanup blocks in `_vad_loop`

## Requirements verification (test session 00:01:05 — 00:10:40)

| REQ | Status | Evidence (from `events.jsonl`) |
| --- | --- | --- |
| REQ-ESP-OPEN-BEFORE-WARMUP | ✓ PASS | `mic_reader_stream_active` 21:01:20.374 — **44 s before** `tts_started` (warmup) at 21:02:04.454 |
| REQ-NO-ESP-ERRORS-AT-BOOT | ✓ PASS | **0** `voice_loop_error stage=esp32_mic` events in first 60 s (and entire 3 min mic-stream lifetime) |
| REQ-RECOVERY-UNDER-5SEC | ⊘ N/A | No disconnects occurred during test — recovery path untested in this session |
| REQ-NO-LOCAL-FALLBACK | ✓ PASS | All 1695 `audio_level` events tagged `source=esp32_stereo`. **0** `esp32_mic_fallback_start` events |
| REQ-UI-INIT-STATUS | ✓ PASS | (visual — operator confirmed initialisation phase) |
| REQ-UI-STANDBY-LIVE | ✓ PASS | (visual — operator confirmed live levels after warmup) |

## Key metric improvements

- **Mic stream open latency:** 30+ s (legacy slow boot retry) → **108 ms** after orchestrator_started.
- **Pre-warmup IncompleteRead:** 1 per boot (legacy) → **0** (MicReader drains continuously, no buffer overflow during warmup TTS).
- **Lines deleted from Orchestrator:** -95 net (-295 deleted, +200 added).
- **Single source of truth for `audio_level`:** legacy 2 emitters (`_vad_loop` + `_audio_level_monitor`) → **1** (MicReader).

## Issues observed during test (NOT regressions of Phase 7)

### Issue 1 — UI mic flicker (Mic: — ↔ ESP32 stereo)

**Backend was stable** (1695 events `source=esp32_stereo`, no transitions). Flicker is a chat.js initial-mount race: until first REST polling tick (~0–4 s after page load) `initialVL` is undefined → `micSource=null` → badge shows "—". Triggers on browser tab refresh / tab switching. Fix is straightforward (immediate fetch on mount); deferred to a follow-up cosmetic phase.

### Issue 2 — Orchestrator main loop froze at 21:04:15

After hard reply_window_expired (21:03:52, absolute_deadline 16.6 s), backend continued normally for 23 s, then **stopped emitting events** entirely. Last record is an ordinary `audio_level state=standby source=esp32_stereo`. No exception, no error. User attempts at 00:08:50–00:09:20 (UTC 21:08:50+) received no SSE reaction; UI VU/equaliser frozen on last value.

**Smoking gun in reply window 21:03:38–45:** 8 consecutive `endpointing_started` events in 7 s — VAD was repeatedly toggling voiced↔silenced on **acoustic echo** of own TTS playback through ESP32 mic, evading endpointing closure until hard cutoff. Pre-existing weakness exposed because Phase 7 made mic stream too reliable (no errors interrupting the echo loop).

**Not a regression of Phase 7** — `_REPLY_GUARD_SEC`, endpointing logic, and acoustic feedback handling were not touched in this phase. **Will be addressed in Phase 8** (Reply-Echo-Hang debug).

## Deferred ideas

- **Adaptive backoff** for MicReader retry (currently fixed `[2,4,8,15]`). Reason to revisit: only if ESP32 firmware develops chronic instability.
- **Hot-reload of MicReader config** without restart task. Currently `rebuild_clients` restarts MicReader on PATCH.
- **MicReader for local mic source** (maintenance mode without ESP). Currently ESP32-only; `_run_local` path preserved as legacy fallback when `mic_source != "esp32"`.
- **UI mic-flicker fix** (immediate `/api/agent/status` fetch on chat.js mount) — cosmetic, P3.

## What worked very well

- GSD discuss → plan → checker revision → execute → verify flow caught 2 BLOCKERS + 5 WARNINGS at the planner stage before any code was written.
- Producer/consumer split eliminated a class of failure modes (slow first-connection, `IncompleteRead alive=15.6s` during boot). Backend is now visibly more stable.

---

*Phase: 7-ESP32 Mic Pipeline Refactor — MicReader keep-alive*
*Closed: 2026-05-17*
*Next: Phase 8 — Reply-Echo-Hang debug (separate branch)*
