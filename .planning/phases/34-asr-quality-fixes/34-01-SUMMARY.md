---
phase: 34-asr-quality-fixes
plan: "01"
subsystem: voice-loop
tags: [asr, bug-fix, pre-wake-buffer, oww, voice-loop]
dependency_graph:
  requires: []
  provides: [pre_wake_buffer_ms config param, _pre_wake_buf rolling buffer]
  affects: [System/Orchestrator.py, System/Config.json, System/Config.schema.json]
tech_stack:
  added: []
  patterns: [rolling deque buffer, pre-wake audio prepend on OWW trigger]
key_files:
  created: []
  modified:
    - System/Orchestrator.py
    - System/Config.json
    - System/Config.schema.json
decisions:
  - "_pre_wake_buf uses deque(maxlen=N) with post-EQ `chunk` (not raw pre-EQ) to match what ASR will process"
  - "speech_ms recalculated as len(speech_frames)*frame_ms after prepend — not reset to 0"
  - "pre_wake_prepend diagnostic event emitted with frame counts for events.jsonl verification"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-09"
  tasks_completed: 2
  files_modified: 3
---

# Phase 34 Plan 01: Pre-Wake Audio Buffer Summary

**One-liner:** Rolling pre-wake deque[bytes] prepended to speech_frames on OWW trigger — fixes empty ASR when user says "адам скажи что-нибудь" as a single phrase.

## What Changed

### Task 1: Config.json + Config.schema.json

Added `pre_wake_buffer_ms: 1500` to `services.asr` in `System/Config.json`, placed after `post_tts_discard_window_ms` (logical grouping of timing parameters).

Added matching schema property in `System/Config.schema.json` with:
- type: integer, minimum: 200, maximum: 5000, default: 1500
- Description explains OWW debounce window coverage and frame computation formula

### Task 2: VoiceLoopController._pre_wake_buf

Three coordinated changes to `System/Orchestrator.py`:

**CHANGE 1 — __init__** (after `_ww_frames_needed = 4`, line ~487):
```python
self._pre_wake_buffer_ms: int = int(asr_cfg.get("pre_wake_buffer_ms", 1500))
_pre_wake_frames = max(1, self._pre_wake_buffer_ms // self.frame_ms)
self._pre_wake_buf: deque[bytes] = deque(maxlen=_pre_wake_frames)
```
1500ms / 20ms = 75 frames max ≈ 24 KB — negligible memory footprint.

**CHANGE 2 — _vad_loop standby block** (before `_ww_buf.append`):
```python
self._pre_wake_buf.append(chunk)  # uses processed post-EQ chunk
```
Captures every standby frame regardless of OWW state.

**CHANGE 3 — OWW triggered block** (replaced `speech_frames.clear()`):
```python
_pre_wake_list = list(self._pre_wake_buf)
speech_frames = _pre_wake_list + speech_frames
self._pre_wake_buf.clear()
speech_ms = len(speech_frames) * self.frame_ms
silence_ms = 0
event_log.append("pre_wake_prepend", {
    "pre_wake_frames": len(_pre_wake_list),
    "pre_wake_ms": len(_pre_wake_list) * self.frame_ms,
    "total_speech_frames": len(speech_frames),
})
```

## Verification Results

```
=== _pre_wake_buf occurrences (7 lines) ===
483: comment in __init__
485: self._pre_wake_buffer_ms: int = int(asr_cfg.get(...))
486: _pre_wake_frames = max(1, ...)
487: self._pre_wake_buf: deque[bytes] = deque(maxlen=_pre_wake_frames)
1155: self._pre_wake_buf.append(chunk)
1186: _pre_wake_list = list(self._pre_wake_buf)
1188: self._pre_wake_buf.clear()

=== pre_wake_prepend event ===
1191: event_log.append("pre_wake_prepend", {...})

=== speech_frames.clear() remaining lines ===
Lines 1209, 1244, 1355, 1413, 1457 — all untouched (VAD-direct + ASR submission paths)
NOTE: line 1178 (old OWW path) is GONE — replaced with prepend logic

=== deque import ===
139: from collections import deque  # noqa: E402  — single import, not duplicated

=== syntax check ===
syntax OK

=== Config/Schema checks ===
Config.json pre_wake_buffer_ms = 1500  OK
Schema pre_wake_buffer_ms present      OK
```

## Commits

- `8668f75` — feat(phase-34-01): add pre_wake_buffer_ms to Config.json and schema
- `b26f4f5` — feat(phase-34-01): implement _pre_wake_buf rolling buffer in VoiceLoopController

## Deviations from Plan

None — plan executed exactly as written.

The plan specified `speech_frames = list(self._pre_wake_buf) + speech_frames` as the prepend pattern but the implementation correctly uses the intermediate `_pre_wake_list` variable (as also described in the plan's CHANGE 3 pseudocode) to enable accurate diagnostic event logging before `.clear()`.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced. Memory bounded by deque(maxlen) as documented in threat register T-34w1-01.

## Self-Check: PASSED

- System/Config.json has pre_wake_buffer_ms: 1500 ✓
- System/Config.schema.json documents pre_wake_buffer_ms ✓
- System/Orchestrator.py passes ast.parse() ✓
- _pre_wake_buf deque initialized in __init__ ✓
- Every standby frame appended to _pre_wake_buf ✓
- OWW trigger prepends pre-wake audio instead of clearing ✓
- speech_ms recalculated from len(speech_frames)*frame_ms ✓
- pre_wake_prepend event emitted ✓
- deque not imported twice ✓
- speech_frames.clear() at OWW site removed ✓
