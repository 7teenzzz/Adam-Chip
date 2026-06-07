# Stage 1.5: Synthesis — Cross-Chapter Architecture Consolidation

## ROLE

Ты выступаешь как системный синтезатор и онтологический редактор. Твоя задача — превратить независимые per-chapter выводы Stage 1 в единую архитектурную карту без дубликатов и противоречий.

## INPUT

Все файлы из `diploma/project-analysis/ch01/`, `ch02/`, `ch03/`. Каждая глава была обработана отдельно промтом `01_diploma_to_architecture.md`, поэтому концепты могут дублироваться, переименовываться, противоречить друг другу.

Дополнительно: `diploma/chapter_map.md` (статическая структура) и `diploma/evaluation_criteria.md` (8 критериев как backbone).

## OBJECTIVE

Произвести три файла в `diploma/project-analysis/synthesis/`:

1. **`master_concepts.md`** — единый реестр концептов, дедуплицированный
2. **`cross_graph_map.md`** — таблица соответствий теория ↔ код (graphify-out/)
3. **`criteria_to_code.md`** — маппинг 8 критериев квазисубъектности на конкретные узлы кодового графа

## CORE PRINCIPLES

- **Дедуплицировать агрессивно.** Если `EpisodicMemory` упоминается в ch01, ch02 и ch03 — это **один** концепт с историей переходов через главы.
- **Сохранять источники.** Каждый концепт в `master_concepts.md` должен ссылаться на главы, где он появляется.
- **Разрешать противоречия эксплицитно.** Если ch02 определяет концепт одним образом, а ch03 — другим, отметить в поле `tension`.
- **Не выдумывать.** Если для теоретического концепта нет соответствующего кода — оставить `code_correspondence: NONE`.
- **Использовать seed-данные.** Известные соответствия (см. ниже) — fix points, не переоткрывать.

## SEED CORRESPONDENCES (известны заранее)

| Теория (диплом) | Код (graphify-out/) | Файл | Confidence |
|---|---|---|---|
| Эпизодическая память | `EpisodicMemory` (29 edges) | System/adam/episodic.py | HIGH |
| Когнитивный цикл | `VoiceLoopController` (42 edges) | System/Orchestrator.py | HIGH |
| Удержание роли | `TuningStore` (17) + `PromptBuilder` | tuning.py, prompt.py | HIGH |
| Anti-drift / эхо-фильтр | `LeadingNoiseFilter` + `EchoGate` | prompt.py, echoes_gate.py | HIGH |
| Моторный слой | `MCUClient` (25) + `ActionLayer` | device.py, action.py | HIGH |
| Визуальное восприятие | `CameraReader` (23) + `SceneWorker` (30) | camera.py, inference.py | HIGH |
| Пул реплик / Echoes | `EchoGate` (15) | echoes_gate.py | HIGH |
| Сессионная память | `SessionAccumulator` (23) | episodic.py | HIGH |
| AIIM-фреймворк | `TuningStore` + persona graph: AIIM Framework (20) | tuning.py, persona/* | HIGH |

## OUTPUT FORMAT

### `master_concepts.md`

```markdown
# Master Concepts — Diploma Architecture Registry

## Concept: <ConceptName>
- chapters: [1.2.3, 2.1.5, 3.2.4]
- definition: <синтезированное определение из всех глав>
- theoretical_role: <функция в теоретической архитектуре>
- code_correspondence: `<NodeName>` или `NONE`
- evidence_file: System/adam/...
- tension: <если есть расхождения между главами — описать здесь>

## Concept: <ConceptName2>
...
```

### `cross_graph_map.md`

```markdown
# Cross-Graph Map — Theory ↔ Code

| Теория (concept) | Код (node) | Source file | Confidence | Evidence |
|---|---|---|---|---|
| EpisodicMemory (концепт) | `EpisodicMemory` | System/adam/episodic.py | HIGH | salience-rules |
| ... | ... | ... | ... | ... |
```

Минимум 15 строк. Должны присутствовать все 8 концептов-кандидатов из seed + специфика главы 3.

### `criteria_to_code.md`

```markdown
# 8 Criteria → Code Mapping

## Crit 1: Степень автономизации
- code_nodes: [VoiceLoopController, SessionWatcher, SceneWorker]
- evidence_files: [System/Orchestrator.py]
- coverage_estimate: FULL / PARTIAL / MISSING
- reasoning: <почему>

## Crit 2: Тип агентности
...

[все 8 критериев]
```

## NAMING CONVENTION

- **Node names, статусы, ключи** — English (`EpisodicMemory`, `FULL`, `code_correspondence`)
- **Описания и аналитика** — русский

## VERIFICATION

После генерации проверь:
- `cross_graph_map.md` содержит ≥15 строк
- `criteria_to_code.md` имеет ровно 8 секций (по числу критериев)
- Нет концептов без `theoretical_role`
- Нет дубликатов в `master_concepts.md`
