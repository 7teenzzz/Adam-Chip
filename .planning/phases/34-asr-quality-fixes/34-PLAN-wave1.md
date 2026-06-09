---
phase: 34-asr-quality-fixes
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - System/Orchestrator.py
  - System/Config.json
  - System/Config.schema.json
autonomous: true
requirements:
  - REQ-ASR-EMPTY-PREWAKE

must_haves:
  truths:
    - "When user says 'адам скажи что-нибудь' as a single phrase, ASR receives audio containing 'скажи что-нибудь', not empty"
    - "asr_result.empty=True no longer appears immediately after wake_word_detected when speech spans the OWW debounce window"
    - "pre_wake_buffer_ms is a Config.json parameter, not a hardcoded value"
    - "speech_frames.clear() on OWW trigger is replaced with pre-wake audio prepend"
  artifacts:
    - path: "System/Orchestrator.py"
      provides: "_pre_wake_buf deque in VoiceLoopController.__init__ + prepend logic on OWW trigger"
      contains: "_pre_wake_buf"
    - path: "System/Config.json"
      provides: "pre_wake_buffer_ms parameter in services.asr"
      contains: "pre_wake_buffer_ms"
    - path: "System/Config.schema.json"
      provides: "schema documentation for pre_wake_buffer_ms"
      contains: "pre_wake_buffer_ms"
  key_links:
    - from: "System/Orchestrator.py (_vad_loop standby block)"
      to: "_pre_wake_buf.append(chunk)"
      via: "every frame appended to rolling buffer before OWW processing"
      pattern: "_pre_wake_buf\\.append"
    - from: "System/Orchestrator.py (OWW triggered block)"
      to: "speech_frames = list(_pre_wake_buf) + speech_frames"
      via: "pre-wake prepend replaces speech_frames.clear()"
      pattern: "list\\(self\\._pre_wake_buf\\)"
---

<objective>
Fix BUG-1: empty ASR transcriptions when user speaks the wake word and command in a single
continuous phrase (e.g. "адам скажи что-нибудь"). The root cause is speech_frames.clear() on
OWW trigger discarding audio captured before debounce confirmation (160ms delay). This plan
introduces a rolling pre-wake audio buffer that is prepended to speech_frames on wake detection.

Purpose: Eliminate asr_result.empty=True events caused by OWW debounce eating the command
start, so Adam responds to single-phrase utterances that include the wake word.

Output: Modified Orchestrator.py with _pre_wake_buf mechanism + Config.json with
pre_wake_buffer_ms parameter.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/34-asr-quality-fixes/34-CONTEXT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add pre_wake_buffer_ms to Config.json and Config.schema.json</name>

  <read_first>
    System/Config.json — section services.asr (all current ASR parameters — understand insertion point)
    System/Config.schema.json — section services.asr (understand parameter documentation pattern)
    .planning/phases/34-asr-quality-fixes/34-CONTEXT.md — decisions D-01 (default value 1500ms)
  </read_first>

  <files>System/Config.json, System/Config.schema.json</files>

  <action>
    In System/Config.json, add "pre_wake_buffer_ms": 1500 into the "services" -> "asr" object.
    Place it after "post_tts_discard_window_ms" entry (maintain logical grouping of timing
    parameters). The value 1500 means 1500ms of audio is kept before OWW trigger, covering
    the debounce window (160ms) plus the full wake-word duration (~400ms) plus early command (~940ms).

    In System/Config.schema.json, add a matching property "pre_wake_buffer_ms" inside the
    "services" -> "asr" -> "properties" object. Use the following schema shape (expressed as
    prose, not code block):
    - type: integer
    - minimum: 200
    - maximum: 5000
    - default: 1500
    - description: "Rolling audio buffer retained before OWW wake-word confirmation (milliseconds).
      When OWW triggers, this audio is prepended to speech_frames instead of being discarded.
      Covers OWW debounce window (debounce_hits=2 × 80ms = 160ms) plus wake-word duration
      (~400ms) and early command start (~940ms). Computed to frames as int(pre_wake_buffer_ms
      / frame_ms) in VoiceLoopController.__init__. Minimum 200ms; values below frame_ms have
      no effect. Deferred: 0 as a disable flag is not supported — use 200ms minimum."

    Config-First invariant: these are the only two files that need to change for the parameter;
    the value is read from Config.json at runtime in __init__.
  </action>

  <verify>
    <automated>python3 -c "
import json, sys
cfg = json.load(open('System/Config.json'))
schema = json.load(open('System/Config.schema.json'))
asr = cfg['services']['asr']
assert 'pre_wake_buffer_ms' in asr, 'Config.json missing pre_wake_buffer_ms'
assert asr['pre_wake_buffer_ms'] == 1500, f'Wrong default: {asr[\"pre_wake_buffer_ms\"]}'
asr_schema = schema['properties']['services']['properties']['asr']['properties']
assert 'pre_wake_buffer_ms' in asr_schema, 'schema missing pre_wake_buffer_ms'
print('OK: Config.json pre_wake_buffer_ms =', asr['pre_wake_buffer_ms'])
"
    </automated>
  </verify>

  <acceptance_criteria>
    - System/Config.json services.asr contains "pre_wake_buffer_ms": 1500
    - System/Config.schema.json services.asr.properties contains "pre_wake_buffer_ms" with type integer, minimum 200, maximum 5000, default 1500
    - python3 -c validation command above exits 0
    - No other Config.json fields are modified
  </acceptance_criteria>

  <done>Config.json and schema validated; pre_wake_buffer_ms: 1500 present in both files.</done>
</task>

<task type="auto">
  <name>Task 2: Implement _pre_wake_buf in VoiceLoopController</name>

  <read_first>
    System/Orchestrator.py lines 378-500 — VoiceLoopController.__init__ (understand all
    existing __init__ fields and where to insert _pre_wake_buf initialization)
    System/Orchestrator.py lines 985-1010 — _vad_loop local variable initialization
    (speech_frames, speech_ms, silence_ms declarations)
    System/Orchestrator.py lines 1135-1195 — STANDBY OWW block with speech_frames.clear()
    on line 1171 (the exact site to modify)
    System/Orchestrator.py lines 1320-1340 — speech_frames.append(chunk) and submit path
    (verify pre_wake_buf.append placement does not interfere with submission logic)
    .planning/phases/34-asr-quality-fixes/34-CONTEXT.md — section "Pre-wake buffer (D-01)
    — точный механизм" (pseudocode for the implementation)
  </read_first>

  <files>System/Orchestrator.py</files>

  <action>
    Make three coordinated changes to System/Orchestrator.py:

    CHANGE 1 — VoiceLoopController.__init__ (after the _ww_buf initialization near line 479):
    Read pre_wake_buffer_ms from asr_cfg (already available at that point in __init__):
      self._pre_wake_buffer_ms: int = int(asr_cfg.get("pre_wake_buffer_ms", 1500))
    Compute frame count using self.frame_ms (already set at line 386):
      _pre_wake_frames = max(1, self._pre_wake_buffer_ms // self.frame_ms)
    Initialize the deque:
      self._pre_wake_buf: deque[bytes] = deque(maxlen=_pre_wake_frames)
    Add the import at the top of the file if not already present:
      from collections import deque
    (Check: deque may already be imported — grep before adding.)

    CHANGE 2 — _vad_loop, inside the STANDBY OWW scanning block, BEFORE the OWW processing:
    Find the line that reads `self._ww_buf.append(_raw_chunk_for_monitor)` (approximately
    line 1145). BEFORE this line (i.e., at the very start of the standby block, before the
    guard-window check), add:
      self._pre_wake_buf.append(chunk)
    This ensures every 20ms frame is captured in the rolling buffer regardless of OWW state.
    Important: use `chunk` (the processed/EQ'd audio going to VAD/ASR), not
    `_raw_chunk_for_monitor` (the raw pre-EQ audio used only for monitor WebSocket).

    CHANGE 3 — _vad_loop, inside the OWW triggered block (line 1165 region, `if triggered:`):
    Replace the current:
      speech_frames.clear()
      speech_ms = 0
      silence_ms = 0
    With:
      speech_frames = list(self._pre_wake_buf) + speech_frames
      self._pre_wake_buf.clear()
      speech_ms = len(speech_frames) * self.frame_ms
      silence_ms = 0
    This prepends pre-wake audio to whatever speech_frames already contain (normally empty
    at OWW trigger, but safe if not), then resets the pre-wake buf. speech_ms is recalculated
    from the actual frame count rather than reset to 0, so the ASR submission threshold
    (min_speech_ms) accounts for the prepended frames.

    Add a diagnostic event after the prepend (for events.jsonl verification):
      event_log.append("pre_wake_prepend", {
          "frames": len(self._pre_wake_buf) + len(speech_frames),  # capture BEFORE clear
          "pre_wake_ms": len(list(self._pre_wake_buf)) * self.frame_ms,
      })
    Note: capture the pre-wake frame count BEFORE calling self._pre_wake_buf.clear().
    Restructure to log before clear:
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

    Do NOT modify the speech_frames.clear() at line 1187 (the VAD-direct path for
    wake_word_required=False) — that path does not use OWW so pre-wake buffering is
    not needed there.

    Also do NOT modify the speech_frames.clear() calls at lines 1333-1334 (ASR submission
    path) — those are correct post-submission resets.
  </action>

  <verify>
    <automated>
grep -n "_pre_wake_buf" System/Orchestrator.py | grep -v "^#"
    </automated>
  </verify>

  <acceptance_criteria>
    - grep "_pre_wake_buf" System/Orchestrator.py returns at least 5 lines: __init__ initialization (deque), append in standby block, list() prepend on triggered, .clear() after prepend, event_log.append("pre_wake_prepend")
    - grep "from collections import deque" System/Orchestrator.py returns 1 line (not duplicated)
    - grep -n "speech_frames.clear" System/Orchestrator.py — the clear() at the OWW trigger site (old line 1171) is GONE; the clear() at the ASR submission path (~line 1333) is still present
    - grep "speech_frames = list(self._pre_wake_buf)" System/Orchestrator.py returns 1 line
    - python3 -c "import ast, sys; ast.parse(open('System/Orchestrator.py').read()); print('syntax OK')" exits 0
    - event_log.append("pre_wake_prepend" is present in Orchestrator.py
  </acceptance_criteria>

  <done>
    Orchestrator.py passes syntax check; _pre_wake_buf initialized in __init__; every standby
    frame appended to rolling buffer; OWW trigger prepends pre-wake audio instead of clearing;
    diagnostic event emitted on each prepend.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| mic → VAD loop | Raw PCM bytes from arecord/MicReader enter _vad_loop; chunk content is untrusted |
| _pre_wake_buf → speech_frames | Pre-wake audio prepended without re-validation; bounded by deque maxlen |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-34w1-01 | Denial of Service | _pre_wake_buf deque | accept | deque(maxlen=N) bounds memory; at 1500ms/20ms=75 frames × 320 bytes = 24KB max — negligible |
| T-34w1-02 | Tampering | speech_frames prepend | accept | pre_wake audio is the same PCM stream already accepted by VAD; no new trust boundary crossed |
| T-34w1-03 | Information Disclosure | pre_wake_prepend event | accept | event contains only frame counts and ms durations, no audio content |
</threat_model>

<verification>
After both tasks complete, verify the fix end-to-end:

1. Syntax check: python3 -c "import ast; ast.parse(open('System/Orchestrator.py').read()); print('OK')"
2. Config check: python3 -c "import json; c=json.load(open('System/Config.json')); assert c['services']['asr']['pre_wake_buffer_ms']==1500; print('OK')"
3. Schema check: python3 -c "import json; s=json.load(open('System/Config.schema.json')); assert 'pre_wake_buffer_ms' in s['properties']['services']['properties']['asr']['properties']; print('OK')"
4. Source assertions:
   - grep "_pre_wake_buf" System/Orchestrator.py | wc -l  (expect >= 5)
   - grep "pre_wake_prepend" System/Orchestrator.py | wc -l  (expect 1)
   - grep "speech_frames = list(self._pre_wake_buf)" System/Orchestrator.py | wc -l  (expect 1)
</verification>

<success_criteria>
- System/Config.json services.asr.pre_wake_buffer_ms = 1500
- System/Config.schema.json documents pre_wake_buffer_ms with correct type/range
- VoiceLoopController._pre_wake_buf: deque[bytes] initialized in __init__ with maxlen from config
- Every standby-state frame is appended to _pre_wake_buf (before OWW processing)
- On OWW trigger: speech_frames = list(_pre_wake_buf) + speech_frames, then _pre_wake_buf.clear()
- speech_ms recalculated from len(speech_frames) * frame_ms after prepend
- speech_frames.clear() at OWW trigger site is removed
- event_log pre_wake_prepend event emitted with frame counts
- Orchestrator.py passes python3 ast.parse() syntax check
</success_criteria>

<output>
After completion, create `.planning/phases/34-asr-quality-fixes/34-01-SUMMARY.md` with:
- What changed: _pre_wake_buf mechanism, Config params
- Verification results
- Any deviations from the plan
</output>
