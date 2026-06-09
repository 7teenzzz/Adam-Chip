# Branch: ultimate-integration-v2

**Diverged from:** main (after ultimate-integration merge)
**Goal:** Интегрировать Dynamic AIIM в ветку-кандидат — добавить живую идентичность Адама поверх полного интеграционного стека.
**Status:** in-progress
**Merge target:** main
**Phase:** 35 — Dynamic AIIM integration

**Интегрированные ветки:**

1. `LuxFlora-modes_V1.2` — аппаратный ремап каналов (вибро 0-3 / свет 4-14) ✓
2. `origin/MemoryFixes` — фикс Echoes/Chinese gate + тесты памяти ✓
3. `origin/Extra` — Skills: шутки + погода (pre-LLM провайдеры) ✓
4. `dynamic-aiim` — Dynamic AIIM: [ctx.identity], identity.py, identity_drift.py ✓

**Merge conditions:**

1. Все ветки влиты без регрессий
2. `[ctx.identity]` инжектируется без эха меток в LLM-ответах
3. `[ctx.weather]` и `[ctx.identity]` сосуществуют в prompt.py
4. Python синтаксис чистый, JSON валидный
5. Unit-тесты identity зелёные

**Global changes:** ДА — новые модули identity.py + identity_drift.py, Config.json (identity tuning), prompt.py (два новых ctx-блока).

**Notes:**
- `input_device` = `pulse` (PipeWire, Phase 32) — НЕ менять на plughw
- `scene_worker_enabled` = `false` — VILA контейнер не включается по умолчанию
- ESP firmware требует перепрошивки под новые channel masks (vibro 0-3 / light 4-14)
