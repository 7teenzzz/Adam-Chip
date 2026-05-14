---
phase: voice-loop-standby-guard
reviewed: 2026-05-11T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - System/Orchestrator.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Voice Loop — Code Review Report

**Reviewed:** 2026-05-11
**Depth:** standard
**Files Reviewed:** 1 (System/Orchestrator.py, VoiceLoopController class, lines 206–488)
**Status:** issues_found

## Summary

Three changes were reviewed: (1) a new `_standby_entry_time` instance variable, (2) a 300 ms OWW guard window in the STANDBY block, and (3) a `not speech_frames` guard on the REPLY timeout plus arming of `_standby_entry_time`. Plans requirements 1–4 are partially satisfied — requirement 2 (OWW guard) has a critical correctness defect (false-triggered at cold boot), and requirements 3–4 are fully met. The pipeline invariants from CLAUDE.md (half_duplex_mute, no JSON in LLM output) are not broken by these changes.

---

## Critical Issues

### CR-01: Guard window fires on every cold boot, blocking OWW for 300 ms indefinitely at startup

**File:** `System/Orchestrator.py:248,327`

**Issue:**
`_standby_entry_time` is initialised to `0.0` (epoch). The guard checks:

```python
if time.perf_counter() - self._standby_entry_time < 0.3:
```

`time.perf_counter()` is the system uptime clock, not wall-clock seconds from epoch. On most Linux systems it starts somewhere between a few minutes and many days after boot — never near 0.0. So the subtraction produces a very large positive number and the guard never fires at startup. This is benign at startup.

**However**, there is a second scenario that is a real correctness defect: if the voice loop is **stopped and restarted** via `stop()` + `start()` without going through a REPLY→standby transition, `_standby_entry_time` retains its last value. The `stop()` method (lines 281–296) resets `_voice_state = "standby"` but does **not** reset `_standby_entry_time`. If the last value was set, say, 290 ms ago, and the loop restarts and immediately enters STANDBY, the guard will fire (`perf_counter() - last_armed < 0.3`) and OWW will be silenced for those remaining milliseconds. This is not catastrophic, but it means the guard can silently suppress the OWW engine on a freshly started loop for up to 300 ms — directly contradicting the stated intent ("guard after reply→standby only").

The more dangerous consequence of the same root cause: if `_standby_entry_time` is left at a non-zero value from a previous session and `stop()` does not clear it, the next `start()` call may enter STANDBY with an armed guard regardless of whether a reply just happened. This creates a hard-to-reproduce window where wake words are dropped.

**Fix:**
Reset `_standby_entry_time` in `stop()` so it cannot bleed across loop restarts:

```python
async def stop(self) -> dict[str, Any]:
    self.running = False
    ...
    self._voice_state = "standby"
    self._standby_entry_time = 0.0          # <-- add this line
    self._ww_buf.clear()
    ...
```

Alternatively, initialise with a sentinel that is guaranteed to be far in the past:

```python
self._standby_entry_time: float = -1e9  # sentinel: guard never fires at startup
```

and clear to the same sentinel in `stop()`. This makes the "never fire unless explicitly armed" contract explicit.

---

## Warnings

### WR-01: REPLY state with speech_frames non-empty has no hard upper-bound escape

**File:** `System/Orchestrator.py:344–358,375–406`

**Issue:**
The REPLY timeout is now conditioned on `not speech_frames` (plan requirement 1). This correctly prevents cutting off mid-speech. However, once `speech_frames` is non-empty the only exits from REPLY are:

- Endpointing: `silence_ms >= _command_endpointing_ms` (default 2500 ms)
- Hard segment cap: `speech_ms >= max_segment_ms` (default 15 000 ms)

The `_reply_window_sec` timer (default 4 s) is completely bypassed for the entire duration of any speech that starts within the reply window — even if the speech lasts 20 s or more. An adversarial or broken input (continuous microphone noise above VAD threshold) keeps the loop in REPLY indefinitely and never allows it to return to STANDBY (for exhibition mode, this means the wake-word gate is bypassed for an arbitrary duration). The existing `max_segment_ms` guard is the only backstop but it only fires when speech has **stopped** (endpointing required).

**Fix:**
Add a hard wall-clock deadline for the REPLY state that cannot be bypassed by continuous speech, separate from the no-speech timeout. For example:

```python
REPLY_HARD_DEADLINE_SEC = 30.0  # absolute max time in REPLY, even with speech

if self._voice_state == "reply":
    elapsed = time.perf_counter() - self._reply_start
    if elapsed >= self._reply_window_sec and not speech_frames:
        ...  # existing logic
    elif elapsed >= REPLY_HARD_DEADLINE_SEC:
        # Force abandon, discard any in-progress speech
        speech_frames.clear()
        speech_ms = 0
        silence_ms = 0
        self._voice_state = "standby"
        self._standby_entry_time = time.perf_counter()
        self._ww_buf.clear()
        event_log.append("reply_hard_deadline", {"elapsed_sec": round(elapsed, 1)})
        continue
```

---

### WR-02: vad_state set to "listening" inside guard window, masking the real state

**File:** `System/Orchestrator.py:328`

**Issue:**
During the 300 ms guard window the code sets:

```python
self.vad_state = "listening"
continue
```

But STANDBY already sets `vad_state = "listening"` at line 340. The issue is that during the guard period the voice loop is actually silently discarding audio — it is **not** listening (OWW is skipped, no VAD, no accumulation). Reporting `"listening"` to the status endpoint and event log gives operators a misleading picture. The Web UI and `/api/agent/status` will show the system as listening when it is actually deaf.

This is a correctness issue for observability, not for audio processing. During the 300 ms window this is benign in practice, but if the guard is ever widened (e.g., a config parameter is added), this masking becomes a real debugging hazard.

**Fix:**
Use a dedicated state name, or at minimum document via an event:

```python
if time.perf_counter() - self._standby_entry_time < 0.3:
    self.vad_state = "standby_guard"   # not "listening" — OWW is suppressed
    continue
```

---

### WR-03: `speech_frames.clear()` on line 354 is dead code (confirmed redundant, not just a smell)

**File:** `System/Orchestrator.py:348,354`

**Issue:**
The condition guarding this branch is:

```python
if elapsed >= self._reply_window_sec and not speech_frames:
```

The `not speech_frames` guard means `speech_frames` is provably empty here. The `speech_frames.clear()` on the next line (354) does nothing. This is dead code introduced as part of Change 3. The original comment in the task description acknowledges this ("now redundant"), but dead code in a state machine loop is a maintenance hazard — a future reader may mistakenly believe the clear is doing useful work and not question whether the condition above it is correct.

**Fix:**
Remove line 354:

```python
if elapsed >= self._reply_window_sec and not speech_frames:
    event_log.append("reply_window_expired", {
        "action": "standby", "elapsed_sec": round(elapsed, 1)
    })
    self._voice_state = "standby"
    self._standby_entry_time = time.perf_counter()
    # speech_frames is empty by condition — no clear needed
    speech_ms = 0
    silence_ms = 0
    self._ww_buf.clear()
    continue
```

---

## Info

### IN-01: Guard window applies only when OWW engine is present — no parallel protection when running Whisper-based wake word

**File:** `System/Orchestrator.py:324,327`

**Issue:**
The 300 ms guard is nested inside `if self._wake_engine is not None:`. When the OWW engine is absent (fallback to Whisper-based wake-word detection, which happens via `_transcribe_and_dispatch` → `_wake_re`), the guard window is completely absent. Any residual ALSA audio after TTS playback feeds straight into the VAD/endpointing path in LISTENING/REPLY with no suppression. This is a pre-existing condition for the Whisper path and is not introduced by these changes, but plan requirement 2 ("300 ms OWW deaf window to prevent immediate false wake on residual audio") only applies to the OWW code path. Whether this gap is acceptable is a design decision, but it should be documented.

**Fix (optional):**
If the same protection is wanted for the Whisper path, move `_standby_entry_time` check outside the `if self._wake_engine is not None:` block, or document explicitly that the Whisper path is intentionally unguarded.

---

### IN-02: Plan requirement 2 specifies 300 ms as a constant; it is not configurable and not named

**File:** `System/Orchestrator.py:327`

**Issue:**
The magic literal `0.3` is used directly in the comparison. The plan explicitly states "no new config parameters" — so this is intentional. However, the value has no symbolic name (no constant, no comment stating the unit). If the value is ever tuned, a reader has to know `0.3` is seconds, not milliseconds.

**Fix:**
Add a module-level or class-level constant, or a comment with explicit unit:

```python
_STANDBY_GUARD_SEC = 0.3  # after reply→standby: suppress OWW for this many seconds

if time.perf_counter() - self._standby_entry_time < _STANDBY_GUARD_SEC:
```

---

## Plan Alignment Summary

| Requirement | Status | Notes |
|---|---|---|
| 1. REPLY timer only expires when `speech_frames` empty | SATISFIED | `not speech_frames` guard added on line 348 |
| 2. 300 ms OWW guard after REPLY→STANDBY | PARTIALLY SATISFIED | Guard is correct in the happy path; defect: `_standby_entry_time` not reset in `stop()` means guard can fire incorrectly after loop restart (CR-01) |
| 3. No new config parameters | SATISFIED | Only a hardcoded literal `0.3` |
| 4. Only `System/Orchestrator.py` modified | SATISFIED | No other files touched |

---

_Reviewed: 2026-05-11_
_Reviewer: Claude (adversarial review)_
_Depth: standard_
