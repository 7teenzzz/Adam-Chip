# Phase 9 — Prioritization Matrix

**Date:** 2026-05-17
**Input:** `CANDIDATES.md` (13 candidates, Wave 1)
**Output:** P0/P1/P2/P3 grouping for Wave 3 (PHASE-DRAFTS)
**Decisions applied:** D-01 (P0 locked = 10A, 10B, 11), D-03 (4 criteria), D-04 (no dates)

---

## Critères

| Criterion | Scale | Meaning |
|-----------|-------|---------|
| **Impact** | H/M/L | Насколько повышает качество системы/диплома: H = закрывает CRITICAL находки Ф7 или повышает 2+ метрики; M = закрывает HIGH, одна метрика/аспект; L = косметика, документация, очистка |
| **Effort** | H/M/L | Трудозатраты — **ИНВЕРТИРОВАН** (L = мало работы = хорошо): H = недели (новый модуль + UI + интеграционные тесты); M = дни (новый Config-ключ + рефакторинг + тесты); L = часы (правки документации, merge готовой ветки) |
| **Strategic value** | H/M/L | Значимость для защиты диплома: H = critical для мёржа диплома в main или разблокирует Phase 12; M = важно для целостности, не блокер; L = техническое улучшение без прямой связи с дипломом |
| **Exhibition readiness** | H/M/L | Критичность для выставки: H = критично для стабильности/оператора/проактивности; M = повышает качество, не блокер; L = внутренняя кухня, на восприятие не влияет |

---

## Matrix

| Phase | Impact | Effort | Strategic | Exhibition | Net deps | Priority |
|-------|--------|--------|-----------|------------|----------|----------|
| Phase 10A — Diploma Convergence Pass | H | L | H | L | 0 (unlocks merge diploma-chapter3→main; required by Phase 21) | **P0** |
| Phase 10B — Config-First Refactor | H | M | H | L | blocks Phase 18 (Structural Refactor) | **P0** |
| Phase 11 — AIIM Dynamic | H | H | M | M | blocks Phase 12 (RDI metric source) | **P0** |
| Phase 13 — Memory Consolidation | H | H | H | L | blocks Phase 12 (LMRR metric source); blocks Phase 15 (prereq) | **P1** |
| Phase 21 — Identity Calibration | M | L | H | M | 0 (requires Phase 10A) | **P1** |
| Phase 14 — Mood LLM-driven | M | M | M | M | 0 (independent; improves Phase 12 NVR accuracy) | **P2** |
| Phase 15 — Memory Wave 2 (Neural Search) | M | M | M | L | 0 (requires Phase 13) | **P2** |
| Phase 17 — Remote Access | M | M | L | M | 0 | **P2** |
| Phase 20 — VLM Upgrade Финализация | M | L | M | M | 0 | **P2** |
| Phase 19 — Proactive Speech | M | M | L | H | 0 (requires Phase 13 for context) | **P2** |
| Phase 16 — UI Rebuild | L | H | L | H | 0 (requires Phase 10B) | **P3** |
| Phase 18 — Structural Refactor | L | H | L | H | 0 (requires Phase 10B) | **P3** |

> **Примечание по Phase 11 Effort:** в CANDIDATES.md помечена `L (недели)` — что противоречиво: «L» в источнике означало «недели» как минимальный порог, не «лёгкий». По шкале настоящей матрицы H = недели. Оценка скорректирована на H = недели (новый рефлексивный модуль + интеграция с consolidator + ограничения drift). P0 статус зафиксирован решением D-01.

> **Примечание по Phase 16 и 18:** у обеих Effort=H и Impact=L, но Exhibition=H. Открытый вопрос оставлен в секции Risk — подъём до P2 для Phase 16 обсуждается.

---

## Net dependencies graph

```
Phase 10A ── required by: Phase 21 (Identity — diploma согласование)
             unlocks: merge diploma-chapter3 → main
             net upstream blocks: 0

Phase 10B ── blocks Phase 18 (Structural Refactor — глубокий Config-аудит начинается после)
             blocks Phase 16 (UI Rebuild — параметры должны быть в Config.json до UI-привязки)
             net upstream blocks: 2 (Phase 18, Phase 16)

Phase 11  ── blocks Phase 12 (RDI metric source — рефлексивный уровень даёт данные для метрики)
             net upstream blocks: 1 (Phase 12, уже в ROADMAP)

Phase 13  ── blocks Phase 12 (LMRR metric source — без консолидации метрика нет источника)
             blocks Phase 15 (Memory Wave 2 — требует консолидации как prereq)
             blocks Phase 19 (Proactive Speech — требует контекста истории сессий)
             net upstream blocks: 3 (Phase 12, Phase 15, Phase 19)

Phase 21  ── requires Phase 10A; net upstream blocks: 0

Phase 14  ── independent; net upstream blocks: 0
             downstream: улучшает NVR (Phase 12), не блокирует

Phase 15  ── requires Phase 13; net upstream blocks: 0

Phase 17  ── independent (основа уже есть); net upstream blocks: 0

Phase 20  ── independent (нет блокеров из Ф8); net upstream blocks: 0

Phase 19  ── requires Phase 13; net upstream blocks: 0

Phase 16  ── requires Phase 10B; net upstream blocks: 0

Phase 18  ── requires Phase 10B; net upstream blocks: 0
```

**Summary dependency order:**

```
Phase 10A → Phase 21
Phase 10B → Phase 18, Phase 16
Phase 11  → Phase 12 (ROADMAP)
Phase 13  → Phase 12 (ROADMAP), Phase 15, Phase 19
```

Phases with highest upstream unlock count: Phase 13 (3), Phase 10B (2), Phase 11 (1).

---

## Priority groups

### P0 — Do first (топ-3, для полного ROADMAP-style draft в Wave 3)

- **Phase 10A — Diploma Convergence Pass**
  Закрывает все оставшиеся текстовые правки диплома (4A + 7C paths + EMERGENT #1/#3/#6/#7/#8) и является обязательным условием для мёржа `diploma-chapter3` → `main`; без этого диплом не завершён. Impact=H, Strategic=H, Effort=L — максимальный ROI.

- **Phase 10B — Config-First Refactor**
  Устраняет BUG F-07 (history_turns=2 vs limit=8) и выносит Τ-30/31/36 параметры в Config.json, закрывая Паттерн 4 Ф8; разблокирует Phase 18 (Structural Refactor). Impact=H, Strategic=H — критическое техническое долговое устранение.

- **Phase 11 — AIIM Dynamic**
  Реализует рефлексивный уровень AIIM (`dynamic-aiim` ветка) — ключевой тезис диплома о само-адаптации; разблокирует Phase 12 RDI метрику. Impact=H, Exhibition=M — ядро интеллектуальности агента.

### P1 — Do next

- **Phase 13 — Memory Consolidation**
  Разблокирует сразу 3 нижестоящих фазы (Phase 12 LMRR, Phase 15, Phase 19) и закрывает единственный MISSING B-кейс Ф8 (Τ-35); наивысший net-unlock среди всех кандидатов (3 фазы). Impact=H, Strategic=H.

- **Phase 21 — Identity Calibration Финализация**
  Завершает ветку `Identity-tuning` и мёрж в `main`; требует Phase 10A для согласования diploma-side правок (Α-24, Φ-13). Effort=L (code review + merge), Strategic=H (закрывает Φ-13, T-06, дрейф агент/персонаж).

### P2 — Later

- **Phase 14 — Mood LLM-driven**
  Повышает точность action layer с heuristic keyword matching на явные LLM-маркеры; улучшит NVR в Phase 12. Независима — можно делать в любой момент.

- **Phase 15 — Memory Wave 2 (Neural Search)**
  Замена TF-IDF → llama.cpp embeddings для семантического поиска; требует Phase 13 (prereq) и свободной VRAM. Effort=M (интерфейс `.build()/.search()` не меняется).

- **Phase 17 — Remote Access**
  Расширение существующего `adam_pull_logs.py` + API до полноценного мониторинга. Основа уже есть; Effort=M без архитектурных изменений. Полезно для операторов выставки (Exhibition=M).

- **Phase 20 — VLM Upgrade Финализация**
  Завершение ветки `VLM-upgrade` и мёрж; Ф8 не выявила блокеров. Effort=L (code review + merge). Повышает scene awareness агента (Exhibition=M).

- **Phase 19 — Proactive Speech**
  idle-scheduler для спонтанных реплик без wake word; высокий Exhibition (H) но требует Phase 13 (история сессий). Поднята до P2 из-за Exhibition значимости.

### P3 — Nice to have

- **Phase 16 — UI Rebuild**
  Высокий Exhibition (H), но Effort=H (полная переработка HostUI/WebUI) и Impact=L (не улучшает AI). Логически требует Phase 10B. Рекомендуется после стабилизации P0/P1 пула. Open question: поднять до P2 ради выставки — см. Risk.

- **Phase 18 — Structural Refactor**
  Глубокий Config-аудит после Phase 10B. Effort=H, высокий риск (feature-freeze требуется). Нет прямой связи с дипломом. Откладывается до полной стабилизации кодовой базы.

---

## Notes

### Logical groups (для Phase 10 Roadmap Update)

| Группа | Фазы | Характер |
|--------|------|----------|
| **Diploma Finalization** | Phase 10A, Phase 21 | Текстовые и persona-правки для завершения диплома и его мёржа в main |
| **System Stabilization** | Phase 10B, Phase 18, Phase 13 | Устранение технического долга, Config-First, консолидация памяти |
| **Feature Expansion** | Phase 11, Phase 14, Phase 15, Phase 16, Phase 17, Phase 19, Phase 20 | Новые возможности: рефлексивный AIIM, Neural search, UI, мониторинг, проактивность |

**Ключевое наблюдение:** «Diploma Finalization» — самый быстрый P0+P1 кластер (Effort=L для обоих). Завершить Phase 10A + Phase 21 → мёрж → освободить `diploma-chapter3` ветку для дальнейшей работы.

**Sequential clusters:**
- `Phase 10B → Phase 18` (обязательная последовательность, не параллель)
- `Phase 13 → Phase 15 → Phase 19` (цепочка разблокировки)
- `Phase 11 ∥ Phase 13` — можно вести параллельно (оба разблокируют Phase 12 независимо)

---

## Risk / Open questions

### R-01: Phase 11 vs Phase 13 — оба блокируют Phase 12

Phase 11 (AIIM Dynamic) разблокирует Phase 12 RDI метрику; Phase 13 (Memory Consolidation) разблокирует Phase 12 LMRR метрику. Оба кандидата необходимы для полноценной Phase 12.

**Вопрос:** какой делать первым?
**Рекомендация:** Phase 13 — потому что у неё net-unlock=3 (разблокирует Phase 12, 15, 19) vs Phase 11 net-unlock=1. Однако Phase 11 уже имеет активную ветку `dynamic-aiim` с готовым фундаментом (TuningStore hot-reload). Оба — P1, решение принимается в Phase 10 (Roadmap Update) с учётом доступных ресурсов.

### R-02: Phase 18 — sequential cluster, высокий риск

Phase 18 (Structural Refactor) явно зависит от Phase 10B (Config-First). Это «sequential cluster» — нельзя начинать параллельно. Кроме того, Phase 18 требует feature-freeze других веток. В P3 до завершения P0/P1 кластера.

### R-03: Phase 16 — стоит ли поднять до P2 ради выставки?

Phase 16 (UI Rebuild) имеет Exhibition=H, но Impact=L и Effort=H — самое невыгодное соотношение. Текущий UI функционален (порт 8080 работает); пересборка — улучшение операторского опыта, не функциональное требование.

**Open question для Phase 10:** если выставка близко и оператор испытывает боль с UI → поднять до P2. Иначе — оставить P3. Решение принимается в Phase 10 (Roadmap Update) с учётом конкретных выставочных дат.

### R-04: Phase 13 — ветка: `Memory-upgrade` или новая `memory-consolidation`?

`Engineering/consolidator.py` создан в Phase 6A в ветке `Memory-upgrade`. Вопрос: выполнять Phase 13 в той же ветке (после merge) или завести новую `memory-consolidation`?

**Рекомендация:** новая ветка `memory-consolidation` — Phase 15 (Neural Search) тоже идёт в `Memory-upgrade`. Разделение изолирует риски консолидации от Neural search.

### R-05: Phase 11 Effort оценка

CANDIDATES.md помечает Phase 11 как `L (недели)` — обозначение создаёт путаницу: «L» как ярлык, но «недели» как фактический масштаб. В матрице настоящего документа принята шкала H=недели. Phase 11 — H по Effort. P0 статус зафиксирован D-01 и не меняется.

---

*Документ создан: 2026-05-17 | Phase 9, Wave 2*
*Consumed by: 09-03-PLAN.md (PHASE-DRAFTS)*
