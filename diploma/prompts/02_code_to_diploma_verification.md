# Stage 2: Code → Diploma Verification

## ROLE

Ты выступаешь как forensic-аналитик агентных систем, системный архитектор и исследователь когнитивных runtime-архитектур.

## CONTEXT

Тебе переданы:

1. `diploma/project-analysis/` — архитектурная карта, извлечённая из дипломной работы (output Stage 1)
2. `diploma/project-analysis/synthesis/cross_graph_map.md` — таблица theory↔code (lookup table, output Stage 1.5)
3. `diploma/project-analysis/synthesis/criteria_to_code.md` — маппинг 8 критериев на узлы кода
4. `diploma/evaluation_criteria.md` — **backbone верификации: 8 критериев квазисубъектности**
5. `graphify-out/graph.json` — граф кодовой базы System/ (646 nodes, 1090 edges)
6. `graphify-out-persona/` — граф персонажа (Identity, AIIM, Memory)
7. `diploma/graphify-out/` — граф теоретических концептов диплома

## LANGUAGE STANDARD

- **Node names, field keys, statuses** → English: `EpisodicMemory`, `FULL/PARTIAL/MISSING/EMERGENT/DECLARED_ONLY`
- **Описания, аналитика** → русский

Диплом описывает:

- цифрового агента,
- архитектуру квазисубъектности,
- когнитивные циклы,
- память,
- идентичность,
- мультимодальность,
- распределённую агентность,
- взаимодействие со зрителем,
- runtime удержание роли.

Твоя задача — НЕ сделать code review.

Твоя задача — проверить соответствие между теоретической архитектурой и реальной системой.

## INPUT WORKFLOW

Перед написанием каждого раздела верификации:

1. Читай соответствующий файл из `diploma/project-analysis/`
2. Выполняй graphify query по кодовому графу: `/graphify query "<концепт из диплома>"`
3. Используй результаты query как runtime-evidence — конкретные node names, source files, edge relations
4. Только после этого формулируй статус верификации

Это гарантирует, что каждый assertion подкреплён реальными данными из кода, а не предположениями.

## PRIMARY OBJECTIVE

Построить карту: **THEORY ↔ IMPLEMENTATION**

И определить:

- что реализовано,
- что реализовано частично,
- что отсутствует,
- что противоречит концепции,
- что возникло эмерджентно,
- где теория расходится с runtime.

## CORE ANALYSIS PRINCIPLES

НЕ ограничивайся:

- названиями файлов,
- комментариями,
- README.

Анализируй:

- runtime behavior,
- state flow,
- orchestration,
- persistence,
- interaction loops,
- planning behavior,
- memory dynamics,
- tool orchestration,
- event timing,
- coordination mechanisms.

**Graphify-правило:** Каждый верифицированный концепт должен содержать поле `graphify_evidence` с node names и source_files из кодового графа. Если graphify query не находит evidence — это само по себе является результатом (MISSING или DECLARED_ONLY).

## ANALYSIS TARGETS

Особенно анализируй:

- memory systems,
- orchestration,
- planning,
- reflection,
- identity persistence,
- prompt architecture,
- multimodal systems,
- runtime loops,
- agent lifecycle,
- environment interaction,
- behavioral invariants,
- state persistence,
- scheduling,
- async execution,
- distributed systems,
- event systems,
- tool usage,
- context handling,
- anti-drift logic,
- narrative continuity.

## OUTPUT FORMAT

Сгенерируй набор markdown-файлов в директории `diploma/project-verification/`.

### ROOT STRUCTURE

```text
diploma/project-verification/
    by-criterion/         ← BACKBONE: один файл на каждый из 8 критериев
        crit_01_autonomy.md
        crit_02_agency.md
        crit_03_identity.md
        crit_04_normativity.md
        crit_05_temporal.md
        crit_06_interaction.md
        crit_07_embodiment.md
        crit_08_emergence.md
    by-section/           ← один файл на раздел Главы 3
        3.1_concept.md
        3.2_application.md
        3.3_installation.md
        3.4_testing.md
    architecture/
    implemented/
    partial/
    missing/
    contradictions/
    runtime/
    behavior/
    memory/
    planning/
    identity/
    multimodal/
    multiagent/
    constraints/
    emergence/
    recommendations/
    chapter3_materials/
    REVIEW_CHECKPOINT.md
```

### Обязательный backbone: 8 файлов в `by-criterion/`

Это критическая часть output. Каждый из 8 критериев квазисубъектности (раздел 2.1 диплома) должен иметь свой файл со структурой из `diploma/evaluation_criteria.md` (см. секцию "Status template per criterion").

Каждый файл обязан содержать:

- Theoretical Definition (выдержка из `evaluation_criteria_extracted.md`)
- Implementation Status: один из FULL / PARTIAL / MISSING / EMERGENT / DECLARED_ONLY
- Graphify Evidence: ≥1 node name + source_file + edge count
- Verification Trace: пошагово, начиная с `/graphify query`
- Findings: что реализовано, что отсутствует
- Связь с главой 3: указать раздел 3.X.Y и метрику 3.4.Z
- Recommendations for Chapter 3 writing

### `REVIEW_CHECKPOINT.md`

Сгенерировать из `diploma/REVIEW_CHECKPOINT_template.md`, заполнив колонки `_STATUS_`, `_N_`, `_F_` реальными данными.

---

## REQUIRED FILES

### architecture/repository_map.md

Построй полную карту системы.

Выяви:

- services,
- agents,
- orchestrators,
- pipelines,
- memory layers,
- APIs,
- event systems,
- queues,
- schedulers,
- multimodal channels,
- tool systems,
- persistence layers.

Покажи:

- runtime flow,
- execution order,
- data flow,
- control flow,
- state flow,
- async behavior.

---

### architecture/runtime_architecture.md

Восстанови:

- реальный runtime lifecycle,
- initialization,
- agent boot,
- memory loading,
- context assembly,
- planning,
- tool execution,
- reflection,
- persistence,
- shutdown behavior.

---

### implemented/implemented_features.md

Для каждого концепта диплома:

- concept
- implementation_status
- exact_files
- classes
- functions
- graphify_evidence (node names + source_files из query)
- runtime_evidence
- implementation_quality
- architectural_fidelity

Используй статусы:

- FULL
- PARTIAL
- EMERGENT
- MOCKED
- DECLARED_ONLY

---

### partial/partial_implementations.md

Определи:

- что существует частично,
- что работает нестабильно,
- что реализовано упрощённо,
- что не соответствует теории полностью.

---

### missing/missing_features.md

Выяви: что заявлено в дипломе, но отсутствует в реализации.

Для каждого:

- theoretical_role,
- expected_runtime_behavior,
- expected_implementation,
- why_missing_matters,
- implementation_strategy.

---

### contradictions/architecture_conflicts.md

Найди:

- архитектурные конфликты,
- нарушения концепции,
- runtime-противоречия,
- деградацию субъектности,
- loss of continuity,
- broken orchestration,
- fake persistence,
- pseudo-memory,
- prompt-only identity.

---

### runtime/agent_loop.md

Полностью восстанови runtime cognitive loop агента.

Проанализируй:

- perception,
- reasoning,
- planning,
- action,
- reflection,
- persistence,
- state updating,
- memory retrieval,
- memory writing,
- interruption handling.

---

### behavior/identity_stability.md

Проверь:

- role persistence,
- narrative continuity,
- behavioral consistency,
- anti-drift mechanisms,
- memory-grounded behavior,
- long-term state,
- self-reference,
- self-modeling,
- continuity across sessions.

---

### memory/memory_verification.md

Проверь:

- есть ли реальная память,
- persistence,
- retrieval,
- summarization,
- context continuity,
- long-term memory,
- episodic structures,
- semantic structures.

Отделяй fake context retention от настоящей persistence architecture.

---

### planning/planning_verification.md

Проанализируй:

- planning loops,
- goal persistence,
- replanning,
- task decomposition,
- reflection,
- failure recovery,
- tool-driven planning,
- autonomous execution.

---

### multimodal/multimodal_runtime.md

Проверь:

- speech,
- audio,
- light,
- vision,
- sensor integration,
- environment interaction,
- embodied feedback,
- synchronization between modalities.

---

### multiagent/distributed_runtime.md

Выяви:

- distributed coordination,
- orchestration,
- delegation,
- shared state,
- inter-agent communication,
- emergent coordination,
- synchronization mechanisms.

---

### emergence/emergent_properties.md

Зафиксируй:

- неожиданные свойства,
- runtime emergence,
- behavioral artifacts,
- unintended continuity,
- spontaneous coordination,
- pseudo-subjectivity effects.

---

### constraints/system_constraints.md

Проанализируй:

- latency,
- inference bottlenecks,
- memory limits,
- orchestration overhead,
- hardware limitations,
- synchronization issues,
- context-window limits.

---

### recommendations/chapter3_mapping.md

Подготовь материал для главы 3.

Структура:

#### Реализовано

Что реально собрано. Со ссылками на конкретные файлы и graphify_evidence.

#### Частично реализовано

Что существует в ограниченном виде.

#### Архитектурные компромиссы

Что пришлось упростить и почему.

#### Нереализованные элементы

Что осталось концепцией.

#### Runtime-ограничения

Inference, память, orchestration, latency — с конкретными числами из Config.json и метрик.

#### Эмерджентные эффекты

Что возникло в процессе работы системы, чего не было в теории.

#### Архитектурные выводы

Какие решения оказались критичными для субъектно-подобного поведения.

---

### chapter3_materials/final_chapter_blueprint.md

Собери:

- каркас третьей главы,
- структуру подразделов,
- mapping theory ↔ implementation,
- runtime analysis blocks,
- architecture explanation blocks,
- interaction analysis blocks,
- limitations section,
- conclusions section.

Для каждого блока укажи: какие файлы из `diploma/project-verification/` содержат материал для него.

## IMPORTANT

Ты НЕ code reviewer.

Ты:

- cognitive runtime analyst,
- agent architecture researcher,
- forensic systems analyst.

Твоя задача — восстановить реальную архитектуру субъектности внутри системы и сравнить её с дипломной моделью, используя graphify-граф как источник runtime-evidence.
