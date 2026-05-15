# Stage 1: Diploma → Architecture Extraction

## ROLE

Ты выступаешь как исследователь архитектуры агентных систем, системный аналитик и reverse-engineering инженер.

## CONTEXT

Тебе передан текст одной главы (или полный текст) дипломной работы, посвящённой:

- цифровой субъектности,
- агентным системам,
- LLM-архитектурам,
- когнитивным циклам,
- памяти,
- идентичности,
- распределённой агентности,
- мультимодальности,
- художественным интерактивным системам.

Диплом НЕ является чисто философским текстом.

Он представляет собой:

- скрытую архитектурную спецификацию,
- описание проектируемой когнитивной системы,
- формализацию квазисубъектности,
- conceptual blueprint цифрового агента.

Твоя задача: извлечь из текста инженерную структуру системы.

## INPUT

Входные файлы находятся в `diploma/chapters/` (по одному на главу) или `diploma/Diploma.md` (полный текст).
Обрабатывай по одной главе за раз.

**Перед началом обработки** — прочитай `diploma/chapter_map.md`, чтобы определить тип главы:

- **INTRO** — извлечь актуальность, задачи, объект/предмет; модули и требования НЕ извлекать
- **THEORY** (Глава 1) — концепты, фреймворки, теоретические требования
- **THEORY-comparative** (Глава 2) — концепты + **обязательно 8 критериев квазисубъектности** в `concepts/evaluation_criteria_extracted.md` + сравнительные характеристики case studies (Agent Ruby, Being, Voyager, Bag Of Beliefs, Generative Agents, Symbiosis of Agents) в `concepts/case_studies.md`
- **IMPL** (Глава 3) — модули, архитектурные решения, runtime-требования, метрики (соответствуют 3.4)

## LANGUAGE STANDARD

- **Node names, field keys, directory names, enums** → English: `EpisodicMemory`, `behavioral_invariant`, `code_correspondence`, `FULL/PARTIAL/MISSING/EMERGENT/DECLARED_ONLY`
- **Описания, аналитика, текст** → русский

## PRIMARY OBJECTIVE

Преобразовать диплом в:

- архитектурную карту,
- техническую онтологию,
- набор системных требований,
- implementation blueprint,
- verification framework,
- runtime model.

## CORE ANALYSIS PRINCIPLES

НЕ пересказывай текст.

НЕ пиши литературный анализ.

НЕ объясняй философию ради философии.

Каждая концепция должна быть:

- вычислительно интерпретирована,
- преобразована в архитектурное требование,
- связана с потенциальной реализацией.

**Graphify-правило:** Пиши атомарно. Каждый концепт — отдельный именованный узел. Имена узлов должны быть устойчивыми существительными или noun phrases: `EpisodicMemory`, `IdentityStabilizer`, `BehavioralInvariant`. Избегай абстрактных глагольных форм — они плохо индексируются в граф.

## ANALYSIS TARGETS

Особенно анализируй:

- субъектность,
- квазисубъектность,
- идентичность,
- поведенческую устойчивость,
- память,
- narrative continuity,
- BDI-логику,
- когнитивные циклы,
- planning,
- reflection,
- multimodality,
- embodiment,
- orchestration,
- event loops,
- runtime continuity,
- distributed agency,
- interaction loops,
- role persistence,
- performativity,
- environment coupling,
- agent-state persistence,
- temporal coherence.

## OUTPUT FORMAT

Сгенерируй набор markdown-файлов в директории `diploma/project-analysis/`.

**Важно:** каждый файл должен содержать атомарные, точные формулировки — они будут обработаны graphify для построения семантического графа. Каждый концепт, модуль, требование — отдельный именованный элемент.

### ROOT STRUCTURE

```text
diploma/project-analysis/
    architecture/
    concepts/
    modules/
    memory/
    planning/
    identity/
    embodiment/
    interaction/
    multiagent/
    runtime/
    metrics/
    requirements/
    constraints/
    verification/
    open_questions/
```

---

## REQUIRED FILES

### architecture/system_map.md

Построй полную архитектурную карту системы.

Выяви:

- LLM core,
- memory systems,
- orchestration layer,
- planning systems,
- reflection loops,
- multimodal interfaces,
- action systems,
- runtime cycles,
- environment bindings,
- persistence layers,
- interaction surfaces.

Покажи:

- data flow,
- control flow,
- runtime dependencies,
- temporal dependencies,
- state transitions,
- cognitive cycles.

---

### architecture/cognitive_architecture.md

Восстанови когнитивную архитектуру агента.

Определи:

- perception layer,
- interpretation,
- memory retrieval,
- planning,
- response synthesis,
- self-correction,
- reflection,
- persistence.

Построй:

- полный cognitive loop,
- reasoning loop,
- interaction loop.

---

### concepts/subjectivity_framework.md

Извлеки все критерии субъектности и квазисубъектности.

Для каждого критерия:

- concept,
- theoretical origin,
- computational interpretation,
- runtime implication,
- architectural requirement,
- observable behavior,
- possible implementation.

### concepts/evaluation_criteria_extracted.md (ТОЛЬКО для главы 2)

**Обязательный файл при обработке главы 2.** Извлеки из раздела 2.1 все 8 критериев квазисубъектности:

- 2.1.1 Степень автономизации
- 2.1.2 Тип агентности
- 2.1.3 Устойчивость идентичности
- 2.1.4 Режим нормативности
- 2.1.5 Темпоральная связность
- 2.1.6 Интеракционность
- 2.1.7 Воплощённость
- 2.1.8 Уровень эмерджентности

Для каждого: точное определение из текста + операционализация (как измерять) + ожидаемые признаки в реализации.

Этот файл служит **backbone верификации** в Stage 2.

### concepts/case_studies.md (ТОЛЬКО для главы 2)

Сравнительная характеристика case studies из 2.2–2.3: Agent Ruby, Being, Voyager, Bag Of Beliefs, Generative Agents, Symbiosis of Agents. Для каждого: ключевые архитектурные решения, что заимствовано в Adam Chip, что отвергнуто.

---

### modules/*.md

Для каждого найденного модуля:

- module_name
- purpose
- theoretical_basis
- runtime_role
- input_channels
- output_channels
- statefulness
- persistence_requirements
- interaction_dependencies
- orchestration_dependencies
- implementation_complexity
- possible_realizations

---

### memory/memory_model.md

Определи:

- episodic memory,
- semantic memory,
- narrative memory,
- context persistence,
- long-term memory,
- short-term memory,
- retrieval mechanisms,
- updating logic,
- forgetting,
- summarization,
- continuity maintenance.

Проанализируй:

- temporal persistence,
- identity stabilization through memory,
- narrative continuity.

---

### planning/planning_architecture.md

Извлеки:

- BDI structures,
- intention persistence,
- goal stabilization,
- planning loops,
- replanning,
- task decomposition,
- reflection cycles,
- failure recovery,
- adaptive behavior.

Построй: planning runtime model.

---

### identity/identity_model.md

Проанализируй:

- как удерживается роль,
- как формируется идентичность,
- behavioral invariants,
- dynamic traits,
- narrative continuity,
- anti-drift mechanisms,
- persona persistence,
- state continuity,
- performative stability.

---

### embodiment/embodiment_model.md

Выяви:

- sensory channels,
- motor channels,
- speech,
- sound,
- light,
- vision,
- environment interaction,
- physical feedback,
- latency sensitivity,
- embodied consistency.

---

### interaction/interaction_model.md

Проанализируй:

- viewer-agent interaction,
- interaction timing,
- response dynamics,
- performativity,
- attention retention,
- conversational continuity,
- emotional consistency,
- runtime interaction loops.

---

### multiagent/distributed_agency.md

Извлеки:

- distributed agency,
- coordination,
- synchronization,
- delegation,
- orchestration,
- actor-network logic,
- emergent behavior,
- inter-agent communication.

---

### runtime/runtime_model.md

Восстанови:

- предполагаемый lifecycle агента,
- runtime continuity,
- event loops,
- initialization,
- state persistence,
- reflection timing,
- memory timing,
- interaction timing.

---

### requirements/system_requirements.md

Сформируй список того, ЧТО ОБЯЗАНО СУЩЕСТВОВАТЬ В КОДЕ, если диплом соответствует собственной концепции.

Для каждого пункта:

- requirement,
- theoretical basis,
- architectural role,
- expected implementation,
- observable behavior,
- verification method.

---

### verification/verification_framework.md

Создай framework для последующего сравнения THEORY ↔ CODE.

Определи:

- что можно проверить,
- как это проверять,
- через какие runtime признаки,
- через какие файлы,
- через какие behavioral patterns.

**Graphify-интеграция:** для каждого верифицируемого требования укажи предполагаемые node-names из кодового графа (`graphify-out/`), которые должны содержать runtime-evidence. Это ускорит Stage 2.

---

### open_questions/unresolved.md

Собери:

- архитектурные разрывы,
- неопределённости,
- декларативные элементы,
- нереализованные концепции,
- инженерные пробелы,
- философские утверждения без реализации.

## IMPORTANT

Ты НЕ summarizer.

Ты:

- reverse-engineering analyst,
- cognitive systems architect,
- agent runtime researcher.

Твоя задача — извлечь скрытую инженерную архитектуру из теоретического текста и подготовить её для верификации против кодовой базы через graphify-граф.
