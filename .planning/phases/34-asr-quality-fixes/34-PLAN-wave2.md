---
phase: 34-asr-quality-fixes
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - System/adam/asr_filter.py
  - System/Speech/ASR_WhisperX.py
  - System/Orchestrator.py
  - compose.yaml
autonomous: false
requirements:
  - REQ-ASR-HALLUCINATION

must_haves:
  truths:
    - "Hallucination 'Спасибо за внимание.' is blocked even if Docker container runs stale ASR_WhisperX.py"
    - "Orchestrator._transcribe_and_dispatch filters hallucinations before passing to dialogue turn"
    - "Hallucination patterns are defined in exactly one place (adam/asr_filter.py) imported by both ASR_WhisperX.py and Orchestrator.py"
    - "A filtered hallucination emits event asr_hallucination_filtered with the raw text"
    - "_HALLUCINATION_PATTERNS in ASR_WhisperX.py is extended with YouTube-subtitle and Whisper-small artefact patterns"
  artifacts:
    - path: "System/adam/asr_filter.py"
      provides: "HALLUCINATION_PATTERNS set + is_hallucination(text) function"
      contains: "is_hallucination"
    - path: "System/Speech/ASR_WhisperX.py"
      provides: "Imports HALLUCINATION_PATTERNS from asr_filter (or keeps own set extended)"
      contains: "спасибо за внимание"
    - path: "System/Orchestrator.py"
      provides: "Second-tier hallucination guard in _transcribe_and_dispatch"
      contains: "asr_hallucination_filtered"
  key_links:
    - from: "System/adam/asr_filter.py"
      to: "System/Speech/ASR_WhisperX.py"
      via: "shared HALLUCINATION_PATTERNS — single source of truth"
      pattern: "from adam\\.asr_filter import|HALLUCINATION_PATTERNS"
    - from: "System/Orchestrator.py (_transcribe_and_dispatch)"
      to: "adam.asr_filter.is_hallucination"
      via: "second-tier filter after ASR service response"
      pattern: "is_hallucination\\(transcript\\)"
---

<objective>
Fix BUG-2: hallucination transcriptions (e.g. "Спасибо за внимание.") reaching the dialogue
turn despite being in _HALLUCINATION_PATTERNS. Root cause A: the Docker ASR container was built
before patterns were added and has not been rebuilt. Root cause B: only one filtering layer.

This plan adds a second tier (orchestrator-side guard) using a shared pattern module, extends
the pattern set with new Whisper-small/Russian artefacts, and adds a Docker rebuild checkpoint.

Purpose: Ensure hallucinations are blocked even when the ASR Docker container is stale, via
defense in depth with a shared canonical pattern list.

Output: System/adam/asr_filter.py (new), updated ASR_WhisperX.py, updated Orchestrator.py,
Docker rebuild checkpoint.
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

<interfaces>
From System/Speech/ASR_WhisperX.py lines 44-57 (current _HALLUCINATION_PATTERNS):

  _HALLUCINATION_PATTERNS = {
      "тревожная музыка", "интригующая музыка", "спокойная музыка",
      "весёлая музыка", "грустная музыка", "музыка",
      "субтитры добавлены", "спасибо за просмотр", "подписывайтесь на канал",
      "продолжение следует", "не забудьте подписаться", "спасибо за внимание",
      "до встречи", "увидимся в следующий раз", "оставайтесь с нами",
      "продолжение в следующей части", "ссылки в описании",
      "[тихая музыка]", "[music]", "[applause]", "[blank_audio]", "[inaudible]",
      "[шум]", "[тишина]", "[нет звука]",
      ".", ",", "...",
  }

From System/Speech/ASR_WhisperX.py lines 196-199 (current filter usage):
  text = seg.get("text", "").strip()
  if text and text.lower().strip("[]().,!? ") not in _HALLUCINATION_PATTERNS:
      parts.append(text)

From System/Orchestrator.py line 1594-1606 (_transcribe_and_dispatch insertion point):
  transcript = (await self.asr_client.transcribe_pcm(pcm)).strip()
  ...
  event_log.append("asr_result", {...})
  if not transcript:
      return False
  # NEW: hallucination guard goes here, after the empty check
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create System/adam/asr_filter.py with shared hallucination pattern set</name>

  <read_first>
    System/Speech/ASR_WhisperX.py lines 44-57 — current _HALLUCINATION_PATTERNS set
    (copy ALL existing patterns verbatim into the new module; do not lose any)
    .planning/phases/34-asr-quality-fixes/34-CONTEXT.md — decisions D-03 and D-04,
    section "Hallucination patterns расширение" (list of new patterns to add)
    System/adam/ directory listing — understand existing module style
    (any existing adam/*.py to match import/export conventions)
  </read_first>

  <files>System/adam/asr_filter.py</files>

  <behavior>
    - is_hallucination("Спасибо за внимание.") returns True
    - is_hallucination("Спасибо за внимание") returns True (no punctuation)
    - is_hallucination("СПАСИБО ЗА ВНИМАНИЕ") returns True (case insensitive)
    - is_hallucination("Как дела?") returns False
    - is_hallucination("") returns False
    - is_hallucination("  ") returns False (whitespace-only)
    - is_hallucination("[музыка]") returns True (bracket marker)
    - is_hallucination("Лайк и подписка.") returns True (new YouTube pattern)
    - is_hallucination("Пока пока!") returns True (new pattern)
    - is_hallucination("Компиция.") returns True (Whisper-small noise artefact)
  </behavior>

  <action>
    Create System/adam/asr_filter.py as a pure Python module with no external dependencies
    (stdlib only — no imports from Orchestrator, settings, or other adam modules).

    The module exports:
    1. HALLUCINATION_PATTERNS: frozenset[str] — canonical set of normalised patterns
       (all lowercase, stripped of surrounding punctuation/brackets — matching the
       normalisation applied before lookup)
    2. is_hallucination(text: str) -> bool — returns True if the text (after normalisation)
       matches any pattern in HALLUCINATION_PATTERNS

    Normalisation function (internal, also used by is_hallucination):
      def _normalise(s: str) -> str:
          return s.lower().strip("[]().,!? \t\n")

    HALLUCINATION_PATTERNS must contain ALL patterns from the current ASR_WhisperX.py
    _HALLUCINATION_PATTERNS PLUS these new patterns from D-03:
    YouTube/attention patterns:
      "лайк и подписка", "колокольчик уведомлений", "смотрите также",
      "следующее видео", "конец видео", "до следующего раза", "пока пока",
      "поставьте лайк", "комментируйте", "поделитесь видео"
    Whisper-small Russian artefacts (near-silence hallucinations):
      "компиция", "цыц", "ля ля ля", "да да", "нет нет",
      "хорошо хорошо", "ок ок"
    Bracket/noise markers (normalised — without brackets, since lookup strips them):
      "музыка", "тихая музыка", "music", "applause", "blank_audio", "inaudible",
      "шум", "тишина", "нет звука", "аплодисменты", "смех"
    Punctuation-only (already present, keep):
      ".", ",", "..."

    Note on duplicate normalisation: the existing patterns in ASR_WhisperX.py are already
    lowercase and stripped in the lookup (text.lower().strip("[]().,!? ")), so store patterns
    in HALLUCINATION_PATTERNS already normalised (lowercase, no surrounding brackets/punctuation).
    The normalise step in is_hallucination mirrors what ASR_WhisperX.py does.

    is_hallucination implementation:
      def is_hallucination(text: str) -> bool:
          if not text or not text.strip():
              return False
          return _normalise(text) in HALLUCINATION_PATTERNS

    The module must be importable standalone:
      python3 -c "from adam.asr_filter import is_hallucination; print(is_hallucination('Спасибо за внимание.'))"
    must print True without importing Orchestrator or settings.
  </action>

  <verify>
    <automated>
cd /home/i17jet/Agents/Adam-Chip && PYTHONPATH=System python3 -c "
from adam.asr_filter import is_hallucination, HALLUCINATION_PATTERNS
tests = [
    ('Спасибо за внимание.', True),
    ('Спасибо за внимание', True),
    ('СПАСИБО ЗА ВНИМАНИЕ', True),
    ('Как дела?', False),
    ('', False),
    ('   ', False),
    ('[музыка]', True),
    ('Лайк и подписка.', True),
    ('Пока пока!', True),
    ('Компиция.', True),
]
failed = [(t, expected, is_hallucination(t)) for t, expected in tests if is_hallucination(t) != expected]
assert not failed, f'Failed: {failed}'
print(f'OK: all {len(tests)} tests pass, {len(HALLUCINATION_PATTERNS)} patterns')
"
    </automated>
  </verify>

  <acceptance_criteria>
    - System/adam/asr_filter.py exists and is importable via PYTHONPATH=System
    - HALLUCINATION_PATTERNS is a frozenset (immutable — no accidental mutation)
    - is_hallucination("Спасибо за внимание.") returns True
    - is_hallucination("Как дела?") returns False
    - is_hallucination("Компиция.") returns True (new pattern)
    - is_hallucination("Лайк и подписка.") returns True (new pattern)
    - All 10 test cases in the verify command above pass
    - Module has no imports outside stdlib (no adam.*, no settings, no fastapi)
  </acceptance_criteria>

  <done>asr_filter.py created; all behavior tests pass; importable standalone.</done>
</task>

<task type="auto">
  <name>Task 2: Wire asr_filter into ASR_WhisperX.py and Orchestrator.py</name>

  <read_first>
    System/adam/asr_filter.py — just created; verify the exports (HALLUCINATION_PATTERNS, is_hallucination)
    System/Speech/ASR_WhisperX.py lines 1-60 — top of file including current _HALLUCINATION_PATTERNS
    definition and imports
    System/Speech/ASR_WhisperX.py lines 183-200 — _transcribe_audio where patterns are used
    System/Orchestrator.py lines 1583-1651 — full _transcribe_and_dispatch function
    (understand the exact insertion point for the second-tier guard)
    System/Dockerfile.asr lines 127-134 — COPY directives (understand what gets into Docker image)
    compose.yaml lines 47-76 — adam-asr-whisperx service definition (volumes, build context)
    .planning/phases/34-asr-quality-fixes/34-CONTEXT.md — D-03 (extend patterns), D-04 (second
    tier), D-05 (Docker rebuild)
  </read_first>

  <files>System/Speech/ASR_WhisperX.py, System/Orchestrator.py</files>

  <action>
    CHANGE A — System/Speech/ASR_WhisperX.py:

    The Dockerfile copies ONLY ASR_WhisperX.py into /app/Speech/ (line 131 of Dockerfile.asr);
    it does not copy System/adam/asr_filter.py. Therefore ASR_WhisperX.py CANNOT import from
    adam.asr_filter at runtime inside Docker. Instead:
    - Keep the _HALLUCINATION_PATTERNS set defined locally in ASR_WhisperX.py
    - EXTEND it with all new patterns from asr_filter.HALLUCINATION_PATTERNS
    - Copy the full merged pattern set into ASR_WhisperX.py's _HALLUCINATION_PATTERNS
    This approach means the Dockerfile rebuild will pick up the extended patterns.

    Replace the existing _HALLUCINATION_PATTERNS set (lines 44-57) with the merged set that
    includes ALL patterns from the new asr_filter.py module. The normalisation is already
    correct in ASR_WhisperX.py (text.lower().strip("[]().,!? ")), so patterns should be stored
    normalised (no surrounding brackets/punctuation). Keep the comment header explaining origin.

    Note: do NOT attempt to import adam.asr_filter in ASR_WhisperX.py — the module is not
    available inside the Docker container without Dockerfile changes. The canonical source is
    asr_filter.py (on the Jetson host); ASR_WhisperX.py keeps a synchronized copy.
    Add a comment at the top of _HALLUCINATION_PATTERNS:
      # Synchronized with System/adam/asr_filter.HALLUCINATION_PATTERNS.
      # When adding patterns: update BOTH files. asr_filter.py is the canonical source.

    CHANGE B — System/Orchestrator.py:

    In _transcribe_and_dispatch, after the `if not transcript: return False` check (approximately
    line 1606) and BEFORE the wake-word strip, add the second-tier hallucination guard:

      from adam.asr_filter import is_hallucination as _is_hallucination
      if _is_hallucination(transcript):
          event_log.append("asr_hallucination_filtered", {
              "raw": transcript[:120],
              "utterance_id": self._utterance_id,
          }, turn_id=turn_id)
          return False

    Place the import at the top of Orchestrator.py (with other adam.* imports) rather than
    inside the function. Add to the existing block of `from adam.*` imports. The function
    should use the already-imported name directly:

    At the top of Orchestrator.py, find the block of `from adam.` imports and add:
      from adam.asr_filter import is_hallucination as _is_hallucination

    In _transcribe_and_dispatch, after `if not transcript: return False` add:
      if _is_hallucination(transcript):
          event_log.append("asr_hallucination_filtered", {
              "raw": transcript[:120],
              "utterance_id": self._utterance_id,
          }, turn_id=turn_id)
          return False

    This guard fires even if ASR_WhisperX.py is running stale Docker code and passes through
    the hallucination — defense in depth per D-04.

    Verify Orchestrator.py syntax after edits.
  </action>

  <verify>
    <automated>
cd /home/i17jet/Agents/Adam-Chip && python3 -c "import ast, sys; ast.parse(open('System/Orchestrator.py').read()); print('Orchestrator syntax OK')" && python3 -c "import ast; ast.parse(open('System/Speech/ASR_WhisperX.py').read()); print('ASR_WhisperX syntax OK')" && PYTHONPATH=System python3 -c "from adam.asr_filter import is_hallucination; print('import OK')" && grep -c "asr_hallucination_filtered" System/Orchestrator.py && grep -c "_is_hallucination" System/Orchestrator.py
    </automated>
  </verify>

  <acceptance_criteria>
    - System/Orchestrator.py: python3 ast.parse passes (no syntax errors)
    - System/Speech/ASR_WhisperX.py: python3 ast.parse passes
    - grep "asr_hallucination_filtered" System/Orchestrator.py returns >= 1 match
    - grep "_is_hallucination" System/Orchestrator.py returns >= 2 matches (import + usage)
    - grep "спасибо за внимание" System/Speech/ASR_WhisperX.py returns 1 match (pattern present)
    - grep "компиция" System/Speech/ASR_WhisperX.py returns 1 match (new pattern present)
    - grep "лайк и подписка" System/Speech/ASR_WhisperX.py returns 1 match (new pattern)
    - grep "Synchronized with System/adam/asr_filter" System/Speech/ASR_WhisperX.py returns 1 match
    - The hallucination guard in _transcribe_and_dispatch appears AFTER the empty-check
      and BEFORE the wake-word strip (_wake_re.sub call)
    - No import of adam.asr_filter inside ASR_WhisperX.py (it would fail inside Docker)
  </acceptance_criteria>

  <done>
    Both files pass syntax check; Orchestrator has second-tier guard with event log;
    ASR_WhisperX.py has extended pattern set with sync comment.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Rebuild ASR Docker container and verify hallucination guard in both tiers</name>

  <read_first>
    compose.yaml lines 47-76 — adam-asr-whisperx service (build config, volumes)
    System/Dockerfile.asr lines 127-134 — COPY directives (confirms ASR_WhisperX.py is copied)
  </read_first>

  <what-built>
    Tasks 1 and 2 have:
    - Created System/adam/asr_filter.py with merged hallucination patterns
    - Extended _HALLUCINATION_PATTERNS in ASR_WhisperX.py (with sync comment)
    - Added second-tier is_hallucination guard in Orchestrator._transcribe_and_dispatch
    The Docker container still runs the old ASR_WhisperX.py until rebuilt.
  </what-built>

  <how-to-verify>
    Run the following commands on the Jetson (where Docker is running):

    Step 1 — Rebuild the ASR container to pick up extended patterns:
      docker compose build adam-asr-whisperx

    Step 2 — Restart the container:
      docker compose up -d adam-asr-whisperx

    Step 3 — Wait ~60 seconds for the model to load, then verify health:
      curl --noproxy '*' http://127.0.0.1:8095/health

    Step 4 — Smoke test first tier (ASR_WhisperX.py inside Docker):
    Send a synthetic near-silence WAV to the ASR service and confirm it does not return
    a hallucination string. (This is hard to force without silence audio; skip if impractical —
    the pattern set change is verifiable via grep above.)

    Step 5 — Verify second tier (Orchestrator) with a live turn test:
    With the Orchestrator running, trigger a voice turn that would previously hallucinate
    (or simulate by checking that the asr_hallucination_filtered event appears in events.jsonl
    when a matching transcript arrives). You can test via:
      curl --noproxy '*' -X POST http://127.0.0.1:8080/api/agent/turn \
        -H 'Content-Type: application/json' \
        -d '{"transcript":"Спасибо за внимание."}'
    Expected: no dialogue turn fires, no Adam response. Check events.jsonl or log viewer
    at http://JETSON_IP:8083 for asr_hallucination_filtered event.

    Note: /api/agent/turn bypasses ASR entirely (transcript is provided directly), so it
    only tests the orchestrator-side guard. That is sufficient to verify D-04.
  </how-to-verify>

  <resume-signal>
    Type "approved" if:
    - Docker rebuild succeeded (docker compose build exited 0)
    - Container is healthy (curl /health returns 200)
    - /api/agent/turn with "Спасибо за внимание." does NOT produce Adam dialogue output
    OR describe any issues encountered.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| ASR service → Orchestrator | Transcript string returned over HTTP; ASR may be stale or bypassed |
| /api/agent/turn HTTP endpoint | External caller can submit arbitrary transcript text |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-34w2-01 | Spoofing | /api/agent/turn | accept | endpoint is on localhost only; no auth required by design for operator use |
| T-34w2-02 | Tampering | asr_filter patterns | accept | frozenset prevents mutation at runtime; patterns updated only via file edit + restart |
| T-34w2-03 | Repudiation | asr_hallucination_filtered event | mitigate | event logged with raw text and utterance_id in events.jsonl for audit trail |
| T-34w2-04 | Elevation of Privilege | hallucination bypass | mitigate | defense-in-depth: two independent filter tiers (ASR_WhisperX + Orchestrator) reduce bypass probability to near-zero |
</threat_model>

<verification>
After all three tasks complete:

1. Pattern coverage: PYTHONPATH=System python3 -c "from adam.asr_filter import is_hallucination; assert is_hallucination('Спасибо за внимание.'); assert is_hallucination('Компиция.'); assert not is_hallucination('Привет'); print('OK')"
2. Orchestrator guard present: grep "asr_hallucination_filtered" System/Orchestrator.py | wc -l  (expect 1)
3. Syntax clean: python3 -c "import ast; [ast.parse(open(f).read()) for f in ['System/Orchestrator.py','System/Speech/ASR_WhisperX.py','System/adam/asr_filter.py']]; print('all syntax OK')"
4. Docker health: curl --noproxy '*' http://127.0.0.1:8095/health (after rebuild)
5. API test: POST /api/agent/turn {"transcript":"Спасибо за внимание."} → no Adam response, asr_hallucination_filtered in events.jsonl
</verification>

<success_criteria>
- System/adam/asr_filter.py exists with HALLUCINATION_PATTERNS (frozenset) and is_hallucination()
- All 10 is_hallucination() behavior tests pass
- ASR_WhisperX.py _HALLUCINATION_PATTERNS extended with new patterns + sync comment
- Orchestrator._transcribe_and_dispatch has second-tier is_hallucination guard
- Guard emits asr_hallucination_filtered event with raw text and utterance_id
- Guard fires AFTER empty-check, BEFORE wake-word strip
- Docker container rebuilt and healthy
- POST /api/agent/turn with "Спасибо за внимание." does not produce dialogue output
</success_criteria>

<output>
After completion, create `.planning/phases/34-asr-quality-fixes/34-02-SUMMARY.md` with:
- What changed: asr_filter.py, ASR_WhisperX.py patterns, Orchestrator guard
- Docker rebuild result
- Any deviations from the plan
</output>
