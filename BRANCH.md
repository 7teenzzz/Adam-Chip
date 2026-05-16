# Branch: V-S07.2-fix_TTS+UI

**Diverged from:** main @ 86fe6b7
**Goal:** Финальная стабилизация голосового pipeline (TTS/ESP-mic) + UI-доработки + миграция Tuning.json → Config.json
**Status:** experimenting
**Merge target:** main
**Merge conditions:**
- ASR/TTS/ESP-mic pipeline стабилен на длинных сессиях (нет zombie sessions, нет утечек)
- WebUI: статус речевого модуля корректно отображается; tuning-панель работает поверх Config.json
- `Agent Adam Chip/Tuning.json` удалён, все runtime-параметры персоны в `System/Config.json` (секция `tuning`)
- Orchestrator стартует без Tuning.json (smoke test)

**Modified areas:**
- System/Config.json — новая секция `tuning` (зеркало старого Tuning.json), `services.tts.filler_probability`
- System/Config.schema.json — описания новых полей
- System/adam/config.py — DEFAULT_CONFIG с `tuning`
- System/adam/tuning.py — TuningStore backing-store swap (Settings вместо Tuning.json)
- System/Orchestrator.py — filler_probability gate в _filler_task
- System/WebUI/static/js/panels/chat.js — переименование «Слух» → «Статус речевого модуля»
- System/WebUI/static/js/panels/tuning.js — добавлена группа «Филлер» (TTS)
- Agent Adam Chip/Tuning.json — DELETED после миграции
- docs — упоминания Tuning.json убраны (CLAUDE.md root, README.md, AGENT-PROTOCOL.md, Agent Adam Chip/CLAUDE.md, System/adam/CLAUDE.md)

**Global changes:**
- Удаление `Agent Adam Chip/Tuning.json` — все runtime-параметры персоны теперь в Config.json. API `/api/tuning` сохраняется, но backing store — секция `tuning` в Config.json. Существующие WebUI-консюмеры не ломаются.
- TTS filler теперь играет вероятностно (`services.tts.filler_probability`, default 0.30) вместо детерминированного всегда-играет.

**Notes for agents:**
- Backing-store swap: `tuning.py` сохраняет pydantic-модели и API `TuningStore`, но читает/пишет в `Settings.section("tuning")`. Импорты в `episodic.py`, `echoes_gate.py`, `Engineering/consolidator.py` не меняются.
- Filler probability: random.random() < P проверка в `_filler_task` перед playback'ом. P=0.0 == filler disabled de facto.
- При смёрже в main удалить этот файл (`git rm BRANCH.md`).
