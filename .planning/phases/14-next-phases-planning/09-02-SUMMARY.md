---
phase: 09-next-phases-planning
plan: 02
subsystem: planning
tags:
  - prioritization
  - roadmap
  - phase-planning
dependency_graph:
  requires:
    - 09-01-PLAN (CANDIDATES.md)
    - 08-SUMMARY (phase candidates, Ф8 findings)
    - 07-SUMMARY (CRITICAL gaps, Strategic value basis)
  provides:
    - 09-PRIORITIZATION.md (P0/P1/P2/P3 matrix, net deps)
  affects:
    - 09-03 (PHASE-DRAFTS — knows which 3 get full template)
    - Phase 10 (Roadmap Global Update — receives logical groups)
tech_stack:
  added: []
  patterns:
    - 4-criteria scoring matrix (H/M/L) with inverted Effort
    - Net dependency graph for unlock sequencing
key_files:
  created:
    - .planning/phases/09-next-phases-planning/09-PRIORITIZATION.md
  modified: []
decisions:
  - "P0 locked to Phase 10A, 10B, 11 per D-01 (diploma + config + AIIM — max ROI cluster)"
  - "Phase 13 → P1 (net-unlock=3, highest among all candidates)"
  - "Phase 21 → P1 (Effort=L, Strategic=H, requires Phase 10A only)"
  - "Phase 19 Proactive Speech → P2 (Exhibition=H overrides default P3 due to exhibition relevance)"
  - "Phase 16 UI Rebuild → P3 with open question: elevate to P2 if exhibition is imminent"
  - "Phase 11 Effort reclassified to H=weeks (source CANDIDATES.md label 'L' was misleading — meaning 'недели' contradicts L=hours scale)"
metrics:
  duration: ~45 min
  completed: 2026-05-17
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 9 Plan 02: Prioritization Matrix — Summary

**One-liner:** 13-phase 4-criteria scoring matrix with P0/P1/P2/P3 grouping and net-dependency unlock graph for Wave 3 drafting.

---

## What was built

`09-PRIORITIZATION.md` — полная матрица оценки 13 кандидатов из `CANDIDATES.md` по 4 критериям (Impact, Effort, Strategic value, Exhibition readiness) с финальными приоритетами P0–P3 и net-dependency графом.

**Структура файла:**
- Critères table (4 критерия, шкала H/M/L с объяснением инверсии Effort)
- Matrix table (13 фаз × 6 колонок: Impact / Effort / Strategic / Exhibition / Net deps / Priority)
- Net dependencies graph (текстовая диаграмма с unlock-цепочками)
- Priority groups (P0=3, P1=2, P2=5, P3=2 с обоснованием каждой фазы)
- Notes: Logical groups для Phase 10 Roadmap Update + sequential clusters
- Risk / Open questions (5 пунктов)

---

## Scoring rationale

### P0 (3 фазы — зафиксированы D-01)

| Phase | Impact | Effort | Strategic | Exhibition | Rationale |
|-------|--------|--------|-----------|------------|-----------|
| 10A Diploma Convergence | H | L | H | L | Max ROI: закрывает диплом, Effort=L |
| 10B Config-First | H | M | H | L | Устраняет BUG F-07 + разблокирует Phase 18, 16 |
| 11 AIIM Dynamic | H | H | M | M | Рефлексивный AIIM — ядро тезиса + разблокирует Phase 12 RDI |

### P1 (2 фазы)

- **Phase 13** — net-unlock=3 (Phase 12 LMRR + Phase 15 + Phase 19), единственный реальный B-кейс Ф8
- **Phase 21** — Effort=L (merge + code review), Strategic=H, requires только Phase 10A

### P2 (5 фаз)

Phase 14, 15, 17, 20, 19 — независимы или требуют завершения P1; Exhibition или Impact=M.

Phase 19 (Proactive Speech) поднята из потенциального P3 в P2 из-за Exhibition=H.

### P3 (2 фазы)

Phase 16 (UI Rebuild) и Phase 18 (Structural Refactor) — оба Effort=H, Impact=L. Phase 16 содержит open question на повышение до P2 если выставка близко.

---

## Net dependency key findings

- **Phase 13** — наибольший unlock-потенциал (3 нижестоящих фазы). Рекомендуется запустить параллельно с Phase 11.
- **Phase 10B → Phase 18, Phase 16** — sequential cluster (нельзя параллелить).
- **Phase 11 ∥ Phase 13** — оба разблокируют Phase 12 независимо, параллельная разработка возможна.

---

## Deviations from plan

**[Rule 1 — Data clarification] Phase 11 Effort переоценка**
- **Found during:** заполнения матрицы
- **Issue:** CANDIDATES.md обозначает Phase 11 как `L (недели)` — `L` по ярлыку противоречит описанию «недели», что по шкале матрицы = H
- **Fix:** Effort переведён в H=weeks согласно фактическому содержанию (новый рефлексивный модуль + интеграция). P0 статус неизменен (зафиксирован D-01)
- **Files modified:** только 09-PRIORITIZATION.md (документировано в Notes + Risk R-05)

---

## Output for Wave 3

`09-03-PLAN.md` (PHASE-DRAFTS) получает:
- **P0 cluster** (10A, 10B, 11) → полный ROADMAP-style template для каждой
- **P1–P3** (~10 фаз) → компактный формат (Phase N: Name — Branch — Goal — Source)
- **Logical groups** → «Diploma Finalization» / «System Stabilization» / «Feature Expansion» для структурирования Roadmap Update в Phase 10

---

## Self-Check

- [x] `09-PRIORITIZATION.md` создан и содержит 193 строки
- [x] Matrix содержит ровно 13 строк фаз
- [x] P0 содержит ровно 3 фазы (10A, 10B, 11)
- [x] P-groups: P0=3, P1=2, P2=5, P3=2
- [x] Net dependencies указаны для каждой фазы
- [x] Logical groups секция присутствует
- [x] Risk/open questions — 5 пунктов
- [x] Commit `1dfb69f` создан

## Self-Check: PASSED
