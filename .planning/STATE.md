# Adam-Chip — Project State

**Last Updated:** 2026-05-15
**Status:** Planning Phase 2

## Active Phase

### Phase 2: Progressive Disclosure — навигация для нового агента

- Status: Planning
- Goal: Сделать документацию прогрессивно раскрывающейся для нового агента
- Started: 2026-05-15

→ Детали: [ROADMAP.md](.planning/ROADMAP.md) | [REQUIREMENTS.md](.planning/REQUIREMENTS.md)

## Completed Phases

### Phase 1: Doc Refactor — Концепция C + A ✓ COMPLETE (2026-05-15)

Что сделано:

- Исправлены критические несоответствия: ASR model small, wake word threshold 0.20, debounce 2
- CONTEXT.md заменён минимальным указателем (lean docs)
- README.md упрощён: убраны числовые параметры из Inference Stack таблицы
- CLAUDE.md очищен от числовых параметров
- `System/Config.schema.json` создан — JSON Schema Draft-07 с 125 `description` + 108 `default` полями
- `System/adam/config.py` DEFAULT_CONFIG синхронизирован с Config.json
- RUNBOOK очищен от Ollama-defaults и неверного audio device

→ Подробности: [phases/01-doc-refactor-c-a/](phases/01-doc-refactor-c-a/)

## History

- 2026-05-15: Phase 1 завершена. 3 атомарных коммита. Введена Config-First архитектура документации.
- 2026-05-15: Аудит документации выполнен. Найдены критические несоответствия: ASR model (medium vs small), wake word threshold (0.35 vs 0.20), debounce_hits (3 vs 2), RUNBOOK с Ollama-defaults.
