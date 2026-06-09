---
phase: 34-asr-quality-fixes
plan: "02"
status: partial
subsystem: ASR / Orchestrator
tags: [asr, hallucination-filter, defense-in-depth, whisper-small]
dependency_graph:
  requires: []
  provides: [asr_filter_module, orchestrator_hallucination_guard]
  affects: [System/adam/asr_filter.py, System/Speech/ASR_WhisperX.py, System/Orchestrator.py]
tech_stack:
  added: [System/adam/asr_filter.py]
  patterns: [defense-in-depth, shared-canonical-pattern-set]
key_files:
  created:
    - System/adam/asr_filter.py
  modified:
    - System/Orchestrator.py
    - System/Speech/ASR_WhisperX.py
decisions:
  - "ASR_WhisperX.py keeps local copy of patterns (no import from adam.asr_filter) — Docker container does not have System/adam/ in COPY directives"
  - "asr_filter.py is declared canonical source; ASR_WhisperX.py has sync comment"
  - "Hallucination guard fires after empty-check, before wake-word strip — correct defense-in-depth position"
metrics:
  completed_date: "2026-06-09T01:03:32Z"
  tasks_completed: 2
  tasks_total: 3
  files_created: 1
  files_modified: 2
---

# Phase 34 Plan 02: Hallucination Guard — Partial Summary (Tasks 1–2)

**One-liner:** Second-tier hallucination guard in Orchestrator + shared canonical pattern module (47 patterns) blocking Whisper artefacts even with stale ASR Docker container.

## Status: PARTIAL — Task 3 (Docker rebuild) pending human action

Tasks 1 and 2 complete and committed. Task 3 requires running `docker compose build adam-asr-whisperx` on the Jetson.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create System/adam/asr_filter.py | 18510c6 | System/adam/asr_filter.py (new, 107 lines) |
| 2 | Wire guard into Orchestrator + sync ASR_WhisperX | 7c6e03f | System/Orchestrator.py, System/Speech/ASR_WhisperX.py |

## What Changed

### Task 1 — System/adam/asr_filter.py (new file)

Pure stdlib module. Exports:
- `HALLUCINATION_PATTERNS: frozenset[str]` — 47 normalised patterns (canonical source)
- `is_hallucination(text: str) -> bool` — case-insensitive, strips brackets/punctuation

Pattern categories:
- YouTube subtitle hallucinations (original 17 patterns from ASR_WhisperX.py)
- Bracket/noise markers (тихая музыка, music, applause, blank_audio, inaudible, аплодисменты, смех)
- Whisper-small Russian artefacts: компиция, цыц, ля ля ля, да да, нет нет, хорошо хорошо, ок ок
- YouTube/attention CTAs: лайк и подписка, колокольчик уведомлений, пока пока, etc.
- Punctuation-only: ".", ",", "..."

All 10 behavior tests pass including: case-insensitive, bracket-stripped, empty/whitespace safe.

### Task 2 — Orchestrator.py

Import added at module top:
```python
from adam.asr_filter import is_hallucination as _is_hallucination
```

Second-tier guard in `_transcribe_and_dispatch` (after empty-check, before wake-word strip):
```python
if _is_hallucination(transcript):
    event_log.append("asr_hallucination_filtered", {
        "raw": transcript[:120],
        "utterance_id": self._utterance_id,
    }, turn_id=turn_id)
    return False
```

Event `asr_hallucination_filtered` provides full audit trail in events.jsonl.

### Task 2 — ASR_WhisperX.py

- `_HALLUCINATION_PATTERNS` extended with all new patterns (YouTube CTAs, Whisper artefacts, bracket markers)
- Sync comment added at top of the set pointing to `asr_filter.py` as canonical source
- **No import** of `adam.asr_filter` — Docker container doesn't have `System/adam/` in COPY directives

## Pending: Task 3 (Docker Rebuild)

The ASR Docker container must be rebuilt to pick up the extended `_HALLUCINATION_PATTERNS` in `ASR_WhisperX.py`. Until rebuilt, first-tier filtering inside Docker uses the old pattern set, but the second tier in Orchestrator (just added) already blocks all hallucinations on the host side.

**To complete Task 3 on Jetson:**
```bash
docker compose build adam-asr-whisperx
docker compose up -d adam-asr-whisperx
# Wait ~60s for model to load
curl --noproxy '*' http://127.0.0.1:8095/health

# Verify second-tier guard (orchestrator side):
curl --noproxy '*' -X POST http://127.0.0.1:8080/api/agent/turn \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"Спасибо за внимание."}'
# Expected: no Adam response; check events.jsonl for asr_hallucination_filtered event
```

## Deviations from Plan

None — plan executed exactly as specified. The constraint that ASR_WhisperX.py cannot import from adam.asr_filter (Docker scope) was documented in the plan and handled correctly.

## Self-Check

- [x] System/adam/asr_filter.py exists and importable
- [x] All 10 behavior tests pass (47 patterns)
- [x] Orchestrator.py syntax clean (ast.parse OK)
- [x] ASR_WhisperX.py syntax clean (ast.parse OK)
- [x] `asr_hallucination_filtered` event name present in Orchestrator.py (1 match)
- [x] `_is_hallucination` appears 2 times in Orchestrator.py (import + usage)
- [x] Guard position: after empty-check (line 1629), before wake-word strip (line 1647)
- [x] Sync comment in ASR_WhisperX.py present
- [x] No import of adam.asr_filter in ASR_WhisperX.py

## Self-Check: PASSED
