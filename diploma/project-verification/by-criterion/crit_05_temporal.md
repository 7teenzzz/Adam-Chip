# Criterion 5 — Темпоральная связность

## Theoretical Definition

Из раздела 2.1.5: связь действий во времени. Четыре уровня: эпизодическая → контекстная → нарративная → процессуальная.

## Implementation Status: **FULL** (нарративная, стремится к процессуальной)

Adam Chip достигает **нарративной связности** уверенно; элементы процессуальной (consolidation, summaries) присутствуют.

## Graphify Evidence

| Node | File | Role |
|---|---|---|
| `EpisodicMemory` | System/adam/memory.py | 29 edges — центр памяти |
| `SessionAccumulator` | System/adam/episodic.py | 23 edges — накопитель сессии |
| `MemoryStore` | System/adam/memory.py | 14 edges — SQLite storage |
| `ConsolidatorTuning` | System/adam/tuning.py | Параметры консолидации |
| `Engineering/consolidator.py` | — | Daily memory consolidation cron |
| `EventLog` | System/adam/events.py | 13 edges — JSONL events |

## Verification Trace

1. `data/adam/memory.sqlite3` — постоянное хранилище эпизодов.
2. `data/adam/events.jsonl` — поток событий с timestamps.
3. `Engineering/consolidator.py` — daily cron, консолидирует логи в summaries.
4. `data/adam/summaries/` + `data/adam/notes/` — output консолидатора.
5. `EpisodicMemory.retrieve()` — выборка релевантных эпизодов по salience.
6. `Config.json` → `history_turns: 2` — короткое окно для LLM context.
7. Salience scoring в `episodic.py` — правила, что попадает в долговременную.
8. Persona files (Bio.md эквивалент) — постоянная биографическая рамка.

## Findings

**Соответствует уровню «нарративная связность» (таблица 7):**

- ✅ Эпизодическая связность (events.jsonl)
- ✅ Контекстная связность (SessionAccumulator)
- ✅ Нарративная связность (EpisodicMemory + salience + persona)
- ⚠️ Процессуальная связность — частично:
  - Есть daily consolidator
  - Есть summaries и notes
  - НО: нет full reflection cycle, переписывающего планы

## Связь с главой 3

- **Раздел 3.2.4** (память) — полностью соответствует:
  - Working history → `SessionAccumulator`
  - Summarized.json → `data/adam/summaries/` (consolidator output)
  - Notes.json → `data/adam/notes/`
  - Bio.md → `Agent Adam Chip/About/*.md`
- **Метрика 3.4.3** (память и темпоральная связность) — операционализирует.

## Recommendations for Chapter 3

В разделе 3.2.4 описать многоуровневую структуру с точными именами файлов: `memory.sqlite3` (working) + `summaries/` (consolidation) + `notes/` (selective) + persona-files (permanent). В разделе 3.4.3 — измерять процент турнов, где retrieve вернул релевантные эпизоды.
