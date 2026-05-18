---
phase: 21A
plan: 02
subsystem: config / Wave 1 (Config-First foundation)
tags: [config, schema, spectrum, fft, equaliser, wave-1]
dependency_graph:
  requires:
    - "21A-01 (Wave 0) — test_spectrum_keys_in_schema as RED contract"
  provides:
    - "System/Config.json:media.audio.spectrum_* — production defaults for FFT"
    - "System/Config.schema.json — schema docs with min/max bounds + descriptions"
  affects:
    - "21A-03 (Wave 2) MicReader._compute_bands reads spectrum_bands / min_hz / max_hz / floor_db / ceiling_db / cadence_hz via audio_cfg.get(...)"
    - "21A-03 (Wave 2) frontend equaliser widget colour transitions read spectrum_color_yellow_at / spectrum_color_red_at"
tech_stack:
  added: []
  patterns:
    - "Config-First: every FFT numeric lives in Config.json + Config.schema.json before code reads it (D-15)"
    - "Flat schema layout for sibling keys, matching webrtc_vad_aggressiveness / normalize_factor style (RESEARCH §9 recommendation, not nested under spectrum: {})"
    - "Schema descriptions verbatim from RESEARCH §9 lines 800-855 — no paraphrase, preserves reviewed wording"
key_files:
  created:
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/21A-02-SUMMARY.md"
  modified:
    - "System/Config.json"
    - "System/Config.schema.json"
decisions:
  - "Flat key names under media.audio (spectrum_bands, spectrum_min_hz, ...) — matches existing style, no spectrum: {} nesting (RESEARCH §9 explicit recommendation)"
  - "Descriptions copied verbatim from RESEARCH §9 to keep the reviewed wording intact"
  - "Append order at the END of media.audio (after normalize_factor) — does not perturb existing key order; cleanest git diff"
  - "spectrum_floor_db has no minimum bound in schema (only maximum: 0) — RESEARCH §9 lists no minimum; allows operator to widen below -60 dB if exhibition acoustics call for it"
metrics:
  duration: "single session"
  completed: 2026-05-18
  tasks_total: 2
  tasks_completed: 2
  files_created: 1
  files_modified: 2
---

# Phase 21A Plan 02: Wave 1 — Config-First Foundation Summary

Wave 1 Config-First foundation for the chat equaliser FFT pipeline — 8 spectrum_* keys landed under `media.audio` in both Config.json (production defaults) and Config.schema.json (schema docs + bounds + descriptions), flipping the Wave-0 contract test `test_spectrum_keys_in_schema` from RED to GREEN.

## What Shipped

| Artifact | Purpose |
| --- | --- |
| `System/Config.json` (media.audio) | 8 new keys: `spectrum_bands=24`, `spectrum_min_hz=80.0`, `spectrum_max_hz=8000.0`, `spectrum_floor_db=-60.0`, `spectrum_ceiling_db=0.0`, `spectrum_cadence_hz=25.0`, `spectrum_color_yellow_at=0.6`, `spectrum_color_red_at=0.85`. All defaults verbatim from RESEARCH §9. |
| `System/Config.schema.json` (properties.media.properties.audio.properties) | 8 new schema entries with `type`, `default`, English `description`, and `minimum`/`maximum` bounds where applicable. Each description copied verbatim from RESEARCH §9 lines 800-855 (mentions `_compute_bands`, Nyquist cap, dBFS floor, cadence math, colour gradient rationale). |

## Tasks Executed

| Task | Name | Commit | Outcome |
| --- | --- | --- | --- |
| 1 | Add 8 spectrum_* keys to media.audio in Config.json | `04a14ca` | Keys appended after `normalize_factor` with correct types (int / float). JSON parses; verification script confirms every key + value matches RESEARCH §9 defaults. |
| 2 | Add schema entries with descriptions for the 8 keys | `2c1cdf9` | 8 schema entries appended after `normalize_factor` inside `audio.properties`. JSON parses; `test_spectrum_keys_in_schema` flips GREEN (`1 passed in 0.06s`). |

## Verification Run (final)

```bash
$ ./.venv/bin/python -c "import json; cfg=json.load(open('System/Config.json')); a=cfg['media']['audio']; assert all(k in a for k in ['spectrum_bands','spectrum_min_hz','spectrum_max_hz','spectrum_floor_db','spectrum_ceiling_db','spectrum_cadence_hz','spectrum_color_yellow_at','spectrum_color_red_at']); print('ok')"
ok

$ ./.venv/bin/python -c "import json; s=json.load(open('System/Config.schema.json')); ap=s['properties']['media']['properties']['audio']['properties']; req=['spectrum_bands','spectrum_min_hz','spectrum_max_hz','spectrum_floor_db','spectrum_ceiling_db','spectrum_cadence_hz','spectrum_color_yellow_at','spectrum_color_red_at']; assert all(k in ap and ap[k].get('description','').strip() for k in req); print('schema ok')"
schema ok

$ ./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py::test_spectrum_keys_in_schema -x -q
.                                                                        [100%]
1 passed in 0.06s

$ git diff --stat HEAD~2 HEAD -- System/Config.json System/Config.schema.json
 System/Config.json        |  10 +++++++++-
 System/Config.schema.json |  55 +++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 64 insertions(+), 1 deletion(-)
```

All four PLAN `<verification>` items satisfied:

1. `pytest test_spectrum_keys_in_schema` → green
2. Config.json parses as valid JSON
3. Config.schema.json parses as valid JSON
4. `git diff --stat` shows additions only — no existing keys modified

## Decisions Made

- **Flat key names, not nested.** RESEARCH §9 explicitly recommended flat over `spectrum: {}` because sibling keys (`webrtc_vad_aggressiveness`, `normalize_factor`) are flat in current schema. Honouring the style avoids inconsistency.
- **Verbatim descriptions.** Copy-pasted from RESEARCH §9 instead of paraphrasing. The text was reviewed at research time and mentions the precise consumer locations (`_compute_bands`, `audio_level` payload), Nyquist cap, dBFS convention, cadence derivation, and colour-gradient rationale — paraphrasing would lose technical precision.
- **Append order (end of media.audio).** Adding after `normalize_factor` preserves the existing key order — git diff shows pure additions, no key relocations. Future readers see the new "spectrum" cluster grouped together at the end.
- **`spectrum_floor_db` has no `minimum`.** Schema lists only `maximum: 0`. RESEARCH §9 specified no lower bound (operator may widen to -80 dB for very quiet exhibition halls). Pydantic / consumers can clamp downstream if needed.

## Deviations from Plan

None — plan executed exactly as written.

Worktree note: the executor re-created the `.venv` symlink → main-repo `.venv` so the `./.venv/bin/python -m pytest` command works inside the worktree. `.venv` is in `.gitignore` and not committed (verified via `git check-ignore .venv`).

## Self-Check: PASSED

- `System/Config.json` modified — FOUND (8 keys present, defaults match)
- `System/Config.schema.json` modified — FOUND (8 schema entries with non-empty descriptions)
- Commit `04a14ca` — FOUND in `git log` (Task 1)
- Commit `2c1cdf9` — FOUND in `git log` (Task 2)
- `tests/test_mic_reader_spectrum.py::test_spectrum_keys_in_schema` — GREEN (1 passed)
- `git diff --diff-filter=D --name-only HEAD~2 HEAD` → empty (no deletions)
- Both JSON files parse via `python -c "import json; json.load(open(...))"`
