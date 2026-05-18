---
phase: 21A
plan: 04
type: execute
wave: 2
depends_on: [01, 02]
files_modified:
  - System/Config.json
  - System/Config.schema.json
  - System/adam/events.py
autonomous: true
requirements:
  - UI-EQ-02
must_haves:
  truths:
    - "events.jsonl no longer grows 2.5× faster after Phase 21A cadence bump — high-frequency event types are sampled writing-side"
    - "SSE broadcast cadence is UNCHANGED — frontend still receives 25 Hz audio_level events"
    - "Only the writing path to data/adam/events.jsonl is throttled; in-memory _recent deque and SSE subscribers see every event"
    - "Sampling is Config-driven (media.audio.events_jsonl_sample_audio_level) — operator can revert to 1:1 logging without code change"
  artifacts:
    - path: "System/adam/events.py"
      provides: "Writing-side sampler for high-frequency audio_level events"
      contains: "events_jsonl_sample_audio_level"
    - path: "System/Config.json"
      provides: "Config key media.audio.events_jsonl_sample_audio_level (default 5 = write every 5th)"
      contains: "events_jsonl_sample_audio_level"
  key_links:
    - from: "System/adam/events.py::EventLog.append"
      to: "data/adam/events.jsonl"
      via: "conditional write based on per-type counter"
      pattern: "events_jsonl_sample_audio_level"
---

<objective>
Mitigate the events.jsonl growth concern flagged by RESEARCH §5/§12 and acknowledged in CONTEXT D-04. The current 417 MB file grows ~36 MB/hour from audio_level alone after Phase 21A's 25 Hz cadence + bands[24] payload. Add a writing-side sampler so that only every Nth audio_level event is appended to disk (default N=5 → effective on-disk cadence 5 Hz). SSE subscribers and the in-memory recent-events deque continue to see every event — the UI keeps its 25 Hz responsiveness.

Purpose: Phase 21A must not ship on top of an already-failing logging substrate without flagging. RESEARCH §12 strong recommendation. This is the cleaner option of the two RESEARCH proposed (vs. full log rotation, which is out of scope and belongs in a separate backlog phase).
Output: One Config key + schema entry + small change in events.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-CONTEXT.md
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-RESEARCH.md
@System/adam/events.py
@System/Config.json
@System/Config.schema.json
@System/adam/CLAUDE.md

<interfaces>
The current EventLog.append() (events.py:32-48 per RESEARCH §5):
  - Opens data/adam/events.jsonl in append mode every event
  - Writes one JSON line per call
  - Has NO rotation, NO sampling
  - Also enqueues to SSE subscribers via _enqueue (events.py:99-111)
  - Also appends to in-memory _recent deque

The sampler must:
  1. Read a per-instance counter map: dict[str, int] keyed by event type
  2. Increment the counter for each event of a high-frequency type
  3. Write to the file ONLY when counter % N == 0 (i.e., 1 of N)
  4. SSE broadcast (_enqueue) and _recent deque continue UNCONDITIONALLY for all events
  5. The set of "high-frequency types" is parameterised; for v1 it is {"audio_level"} only

Config-key naming:
  media.audio.events_jsonl_sample_audio_level (integer)
    1 = write every audio_level (legacy behavior; back-out switch)
    5 = write every 5th (default — reduces disk pressure to ~7 MB/hour with bands[24])
    25 = write every 25th (effectively 1 Hz on disk; maximum compression)

Where the Config key is read:
  events.py initialiser (or EventLog construction site) reads the value via Settings.load() OR receives it through a dependency-injected dict. Pick the path that matches the existing wiring — see how EventLog is currently constructed in Orchestrator.py to choose.

If Settings.load() must be called inside events.py (which is on the System/adam/ boundary), guard it: in tests/no-config scenarios fall back to default 1 (no sampling). This keeps unit tests of EventLog working without a Config.json on the test path.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Add Config key events_jsonl_sample_audio_level + schema entry</name>
  <read_first>
    - System/Config.json (the new media.audio block from Plan 02 — append AFTER spectrum_color_red_at)
    - System/Config.schema.json (properties.media.properties.audio.properties — append AFTER spectrum_color_red_at schema entry from Plan 02)
    - 21A-RESEARCH.md §5 (events.jsonl growth math) and §12 (recommendation)
  </read_first>
  <files>System/Config.json, System/Config.schema.json</files>
  <behavior>
    Both files contain a new key media.audio.events_jsonl_sample_audio_level. Default value 5. Schema description explains the trade-off (disk pressure vs. forensic completeness) and that SSE cadence is unaffected.
  </behavior>
  <action>
    1. In System/Config.json, after the last new key from Plan 02 (`spectrum_color_red_at`), add:
       `"events_jsonl_sample_audio_level": 5`
       Update the preceding line to add the required trailing comma after `spectrum_color_red_at`'s value.

    2. In System/Config.schema.json, under properties.media.properties.audio.properties, AFTER the spectrum_color_red_at entry from Plan 02, add a new property entry for events_jsonl_sample_audio_level with:
       - type: integer
       - minimum: 1
       - maximum: 100
       - default: 5
       - description: full English sentence explaining: writing-side sampler for high-frequency audio_level events in data/adam/events.jsonl; N means "write every Nth event"; SSE subscribers and in-memory recent-events deque are NOT affected (frontend cadence unchanged); 1 reverts to legacy 1:1 logging; 5 is the production default reducing disk pressure to ~7 MB/hour at 25 Hz cadence with bands[24] payload.

    Validate both files parse as JSON after edit.
  </action>
  <verify>
    <automated>./.venv/bin/python -c "import json; cfg=json.load(open('System/Config.json')); assert cfg['media']['audio']['events_jsonl_sample_audio_level']==5, 'wrong default'; s=json.load(open('System/Config.schema.json')); e=s['properties']['media']['properties']['audio']['properties']['events_jsonl_sample_audio_level']; assert e['type']=='integer' and e['default']==5 and len(e.get('description','').strip())>40; print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `python -c "import json; json.load(open('System/Config.json'))"` exits 0
    - `python -c "import json; json.load(open('System/Config.schema.json'))"` exits 0
    - `cfg['media']['audio']['events_jsonl_sample_audio_level'] == 5` (verified by script above)
    - Schema entry has type=integer, default=5, description &gt; 40 chars (verified by script above)
  </acceptance_criteria>
  <done>Config key + schema entry added; defaults match RESEARCH recommendation.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Add writing-side sampler to EventLog.append in System/adam/events.py</name>
  <read_first>
    - System/adam/events.py entire file — locate EventLog class, __init__, append(), _enqueue(), _recent deque
    - 21A-RESEARCH.md §5 "events.jsonl rotation behavior — ABSENT" and §12 "Cadence × jsonl growth"
    - System/Orchestrator.py — search for `EventLog(` to find the construction site; note what audio_cfg or settings dict is passed
    - System/adam/CLAUDE.md rule on Config access
  </read_first>
  <files>System/adam/events.py</files>
  <behavior>
    - EventLog gains a `_jsonl_sample_audio_level` integer attribute (default 1; populated from audio_cfg.get("events_jsonl_sample_audio_level", 1) at construction)
    - EventLog gains a `_jsonl_write_counters: dict[str, int]` mapping event type → count (initialised empty or with "audio_level": 0)
    - In append(): every call still appends to _recent and _enqueues to SSE subscribers (UNCHANGED). The file write is now conditional:
        if event.type == "audio_level":
            self._jsonl_write_counters["audio_level"] += 1
            if self._jsonl_write_counters["audio_level"] % self._jsonl_sample_audio_level != 0:
                return  # skip disk write
        # else, or when divisible, proceed to existing file-write code
    - Construction-site change: Orchestrator (or whichever module builds EventLog) passes audio_cfg or settings.section("media").get("audio", {}) so events_jsonl_sample_audio_level is available. If EventLog currently has no kwargs, add `audio_cfg: dict | None = None` to __init__ with a default of None (no sampling).
    - If audio_cfg is None at __init__, default to 1 (no sampling). This keeps legacy callers and tests working.
  </behavior>
  <action>
    1. Read EventLog.__init__ in events.py. Add an optional `audio_cfg: dict | None = None` parameter (keyword-only is fine). Inside __init__:
         self._jsonl_sample_audio_level = max(1, int((audio_cfg or {}).get("events_jsonl_sample_audio_level", 1)))
         self._jsonl_write_counters: dict[str, int] = {}

    2. In EventLog.append (events.py:32-48), at the TOP of the function (before any file-open / write), add the sampler:
         if event.type == "audio_level" and self._jsonl_sample_audio_level &gt; 1:
             c = self._jsonl_write_counters.get("audio_level", 0) + 1
             self._jsonl_write_counters["audio_level"] = c
             skip_file_write = (c % self._jsonl_sample_audio_level) != 0
         else:
             skip_file_write = False

       Then guard the existing file-write block: `if not skip_file_write: <existing file-open + write code>`.

       Do NOT guard the _enqueue / _recent paths — they MUST run unconditionally. Verify their position in the function and place the file-write guard correctly around just the disk-IO lines.

    3. Open System/Orchestrator.py (or wherever `EventLog(` is constructed) and update the call to pass audio_cfg:
         event_log = EventLog(..., audio_cfg=settings.section("media").get("audio", {}))
       If multiple construction sites exist, update all. If the construction is in a place where `settings` is not easily reachable, fall back to: `audio_cfg=cfg.get("media", {}).get("audio", {})` using whatever Config handle is in scope.

    4. Add a one-line emit when a real disk write is skipped, but ONLY at high counter values to avoid recursion (or, simpler: do NOT emit — comment in the code explains the silent-skip is intentional). Choose silent-skip; spam-free.

    5. Add the new instance attributes to any type stubs / dataclass fields if present. If EventLog is a plain class, no extra work.

    6. Run the full test suite to verify no regression. If EventLog has existing tests, they should pass (default = 1, no sampling).
  </action>
  <verify>
    <automated>./.venv/bin/python -m pytest tests/ -x -q &amp;&amp; ./.venv/bin/python -c "from System.adam.events import EventLog; el = EventLog.__init__; import inspect; sig=inspect.signature(el); assert 'audio_cfg' in sig.parameters, f'audio_cfg kwarg missing from EventLog.__init__: {sig}'; print('signature ok:', sig)" &amp;&amp; grep -nE "_jsonl_sample_audio_level" System/adam/events.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "events_jsonl_sample_audio_level" System/adam/events.py` returns at least one match (config-key read)
    - `grep -nE "_jsonl_write_counters" System/adam/events.py` returns at least one match (counter map)
    - EventLog.__init__ signature contains a parameter named `audio_cfg` (verified by inspect)
    - `pytest tests/ -x -q` exits 0 (no regression to existing event-bus / memory tests)
    - Manual probe (post-Plan 03): launch Orchestrator, tail data/adam/events.jsonl for 10 seconds, count audio_level lines — should be ~50 (not ~250) at default sampling=5
    - SSE-side cadence unchanged: `curl --noproxy '*' -N -fsS http://127.0.0.1:8080/api/agent/stream | grep --line-buffered audio_level | head -100` shows ~25 events/sec (verified during Plan 07 smoke test)
  </acceptance_criteria>
  <done>Sampler integrated; default 5:1 disk-write throttle; SSE cadence preserved; no regression to existing tests.</done>
</task>

</tasks>

<verification>
- `./.venv/bin/python -m pytest tests/ -x -q` exits 0
- Config and schema files valid JSON
- EventLog.__init__ has audio_cfg keyword parameter
- audio_level write path is guarded by counter modulo check
- _enqueue and _recent paths remain unconditional (SSE + in-memory cadence preserved)
</verification>

<success_criteria>
- events.jsonl growth concern from RESEARCH §5/§12 mitigated within Phase 21A scope
- Operator can disable sampling (set to 1) without code change
- No regression to existing event bus consumers (UI dashboards, log viewer, /api/agent/events endpoint)
</success_criteria>

<output>
After completion, create `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-04-SUMMARY.md`
</output>
