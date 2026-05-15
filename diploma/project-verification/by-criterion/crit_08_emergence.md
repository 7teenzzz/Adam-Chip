# Criterion 8 — Уровень эмерджентности

## Theoretical Definition

Из раздела 2.1.8: где возникает поведение. Три уровня: локальный → интеракционный → системный.

## Implementation Status: **PARTIAL** (преимущественно локальный + интеракционный)

Adam Chip — **интеракционный** уровень эмерджентности; системный — частично через event bus.

## Graphify Evidence

| Node | File | Role |
|---|---|---|
| `EventLog` | System/adam/events.py | 13 — централизованный event bus |
| `api_runtime.py` | System/adam/api_runtime.py | 17 — events SSE + /api/events |
| Cross-community connections | graphify-out/ | 47 communities, multiple cross-edges |
| `Orchestrator.py` | System/Orchestrator.py | 85 — composition center |

## Verification Trace

1. graphify report: 47 communities, **11 thin omitted** — основные 36 имеют cross-connections.
2. `EventLog` собирает события из всех модулей в один stream → системная видимость.
3. `/api/agent/turns` API группирует события по turn_id → системная агрегация.
4. Persona graph отдельно (`graphify-out-persona/`) — дополнительный layer эмерджентности.
5. `consolidator.py` (daily) — переписывает память на основе всей истории → time-emerging behavior.

## Findings

**Уровень «интеракционный + частично системный» (таблица 10):**

- ✅ **Локальный.** Каждый модуль чётко определён (FULL coverage критериев 2-7 показывает).
- ✅ **Интеракционный.** Behavior эмерджентен из взаимодействий: prompt (memory + persona + scene + tuning + history) → LLM → action → TTS + MCU. Никакой один модуль не определяет ответ.
- ⚠️ **Системный.** Частично:
  - ✅ Event bus собирает события в один stream
  - ✅ Cross-community connections в graphify
  - ❌ Нет emergent goals (нет внутренней постановки задач)
  - ❌ Нет system-wide reflection (consolidator техническая, не семантическая)

## Связь с главой 3

- **Раздел 3.4.5** (интерпретация результатов и ограничения) — операционализирует этот критерий.
- В дипломе явно указано: эмерджентность не выделяется как самостоятельная метрика, рассматривается «лишь косвенно — через согласованность наблюдаемого поведения системы» (раздел 3.4.1).

## Эмерджентные эффекты (наблюдаемые)

1. **Композиционный персонаж** — Adam Chip как «характер» возникает только при работе всех модулей: один модуль (например, только LLM) даёт generic ответы.
2. **Контекст-зависимая модуляция** — память + scene + tuning меняют тон ответа без переключения «персонажа».
3. **Distributed body presence** — light + sound + vibration синхронно создают ощущение присутствия, ни один канал отдельно не воспроизводит этот эффект.
4. **Latency-driven personality** — задержки LLM (9с prefill для Gemma SWA) и filler phrases создают «задумчивого» персонажа.

## Recommendations for Chapter 3

В разделе 3.4.5 описать **4 эмерджентных эффекта** (см. выше) как наблюдения, ограничения, и предмет для дальнейшего исследования. Подчеркнуть: эмерджентность не запланирована, но возникает из правильной композиции модулей.
