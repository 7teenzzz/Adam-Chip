# Phase 8: Discussion Log

**Date:** 2026-05-17
**Mode:** standard (full GSD cycle, decisions in Russian)

---

## Discussion areas

### Area 1: Scope verification

**Options presented:**
- Все 48 терминов из TERMINOLOGY-MATRIX (рекомендовано)
- Только CRITICAL + HIGH из Ф7 (~50 находок)
- EMERGENT-only фокус

**User selected:** Все 48 терминов из TERMINOLOGY-MATRIX

**Rationale:** полная картина даёт надёжный input для Ф9 (Next-Phases Planning). EMERGENT-only пропустит большую часть verification, CRITICAL/HIGH — не учтёт MEDIUM-зоны.

---

### Area 2: Graphs

**Options presented (multiSelect):**
- code/
- persona/
- esp32/
- docs/

**User selected:** code/ + persona/ + esp32/ (без docs/)

**Rationale:** docs/ — внешние библиотеки (Silero, Jetson AI Lab), не нужны для verification внутренних концептов диплома. Три графа покрывают: основной код, персонаж (AIIM/Identity/Memory), прошивку (технофлора).

---

### Area 3: CONTRADICTED decisions

**Options presented:**
- Ф8 предлагает, Ф9 решает (рекомендовано)
- Ф8 сразу классифицирует
- Гибрид: CRITICAL → Ф9, остальные → Ф8

**User selected:** Гибрид (CRITICAL → Ф9, HIGH/MEDIUM → Ф8 классифицирует)

**Rationale:** CRITICAL противоречия требуют контекста других приоритетов (есть ли ресурсы на правку кода, какие ветки активны). Их решает Ф9. HIGH/MEDIUM проще — Ф8 может сразу классифицировать (A/B/C path).

---

### Area 4: Уровень детализации

**Options presented:**
- Компактно: 1 строка + тег + файл/класс
- Детально: исходник + grep-evidence + 1-2 абзаца (рекомендовано)
- Гибрид: таблица всех + детально по CONTRADICTED и EMERGENT

**User selected:** Гибрид (таблица всех концептов + детально по CONTRADICTED и EMERGENT)

**Rationale:** компактная таблица для общего обзора (можно бегло читать), детальные секции для проблемных категорий. Best-of-both — экономия времени без потери качества.

---

## Deferred Ideas (для будущих фаз)

- **Стилистические правки диплома (типографские аномалии)** → Phase 10A (Diploma Convergence Pass)
- **Реализация метрик 3.4** → Phase 12 (Metrics & Evaluation Framework)
- **Verification внешних библиотек (Silero, Jetson)** → не требуется
- **Library version checks** → операционная задача, не scope Ф8

---

## Claude's discretion (auto-decided)

- **Wave structure:** Wave 0 (graphify) → Wave 1 (4 parallel по категориям) → Wave 2 (synthesis) → Wave 3 (summary). Параллельность по категориям (а не по главам как в Ф7) — потому что concepts уже агрегированы из всех 4 глав в TERMINOLOGY-MATRIX
- **Decision tree для классификации:** FULL = граф находит точное соответствие; PARTIAL = частично; MISSING = только в дипломе; EMERGENT = только в коде; CONTRADICTED = разное поведение
- **Wave 1 категории:** философские (16) / AIIM (9) / технические (18) / художественные (5) — даёт примерно равную нагрузку на subagents
- **Не переоткрывать правки 6c84c71** — Commander/Communication/PromtBuilder/ASR/TF-IDF уже RESOLVED
- **Severity calibration для CONTRADICTED:**
  - CRITICAL = расхождение в фундаментальном механизме (например, action layer mood inference)
  - HIGH = расхождение в одном модуле (например, специфика VLM polling)
  - MEDIUM = расхождение в детали (например, имя параметра, единица измерения)
