# Requirements — Doc Refactor

## Phase 1

| ID | Requirement |
|----|-------------|
| DOC-01 | Исправить ASR model в CONTEXT.md и README.md: "medium" → "small" |
| DOC-02 | Исправить wake word threshold в CONTEXT.md: 0.35 → 0.20 |
| DOC-03 | Исправить wake word debounce_hits в CONTEXT.md: 3 → 2 |
| DOC-04 | Удалить/переписать устаревшие Ollama-defaults из docs/RUNBOOK_JETSON_EXHIBITION.md; исправить audio input device hw:0,0 → pulse |
| DOC-05 | Создать System/Config.schema.json с JSON Schema описаниями всех параметров Config.json |
| DOC-06 | Синхронизировать DEFAULT_CONFIG в System/adam/config.py с реальными значениями System/Config.json |
| DOC-07 | Удалить CONTEXT.md или свести к указателю; убрать числовые параметры из README.md и CLAUDE.md, которые дублируют Config.json |
