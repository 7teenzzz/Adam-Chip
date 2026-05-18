---
phase: 10-roadmap-global-update
branch: diploma-chapter3
status: planning
created: "2026-05-17"
type: documentation-update
---

# Phase 10: Roadmap Global Update — Context

## Goal

Обновить `.planning/ROADMAP.md` и `.planning/REQUIREMENTS.md` с глобальной картой будущих фаз (12 новых фаз из Phase 9 output). Добавить milestone-структуру. Привести ROADMAP в полностью синхронизированное состояние — единый источник истины для планирования на 3–6 месяцев вперёд.

## Source artifacts (готовые данные из Phase 9)

| Файл | Что содержит |
|------|-------------|
| [09-PHASE-DRAFTS.md §1](../09-next-phases-planning/09-PHASE-DRAFTS.md) | Полные ROADMAP-style drafts для P0: Phase 10A, 10B, 11 |
| [09-PHASE-DRAFTS.md §2](../09-next-phases-planning/09-PHASE-DRAFTS.md) | Compact drafts для P1–P3: Phase 13, 21, 14, 15, 17, 20, 19, 16, 18 |
| [09-PHASE-DRAFTS.md §3](../09-next-phases-planning/09-PHASE-DRAFTS.md) | 32 REQUIREMENTS-IDs (copy-paste ready) |
| [09-PHASE-DRAFTS.md §4](../09-next-phases-planning/09-PHASE-DRAFTS.md) | Dependency graph + Sequential/Parallel clusters |
| [09-SUMMARY.md §4](../09-next-phases-planning/09-SUMMARY.md) | Детальные инструкции для Phase 10 (4.1 ROADMAP, 4.2 REQUIREMENTS, 4.3 open questions, 4.4 milestones) |

## Scope of changes

### Target 1: `.planning/ROADMAP.md`

**Добавить после Phase 9:**
- Phase 10A: Diploma Convergence Pass (`diploma-chapter3`, P0)
- Phase 10B: Config-First Refactor (new `config-refactor`, P0)
- Phase 11: AIIM Dynamic (`dynamic-aiim`, P0)
- Phase 13: Memory Consolidation (new `memory-consolidation`, P1)
- Phase 21: Identity Calibration Финализация (`Identity-tuning`, P1)
- Phase 14: Mood LLM-driven (new `mood-llm`, P2)
- Phase 15: Memory Wave 2 / Neural Search (`Memory-upgrade`, P2)
- Phase 17: Remote Access (new `remote-access`, P2)
- Phase 20: VLM Upgrade Финализация (`VLM-upgrade`, P2)
- Phase 19: Proactive Speech (new `proactive-speech`, P2)
- Phase 16: UI Rebuild (new `ui-rebuild`, P3)
- Phase 18: Structural Refactor (new `refactor`, P3)

**Обновить Phase 12 (Metrics & Evaluation):**
- Изменить секцию Requires: «Phase 11 (AIIM Dynamic) завершена + Phase 13 (Memory Consolidation) завершена»
- Пометить как **DEFERRED** с условием разблокировки

**Удалить из Backlog** (эти items промотированы в фазы):
- Memory Wave 2: Neural search → Phase 15
- UI: Пересборка интерфейса управления → Phase 16
- Remote: Удалённый доступ к Jetson → Phase 17
- Refactor: Структурный рефакторинг → Phase 18
- Proactive Speech: Спонтанная речевая инициатива → Phase 19
- AIIM Dynamic: Рефлексивный уровень идентичности → Phase 11

**Добавить Milestone-структуру** (секция ## Milestones в ROADMAP.md):

| Milestone | Фазы | Критерий |
|-----------|------|---------|
| M1: Diploma Defence Ready | 10A, 21 | `diploma-chapter3` + `Identity-tuning` смёржены в main |
| M2: System Stable Pre-Exhibition | 10B, 13, 20 | Config-First + Memory Consolidation + VLM merge |
| M3: Exhibition Feature Set | 11, 14, 19, 16, 17 | AIIM Dynamic, Proactive Speech, UI Rebuild |
| M4: Research Loop | 12, 15, 18 | Phase 12 разблокирована (M2+M3) + Neural Search + Structural Refactor |

### Target 2: `.planning/REQUIREMENTS.md`

Добавить 12 новых секций с 32 REQUIREMENTS-IDs (из 09-PHASE-DRAFTS.md §3):

| Prefix | Phase | IDs |
|--------|-------|-----|
| DIPL- | 10A Diploma Convergence | DIPL-09..DIPL-15 (7 IDs) |
| CFG- | 10B Config-First Refactor | CFG-01..CFG-04 (4 IDs) |
| AIIM- | 11 AIIM Dynamic | AIIM-01..AIIM-04 (4 IDs) |
| MEM- | 13 Memory Consolidation | MEM-01..MEM-03 (3 IDs) |
| ID- | 21 Identity Calibration | ID-01..ID-03 (3 IDs) |
| MOOD- | 14 Mood LLM-driven | MOOD-01..MOOD-02 (2 IDs) |
| MEMN- | 15 Memory Wave 2 | MEMN-01..MEMN-02 (2 IDs) |
| REM- | 17 Remote Access | REM-01..REM-02 (2 IDs) |
| VLM- | 20 VLM Upgrade | VLM-01..VLM-02 (2 IDs) |
| PROAC- | 19 Proactive Speech | PROAC-01..PROAC-03 (3 IDs) |
| UI- | 16 UI Rebuild | UI-01..UI-04 (4 IDs) |
| REF- | 18 Structural Refactor | REF-01..REF-02 (2 IDs) |

### Target 3: `.planning/STATE.md`

- Phase 9 пометить ✓ COMPLETE (2026-05-17) с кратким итогом (13 фаз спроектированы)
- Обновить Active Phase → Phase 10: Roadmap Global Update

### Target 4: `.planning/ROADMAP.md` — Phase 9 block

- Отметить Phase 9 планы `[x]` (09-01..09-04 все выполнены)
- Добавить строку `**Completed:** 2026-05-17`

## Decisions from Phase 9 to carry forward

| Open question | Decision for Phase 10 |
|---------------|----------------------|
| Phase 11 vs Phase 13 — какой первым? | В ROADMAP оба P0/P1 соответственно; order: Phase 13 первая (net-unlock=3), Phase 11 можно вести параллельно |
| Phase 16 — P2 или P3? | Оставить P3 (дата выставки неизвестна) — в Open question отметить условие повышения до P2 |
| Phase 13 branch: `Memory-upgrade` или новая? | Новая `memory-consolidation` — изолирует риски от Neural search |

## Constraints

- НЕ менять код, диплом, Config.json или что-либо вне `.planning/`
- НЕ создавать MILESTONES.md как отдельный файл — milestone-секция идёт прямо в ROADMAP.md (минимизация файлов)
- НЕ создавать roadmap-visual.md (Mermaid уже есть в 09-PHASE-DRAFTS.md §4 — ссылки достаточно)
- Порядок фаз в ROADMAP: 10A, 10B, 11, 13, 21, 14, 15, 17, 20, 19, 16, 18 (по Priority → Branch readiness → Net-unlock)
- Формат каждой фазы в ROADMAP: Branch / Goal / Requires / Delivers / Requirements IDs / Mode

## Decisions

| ID | Decision |
|----|---------|
| D-01 | Milestones — inline в ROADMAP.md, не отдельный файл |
| D-02 | Phase 12 остаётся в ROADMAP как DEFERRED (не удалять); обновить Requires |
| D-03 | Backlog очищается от промотированных items (6 удалений) |
| D-04 | Phase 13 branch = `memory-consolidation` (new), не `Memory-upgrade` |
| D-05 | Порядок добавления в ROADMAP: P0 первыми, затем P1 по sequential clusters, затем P2 по Exhibition value |

## Subagent strategy

Одна волна — main agent или один executor:
- PLAN.md создаёт gsd-planner (spawn)
- Execute: 1 wave, 2 задачи (ROADMAP update + REQUIREMENTS update + STATE.md update)
- Всё в одном PLAN.md — объём предсказуемый (copy-paste из готовых артефактов)

## Success criteria

- ROADMAP.md содержит все 12 новых фаз после Phase 9
- Backlog содержит 0 из 6 промотированных items
- Phase 12 помечена как DEFERRED с обновлёнными Requires
- Milestone-секция (M1–M4) присутствует
- REQUIREMENTS.md содержит все 32 новых ID (DIPL-09..ID-03)
- STATE.md: Phase 9 = ✓ COMPLETE, Active = Phase 10

---

*Создан: 2026-05-17 | Phase 10, Wave 0 (main agent inline)*
*Consumed by: 10-PLAN.md → gsd-executor*
