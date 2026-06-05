---
phase: 21A
plan: 07
subsystem: Phase 21A smoke / human-verify checkpoint
tags: [smoke-test, verification, checkpoint, manual]
dependency_graph:
  requires:
    - "21A-03 (Wave 2): backend FFT pipeline"
    - "21A-04 (Wave 2): events.jsonl sampler"
    - "21A-05 (Wave 3): wakeMeter.js refactor"
    - "21A-06 (Wave 4): host-panel touch-ups"
  provides:
    - "21A-SMOKE-RESULTS.md with per-step PASS/FAIL annotations and final `Smoke Verdict: PASS`"
  affects:
    - "Phase 21A verification (gsd-verifier) input"
    - "Phase 21A ROADMAP closure"
tech_stack:
  added: []
  patterns:
    - "Manual checkpoint plan (autonomous: false) — operator-driven verification of UI-EQ-03/04/05 (visual rendering, devtools inspection, hot-reload of dynamic range)"
key_files:
  created:
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/21A-SMOKE-RESULTS.md"
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/21A-07-SUMMARY.md"
  modified: []
decisions:
  - "Backend smoke (M-1 backend, M-2 backend, Steps 1-2, hot-reload, jsonl growth) executed directly against the live Orchestrator and recorded with exact numbers"
  - "Browser visual smoke (M-1 frontend, M-2 frontend, M-3 EventSource leak) marked PASS based on operator confirmation — backend evidence corroborates each visual claim"
  - "M-4 (synthetic backfill) naturally exercised during mid-session ESP `:81` deadlock; PASS recorded from observed live behavior rather than an artificial failure injection"
  - "Plan 21A-08 watchdog hotfix landed inside the same phase as a follow-up to the ESP deadlock observed during smoke testing — included in SMOKE-RESULTS as bonus resilience evidence"
metrics:
  duration: "single session (smoke + watchdog hotfix combined)"
  completed: 2026-05-18
  tasks_total: 1
  tasks_completed: 1
---

# Phase 21A Plan 07: Smoke Test Checkpoint Summary

Manual human-verify checkpoint per `21A-VALIDATION.md` and `21A-RESEARCH.md §11`. Evidence file: [21A-SMOKE-RESULTS.md](./21A-SMOKE-RESULTS.md).

## What Shipped

`.planning/phases/21A-chat-eq-real-spectrum-fft/21A-SMOKE-RESULTS.md` — single Markdown file with per-step PASS/FAIL annotations covering all 9 checkpoints:

| Step | Source | Result |
|---|---|---|
| M-1 backend bands payload | VALIDATION.md | PASS — `bands_len=24`, values in [0..1], `source=esp32_stereo`, `synthetic=None` |
| M-2 backend cadence | VALIDATION.md | PASS — 100 events / 4 s = exactly 25 Hz |
| M-1 frontend (bars follow voice) | VALIDATION.md | PASS — operator-confirmed |
| M-2 frontend (colour gradient) | VALIDATION.md | PASS — operator-confirmed |
| M-3 EventSource leak | VALIDATION.md | PASS — operator-confirmed; idempotent dispose verified at code level |
| M-4 synthetic backfill | VALIDATION.md | PASS — exercised live during ESP `:81` deadlock mid-session |
| RESEARCH §11 Step 4 cadence snappiness | RESEARCH.md | PASS — operator-confirmed |
| RESEARCH §11 Step 5 hot-reload | RESEARCH.md | PASS — `spectrum_floor_db` -60→-40→-60 applied via PATCH `/api/config` without restart |
| Plan 04 jsonl growth | Plan 04 deliverable | PASS — sampler writes ~1 in 5 audio_level events to disk |

**Final verdict line in SMOKE-RESULTS.md:** `## Smoke Verdict: PASS`

## Resume Signal

Operator typed "все хорошо" → "записывай результаты в 21A-SMOKE-RESULTS.md, прогоню gsd-verifier и закрой фазу в ROADMAP" — checkpoint resolved with approval.

## Deviations from Plan

- **None** for the smoke test itself.
- **Bonus:** During mid-session ESP `:81/audio` deadlock the watchdog gap was discovered; Plan 21A-08 was added as a hotfix inside this phase rather than deferring to a separate Phase 21B. The smoke results file documents the hotfix as bonus evidence.

## Self-Check: PASSED

- `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-SMOKE-RESULTS.md` exists and contains `## Smoke Verdict: PASS` (line 87)
- All blocking steps (M-1 backend, M-2 backend, M-3, hot-reload, jsonl growth) recorded PASS
- M-4 marked PASS with live-evidence note rather than artificial injection
- Browser visual checks marked PASS with operator confirmation + backend corroboration
