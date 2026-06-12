# Phase 37 — SmartFlora: Управление технофлорой

**Ветка:** SmartFlora  
**Статус:** in-progress  
**Дата начала:** 2026-06-12

## Цель

Превратить технофлору из набора жёстко прошитых пресетов в управляемую трёхуровневую систему:
1. **Библиотека пользовательских пресетов** — CRUD через API + UI, на основе существующих пресетов
2. **Последовательности (sequences)** — цепочки пресетов с таймингом, средний уровень программирования состояний
3. **Привязка к эмоциям AIIM** — явный emotion_map вместо naming convention, редактируется из UI

## Контекст

- Phase 35 (ultimate-integration) завершила систему приоритетов P1/P2/P3 и RMS speech sync
- Текущий FloraController уже работает как event consumer
- Системные пресеты живут в flora.states (Config.json) — readonly
- Образец для CRUD: аудио-пресеты в api_runtime.py + AudioInputTuning pydantic model

## Решения (D-)

**D-01: Хранилище user_presets**
Отдельный dict `flora.user_presets` в Config.json, НЕ в flora.states.
Причина: не смешивать системные и пользовательские пресеты; проще CRUD без риска затереть системные.

**D-02: Обращение к пресету в _build_params**
Приоритет: flora.states → flora.user_presets → {}.
Причина: системные пресеты неизменны из API, но пользовательские могут переопределять их имена нежелательно — поэтому states первее (защита от shadowing системных имён).
Wait, обратно: states первее означает что пользователь НЕ может shadow системный пресет даже случайно — правильно.

**D-03: Зарезервированные имена**
SYSTEM_PRESET_NAMES = {breathe, accent, attentive, think_pulse, wake_bloom, external, idle}
API отклоняет user preset с таким именем (409 Conflict).

**D-04: Структура шага последовательности**
`{preset: str, hold_ms: int, crossfade_ms?: int}`
crossfade_ms optional — если не указан, берётся глобальный flora.crossfade_ms.

**D-05: Секвенции как asyncio Task**
FloraController._sequence_task: asyncio.Task | None
Отменяется в _handle() при wake_word_detected, voice_state_change(to=listening|standby).
Явная остановка: новый метод stop_sequence() → API POST /api/flora/sequences/stop.

**D-06: emotion_map — optional override**
flora.emotion_map: dict[str, str] (emotion → preset_name)
Если ключ отсутствует или пуст → fallback на naming convention (emotion_a / emotion_b).
Intensity routing остаётся: если emotion_map задаёт конкретный пресет без варианта — он используется для любой интенсивности.

**D-07: API в Orchestrator.py**
Новые endpoints добавляются напрямую в Orchestrator.py рядом с существующими flora endpoints (не в api_runtime.py, чтобы иметь прямой доступ к flora_controller глобалу).

## Файлы изменений (этот агент)

- `BRANCH.md` ✓
- `.planning/phases/37-SmartFlora/37-CONTEXT.md` (этот файл) ✓
- `System/Config.json` — flora.user_presets, flora.sequences, flora.emotion_map
- `System/Config.schema.json` — документация новых секций
- `System/adam/flora.py` — user_presets в _build_params + push_preset, emotion_map lookup, sequence runner
- `System/Orchestrator.py` — 12 новых endpoints
- `System/WebUI/static/js/panels/flora.js` — 3 новых секции UI

## Ограничения

- peak_pct/base_pct в user_presets подчиняются flora.max_duty_pct (глобальный потолок 71%)
- Вибро ВСЕГДА выключено в attentive — это инвариант, нельзя нарушать ни в одном пресете/секвенции
- Секвенции не запускаются если P3 pipeline активен (отменяются немедленно при P3 событии)
