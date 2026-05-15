# Phase 1 Summary: Doc Refactor — Концепция C + A

**Дата завершения:** 2026-05-15

## Что было сделано

- `System/Config.schema.json` — создан с нуля: JSON Schema Draft-07 с 125 `description` + 108 `default` полями для всех параметров Config.json
- `System/adam/config.py` — DEFAULT_CONFIG синхронизирован с реальными значениями Config.json
- `README.md` — удалены числовые параметры из Inference Stack таблицы (дублировали Config.json)
- `CLAUDE.md` — очищен от числовых параметров (threshold, debounce, sample_rate и т.п.)
- `docs/RUNBOOK_JETSON_EXHIBITION.md` — удалены Ollama-defaults; аудио device исправлен (hw:0,0 → pulse)
- `System/CONTEXT.md` — сведён к минимальному указателю (lean docs, без дублирования Config.json)
- Критические несоответствия исправлены: ASR model small, wake word threshold 0.20, debounce_hits 2

## Принципы, введённые в Phase 1

**Config-First** — числовые параметры живут только в `System/Config.json` + `System/Config.schema.json`. Markdown-документы ссылаются на Config, не дублируют значения. Если значение изменилось — меняется только Config.json, документация не устаревает.

**Lean Docs** — документ существует ровно в одном месте. Дублирование устраняется, даже если файл превращается в указатель из одной строки. Устранение дублирования важнее полноты.

## Принятые решения

- `Config.schema.json` = элемент "A" архитектуры C+A: конфиг без аннотаций недостаточен для команды из 4 агентов. Schema читается рядом с Config — никакой отдельной документации параметров не нужно.
- `CONTEXT.md` удалён как самостоятельный документ: содержимое, которое нужно сохранить, поглощено README.md; числовые параметры переехали в Config.schema.json.

## Навигация

- Фазы проекта: [.planning/ROADMAP.md](../../ROADMAP.md)
- Текущее состояние: [.planning/STATE.md](../../STATE.md)
