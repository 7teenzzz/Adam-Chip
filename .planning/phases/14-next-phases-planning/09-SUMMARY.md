# 09-SUMMARY.md — Phase 9: Next-Phases Planning

**Date:** 2026-05-17
**Branch:** `diploma-chapter3`
**Status:** Phase 9 complete — ready for Phase 10 (Roadmap Global Update)
**Format:** Hybrid (compact matrix + detailed Phase 10 recommendations)

---

## Часть 1 — Краткая матрица фаз

| Phase | Name | Branch | Priority | Goal (1 line) |
|-------|------|--------|----------|---------------|
| 10A | Diploma Convergence Pass | `diploma-chapter3` | **P0** | Применить все оставшиеся правки диплома из Ф8 (4A + 7C + 10 EMERGENT) и подготовить ветку к мёржу в main |
| 10B | Config-First Refactor | new `config-refactor` | **P0** | Вынести хардкоды Τ-30/31/36 в Config.json и устранить BUG F-07 (history_turns vs limit рассинхрон) |
| 11 | AIIM Dynamic | `dynamic-aiim` | **P0** | Реализовать рефлексивный уровень AIIM: консолидатор автокорректирует Tuning.json после каждой сессии |
| 13 | Memory Consolidation | new `memory-consolidation` | **P1** | Интегрировать `consolidator.py` в Orchestrator runtime с daily cron или post-session trigger |
| 21 | Identity Calibration | `Identity-tuning` | **P1** | Завершить ветку Identity-tuning (Φ-13 path C, Α-24) и выполнить merge в main |
| 14 | Mood LLM-driven | new `mood-llm` | **P2** | Заменить heuristic mood-парсинг на явные LLM-маркеры в action.py |
| 15 | Memory Wave 2 (Neural Search) | `Memory-upgrade` | **P2** | Заменить TF-IDF → llama.cpp embeddings в FaissEpisodeIndex |
| 17 | Remote Access | new `remote-access` | **P2** | Расширить adam_pull_logs.py до полноценного удалённого мониторинга pipeline |
| 19 | Proactive Speech | new `proactive-speech` | **P2** | idle-scheduler для спонтанных реплик агента без wake word |
| 20 | VLM Upgrade | `VLM-upgrade` | **P2** | Завершить ветку VLM-upgrade и выполнить merge в main |
| 16 | UI Rebuild | new `ui-rebuild` | **P3** | Пересобрать операторский интерфейс с доменной перегруппировкой параметров |
| 18 | Structural Refactor | new `refactor` | **P3** | Глубокий Config-аудит второго слоя параметров после Phase 10B |

*Phase 12 (Metrics & Evaluation) — уже в ROADMAP, DEFERRED. Разблокируется фазами 11 (RDI) и 13 (LMRR).*

---

## Часть 2 — Logical groups

### Diploma Finalization
- **Phase 10A → Phase 21** (sequential: Identity-merge согласован с diploma-правками Α-24/Φ-13)
- Fastest cluster: оба Effort=L/S, максимальный дипломный ROI

### System Stabilization
- **Phase 10B → Phase 18** (sequential: глубокий рефакторинг после Config-First)
- **Phase 13** (параллельно с 10B — нет зависимости)
- Phase 10B разблокирует также Phase 16 (UI Rebuild)

### Feature Expansion
- **Phase 11, 14, 20** — независимые, параллельные
- **Phase 13 → Phase 15 → Phase 19** — цепочка разблокировки
- **Phase 11 ∥ Phase 13** — оба блокируют Phase 12, можно вести одновременно

---

## Часть 3 — Connection map с активными ветками

| Active branch | Linked candidate phase | Action |
|---------------|------------------------|--------|
| `diploma-chapter3` | Phase 10A | Продолжить в текущей ветке; merge → main после Phase 10A |
| `Memory-upgrade` | Phase 15 (Neural Search) | Wave 1 (BM25+FAISS) готова; после code-review merge; Phase 15 = Wave 2 |
| `dynamic-aiim` | Phase 11 (AIIM Dynamic) | Продолжить разработку; TuningStore hot-reload — фундамент готов |
| `Identity-tuning` | Phase 21 (Identity Calibration) | Финализировать + merge после согласования с Phase 10A |
| `VLM-upgrade` | Phase 20 (VLM Upgrade) | Нет блокеров из Ф8; code-review + merge |

---

## Часть 4 — Recommendations for Phase 10

### 4.1 Что копировать в ROADMAP.md

1. **Из `09-PHASE-DRAFTS.md` §1** — взять три полных draft (Phase 10A, 10B, 11) без изменений и добавить в ROADMAP после текущей Phase 9
2. **Из `09-PHASE-DRAFTS.md` §2** — взять компактные drafts для P1–P3 (фазы 13, 21, 14, 15, 17, 19, 20, 16, 18), развернуть в стандартный ROADMAP-формат (Branch / Goal / Requires / Delivers / Mode)
3. **Удалить из Backlog** 6 items, промотированных в фазы: Memory Wave 2 → Phase 15; UI Rebuild → Phase 16; Remote Access → Phase 17; Structural Refactor → Phase 18; Proactive Speech → Phase 19; AIIM Dynamic → Phase 11
4. Phase 12 (Metrics & Evaluation) — оставить как DEFERRED, обновить условие разблокировки: «после Phase 11 + Phase 13»

### 4.2 Что копировать в REQUIREMENTS.md

Из `09-PHASE-DRAFTS.md` §3 — все 32 предложенных REQUIREMENTS-IDs по 12 префиксам:

| Prefix | Phase | Count |
|--------|-------|-------|
| DIPL- | 10A Diploma Convergence | DIPL-09..DIPL-15 (7 IDs) |
| CFG- | 10B Config-First Refactor | CFG-01..CFG-04 (4 IDs) |
| AIIM- | 11 AIIM Dynamic | AIIM-01..AIIM-04 (4 IDs) |
| MEM- | 13 Memory Consolidation | MEM-01..MEM-03 (3 IDs) |
| MOOD- | 14 Mood LLM-driven | MOOD-01..MOOD-02 (2 IDs) |
| MEMN- | 15 Memory Wave 2 | MEMN-01..MEMN-02 (2 IDs) |
| UI- | 16 UI Rebuild | UI-01..UI-04 (4 IDs) |
| REM- | 17 Remote Access | REM-01..REM-02 (2 IDs) |
| REF- | 18 Structural Refactor | REF-01..REF-02 (2 IDs) |
| PROAC- | 19 Proactive Speech | PROAC-01..PROAC-03 (3 IDs) |
| VLM- | 20 VLM Upgrade | VLM-01..VLM-02 (2 IDs) |
| ID- | 21 Identity Calibration | ID-01..ID-03 (3 IDs) |

### 4.3 Открытые вопросы (решить в Phase 10)

1. **Phase 11 vs Phase 13 — порядок:** оба разблокируют Phase 12 (RDI и LMRR соответственно). Рекомендация: Phase 13 сначала (net-unlock=3 vs 1), но Phase 11 имеет готовую ветку `dynamic-aiim` — решение за Phase 10 с учётом реального ресурса.

2. **Phase 16 UI Rebuild — P2 или P3?** Exhibition=H, но Effort=H и Impact=L. Если выставка близко и операторский UI — боль: поднять до P2. Иначе оставить P3 до стабилизации P0/P1 кластера.

3. **Phase 13 branch: `memory-consolidation` или `Memory-upgrade`?** Рекомендация из Wave 2: новая ветка `memory-consolidation` — Phase 15 (Neural Search) тоже идёт в `Memory-upgrade`; разделение изолирует риски.

### 4.4 Milestone-структура (предложение)

| Milestone | Фазы | Критерий |
|-----------|------|---------|
| **M1: Diploma Defence Ready** | 10A, 21 | `diploma-chapter3` и `Identity-tuning` смёржены в `main` |
| **M2: System Stable Pre-Exhibition** | 10B, 13, 20 | Config-First + Memory Consolidation + VLM merge |
| **M3: Exhibition Feature Set** | 11, 14, 19, 16, 17 | AIIM Dynamic, Proactive Speech, UI Rebuild, мониторинг |
| **M4: Research Loop** | 12, 15, 18 | Phase 12 (разблокирована M2+M3) + Neural Search + Structural Refactor |

*Milestone-сетка — рекомендация. Итоговое решение принимает Phase 10 (Roadmap Global Update).*

---

## Часть 5 — Артефакты Phase 9

| Artifact | Wave | Purpose |
|----------|------|---------|
| [CANDIDATES.md](CANDIDATES.md) | 1 | Реестр 13 кандидатов из 3 источников (Ф8 + Backlog + активные ветки) |
| [09-PRIORITIZATION.md](09-PRIORITIZATION.md) | 2 | Матрица 4 критериев + Net dependencies + P0/P1/P2/P3 + Risk |
| [09-PHASE-DRAFTS.md](09-PHASE-DRAFTS.md) | 3 | Полный draft для P0 + компактный для P1–P3 + 32 REQUIREMENTS-IDs |
| [09-SUMMARY.md](09-SUMMARY.md) | 4 | Этот файл — рекомендации для Phase 10 |

---

## Готовность к Phase 10

✓ Все 13 фаз спроектированы с branch и REQUIREMENTS-IDs  
✓ Зависимости явно прописаны (Net deps + sequential clusters)  
✓ Открытые вопросы выделены — Phase 10 разрешит (4.3)  
✓ Логические группы готовы — Phase 10 нарежет на milestones  

---

*Документ создан: 2026-05-17 | Phase 9, Wave 4 (main agent inline)*  
*Consumed by: Phase 10 (Roadmap Global Update)*
