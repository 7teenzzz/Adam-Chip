# Flora Coexistence: Priority Layers Design

**Date:** 2026-06-11  
**Scope:** Full analysis of FloraController (flora.py) + Orchestrator event flow + coexistence design  
**Input files:** System/adam/flora.py (586 lines), System/Orchestrator.py (partial), System/Config.json (flora.states section)

---

## 1. AS-IS: FloraController (flora.py)

### 1.1 Architecture

FloraController is a **pure event consumer** — no timers, no priorities, no state machine. It:
- Subscribes to EventBus via `event_log.subscribe()` → gets a queue
- Runs `_consume()` task that awaits events and calls `_handle(event)`
- `_handle()` maps event type → preset name → calls `_set_state(preset)`
- `_set_state()` builds params from Config.json and POSTs to ESP32 via `MCUClient.set_flora_state`

### 1.2 Current Event → Preset Mapping

| Event type | Condition | Preset | Note |
|-----------|-----------|--------|------|
| `wake_word_detected` | any | `accent` | Barge-in guard: cancels RMS task first |
| `wake_word_detected` | any | `accent` + `asyncio.sleep(hold_ms/1000)` | hold_ms=220ms, then returns (voice_state_change fires next) |
| `voice_state_change` | `from=boot_warmup` AND `_booted==False` | `wake_bloom` | Once only |
| `voice_state_change` | `to=listening` | `attentive` | Barge-in guard: cancels RMS task |
| `voice_state_change` | `to=standby` | `breathe` | Barge-in guard: cancels RMS task |
| `llm_thinking_started` | any | `think_pulse` | No guard |
| `tts_started` | any | `external` | Suppresses firmware animation; enables RMS stream |
| `tts_finished` | `_answer_active==True` | `breathe` | After RMS stream stops |

### 1.3 Answer State (RMS Speech Sync — FLORA-04)

The `_answer_active` flag controls the RMS speech streaming path:
- `tts_started` → `_on_answer_start()` → `_answer_active=True`, push `external` preset
- `feed_speech_wav(wav_bytes)` called by Orchestrator `_consumer()` at each chunk dispatch
- Each WAV chunk spawns `_rms_chunk_task()` → `_rms_envelope()` in thread → `_rms_stream(duties)`
- `_rms_stream` sends brightness frames at ~12.5fps (80ms interval) in lockstep with playback
- `tts_finished` → `_on_answer_end()` → cancel RMS task → `_answer_active=False` → push `breathe`

### 1.4 Barge-in Guard (D-09)

Three events trigger the barge-in guard path (cancel RMS + clear answer_active):
1. `wake_word_detected`
2. `voice_state_change(to=listening)` 
3. `voice_state_change(to=standby)`

The `_on_answer_end()` has an R2 guard: if `_answer_active==False` (already cleared by barge-in), it returns immediately and does NOT push `breathe` over the post-barge-in state.

### 1.5 State Fields in FloraController

```python
self._booted: bool          # wake_bloom fires only once (boot_warmup exit)
self._answer_active: bool   # True during tts_started..tts_finished
self._fed_wav_this_answer: bool  # tracking: streaming vs degraded path
self._rms_task: asyncio.Task    # per-chunk RMS stream task
self._task: asyncio.Task        # consumer loop
self._queue: asyncio.Queue      # EventBus subscription
```

**No priority tracking. No `current_preset` field. No P2/P3 distinction.**

---

## 2. VOICE STATE MACHINE (Orchestrator)

### 2.1 Valid States

```python
VALID_VOICE_STATES = ("boot_warmup", "standby", "listening", "reply")
```

Note: `thinking` and `speaking` are NOT voice states — they are `runtime_state["thinking"]` and `runtime_state["speaking"]` bool flags overlaid on voice state.

### 2.2 Transitions

```
boot_warmup ──warmup_done──────────────────────────► standby
                                                        │
standby ──wake_word_detected───────────────────────► listening
standby ──vad_no_wake (no OWW, maintenance mode)───► listening
                                                        │
listening ──silence timeout (6s without speech)────► standby
listening ──ASR → LLM → TTS → spoke=True──────────► reply
listening ──ASR → LLM → spoke=False (no reply)────► standby
                                                        │
reply ──silence timeout (reply_silence_timeout)────► standby
reply ──barge_in (OWW during TTS)──────────────────► reply (reset)
reply ──manual_interrupt───────────────────────────► standby
```

### 2.3 Concurrent State Flags During a Turn

While `voice_state == "listening"` (ASR/LLM/TTS in progress):
- `runtime_state["thinking"] = True` → set before LLM call
- `runtime_state["thinking"] = False` → set in finally after LLM
- `runtime_state["speaking"] = True` → set when first WAV chunk starts playing (`_mark_speaking_started`)
- `runtime_state["speaking"] = False` → set in finally after all chunks done

Voice state transitions to `reply` **after** `speaking=False` (after TTS fully done).

---

## 3. FULL DIALOGUE TURN TIMELINE (Flora perspective)

One complete turn from wake word to reply-window:

```
t=0ms    OWW detects wake word
         event: wake_word_detected
         flora: accent  ← immediate
         flora: sleep(220ms)  ← hold_ms

t+20ms   voice_state_change(from=standby, to=listening)
         [flora _handle: sees to=listening, cancels RMS (already none), sets attentive]
         BUT: wake_word_detected handler is still sleeping!

RACE CONDITION HERE:
  - wake_word handler sleeps 220ms then returns (no further action)
  - voice_state_change(to=listening) sets attentive concurrently ~20ms after

Because both handlers are await'd sequentially from _consume(),
the event queue is processed one at a time:
  - wake_word_detected: sets accent, then sleeps 220ms → BLOCKS _consume
  - voice_state_change: QUEUED, waits for wake_word handler to finish
  → attentive fires at t+220ms (correct behaviour, hold is for firmware)

t+220ms  attentive fires (after accent hold)

t+500ms  User speaks, VAD detects speech

t+2500ms ASR transcription done
         event: llm_thinking_started
         flora: think_pulse

t+8000ms LLM token generation done (Gemma 4 E4B ~6-9s)
         event: llm_thinking_finished  (NOT subscribed by flora)

t+8100ms First TTS WAV chunk synthesized, playback dispatched
         runtime_state["speaking"] = True
         event: tts_started
         flora: external (suppresses firmware animation)
         flora_controller.feed_speech_wav(chunk1)  ← RMS stream spawned

t+8200ms..t+10000ms (multi-chunk TTS)
         For each chunk: feed_speech_wav(wav) → RMS light stream

t+10000ms All chunks done
         runtime_state["speaking"] = False
         event: tts_finished
         flora: stop RMS task, answer_active=False, breathe

t+10000ms voice_state: listening → reply  (set in _transcribe_and_dispatch after TTS)
         event: voice_state_change(to=reply)  ← NOT handled by flora
         (flora does not react to to=reply)

t+14000ms User doesn't reply (reply_silence_timeout_sec=4s default)
         voice_state: reply → standby
         event: voice_state_change(to=standby)
         flora: breathe  (already breathe, no-op in practice)
```

---

## 4. CURRENT PROBLEMS

### 4.1 "Last Writer Wins" (Real Problem)

**When does it manifest?**

Scenario: rapid `think_pulse` → `tts_started` transition:
- `llm_thinking_started` fires → flora queues `think_pulse` 
- Immediately (microseconds later), first WAV chunk arrives → `tts_started` fires
- Queue: [think_pulse, external]
- `think_pulse` executes first (HTTP POST), then `external` executes
- Result: correct. In this scenario ordering is deterministic and intentional.

Scenario: **barge-in during think_pulse**:
- Flora in `think_pulse` (ESP32 animating)
- User says "адам" during LLM thinking
- But: barge-in OWW is NOT active during thinking (intentional — see Orchestrator comment line 1005-1009)
- So this specific race cannot occur in the current architecture

**Actual current race:**

`wake_word_detected` + immediately queued `voice_state_change(to=listening)`:
- Wake handler: sets accent, sleeps 220ms (accent_hold_ms), BLOCKS _consume
- listening handler: queued, executes at t+220ms → sets attentive
- This is intentional and correct behaviour. No real problem here.

**True "last writer wins" risk:**

If two pipeline branches both emit events that both map to different presets within the same asyncio tick (before _consume processes them), the queue serializes them — the second one wins. This is fine for the current single-path architecture. 

**The real problem is architectural, not timing:**

Currently there is **no concept of P2 (subconscious/emotion) vs P3 (pipeline/dialog)**. When we add emotion-driven flora (P2), any pipeline event (P3) will blindly overwrite it, and vice versa. `breathe` after TTS finishes will overwrite `curious_b` from 3 turns ago. `think_pulse` will overwrite `warm_a` from the current AIIM emotion.

### 4.2 No P2 Restoration After P3

When TTS ends: `tts_finished → breathe`. But the previous P2 state (e.g., `unease_b` from AIIM) is lost. There is no mechanism to restore it.

### 4.3 AIIM Emotion Never Drives Flora

EmotionMachine runs every turn in `_run_dialogue_turn_locked` (line 3453-3459). Current emotion state (`curious`, `warm`, `unease`, `sharp`, `calm`) is computed but **never forwarded to FloraController**. This is the gap documented in `flora_animations.md §2`.

### 4.4 D-11 Invariant Binding

`attentive` → `vibro_enabled=False` is hardcoded in `_silent_states` set. This is correct and must stay. Any P2 emotion preset that fires during listening must also respect D-11. Currently this cannot happen (no P2 layer), but the design must account for it.

---

## 5. PRIORITY DESIGN

### 5.1 Three Layers

```python
from enum import IntEnum

class FloraPriority(IntEnum):
    P1_BARGE_IN = 3    # Emergency: barge-in during TTS (immediate override of everything)
    P3_PIPELINE = 2    # Dialog pipeline: wake→accent, listening→attentive, thinking→think_pulse, tts→external+RMS
    P2_SUBCONSCIOUS = 1  # AIIM emotion: curious/warm/unease/sharp/calm ambient state
```

**P1 (BARGE-IN)** — current barge-in guard behavior already implemented. Not a persistent state; it fires once and transitions to P3_PIPELINE (wake_word_detected → accent → attentive).

**P3 (PIPELINE)** — all currently implemented presets. Driven by hard pipeline events:
- `accent` (wake detection)
- `attentive` (listening, D-11 vibro-off)
- `think_pulse` (LLM thinking)
- `external` + RMS stream (TTS speaking)
- `breathe` (standby/idle)

**P2 (SUBCONSCIOUS)** — NEW. Driven by AIIM EmotionMachine output. Ambient "mood" of the installation. Changes per-turn when emotion changes. Should be visible during `breathe` (standby) and after TTS ends.

### 5.2 Transition Table

| Current priority | Incoming priority | Action |
|-----------------|-------------------|--------|
| P2 | P3 | **Override**: apply P3. Save P2 state as `_p2_pending` (preset + params). |
| P2 | P2 | **Update**: apply new P2 state. Clear `_p2_pending` (P2 → P2 is normal update). |
| P3 | P3 | **Override**: apply new P3 state. P2 is unchanged in `_p2_pending`. |
| P3 | P2 | **Reject**: P3 is active. Store as `_p2_pending`, apply after P3 ends. |
| none | any | **Apply**: set state, set priority. |

### 5.3 P3 End Detection: When to Restore P2

P3 ends when flora transitions back to `breathe` from `_on_answer_end()` or from `voice_state_change(to=standby)`. These are the two "return to idle" transitions.

**After P3 ends → restore P2 if `_p2_pending` exists.**

Exception: if P3 ends via barge-in (`_on_answer_end` R2 guard) → P3 has already transitioned to P3_PIPELINE (accent → attentive). Do NOT restore P2 here — the user is speaking again.

### 5.4 P3 Pipeline Presets (never interruptible by P2)

The following presets are P3 and block P2:
- `accent` — wake detection (brief, ~220ms then overridden by attentive)
- `attentive` — listening (D-11 requires no vibro, P2 would add vibro)
- `think_pulse` — LLM thinking
- `external` + RMS stream — TTS speaking
- `wake_bloom` — boot animation (P3, fires once)

The following preset is the P3/P2 boundary:
- `breathe` — standby idle. P3 sets it. P2 should replace it with emotion preset.

### 5.5 D-11 Invariant in Priority System

`attentive` is **P3 and absolute**. P2 must never fire while `voice_state == "listening"`.

Implementation: in `push_preset_p2()`, check if current voice state is `listening`. If yes, store as `_p2_pending` and return without pushing. This is belt-and-suspenders; the P3 > P2 rule already handles it.

D-11 check in `_set_state()` is already implemented for the `silent_states` set and must stay.

---

## 6. NEW FLORACONTROLLER STATE MACHINE DESIGN

### 6.1 New Fields

```python
self._current_priority: FloraPriority | None = None   # priority of last applied state
self._current_preset: str | None = None               # name of last applied state
self._p2_preset: str | None = None                    # last P2 emotion preset name
self._p2_params: dict | None = None                   # last P2 params (for restore)
```

### 6.2 New Public Methods

```python
# EXISTING (unchanged):
async def push_preset(self, state: str) -> bool
    # Manual API push — no priority tracking, maps to P3 for simplicity

# NEW:
async def push_preset_p2(self, preset: str, params: dict | None = None) -> None:
    """Push an emotion/subconscious preset (P2). Rejected if P3 is active.
    
    Args:
        preset: flora preset name (e.g. "curious_a", "warm_b")
        params: optional param override dict; if None, built from Config.json
    """

async def on_p3_ended(self) -> None:
    """Called after breathe is set by a P3 → idle transition.
    Restores _p2_pending if exists. Called internally from _on_answer_end
    and from the standby voice_state handler.
    """
```

### 6.3 Modified `_handle()` Logic

```python
async def _handle(self, event):
    etype = event.get("type")
    if etype == "wake_word_detected":
        # P3 override — same as now + set priority
        await self._cancel_rms_task()
        self._answer_active = False
        self._current_priority = FloraPriority.P3_PIPELINE
        await self._set_state("accent")
        await asyncio.sleep(hold_ms / 1000.0)
        
    elif etype == "voice_state_change":
        to = payload.get("to")
        if to == "listening":
            self._current_priority = FloraPriority.P3_PIPELINE
            await self._set_state("attentive")
        elif to == "standby":
            # P3 ending: set breathe, then restore P2
            await self._cancel_rms_task()
            self._answer_active = False
            self._current_priority = FloraPriority.P3_PIPELINE
            await self._set_state("breathe")
            await self._restore_p2()   # NEW
            
    elif etype == "llm_thinking_started":
        self._current_priority = FloraPriority.P3_PIPELINE
        await self._set_state("think_pulse")
        
    elif etype == "tts_started":
        self._current_priority = FloraPriority.P3_PIPELINE
        await self._on_answer_start(event)
        
    elif etype == "tts_finished":
        # _on_answer_end already has R2 guard
        # After breathe is set, restore P2
        await self._on_answer_end()   # sets breathe
        await self._restore_p2()     # NEW

async def _restore_p2(self) -> None:
    """After P3 settles, restore P2 emotion preset if one is pending."""
    if self._p2_preset is None:
        return
    # Don't restore if we're in an active P3 state again
    # (can happen if events queue up: standby → wake_word in rapid succession)
    if self._current_priority == FloraPriority.P3_PIPELINE and self._current_preset != "breathe":
        return
    self._current_priority = FloraPriority.P2_SUBCONSCIOUS
    await self._set_state(self._p2_preset, **(self._p2_params or {}))
```

### 6.4 New `push_preset_p2()` Implementation

```python
async def push_preset_p2(self, preset: str, params: dict | None = None) -> None:
    # Always save P2 state for restoration after P3
    self._p2_preset = preset
    self._p2_params = params
    
    # If P3 is active (not breathe), defer
    if (self._current_priority == FloraPriority.P3_PIPELINE 
            and self._current_preset not in (None, "breathe")):
        # Saved in _p2_preset/_p2_params — will be applied after P3 ends
        return
    
    # Apply immediately: P2 > nothing, P2 > breathe
    self._current_priority = FloraPriority.P2_SUBCONSCIOUS
    self._current_preset = preset
    if params:
        await self._set_state(preset, **params)
    else:
        await self._set_state(preset)
```

---

## 7. DURATION / HOLDOUT AFTER P3

### 7.1 Current Holdout

`accent_hold_ms = 220ms` — already implemented. This is the only duration-based hold.

### 7.2 Proposed Holdout After TTS (P3 → P2 transition)

**Question:** when TTS finishes, should P2 restore immediately or wait?

**Analysis:**
- `tts_finished` fires after `speaking=False` (finally block in `_streaming_turn`)
- voice_state transitions to `reply` shortly after (not standby yet)
- The user has a reply window (4s default)
- If P2 restores `curious_b` immediately after TTS, and the user says something → P3 fires `accent` then `attentive` on the next wake word → correct

**Recommendation: NO additional holdout after P3 TTS end.**

Rationale:
- `breathe` is boring; P2 emotion preset is more expressive
- The P3 restoration chain is fast (~20-80ms) — no visible flicker
- The reply window (4s) is plenty of time to show P2 before the next P3 event

For `voice_state_change(to=standby)` specifically: P2 should restore immediately. Standby can last minutes.

### 7.3 `breathe` as Transitional State

In the new design, `breathe` is a **transitional state** that P3 sets and P2 immediately replaces. It signals "P3 ended, restore P2". The visual result: lamps briefly breathe, then shift to the emotion pattern. This is aesthetically correct — a brief exhale before the ambient mood.

If P2 is not set (first turn, no emotion detected yet), `breathe` stays as the ambient default. This is current behavior.

---

## 8. CROSSFADE WITH PRIORITIES

`crossfade_ms = 200ms` — firmware-side parameter, always applied to any preset transition regardless of priority.

Priority system does not need to modify crossfade. All state transitions look smooth:
- P3 override of P2: 200ms crossfade into pipeline state — smooth
- P2 restore after P3: 200ms crossfade from breathe into emotion state — smooth
- P2 update (new emotion): 200ms crossfade from old emotion to new — smooth

Only P1 barge-in should bypass crossfade: `crossfade_ms=0` for immediate snap to accent. This already happens implicitly because `_cancel_rms_task()` fires and immediately pushes accent before any animation can run.

If needed, add `crossfade_ms=0` override to P1 barge-in `_set_state("accent")` call.

---

## 9. EMOTION → FLORA INTEGRATION (P2 Call Point)

### 9.1 Where to Call `push_preset_p2`

In `_run_dialogue_turn_locked` (Orchestrator.py, ~line 3453-3476), after AIIM emotion update:

```python
# EXISTING AIIM block:
new_emotion, emotion_src = _emotion_machine.transition(...)
if new_emotion != aiim_state.emotion or emotion_src:
    aiim_state.emotion_src = emotion_src
aiim_state.emotion = new_emotion

# ADD AFTER (non-blocking, fire-and-forget):
if flora_controller.is_enabled():
    # Compute intensity from AspectModulator's last weight or hardcode 0.5
    asyncio.create_task(
        flora_controller.push_preset_p2_emotion(new_emotion, intensity=0.5),
        name="flora_p2_emotion"
    )
```

**Why `create_task` not `await`:** `_run_dialogue_turn_locked` is in the hot path. `push_preset_p2` does an HTTP POST to ESP32 (up to `flora_timeout_sec=3s`). This must not block the dialogue pipeline.

### 9.2 Emotion → Preset Name Mapping

| AIIM Emotion | P2 Preset (default) | Switch to variant B when |
|-------------|---------------------|--------------------------|
| `curious` | `curious_a` | intensity > 0.65 |
| `warm` | `warm_a` | intensity > 0.65 |
| `unease` | `unease_a` | intensity > 0.65 |
| `sharp` | `sharp_a` | intensity > 0.65 |
| `calm` | `calm_a` | intensity > 0.65 |

Intensity signal: currently missing a clean metric. Options:
1. Use `aiim_state.vector` aspect values (e.g., `em` for warmth, `me` for unease)
2. Use fixed 0.5 initially, tune later

### 9.3 `push_preset_p2_emotion()` Helper Method

```python
async def push_preset_p2_emotion(self, emotion: str, intensity: float = 0.5) -> None:
    """High-level entry point: map AIIM emotion → flora P2 preset and push."""
    variant = "b" if intensity > 0.65 else "a"
    preset = f"{emotion}_{variant}"
    # Fallback: if preset not in Config, use breathe
    known = set((self._live_flora_cfg().get("states") or {}).keys())
    if preset not in known:
        logger.warning("flora P2: emotion preset %r not in Config.json — skipping", preset)
        return
    await self.push_preset_p2(preset)
```

---

## 10. P2 PENDING RESTORATION: DETAILS

### 10.1 What Happens to P2 Signal When P3 Fires

P3 event arrives → P2 is "saved" in `_p2_preset/_p2_params` fields. Not discarded.

P3 ends → `_restore_p2()` checks `_p2_preset` → applies it. The last emotion state is recovered.

### 10.2 P2 Staleness

Should a P2 emotion preset saved 10 minutes ago be restored?

**Decision: yes.** The emotion state in AIIMRuntimeState persists for the session. The P2 preset reflects the emotional state of THIS session. It's correct to restore it after a P3 event, regardless of elapsed time.

If the session ends (`session_state["accumulator"]` commits), the next session starts with default emotion `curious`. When the new session's first turn fires, `push_preset_p2_emotion("curious", 0.5)` will set the P2 preset — clearing the old one.

### 10.3 P2 Persistence Across Standby

When Adam is in standby between turns:
- `breathe` is the current P3 baseline
- After P2 is implemented: `curious_a` (or current emotion variant) is the P2 ambient
- This is the desired behavior: the lights breathe in the current emotional character

### 10.4 Session Reset

On `voice_state_change(from=boot_warmup)` → `wake_bloom` → no P2 yet (session just started). `_p2_preset = None`. P2 will be set after the first turn.

---

## 11. COMPLETE NEW STATE MACHINE SUMMARY

### 11.1 Fields

```python
_current_priority: FloraPriority | None   # current active layer
_current_preset: str | None               # last preset name pushed to ESP32
_p2_preset: str | None                    # saved P2 emotion preset (may be pending)
_p2_params: dict | None                   # saved P2 params
_booted: bool                             # wake_bloom once-only flag (unchanged)
_answer_active: bool                      # tts_started..tts_finished (unchanged)
_fed_wav_this_answer: bool                # RMS vs degraded path flag (unchanged)
_rms_task: asyncio.Task | None            # per-chunk RMS stream task (unchanged)
```

### 11.2 Lifecycle of One Full Turn with P2

```
[Session start, no P2 set]
  flora: breathe (boot default)

[First dialogue turn]
  Orchestrator: wake_word_detected
  P3: accent (220ms hold)
  P3: attentive (after hold)

  Orchestrator: llm_thinking_started
  P3: think_pulse

  Orchestrator: tts_started
  P3: external + RMS stream

  Orchestrator: tts_finished
  P3: breathe
  P3 → P2: _restore_p2() → _p2_preset is None → stay at breathe

  Orchestrator: AIIM emotion computed = "curious"
  P2: push_preset_p2_emotion("curious", 0.5)
  → current_priority = P2, current_preset = "curious_a"
  Flora: curious_a ← first P2 state established

[Second dialogue turn — 30s later]
  flora: curious_a (P2 ambient, visible for 30s)

  wake_word_detected
  P3 override → accent (P2 saved: _p2_preset="curious_a")

  attentive
  think_pulse
  tts_started → external + RMS

  tts_finished → breathe
  → _restore_p2() → _p2_preset="curious_a" → apply
  Flora: curious_a restored

  AIIM emotion shifts to "unease" (topic about death)
  P2 update: push_preset_p2_emotion("unease", 0.7)
  → variant b (intensity > 0.65)
  → _p2_preset = "unease_b"
  Flora: unease_b ← P2 update in place

[Third turn — user still in unease topic]
  flora: unease_b (P2, visible between turns)
  ... same P3 cycle ... P2 restores unease_b
```

---

## 12. QUESTIONS RESOLVED

**"Last writer wins — is this a real problem?"**
No, in the current single-path architecture the queue serializes events correctly. The real problem is the absence of P2 and the absence of P2 restoration after P3 ends. Once P2 is added without priority logic, then yes — last writer wins becomes a real problem.

**"When P3 finishes (TTS done) — P2 restores immediately or waits?"**
Immediately, no holdout. The crossfade_ms=200ms provides visual smoothness.

**"P2 pending — restores or lost after P3?"**
Restores. `_p2_preset` is saved on P3 override and applied in `_restore_p2()`.

**"How crossfade_ms interacts with priorities?"**
Crossfade applies to all transitions. No special casing needed. P1 barge-in could use crossfade_ms=0 for snappier override — optional.

**"D-11: attentive is P3 or special case?"**
P3 (it's a pipeline event — listening state). The D-11 vibro-off enforcement stays in `_set_state()` via `_silent_states` set — independent of priority layer. Belt-and-suspenders.

**"EmotionMachine → push_preset_p2: who calls and when?"**
Orchestrator calls `flora_controller.push_preset_p2_emotion(new_emotion, intensity)` inside `_run_dialogue_turn_locked` after AIIM emotion update, as `asyncio.create_task` (non-blocking).

**"voice_state lacks thinking/speaking"**
Correct. `thinking` and `speaking` are `runtime_state` bool flags. Flora receives `llm_thinking_started` event (maps to think_pulse) and `tts_started/finished` events. No need to read runtime_state from flora.

---

## 13. IMPLEMENTATION CHECKLIST (ordered by dependency)

1. **Config.json**: Add 10 emotion presets to `flora.states` (from flora_animations.md §3)
2. **Config.schema.json**: Document new emotion preset fields
3. **flora.py**: Add `FloraPriority` enum
4. **flora.py**: Add `_current_priority`, `_current_preset`, `_p2_preset`, `_p2_params` fields
5. **flora.py**: Add `push_preset_p2()` method
6. **flora.py**: Add `push_preset_p2_emotion()` helper
7. **flora.py**: Add `_restore_p2()` internal method
8. **flora.py**: Modify `_handle()` to set `_current_priority`/`_current_preset` and call `_restore_p2()`
9. **Orchestrator.py**: After AIIM emotion block → `create_task(flora_controller.push_preset_p2_emotion(...))`
10. **Tests**: test P2 deferred, P3 override, P2 restore, D-11 with P2

**Estimated scope:** ~120 lines added/modified across 2 files + Config.json entries.

---

## 14. CONFIG.JSON CHANGES REQUIRED

New entries in `flora.states`:
```json
"curious_a": { "base_pct": 15, "peak_pct": 55, "period_ms": 2800, "spark_probability": 0.25, "vibro": false },
"curious_b": { "base_pct": 20, "peak_pct": 65, "period_ms": 1800, "spark_probability": 0.40, "vibro": false },
"warm_a":    { "base_pct": 25, "peak_pct": 50, "period_ms": 5000, "vibro": false },
"warm_b":    { "base_pct": 30, "peak_pct": 60, "period_ms": 3500, "vibro": "soft" },
"unease_a":  { "base_pct": 10, "peak_pct": 60, "period_ms": 1200, "vibro": "medium" },
"unease_b":  { "base_pct": 5,  "peak_pct": 71, "period_ms": 600,  "vibro": "intense" },
"sharp_a":   { "base_pct": 20, "peak_pct": 71, "period_ms": 1600, "attack_ms": 60, "vibro": "sync" },
"sharp_b":   { "base_pct": 15, "peak_pct": 71, "period_ms": 800,  "attack_ms": 30, "vibro": "intense_sync" },
"calm_a":    { "base_pct": 35, "peak_pct": 45, "period_ms": 6000, "vibro": false },
"calm_b":    { "base_pct": 40, "peak_pct": 55, "period_ms": 4500, "vibro": false }
```

Note: `sharp_a/b` use `attack_ms` which is currently in `_SKIP` in `_build_params`. This must be removed from `_SKIP` or the field must be mapped to a firmware param name. Requires firmware-side support for `attackMs` field.

---

## 15. FIRMWARE NOTE

Current FloraParams in ESP32 does not have fields for `jitter`, `attackMs`, or vibro mode strings like `"soft"`, `"medium"`, `"intense"`, `"sync"`. The `_build_params()` method maps `vibro: bool → vibro_enabled: bool` and `vibro: str → vibro_mode: str`. The firmware must support `vibro_mode` values. This is a firmware dependency — must be verified before implementing `unease_a/b`, `sharp_a/b`, `warm_b`.

For `vibro: false` presets (curious_a/b, warm_a, calm_a/b): no firmware changes needed.

---

*End of analysis*
