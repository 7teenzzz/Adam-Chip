# Branch: subconscious-symbiont

**Diverged from:** ultimate-integration-v2
**Goal:** Переосмысление Cosmos Reason2-2B как визуального подсознания симбионта Адама — нарратив + архитектурное решение.
**Status:** in-progress
**Merge target:** ultimate-integration-v2 (затем main)

**Что изменено:**

- `Agent-Adam-Chip/About/Lore.md` — добавлен раздел "Зрение": симбионт видит раньше, чем Adam осмысляет; первое лицо, согласовано с существующим лором про симбионт-в-технофлоре
- `Agent-Adam-Chip/About/System.md` — `[ctx.vision]` переформулирован с "служебная телеметрия" на "поток от симбионта, который обрабатывает пространство раньше тебя"
- `.planning/STATE.md` — зафиксировано архитектурное решение (Cosmos locked, 759ms vs 1135ms Gemma) + roadmap Cosmos-агента (Phase A→B→C)
- `System/WebUI/static/js/panels/camera.js` — fix: stale `clearJetTimer` ref (удалён после MJPEG-миграции)

**Merge conditions:**

1. Smoke-test: перезапуск оркестратора, убедиться что `[ctx.vision]` попадает в промпт с новой формулировкой
2. Нарратив согласован с AIIM (симбионт уже упомянут в Lore — здесь его визуальный аспект)
3. Изменения только в persona/planning файлах — нет рисков для inference pipeline

**Global changes:** НЕТ — только persona MD-файлы и planning artifacts.

**Roadmap Cosmos-агента (backlog, не в этой ветке):**

- Phase A: Cosmos → EventBus (заметил изменение сцены → событие, Adam реагирует)
- Phase B: Cosmos управляет частотой съёмки адаптивно
- Phase C: Cosmos с собственным эмоциональным состоянием, независимым от Adam
