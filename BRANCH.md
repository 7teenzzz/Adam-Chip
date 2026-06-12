# Branch: SmartFlora

**Diverged from:** subconscious-symbiont @ 028bea5
**Goal:** Трёхуровневая система управления технофлорой — библиотека пользовательских пресетов, последовательности анимаций, привязка к эмоциям AIIM и страница управления в WebUI.
**Status:** experimenting
**Merge target:** subconscious-symbiont (затем main)
**Merge conditions:**
1. Все три уровня реализованы и работают на железе (пресеты, секвенции, emotion_map)
2. Существующее поведение флоры не сломано (тест: wake_word→accent→attentive→breathe цикл)
3. Системные пресеты (flora.states) не изменяются через новый API
4. WebUI: страница SmartFlora открывается без JS-ошибок

**Modified areas:**
- `BRANCH.md` (этот файл)
- `.planning/phases/37-SmartFlora/` (GSD phase artifacts)
- `System/Config.json` — добавлены `flora.user_presets`, `flora.sequences`, `flora.emotion_map`
- `System/Config.schema.json` — документация новых ключей
- `System/adam/flora.py` — поддержка user_presets, emotion_map, sequence runner (поверх Phase 36)
- `System/Orchestrator.py` — новые API endpoints (preset CRUD, sequences, emotion_map)
- `System/WebUI/static/js/panels/flora.js` — UI: библиотека пресетов, редактор секвенций, emotion map

**Global changes:** да — новые ключи в Config.json (flora.user_presets, flora.sequences, flora.emotion_map); новые API endpoints; push_preset_p2_emotion теперь проверяет emotion_map перед naming convention (backward-compatible).

**Notes for agents:**
- НЕ трогать flora.states в Config.json — это системные пресеты
- user_presets хранятся в flora.user_presets (dict), НЕ в flora.states
- Зарезервированные имена: breathe, accent, attentive, think_pulse, wake_bloom, external, idle
- Секвенции — asyncio-task, отменяется P1/P3 событиями и /api/flora/sequences/stop
- emotion_map optional: если пусто — fallback на naming convention (emotion_a/b)
- push_preset_p2_emotion роутит через push_preset_p2() для соблюдения Phase 36 priority system
- ИНВАРИАНТ: вибро всегда выключено в attentive — не нарушать ни в пресетах, ни в секвенциях
