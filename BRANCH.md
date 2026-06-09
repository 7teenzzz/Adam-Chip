# Branch: ultimate-integration

**Diverged from:** `vlr-main-integrated` (43b7f2f)
**Goal:** Интегрировать все параллельные потоки работ в единую ветку — кандидат на мёрдж в main.
**Status:** in-progress
**Merge target:** main
**Phase:** 35 — см. `.planning/phases/35-ultimate-integration/35-PLAN.md`

**Интегрируемые ветки (пофазно):**
1. `LuxFlora-modes_V1.2` — аппаратный ремап каналов (вибро 0-3 / свет 4-14) ✓
2. `origin/MemoryFixes` — фикс Echoes/Chinese gate + тесты памяти
3. `origin/Extra` — Skills: шутки + погода (pre-LLM провайдеры)

**Merge conditions:**
1. Все три ветки влиты без регрессий
2. Channel map прошивки (AdamsConfig.h) = Config.json = flora.py — консистентно
3. Python синтаксис чистый, JSON валидный
4. `/gsd-debug` проверка пройдена
5. Knowledge graph обновлён (`graphify update System/`)

**Global changes:** ДА — firmware (reflash обязателен после LuxFlora), Config.json (каналы, параметры), новые модули skills.py + asr_filter.py.

**Notes:**
- `input_device` = `pulse` (PipeWire, Phase 32) — НЕ менять на plughw
- `scene_worker_enabled` = `false` — VILA контейнер не включается по умолчанию
- ESP firmware требует перепрошивки под новые channel masks (vibro 0-3 / light 4-14)
