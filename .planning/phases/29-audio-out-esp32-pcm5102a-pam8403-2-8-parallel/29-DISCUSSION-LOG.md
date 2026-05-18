# Phase 29 — Discussion Log

**Date:** 2026-05-18
**Phase:** 29 — Audio Out на ESP32 динамики (PCM5102A → PAM8403 → 2×8Ω parallel)
**Branch:** `V-S09.1-Audio_out`

---

## Pre-discuss alignment (plan mode)

Перед формальным `/gsd-discuss-phase 29` пользователь и агент уже зафиксировали ключевые инженерные решения в plan-mode (см. `/home/i17jet/.claude/plans/transient-shimmying-rabin.md` approved 2026-05-18). Это сократило discuss-phase до 3 открытых вопросов.

**Что было решено в plan-mode (не пере-обсуждалось):**

1. Топология динамиков: **параллель 8 ∥ 8 = 4 Ω на канал**. Обоснование — datasheet PAM8403 специфицирует 4Ω, серия 16Ω не специфицирована и тише на 3 dB.
2. Аттенюатор PCM5102A→PAM8403: **резистивный делитель 1:6** (R1=10 кОм + R2=2 кОм на канал). Обоснование — PCM5102A line-out 2.1 Vrms × PAM8403 gain ×16 без делителя = hard clip; делитель даёт ~0.35 Vrms на входе.
3. Documentation: краткая заметка про делитель прямо в `29-CONTEXT.md`, без отдельного `29-HARDWARE.md`.
4. Software-cap: `tuning.voice.volume ≤ 1.0` обязателен (динамики 1W RMS, без cap PAM8403 на 4Ω даёт до 1.6 W/динамик).
5. Wave-структура исполнения определена (Wave 1 hardware → Wave 2 cap → Wave 3 loopback → Wave 4 target flip → Wave 5 ramp → Wave 6 self-echo → Wave 7 docs).

## Discuss-phase questions (3 gray areas)

### Q1. Питание PAM8403 (5V)

**Options:**

- Отдельный 5V с LC-фильтром (recommended) — изоляция от спайков PCA9685
- Общая 5V шина с PCA9685/моторами — проще монтаж, риск шума
- Решим по факту в Wave 1

**User answer:** «От понжающего модуля на 5в, сидит на одном питании с есп»

**Decision:** общая 5V ветка через тот же понижающий модуль, что и ESP. В Wave 1 поставить локальный decoupling (100 мкФ электролит + 100 нФ керамика на пинах VDD PAM8403) как первичный демпфер. Если шум всё равно слышен в Wave 3 loopback test — Wave 1 ревизит с разделением веток или LC-фильтром (10–47 мкГн дроссель + 470 мкФ).

### Q2. Стартовый `tuning.voice.volume`

**Options:**

- 0.5 — консервативный
- 0.7 — рабочий базовый (recommended)
- 1.0 — сразу потолок

**User answer:** «0.5 — консервативный старт»

**Decision:** `tuning.voice.volume = 0.5` для первого включения. Ramp 0.5 → 0.7 → 0.85 → 1.0 в Wave 5, на каждой ступени — слушать клиппинг, трогать корпус динамиков.

### Q3. Снизить `tuning.voice.volume.maximum` в Config.schema.json (2.0 → 1.0)?

**Options:**

- Да — опустить до 1.0 (defense-in-depth)
- Нет — оставить 2.0

**User answer:** «Да — опустить до 1.0»

**Decision:** `Config.schema.json` `tuning.voice.volume.maximum: 2.0 → 1.0`. Описание ключа дополнить упоминанием hardware-chain (PCM5102A → делитель 1:6 → PAM8403 → 4Ω нагрузка) и rating динамиков (1W RMS). Это защита от оператора, который мог бы выкрутить slider в UI и сжечь динамики.

## Решения зафиксированы в `29-CONTEXT.md`

См. секции `<decisions>` и `<verify>`. Wave-структура переходит к `/gsd-plan-phase 29`.

## Claude's discretion (locked без вопроса к пользователю)

- **Failover на jetson_hdmi:** оставить документировано в RUNBOOK как процедуру отката (явный config-flip + restart). Стандартная exhibition-практика — не убирать.
- **`post_tts_discard_window_ms`:** оставить 2500, ревалидировать эмпирически в Wave 6 (динамик теперь физически ближе к мик через корпус → возможно лаг изменится).
- **Barge-in на ESP target:** принимаем как V1 limitation, в Deferred — будущая firmware-фаза с `POST :81/api/speaker/stop`.

## Deferred ideas (out of scope, backlog)

- Barge-in для esp32_speaker target (требует firmware-доработки)
- UI tuning slider refresh после смены schema ceiling
- Стерео-эффекты / scene-driven audio cues
- Окружающий звук / эмбиент микс на ESP

---

**Next step:** `/gsd-plan-phase 29` для генерации PLAN.md с 7 волнами.
