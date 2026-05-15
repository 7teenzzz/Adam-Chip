# Criterion 2 — Тип агентности

## Theoretical Definition

Из раздела 2.1.2: топология локализации действия. Четыре типа: централизованная → модульная → гибридная → распределённая.

## Implementation Status: **FULL** (модульная)

Adam Chip — **модульная агентность**: единый orchestrator + распределённые подсистемы памяти, идентичности, действия, восприятия.

## Graphify Evidence

| Node | Role | Edges |
|---|---|---|
| `Orchestrator.py` | Central dispatcher | 85 |
| `VoiceLoopController` | Voice cycle | 42 |
| `EpisodicMemory` | Memory subsystem | 29 |
| `TuningStore` | Identity config | 17 |
| `MCUClient` | Motor subsystem | 25 |
| `PromptBuilder` | Context assembly | — |
| `ActionLayer` | Action validation | — |
| `EchoGate` | Reply selection | 15 |

## Verification Trace

1. `graphify path "Orchestrator.py" "EpisodicMemory"` — путь через VoiceLoopController.
2. Структура каталога `System/adam/`: 25+ модулей, каждый со своим назначением.
3. Один Orchestrator управляет всеми, но logic распределена по модулям.
4. Persona graph (`graphify-out-persona/`) — отдельный граф для идентичности → дополнительное распределение.

## Findings

**Соответствует типу «модульная агентность» (таблица 4 диплома).**

Признаки:
- ✅ Восприятие, решение, действие НЕ в одной модели
- ✅ Распределение по подсистемам с явным интерфейсом
- ✅ Единый orchestrator как координатор
- ✅ Action layer как отдельный validation pipeline
- ❌ Не распределённая (нет multi-agent координации) — это сознательный выбор

## Связь с главой 3

- **Раздел 3.2.1** (общая архитектура) — явно описывает модульную структуру с blocks: Speech, Interlayers, Memory, Tools.
- **Раздел 3.1.2** — описание поведенческой логики соответствует.

## Recommendations for Chapter 3

В разделе 3.2.1 подчеркнуть: проект сознательно выбрал модульную (не распределённую) агентность для художественной задачи единого персонажа. Multi-agent был отвергнут (см. case studies 2.3).
