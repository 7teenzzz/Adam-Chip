# System/adam — карта Python-модулей оркестратора

## Правила доступа (обязательно)

- **Config:** только `Settings.load()` или `settings.section("name")` — никогда `DEFAULT_CONFIG` напрямую
- **Сервисы:** только через `inference.py` — не вызывать LLM/TTS/ASR/VLM из других модулей напрямую
- **События:** `events.EventBus` — не `print()`, не `logging.getLogger()`
- **Hot-reload:** `tuning.py` значения читать каждый turn, не кешировать в `__init__`. Backing store — секция `tuning` в `Config.json` (раньше `Agent Adam Chip/Tuning.json`, файл удалён в V-S07.2).

## Модули (23)

→ [graphify-out/GRAPH_REPORT.md](../../graphify-out/GRAPH_REPORT.md) — автогенерируемый граф зависимостей (всегда актуален)

Для граф-запросов в Claude Code:

- `/graphify query "что импортирует inference.py"` — зависимости модуля
- `/graphify path "echoes_gate.py" "EventBus"` — путь между модулями
- `/graphify explain "tuning.py"` — онбординг в незнакомый модуль
