---
phase: 21A
plan: 02
type: execute
wave: 1
depends_on: [01]
files_modified:
  - System/Config.json
  - System/Config.schema.json
autonomous: true
requirements:
  - UI-EQ-06
must_haves:
  truths:
    - "8 new spectrum_* keys exist in System/Config.json under media.audio"
    - "8 new spectrum_* keys documented in System/Config.schema.json with non-empty descriptions"
    - "Default values match RESEARCH.md §9 exactly (24, 80, 8000, -60, 0, 25, 0.6, 0.85)"
    - "test_spectrum_keys_in_schema passes after this plan"
  artifacts:
    - path: "System/Config.json"
      provides: "Production spectrum_* defaults"
      contains: "spectrum_bands.*24"
    - path: "System/Config.schema.json"
      provides: "Schema documentation for new keys"
      contains: "spectrum_color_yellow_at"
  key_links:
    - from: "System/Config.json#media.audio.spectrum_bands"
      to: "System/Config.schema.json#properties.media.properties.audio.properties.spectrum_bands"
      via: "schema-validated config key"
      pattern: "spectrum_bands.*default.*24"
---

<objective>
Add 8 spectrum_* keys to media.audio in Config.json AND document each with default + description in Config.schema.json. This is the Config-First foundation Plan 03 (MicReader FFT) reads via `audio_cfg.get(...)`.

Purpose: D-15 mandates all FFT numerics live in Config.json. D-16 requires hot-reload, which is only meaningful if keys are present in the file at startup.
Output: Two files patched, schema test goes green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-CONTEXT.md
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-RESEARCH.md
@System/Config.json
@System/Config.schema.json
@CLAUDE.md
@System/adam/CLAUDE.md

<interfaces>
<!-- Schema additions go under properties.media.properties.audio.properties. -->
<!-- Sibling keys for reference: normalize_factor, webrtc_vad_aggressiveness, max_command_segment_ms. -->
<!-- Schema description style: English, full sentences, mention the consumer location and default rationale. -->

Required key set (exact names, exact defaults, all under media.audio):

  spectrum_bands:           integer 24   (min 4, max 128)
  spectrum_min_hz:          number  80.0 (min 20, max 8000)
  spectrum_max_hz:          number  8000.0 (min 1000, max 8000)
  spectrum_floor_db:        number  -60.0 (max 0)
  spectrum_ceiling_db:      number  0.0 (min -20, max 0)
  spectrum_cadence_hz:      number  25.0 (min 5, max 50)
  spectrum_color_yellow_at: number  0.6 (min 0.0, max 1.0)
  spectrum_color_red_at:    number  0.85 (min 0.0, max 1.0)

Schema descriptions: copy verbatim from RESEARCH.md §9 "Config.schema.json descriptions" (lines ~800-855 of RESEARCH.md). Keep them in English.

Insertion order in Config.json: append the 8 keys to the END of the media.audio object (after `normalize_factor`), preserving existing key order. Use 2-space indentation matching the surrounding style.

Insertion order in Config.schema.json: append under `properties.media.properties.audio.properties`, after the last existing audio key (likely `normalize_factor` or the last alphabetical entry — DO NOT reorder existing keys).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Add 8 spectrum_* keys to System/Config.json under media.audio</name>
  <read_first>
    - System/Config.json lines 20-65 (full media.audio block, ending at normalize_factor)
    - 21A-CONTEXT.md decisions D-05 through D-11
    - 21A-RESEARCH.md §9 "Config Code shape" — the literal default values
  </read_first>
  <files>System/Config.json</files>
  <behavior>
    After patch, media.audio contains all original keys unchanged + 8 new keys with the exact defaults from <interfaces>. JSON parses successfully. No keys reordered. No trailing comma errors.
  </behavior>
  <action>
    Use Edit tool. Locate the line `"normalize_factor": 8000` inside the `media.audio` object (currently the LAST key). Replace it with:

      `"normalize_factor": 8000,`
      followed by 8 new key-value lines, in this order:
        - `"spectrum_bands": 24,`
        - `"spectrum_min_hz": 80.0,`
        - `"spectrum_max_hz": 8000.0,`
        - `"spectrum_floor_db": -60.0,`
        - `"spectrum_ceiling_db": 0.0,`
        - `"spectrum_cadence_hz": 25.0,`
        - `"spectrum_color_yellow_at": 0.6,`
        - `"spectrum_color_red_at": 0.85`   ← NO trailing comma; this is the new last key

    Use the same indentation as the surrounding lines (look at the existing block — likely 6 spaces per indent level for media.audio properties).

    Do NOT touch any other section of Config.json.

    After editing, validate JSON: `./.venv/bin/python -c "import json; json.load(open('System/Config.json'))"` must exit 0.
  </action>
  <verify>
    <automated>./.venv/bin/python -c "import json; cfg=json.load(open('System/Config.json')); a=cfg['media']['audio']; missing=[k for k in ['spectrum_bands','spectrum_min_hz','spectrum_max_hz','spectrum_floor_db','spectrum_ceiling_db','spectrum_cadence_hz','spectrum_color_yellow_at','spectrum_color_red_at'] if k not in a]; assert not missing, f'missing keys: {missing}'; assert a['spectrum_bands']==24 and a['spectrum_min_hz']==80.0 and a['spectrum_max_hz']==8000.0 and a['spectrum_floor_db']==-60.0 and a['spectrum_ceiling_db']==0.0 and a['spectrum_cadence_hz']==25.0 and a['spectrum_color_yellow_at']==0.6 and a['spectrum_color_red_at']==0.85, 'wrong defaults'; print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `python -c "import json; json.load(open('System/Config.json'))"` exits 0 (valid JSON)
    - All 8 keys exist in media.audio with exact values listed above (script verifies)
    - Pre-existing keys (sample_rate=16000, frame_ms=20, normalize_factor=8000, etc.) unchanged — verify by `git diff --stat System/Config.json` shows only the additions, OR by re-parsing and asserting the original key set is a subset
    - File ends with a single newline (no `\r\n`, no trailing whitespace)
  </acceptance_criteria>
  <done>Config.json contains all 8 spectrum_* keys with documented defaults; JSON parses; no existing keys mutated.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Add schema entries for the 8 new keys in System/Config.schema.json</name>
  <read_first>
    - System/Config.schema.json — find the `properties.media.properties.audio.properties` block. Look for the existing `normalize_factor` entry as the insertion anchor.
    - 21A-RESEARCH.md §9 lines ~800-855 — copy descriptions verbatim
    - 21A-CONTEXT.md D-15 — Config-First mandate
  </read_first>
  <files>System/Config.schema.json</files>
  <behavior>
    Schema file remains valid JSON. Each new key under `properties.media.properties.audio.properties` has: type, default, description, and (where applicable) minimum/maximum. Descriptions are non-empty English sentences referencing _compute_bands or the equaliser widget.
  </behavior>
  <action>
    Locate `properties.media.properties.audio.properties` block. Find the LAST audio property entry (likely `normalize_factor`). Insert the 8 new property entries immediately AFTER it, before the closing `}` of the `audio.properties` object.

    Each entry follows this exact shape (use values from RESEARCH.md §9):

      `"spectrum_bands"`: type=integer, minimum=4, maximum=128, default=24, description per RESEARCH §9 (mentions _compute_bands and 24-band default)
      `"spectrum_min_hz"`: type=number, minimum=20, maximum=8000, default=80.0, description mentions male speech fundamental
      `"spectrum_max_hz"`: type=number, minimum=1000, maximum=8000, default=8000.0, description mentions Nyquist cap
      `"spectrum_floor_db"`: type=number, maximum=0, default=-60.0, description mentions noise floor / bar height 0
      `"spectrum_ceiling_db"`: type=number, minimum=-20, maximum=0, default=0.0, description mentions digital full scale / solid red
      `"spectrum_cadence_hz"`: type=number, minimum=5, maximum=50, default=25.0, description mentions per-Nth-frame derivation and 10 KB/s budget
      `"spectrum_color_yellow_at"`: type=number, minimum=0.0, maximum=1.0, default=0.6, description mentions colour transition green→yellow
      `"spectrum_color_red_at"`: type=number, minimum=0.0, maximum=1.0, default=0.85, description mentions clipping/peak visual cue

    Copy each description text VERBATIM from RESEARCH.md §9 (lines ~800-855). Do NOT paraphrase — these have been reviewed in research.

    Preserve trailing-comma rules: the new LAST audio property must NOT have a trailing comma if it precedes the closing `}` of audio.properties. The PRIOR last entry (`normalize_factor`) must gain a trailing comma when new entries follow.

    After editing, validate: `./.venv/bin/python -c "import json; json.load(open('System/Config.schema.json'))"` exits 0.
  </action>
  <verify>
    <automated>./.venv/bin/python -c "import json; s=json.load(open('System/Config.schema.json')); ap=s['properties']['media']['properties']['audio']['properties']; req=['spectrum_bands','spectrum_min_hz','spectrum_max_hz','spectrum_floor_db','spectrum_ceiling_db','spectrum_cadence_hz','spectrum_color_yellow_at','spectrum_color_red_at']; missing=[k for k in req if k not in ap]; assert not missing, f'missing schema keys: {missing}'; empty=[k for k in req if not ap[k].get('description','').strip()]; assert not empty, f'empty descriptions: {empty}'; assert ap['spectrum_bands']['default']==24 and ap['spectrum_min_hz']['default']==80.0; print('schema ok')" && ./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py::test_spectrum_keys_in_schema -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `python -c "import json; json.load(open('System/Config.schema.json'))"` exits 0
    - All 8 keys present under properties.media.properties.audio.properties (script verifies)
    - Every new key has a non-empty `description` field (script verifies via stripping)
    - `pytest tests/test_mic_reader_spectrum.py::test_spectrum_keys_in_schema -x -q` exits 0 (this previously-failing Wave-0 stub now passes)
    - Existing audio schema entries untouched: `git diff` on Config.schema.json should show only additions in the audio.properties block
  </acceptance_criteria>
  <done>Schema valid, all 8 spectrum_* keys documented with descriptions matching RESEARCH §9, Wave-0 schema test goes green.</done>
</task>

</tasks>

<verification>
- `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py::test_spectrum_keys_in_schema -x -q` exits 0
- Both Config.json AND Config.schema.json parse as valid JSON
- No existing keys were modified — verify via `git diff --unified=0 System/Config.json System/Config.schema.json` showing only added lines
</verification>

<success_criteria>
- UI-EQ-06 partially satisfied: Config-First foundation present
- Plan 03 (MicReader FFT) can now use `audio_cfg.get("spectrum_*", default)` with confidence the keys exist
- Wave 0 schema test green — first green stub of the phase
</success_criteria>

<output>
After completion, create `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-02-SUMMARY.md`
</output>
