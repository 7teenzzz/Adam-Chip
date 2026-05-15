# Adam-Chip — Roadmap

**Project:** Adam Chip — выставочный ИИ-агент на Jetson Orin NX
**Goal:** Поддерживать систему в рабочем, документированном и выставочно-готовом состоянии

---

## Phase 1: Doc Refactor — Концепция C + A

**Goal:** Устранить несоответствия между документацией и кодом; удалить дублирование; ввести Config.schema.json как единый источник истины для параметров; сократить поверхность документации до минимума (Концепция C + элемент A).

**Requires:** Аудит документации выполнен (завершён 2026-05-15)

**Delivers:**

- Исправлены все критические несоответствия (ASR model, wake word params, RUNBOOK)
- CONTEXT.md удалён (содержимое поглощено README.md там, где нужно)
- README.md упрощён: только архитектура и быстрый старт, без числовых параметров
- CLAUDE.md очищен: только инварианты и gotchas, без числовых параметров
- docs/RUNBOOK_JETSON_EXHIBITION.md обновлён: убраны Ollama-defaults, исправлен audio device
- System/Config.schema.json создан с описаниями каждого параметра (элемент A)
- DEFAULT_CONFIG в System/adam/config.py синхронизирован с реальным Config.json

**Mode:** standard

**Requirements:** DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06, DOC-07

**Plans:** 4 plans

Plans:

- [ ] 01-01-PLAN.md — Quick fixes: исправить ASR model, threshold, debounce в CONTEXT.md/README.md; удалить Ollama-defaults из RUNBOOK
- [ ] 01-02-PLAN.md — Config schema: создать System/Config.schema.json с JSON Schema описаниями всех параметров
- [ ] 01-03-PLAN.md — Structural refactor: заменить CONTEXT.md указателем; упростить README.md и CLAUDE.md
- [ ] 01-04-PLAN.md — Code sync: синхронизировать DEFAULT_CONFIG в config.py с Config.json
