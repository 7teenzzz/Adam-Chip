---
phase: 09-next-phases-planning
plan: 01
subsystem: planning
tags: [roadmap, candidates, phase-planning, diploma, backlog]

# Dependency graph
requires:
  - phase: 08-theory-code-verification
    provides: "5 phase candidates из §4.1, 17 path-рекомендаций, 13 EMERGENT-фичей"
  - phase: 07-comprehensive-diploma-analysis
    provides: "83 находки, 44 GAPS, 7 кандидатов для Phase 9"
provides:
  - "CANDIDATES.md — полный реестр 13 кандидатов в будущие фазы с source/branch/goal/effort"
  - "Нормализованный ввод для Wave 2 (09-02 PRIORITIZATION)"
affects: [09-02-PRIORITIZATION, 09-03-PHASE-DRAFTS, 09-04-SUMMARY, 10-roadmap-global-update]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Three-source candidate aggregation (Ф8 §4.1 + Backlog + active branches)", "Single-edit optimization mapping (Ф8 §4.3 совмещения)"]

key-files:
  created:
    - ".planning/phases/09-next-phases-planning/CANDIDATES.md"
  modified: []

key-decisions:
  - "Phase 11 AIIM Dynamic: объединён из Ф8-кандидата (F-05 hot-reload) + Backlog-item — один candidate, два источника"
  - "Phase 13 Memory Consolidation: создаётся как отдельная фаза (не в Memory-upgrade branch) — требует решения в Wave 2"
  - "Phase 12 Metrics: не передрачена, упомянута только в Already in ROADMAP как DEFERRED"
  - "Топ-3 EMERGENT (F-04/F-05/F-06, commit b48ccb8) уже применены — вычтены из Phase 10A scope"

patterns-established:
  - "Candidate format: source / branch / goal / trigger-artifact / dependencies / effort / linked-findings / notes"
  - "Cross-source merge: Backlog-item + Ф8-candidate → один Phase (не дублировать)"

requirements-completed: [PLAN9-01, PLAN9-02, PLAN9-03]

# Metrics
duration: 25min
completed: 2026-05-17
---

# Phase 9 Plan 01: Candidates Collection Summary

**Реестр 13 кандидатов в будущие фазы собран из трёх источников (Ф8 §4.1, ROADMAP Backlog, активные ветки) в едином нормализованном формате для Wave 2 приоритизации.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-17T (session start)
- **Completed:** 2026-05-17
- **Tasks:** 1 (Task 1: Extract candidates and write CANDIDATES.md)
- **Files created:** 1

## Accomplishments

- Прочитаны все 7 источников: 08-SUMMARY §4.1, CONTRADICTIONS.md, EMERGENT-FEATURES.md, 07-SUMMARY.md, ROADMAP.md Backlog, STATE.md активные ветки, 09-CONTEXT.md решения D-01–D-05
- Создан CANDIDATES.md с 13 кандидатами в едином формате (Phase 10A, 10B, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21)
- Все три источника репрезентированы: 5 из Ф8, 6 из Backlog, 2 финализационных из активных веток; Phase 11 объединяет Ф8 + Backlog (merged source)
- Секции Already in ROADMAP, Cross-source notes (совмещения Ф8 §4.3), Verification checklist — все присутствуют
- Phase 12 Metrics — упомянута исключительно в "Already in ROADMAP", не передрачена

## Task Commits

1. **Task 1: Extract candidates and write CANDIDATES.md** - `ab34168` (docs)

**Plan metadata:** (будет добавлен финальным коммитом)

## Files Created/Modified

- `.planning/phases/09-next-phases-planning/CANDIDATES.md` — 226 строк; 13 кандидатов + Already in ROADMAP + Cross-source notes + Verification checklist

## Decisions Made

- **Phase 11 merged:** Backlog-item «AIIM Dynamic» и Ф8-кандидат Phase 11 — один и тот же scope. Объединены в одну запись с пометкой "merged source". Исключает дубликат в реестре.
- **Phase 13 branch-вопрос оставлен открытым:** `Engineering/consolidator.py` создан в `Memory-upgrade` (Phase 6A), но логически Phase 13 — отдельная фаза. Решение вынесено в Wave 2 (приоритизация).
- **Scope Phase 10A уточнён:** из 13 EMERGENT топ-3 (F-04/F-05/F-06) уже применены (commit `b48ccb8`); в Phase 10A входят оставшиеся 5 HIGH + 4 MEDIUM (EMERGENT #1, #3, #6, #7, #8) + все 4A + 7C path-правки.

## Deviations from Plan

None — план выполнен точно по спецификации. Структура файла, шаблон записей, секции — строго по `<interfaces>` блоку из 09-01-PLAN.md.

## Issues Encountered

None.

## Next Phase Readiness

- **Wave 2 (09-02 PRIORITIZATION) может начинаться немедленно:** CANDIDATES.md содержит все необходимые поля для оценки по 4 критериям (Impact / Effort / Strategic value / Exhibition readiness)
- **Каждый из 13 кандидатов имеет:** source (откуда взят), branch (существующая или новая), goal (1 предложение), dependencies (что блокирует / что требует), effort (S/M/L)
- **Открытые вопросы для Wave 2:** Phase 13 branch (Memory-upgrade vs новая); порядок Phase 20/21 vs Phase 10A (finalization сначала или diploma convergence первее?); зависимость Phase 19 от Phase 13

---
*Phase: 09-next-phases-planning*
*Completed: 2026-05-17*
