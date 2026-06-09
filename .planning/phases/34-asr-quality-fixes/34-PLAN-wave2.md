---
phase: 34-asr-quality-fixes
plan: 02
type: execute
wave: 2
depends_on: [34-PLAN-wave1.md]
files_modified:
  - System/Config.json
  - System/Config.schema.json
  - System/Orchestrator.py
  - System/adam/asr_filter.py
  - System/Speech/ASR_WhisperX.py
  - compose.yaml
autonomous: true
requirements:
  - REQ-ASR-HALLUCINATION

must_haves:
  truths:
    - "vad_onset is 0.2 in both Config.json and compose.yaml (root cause fix)"
    - "Segments with no_speech_prob > 0.85 are discarded in ASR_WhisperX.py"
    - "Segments with compression_ratio < 1.2 are discarded in ASR_WhisperX.py"
    - "Orchestrator drops audio below asr_pre_send_min_rms before calling ASR"
    - "Orchestrator._transcribe_and_dispatch has second-tier pattern guard emitting asr_hallucination_filtered"
    - "_HALLUCINATION_PATTERNS in ASR_WhisperX.py is NOT expanded — current list is sufficient"
  artifacts:
    - path: "System/Config.json"
      provides: "vad_onset: 0.2, asr_pre_send_min_rms: 200"
      contains: "asr_pre_send_min_rms"
    - path: "System/adam/asr_filter.py"
      provides: "is_hallucination() using current pattern set"
      contains: "is_hallucination"
    - path: "System/Orchestrator.py"
      provides: "RMS gate + second-tier pattern guard in _transcribe_and_dispatch"
      contains: "asr_hallucination_filtered"
    - path: "System/Speech/ASR_WhisperX.py"
      provides: "no_speech_prob + compression_ratio per-segment filters"
      contains: "no_speech_prob"
    - path: "compose.yaml"
      provides: "ADAM_ASR_VAD_ONSET default 0.2"
      contains: "0.2"
  key_links:
    - from: "compose.yaml ADAM_ASR_VAD_ONSET"
      to: "_VAD_ONSET in ASR_WhisperX.py"
      via: "env var default changed from 0.1 to 0.2"
      pattern: "ADAM_ASR_VAD_ONSET.*0\\.2"
    - from: "System/Orchestrator.py (_transcribe_and_dispatch)"
      to: "adam.asr_filter.is_hallucination"
      via: "second-tier filter after ASR response"
      pattern: "is_hallucination\\(transcript\\)"
    - from: "System/Speech/ASR_WhisperX.py (_transcribe_audio)"
      to: "per-segment no_speech_prob check"
      via: "seg.get('no_speech_prob', 0.0) >= _NO_SPEECH_THRESHOLD"
      pattern: "no_speech_prob"
---

<objective>
Fix BUG-2: hallucination transcriptions reaching the dialogue turn.

Root cause analysis vs stable commit 9da07f92 (June 5, no hallucinations):
- That commit ran vad_onset=0.3 (code default, no env override)
- Current config: vad_onset=0.1 → Silero VAD triggers on room noise/hum/breathing
  → Whisper receives near-silence segments → hallucinates YouTube phrases
- logprob_threshold change (-0.8 → -1.85) is secondary: classic Whisper hallucinations
  have HIGH logprob (-0.3 to -0.5) because they are memorised from training data

Four-layer defense (all in one wave):
1. vad_onset 0.1 → 0.2 — root cause: fewer false VAD activations
2. Per-segment statistical filters (no_speech_prob, compression_ratio) — catches
   near-silence segments that slip past VAD
3. Pre-send RMS gate in orchestrator — catches fully-silent PCM before calling ASR
4. Orchestrator-side pattern guard — last resort for specific high-logprob phrases

DO NOT expand _HALLUCINATION_PATTERNS. Current list is correct; the problem is
that vad_onset=0.1 was creating near-silence segments that Whisper then filled
with patterns already in the list. Statistical filters are the right lever here.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/34-asr-quality-fixes/34-CONTEXT.md
@.planning/phases/34-asr-quality-fixes/34-01-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Config.json — vad_onset and asr_pre_send_min_rms</name>

  <read_first>
    System/Config.json — section services.asr (find vad_onset: 0.1 and pre_wake_buffer_ms added in wave 1)
    System/Config.schema.json — section services.asr.properties (find vad_onset description, understand insertion point for new param)
  </read_first>

  <files>System/Config.json, System/Config.schema.json</files>

  <action>
    In System/Config.json, section "services" -> "asr":

    CHANGE 1: Update existing value:
      "vad_onset": 0.1  →  "vad_onset": 0.2
    Rationale: 0.1 is the root cause of hallucinations — it triggers on room noise/hum,
    creating near-silence segments that Whisper fills with memorised phrases.
    0.2 catches brief far-field commands (tested stable at 0.3 previously; 0.2 is a
    better middle ground between sensitivity and hallucination rate).

    CHANGE 2: Add new parameter after "vad_onset":
      "asr_pre_send_min_rms": 200
    Rationale: Pre-send RMS gate — if assembled speech_frames have mean RMS below this,
    skip ASR call entirely. 200 is deliberately conservative: only catches truly silent
    submissions. At normalize_factor=8000, a real whispered command would be ~1000+ RMS.

    In System/Config.schema.json, section services.asr.properties:

    UPDATE existing "vad_onset" description to reflect the new recommended value:
    Add to the description: "0.2 is the recommended production value (reduced from 0.1
    after 2026-06-09 analysis: 0.1 triggered on room noise creating near-silence segments
    that Whisper fills with YouTube hallucination phrases; 0.3 was stable on 2026-06-05
    but missed single-syllable commands)."

    ADD new property "asr_pre_send_min_rms":
    - type: integer
    - minimum: 0
    - maximum: 2000
    - default: 200
    - description: "Pre-send RMS gate: if the mean RMS of collected speech_frames falls
      below this value, the orchestrator skips the ASR call and returns an empty result.
      Catches fully-silent submissions that slipped past WebRTC VAD (e.g. stuck VAD state
      or very long silence-misclassified segment). 0 disables the gate. 200 is conservative
      — a real whispered command normalised through normalize_factor=8000 would exceed this.
      Compare with media.audio.silence_rms_threshold (per-frame gate during recording)."
  </action>

  <verify>
    <automated>python3 -c "
import json
cfg = json.load(open('System/Config.json'))
schema = json.load(open('System/Config.schema.json'))
asr = cfg['services']['asr']
asr_props = schema['properties']['services']['properties']['asr']['properties']
assert asr.get('vad_onset') == 0.2, f'vad_onset still {asr.get(\"vad_onset\")}'
assert 'asr_pre_send_min_rms' in asr, 'asr_pre_send_min_rms missing from Config.json'
assert asr['asr_pre_send_min_rms'] == 200
assert 'asr_pre_send_min_rms' in asr_props, 'asr_pre_send_min_rms missing from schema'
print('OK: vad_onset=0.2, asr_pre_send_min_rms=200')
"
    </automated>
  </verify>

  <acceptance_criteria>
    - Config.json services.asr.vad_onset == 0.2 (was 0.1)
    - Config.json services.asr.asr_pre_send_min_rms == 200
    - Config.schema.json documents asr_pre_send_min_rms with type integer, min 0, max 2000
    - Config.schema.json vad_onset description updated with 0.2 rationale
    - No other Config.json fields modified
  </acceptance_criteria>

  <done>Config.json vad_onset=0.2; asr_pre_send_min_rms=200; schema updated.</done>
</task>

<task type="auto">
  <name>Task 2: Create System/adam/asr_filter.py</name>

  <read_first>
    System/Speech/ASR_WhisperX.py lines 44-57 — _HALLUCINATION_PATTERNS (copy verbatim, do NOT expand)
    System/adam/ — ls to understand existing module style
  </read_first>

  <files>System/adam/asr_filter.py</files>

  <action>
    Create System/adam/asr_filter.py — minimal standalone module, no external deps.

    Exports:
    1. HALLUCINATION_PATTERNS: frozenset[str] — CURRENT patterns from ASR_WhisperX.py,
       NOT EXPANDED. Copy verbatim from ASR_WhisperX.py lines 44-57. No new patterns.
    2. is_hallucination(text: str) -> bool — returns True if normalised text matches

    Normalisation (internal):
      def _normalise(s: str) -> str:
          return s.lower().strip("[]().,!? \t\n")

    is_hallucination:
      def is_hallucination(text: str) -> bool:
          if not text or not text.strip():
              return False
          return _normalise(text) in HALLUCINATION_PATTERNS

    Pattern set: copy from ASR_WhisperX.py _HALLUCINATION_PATTERNS as-is.
    Store as frozenset to prevent mutation.
    The set already covers the observed hallucinations:
    - "спасибо за внимание" (confirmed in events.jsonl 23:42:25)
    - "музыка", "[тихая музыка]", etc. (near-silence YouTube artefacts)
    Adding more patterns is deferred — statistical filters in ASR are the correct
    lever for hallucinations not on this list.

    Module must be importable standalone:
      PYTHONPATH=System python3 -c "from adam.asr_filter import is_hallucination; print(is_hallucination('Спасибо за внимание.'))"
    must print True without importing Orchestrator or settings.
  </action>

  <verify>
    <automated>cd /home/i17jet/Agents/Adam-Chip && PYTHONPATH=System python3 -c "
from adam.asr_filter import is_hallucination, HALLUCINATION_PATTERNS
tests = [
    ('Спасибо за внимание.', True),
    ('СПАСИБО ЗА ВНИМАНИЕ', True),
    ('музыка', True),
    ('[тихая музыка]', True),
    ('Как дела?', False),
    ('', False),
    ('   ', False),
]
failed = [(t, e, is_hallucination(t)) for t, e in tests if is_hallucination(t) != e]
assert not failed, f'Failed: {failed}'
assert isinstance(HALLUCINATION_PATTERNS, frozenset), 'Must be frozenset'
print(f'OK: {len(tests)} tests pass, {len(HALLUCINATION_PATTERNS)} patterns')
"
    </automated>
  </verify>

  <acceptance_criteria>
    - System/adam/asr_filter.py exists
    - HALLUCINATION_PATTERNS is a frozenset
    - is_hallucination("Спасибо за внимание.") returns True
    - is_hallucination("Как дела?") returns False
    - is_hallucination("") returns False
    - No imports outside stdlib
    - Pattern count matches ASR_WhisperX.py (not expanded)
  </acceptance_criteria>

  <done>asr_filter.py created; all behavior tests pass.</done>
</task>

<task type="auto">
  <name>Task 3: Orchestrator.py — RMS gate + second-tier hallucination guard</name>

  <read_first>
    System/Orchestrator.py — grep for "_transcribe_and_dispatch" to find the function
    System/Orchestrator.py — full _transcribe_and_dispatch function body
      (find: asr_client.transcribe_pcm call, "if not transcript: return False" check,
       wake-word strip, event_log.append("asr_result") call)
    System/Orchestrator.py — grep for "from adam\." to find import block insertion point
    System/Orchestrator.py — grep for "asr_cfg" in __init__ to confirm asr_pre_send_min_rms
      will be accessible (or check how asr settings are accessed in _transcribe_and_dispatch)
    System/adam/asr_filter.py — just created, confirm exports
  </read_first>

  <files>System/Orchestrator.py</files>

  <action>
    TWO changes to System/Orchestrator.py:

    CHANGE 1 — Import at top of file, in the existing block of "from adam." imports:
      from adam.asr_filter import is_hallucination as _is_hallucination

    CHANGE 2 — _transcribe_and_dispatch function:

    Read the function carefully before editing. Make both sub-changes in the correct order.

    SUB-CHANGE A — RMS gate (BEFORE calling ASR):
    The function receives PCM audio (as bytes). Before calling the ASR service, add:

      # Pre-send RMS gate: skip ASR on near-silent audio to prevent hallucinations.
      _rms_gate = int(settings.section("asr").get("asr_pre_send_min_rms", 200))
      if _rms_gate > 0 and pcm:
          import numpy as _np
          _audio = _np.frombuffer(pcm, dtype=_np.int16).astype(_np.float32)
          if _audio.size > 0 and _np.sqrt(_np.mean(_audio ** 2)) < _rms_gate:
              event_log.append("asr_skipped_silent", {"rms_gate": _rms_gate})
              return False

    Find the exact position: just before the line that calls the ASR service
    (asr_client.transcribe_pcm or similar). The function argument name for PCM bytes
    may differ — read the function signature and body carefully.

    NOTE: numpy is already imported in Orchestrator.py (check: grep "import numpy").
    If already imported as `np`, use `np` instead of `_np` to avoid redefinition.
    Use a module-level import style (move import to top) only if numpy is not yet imported
    at module level. Do NOT use an inline import inside the if-block.

    SUB-CHANGE B — Hallucination pattern guard (AFTER empty-check, BEFORE wake-word strip):
    After the "if not transcript: return False" check, add:

      if _is_hallucination(transcript):
          event_log.append("asr_hallucination_filtered", {
              "raw": transcript[:120],
          }, turn_id=turn_id if "turn_id" in dir() else None)
          return False

    Verify the exact turn_id variable name by reading the function. If turn_id is not a
    local variable at that point, omit the turn_id kwarg:
      event_log.append("asr_hallucination_filtered", {"raw": transcript[:120]})

    Verify syntax after both changes.
  </action>

  <verify>
    <automated>
python3 -c "import ast; ast.parse(open('System/Orchestrator.py').read()); print('syntax OK')" && grep -c "asr_hallucination_filtered" System/Orchestrator.py && grep -c "_is_hallucination" System/Orchestrator.py && grep -c "asr_skipped_silent" System/Orchestrator.py
    </automated>
  </verify>

  <acceptance_criteria>
    - python3 ast.parse(Orchestrator.py) passes (syntax OK)
    - grep "from adam.asr_filter import is_hallucination" Orchestrator.py returns 1 match
    - grep "asr_hallucination_filtered" Orchestrator.py returns >= 1 match
    - grep "asr_skipped_silent" Orchestrator.py returns >= 1 match
    - grep "_is_hallucination(transcript)" Orchestrator.py returns 1 match
    - The RMS gate appears BEFORE the ASR service call
    - The pattern guard appears AFTER "if not transcript: return False"
      and BEFORE any wake-word strip call
  </acceptance_criteria>

  <done>Orchestrator.py: RMS gate + hallucination guard present; syntax OK.</done>
</task>

<task type="auto">
  <name>Task 4: ASR_WhisperX.py — no_speech_prob and compression_ratio filters</name>

  <read_first>
    System/Speech/ASR_WhisperX.py lines 27-60 — VAD/logprob config + _HALLUCINATION_PATTERNS
    System/Speech/ASR_WhisperX.py lines 183-200 — _transcribe_audio with segment loop
      (this is the exact function to modify)
    System/Speech/ASR_WhisperX.py lines 1-30 — env var block (understand where to add
      new env var constants NO_SPEECH_THRESHOLD and COMPRESSION_RATIO_MIN)
  </read_first>

  <files>System/Speech/ASR_WhisperX.py</files>

  <action>
    Two additions to System/Speech/ASR_WhisperX.py:

    CHANGE 1 — env var constants (after the _LOGPROB_THRESHOLD line, ~line 39):
    Add two new configurable thresholds:

      # Per-segment no_speech_prob: probability that the segment contains no speech.
      # Available from faster-whisper (which whisperx uses internally). Conservative
      # default 0.85 — only discard when Whisper itself is 85%+ certain it's silence.
      # Set 1.0 to disable. Not exposed in all whisperx versions; safe fallback in seg loop.
      _NO_SPEECH_THRESHOLD = float(os.environ.get("ADAM_ASR_NO_SPEECH_THRESHOLD", "0.85"))

      # Per-segment compression_ratio: low values indicate a short repetitive/template
      # token sequence — characteristic of near-silence hallucinations. 1.1 is conservative
      # (real speech: 1.8+; hallucinations: 1.0–1.4 typically). Set 0.0 to disable.
      _COMPRESSION_RATIO_MIN = float(os.environ.get("ADAM_ASR_COMPRESSION_RATIO_MIN", "1.1"))

    CHANGE 2 — _transcribe_audio segment loop (lines 190-199):
    Add two filter checks BEFORE the avg_logprob check (or alongside it). The checks use
    .get() with safe fallback defaults so that if a field is absent (older whisperx version),
    the filter never fires:

      for seg in result.get("segments", []):
          if seg.get("avg_logprob", -1.0) < _LOGPROB_THRESHOLD:
              continue
          # Statistical hallucination filters — use safe defaults if field absent
          if seg.get("no_speech_prob", 0.0) >= _NO_SPEECH_THRESHOLD:
              continue
          if seg.get("compression_ratio", 999.0) <= _COMPRESSION_RATIO_MIN:
              continue
          text = seg.get("text", "").strip()
          if text and text.lower().strip("[]().,!? ") not in _HALLUCINATION_PATTERNS:
              parts.append(text)

    DO NOT modify _HALLUCINATION_PATTERNS — keep the current set exactly as-is.
    DO NOT add a sync comment referencing asr_filter.py (ASR_WhisperX.py runs inside
    Docker and cannot import from adam.asr_filter; the two pattern sets are maintained
    independently).

    Verify syntax after changes.
  </action>

  <verify>
    <automated>
python3 -c "import ast; ast.parse(open('System/Speech/ASR_WhisperX.py').read()); print('ASR syntax OK')" && grep -c "no_speech_prob" System/Speech/ASR_WhisperX.py && grep -c "compression_ratio" System/Speech/ASR_WhisperX.py && grep -c "_NO_SPEECH_THRESHOLD" System/Speech/ASR_WhisperX.py
    </automated>
  </verify>

  <acceptance_criteria>
    - python3 ast.parse(ASR_WhisperX.py) passes
    - _NO_SPEECH_THRESHOLD and _COMPRESSION_RATIO_MIN defined at module level via os.environ
    - grep "no_speech_prob" ASR_WhisperX.py returns >= 2 (comment + usage)
    - grep "compression_ratio" ASR_WhisperX.py returns >= 2 (comment + usage)
    - _HALLUCINATION_PATTERNS set is UNCHANGED (same count as before)
    - Filters use .get() with safe fallback: no_speech_prob default 0.0, compression_ratio default 999.0
  </acceptance_criteria>

  <done>ASR_WhisperX.py: statistical filters added; syntax OK; patterns unchanged.</done>
</task>

<task type="auto">
  <name>Task 5: compose.yaml — update vad_onset default to 0.2</name>

  <read_first>
    compose.yaml — grep "ADAM_ASR_VAD_ONSET" to find exact current line
  </read_first>

  <files>compose.yaml</files>

  <action>
    In compose.yaml, section adam-asr-whisperx environment:

    Change the default for ADAM_ASR_VAD_ONSET from 0.1 to 0.2:
      ADAM_ASR_VAD_ONSET: ${ADAM_ASR_VAD_ONSET:-0.1}
    becomes:
      ADAM_ASR_VAD_ONSET: ${ADAM_ASR_VAD_ONSET:-0.2}

    This is an env var default — the Docker container reads it at startup and passes it
    to whisperx.load_model() via vad_options. Change requires container RESTART (not rebuild)
    to take effect. The rebuild needed for ASR_WhisperX.py code changes will pick this up.

    No other compose.yaml changes.
  </action>

  <verify>
    <automated>grep "ADAM_ASR_VAD_ONSET" compose.yaml</automated>
  </verify>

  <acceptance_criteria>
    - grep "ADAM_ASR_VAD_ONSET" compose.yaml returns exactly:
      ADAM_ASR_VAD_ONSET: ${ADAM_ASR_VAD_ONSET:-0.2}
    - No other compose.yaml lines changed
  </acceptance_criteria>

  <done>compose.yaml vad_onset default updated to 0.2.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 6: Docker rebuild + restart ASR container</name>

  <what-built>
    Code changes completed:
    - Config.json: vad_onset=0.2, asr_pre_send_min_rms=200
    - System/adam/asr_filter.py: is_hallucination() module
    - System/Orchestrator.py: RMS gate + second-tier pattern guard
    - System/Speech/ASR_WhisperX.py: no_speech_prob + compression_ratio filters
    - compose.yaml: ADAM_ASR_VAD_ONSET default 0.2

    Docker container still runs old ASR_WhisperX.py. Rebuild required to activate:
    - no_speech_prob/compression_ratio filters (code change)
    - vad_onset=0.2 (env var change)
  </what-built>

  <how-to-verify>
    Step 1 — Rebuild the ASR container:
      docker compose build adam-asr-whisperx

    Step 2 — Restart with new env vars:
      docker compose up -d adam-asr-whisperx

    Step 3 — Wait ~60s for model load, check health:
      curl --noproxy '*' http://127.0.0.1:8095/health

    Step 4 — Restart orchestrator to pick up Config.json changes:
      sudo systemctl restart adam-orchestrator.service
      (or: PYTHONPATH=System python System/Orchestrator.py in maintenance mode)

    Step 5 — Verify second-tier guard via API (bypasses ASR, tests orchestrator filter):
      curl --noproxy '*' -X POST http://127.0.0.1:8080/api/agent/turn \
        -H 'Content-Type: application/json' \
        -d '{"transcript":"Спасибо за внимание."}'
      Expected: no Adam dialogue response, asr_hallucination_filtered in events.jsonl

    Step 6 — Live voice test: speak a short command from distance, verify no hallucinations.
  </how-to-verify>

  <resume-signal>
    Type "approved" after:
    - docker compose build exited 0
    - curl /health returns {"status": "ok"}
    - /api/agent/turn "Спасибо за внимание." produces no Adam response
    OR describe any issues encountered.
  </resume-signal>
</task>

</tasks>

<threat_model>
## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-34w2-01 | DoS | asr_pre_send_min_rms gate | accept | gate drops silent frames, not real speech; conservative default 200 |
| T-34w2-02 | Tampering | no_speech_prob filter | accept | safe .get() fallbacks ensure filter never fires on absent field |
| T-34w2-03 | Repudiation | asr_hallucination_filtered event | mitigate | raw text logged in events.jsonl with turn context |
| T-34w2-04 | False positive | vad_onset 0.1→0.2 | accept | 0.2 tested stable; brief commands ("да") confirmed captured at 0.2 vs 0.3 not |
</threat_model>

<verification>
After all tasks complete (before Docker rebuild):

1. Config: python3 -c "import json; c=json.load(open('System/Config.json')); assert c['services']['asr']['vad_onset']==0.2; assert c['services']['asr']['asr_pre_send_min_rms']==200; print('Config OK')"
2. asr_filter: PYTHONPATH=System python3 -c "from adam.asr_filter import is_hallucination; assert is_hallucination('Спасибо за внимание.'); assert not is_hallucination('Привет'); print('asr_filter OK')"
3. Orchestrator: python3 -c "import ast; ast.parse(open('System/Orchestrator.py').read()); print('syntax OK')" && grep -c "asr_skipped_silent" System/Orchestrator.py && grep -c "asr_hallucination_filtered" System/Orchestrator.py
4. ASR: python3 -c "import ast; ast.parse(open('System/Speech/ASR_WhisperX.py').read()); print('syntax OK')" && grep "no_speech_prob" System/Speech/ASR_WhisperX.py
5. compose.yaml: grep "ADAM_ASR_VAD_ONSET" compose.yaml
</verification>

<success_criteria>
- Config.json vad_onset = 0.2 (root cause fix)
- Config.json asr_pre_send_min_rms = 200
- System/adam/asr_filter.py exists with is_hallucination() using CURRENT patterns (not expanded)
- Orchestrator RMS gate: silent audio skipped before ASR call, emits asr_skipped_silent
- Orchestrator pattern guard: _is_hallucination(transcript) check after empty-check,
  emits asr_hallucination_filtered, returns False
- ASR_WhisperX.py: no_speech_prob >= 0.85 → segment discarded (safe fallback if absent)
- ASR_WhisperX.py: compression_ratio <= 1.1 → segment discarded (safe fallback if absent)
- _HALLUCINATION_PATTERNS in ASR_WhisperX.py unchanged (not expanded)
- compose.yaml ADAM_ASR_VAD_ONSET default = 0.2
- Docker container rebuilt, healthy, vad_onset=0.2 active
- POST /api/agent/turn "Спасибо за внимание." → no Adam response, event logged
</success_criteria>

<output>
After completion, create `.planning/phases/34-asr-quality-fixes/34-02-SUMMARY.md` with:
- What changed in each of the 5 files
- Verification results (all checks from <verification> section)
- Docker rebuild result and health check
- Any deviations from the plan
</output>
