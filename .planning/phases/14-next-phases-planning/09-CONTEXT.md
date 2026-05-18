# Phase 9: Next-Phases Planning — CONTEXT

**Date:** 2026-05-17
**Branch:** `diploma-chapter3`
**Status:** Context gathered, ready for `/gsd-plan-phase 9`

---

## Domain

На основе аудита диплома (Phase 7) и матрицы соответствия теория↔код (Phase 8) сформировать конкретные phase drafts для следующих волн разработки. Привязать каждый draft к активным веткам и Backlog items. Результат — готовый input для Phase 10 (Roadmap Global Update).

**Phase 9 не реализует — она планирует.** Это бумажная фаза.

---

## Carrying forward from prior phases

### Phase 7 (Diploma Analysis)
- 83 находки, классифицированы по severity (17 CRITICAL → 3 после правок)
- TERMINOLOGY-MATRIX.md (48 терминов)
- GAPS.md (44 концепта)
- Все CRITICAL частично закрыты commit `6c84c71`

### Phase 8 (Theory-Code Verification)
- 48 терминов: 26 FULL + 16 PARTIAL + 4 MISSING + 13 EMERGENT + 0 CONTRADICTED
- 17 path-рекомендаций (4A + 6B + 7C + 1 accepted)
- Топ-3 EMERGENT уже добавлены в диплом (commit `b48ccb8`)
- 5 phase candidates сформулированы в 08-SUMMARY §4.1

### Активные ветки разработки
| Ветка | Текущий статус | Готова к мёржу? |
|-------|----------------|------------------|
| `Memory-upgrade` | Phase 6A + 6B done | Да, после code-review |
| `Identity-tuning` | Активная разработка | Нет |
| `VLM-upgrade` | Активная разработка | Нет |
| `dynamic-aiim` | Активная разработка | Нет |
| `diploma-chapter3` | Текущая (Ф7-Ф9) | Нет |

### Backlog items в ROADMAP.md
1. Memory Wave 2 (Neural search) — ветка `Memory-upgrade`
2. UI: Пересборка интерфейса управления — новая ветка
3. Remote: Удалённый доступ к Jetson — новая ветка
4. Refactor: Структурный рефакторинг — новая ветка
5. Proactive Speech: Спонтанная речевая инициатива — новая ветка
6. AIIM Dynamic: Рефлексивный уровень — ветка `dynamic-aiim`

### Уже запланированные фазы
- **Phase 10**: Roadmap Global Update (уже в Roadmap)
- **Phase 12**: Metrics & Evaluation Framework (уже в Roadmap, DEFERRED)

---

## Decisions

### D-01: Scope — 10+ фаз (всё промотировать)

Промотировать **все** Backlog items в полноценные фазы + добавить 5 кандидатов из Ф8. Это даст полную карту следующих 3-6 месяцев разработки.

Ожидаемый список фаз для draft:

**От Ф8 candidates:**
- Phase 10A: Diploma Convergence Pass (правки 4A + 7C + 5 оставшихся EMERGENT)
- Phase 10B: Config-First Refactor (BUG F-07 + Τ-30/31/36 path B)
- Phase 11: AIIM Dynamic (`dynamic-aiim` branch + Phase 8 F-05)
- ~~Phase 12: Metrics & Evaluation~~ (уже в Roadmap)
- Phase 13: Memory Consolidation (Τ-35 single B-path с реальной разработкой)
- Phase 14: Mood LLM-driven (Φ-3 Агентность B-path)

**От Backlog:**
- Phase 15: Memory Wave 2 — Neural search (`Memory-upgrade` branch)
- Phase 16: UI Rebuild (новая ветка `ui-rebuild`)
- Phase 17: Remote Access (новая ветка `remote-access`)
- Phase 18: Structural Refactor (новая ветка `refactor`)
- Phase 19: Proactive Speech (новая ветка `proactive-speech`)
- Phase 20: VLM Upgrade — финализация (`VLM-upgrade` branch)
- Phase 21: Identity Calibration — финализация (`Identity-tuning` branch)

Итого: **~13 новых фаз** (10 + 3 финализационных для активных веток).

### D-02: Формат — гибрид (краткий summary + детальный draft для топ-3)

Структура `09-PHASE-DRAFTS.md`:
- **Топ-3 ближайших фазы** (10A, 10B, 11) — полный ROADMAP-style шаблон:
  - Goal (1-2 предложения)
  - Branch (явно)
  - Requires (зависимости от других фаз / merge'ов)
  - Delivers (bullet-list конкретных артефактов)
  - Requirements IDs (новые: DIPL-09, CFG-01, AIIM-01 ...)
  - Mode (standard / mvp / discovery)
  - Связь с Ф7/Ф8 находками
- **Остальные ~10 фаз** — компактный формат:
  - Phase N: Name — Branch — Goal (1 предложение) — Связь с источником

### D-03: Критерии приоритизации — 4 измерения

Каждая фаза получает оценку по 4 критериям (3-балльная шкала: H/M/L):

1. **Impact** — насколько повышает качество системы / диплома
2. **Effort** — оценка трудозатрат (H = недели, M = дни, L = часы)
3. **Strategic value** — закрывает ли вопросы для защиты диплома / закрывает gaps из Ф7
4. **Exhibition readiness** — нужно ли к выставке (стабильность, операторский UI, проактивность)

Финальный приоритет: P0 (do first) / P1 (do next) / P2 (later) / P3 (nice to have).

Также вычислить «Net dependencies» — сколько фаз блокирует данная (например, Τ-35 Консолидация блокирует Phase 12 LMRR).

### D-04: Timeline — без фиксированных дат

Не пытаться расставить календарь. Только:
- Dependencies (что после чего)
- Логические группы фаз («Diploma Finalization», «System Stabilization», «Feature Expansion»)

Phase 10 (Roadmap Update) — следующая после Ф9 — решит milestone-структуру.

### D-05: Wave structure для Ф9

**Wave 1 (1 plan):** аккумулировать кандидатов из всех источников (Ф7 + Ф8 + Backlog + активные ветки) → `CANDIDATES.md`

**Wave 2 (1 plan):** приоритизация — оценка каждого кандидата по 4 критериям → `09-PRIORITIZATION.md` с матрицей и P0/P1/P2/P3 группировкой

**Wave 3 (1 plan):** написание phase drafts → `09-PHASE-DRAFTS.md`:
- Полный шаблон для топ-3 (10A, 10B, 11)
- Компактный для остальных ~10

**Wave 4 (main agent inline):** `09-SUMMARY.md` — рекомендации для Phase 10 (Roadmap Update)

---

## Canonical refs

### Из Phase 7 + Phase 8 (главные входы)
- `.planning/phases/07-comprehensive-diploma-analysis/07-SUMMARY.md`
- `.planning/phases/07-comprehensive-diploma-analysis/GAPS.md` (44 концепта)
- `.planning/phases/08-theory-code-verification/08-SUMMARY.md` (§4.1 — 5 phase candidates)
- `.planning/phases/08-theory-code-verification/CONTRADICTIONS.md` (17 path-рекомендаций)
- `.planning/phases/08-theory-code-verification/EMERGENT-FEATURES.md` (13 фич)

### Из Roadmap (текущая структура)
- `.planning/ROADMAP.md` (Phase 7-12 описаны; Backlog в конце)
- `.planning/REQUIREMENTS.md` (для генерации новых REQUIREMENTS-IDs)
- `.planning/STATE.md` (статус активных веток)

### Project state
- `CLAUDE.md` (root) — invariants
- `docs/AGENT-PROTOCOL.md` — phase planning protocol
- `Agent Adam Chip/Tuning.json` (для AIIM Dynamic контекста)
- `System/Config.json` + `Config.schema.json` (для Config-First Refactor)

---

## Out of scope (Deferred Ideas)

- **Реализация любой из планируемых фаз** → отдельные phase executions (Ф10+)
- **Изменение Roadmap.md** → Phase 10 (Roadmap Global Update)
- **Code changes** → не в этой фазе
- **Diploma rewrites** → Phase 10A (Diploma Convergence Pass)
- **Календарь / дедлайны** → out of scope, нет фиксированных дат

---

## Code context (для downstream)

- **Не применимо:** Phase 9 — чисто аналитическая фаза, нет code/diploma changes
- **Output только в `.planning/phases/09-next-phases-planning/`**
- **Subagent strategy:**
  - Wave 1 (CANDIDATES) — Explore subagent (read-only sources)
  - Wave 2 (PRIORITIZATION) — general-purpose (анализ + writing)
  - Wave 3 (PHASE-DRAFTS) — general-purpose (writing шаблонов)
  - Wave 4 (SUMMARY) — main agent inline

---

## Success criteria

- [ ] `CANDIDATES.md` содержит все ~13 кандидатов из 3 источников (Ф8 + Backlog + active branches)
- [ ] `09-PRIORITIZATION.md` содержит матрицу 4 критериев + группировку P0/P1/P2/P3
- [ ] `09-PHASE-DRAFTS.md`:
  - Топ-3 (10A, 10B, 11) — полные ROADMAP-style шаблоны
  - Остальные ~10 — компактный формат
- [ ] Каждая фаза привязана к branch (существующая или новая `<name>`)
- [ ] Net dependencies явно указаны (что блокирует что)
- [ ] `09-SUMMARY.md` готов как input для Phase 10 (Roadmap Update)
- [ ] Все новые REQUIREMENTS-IDs предложены (для добавления в REQUIREMENTS.md в Phase 10)

---

## Next step

`/gsd-plan-phase 9`
