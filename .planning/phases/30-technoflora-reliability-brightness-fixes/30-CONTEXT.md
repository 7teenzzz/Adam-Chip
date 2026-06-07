# Phase 30: Technoflora Reliability & Brightness Fixes - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning
**Source:** debug session `.planning/debug/flora-stops-on-state-change.md` + remaining-bug analysis R1–R9

<domain>
## Phase Boundary

Закрыть **оставшиеся** баги технофлоры (R1–R9) после фикса погасания. Фикс
погасания уже применён (Parts A/B/C в debug-сессии: I2C-мьютекс, External-режим,
развод легаси action-слоя — НЕ переделывать). Эта фаза — про надёжность краёв
(barge-in, watchdog, калибровочный скрипт) и яркость (двойная гамма → сырой PWM +
safe-ceiling).

**В scope:** R1–R9 + параметр `flora.max_duty_pct` (safe-ceiling).
**Вне scope:** страница настроек технофлоры (WebUI — отдельная фаза); реализация
listening-mic-RMS и гетерогенного think_pulse (это pending-фичи, не баги).
</domain>

<decisions>
## Implementation Decisions

### Яркость / гамма (R5)
- **D-01:** **Вариант A — сырой PWM, без перцептивной гаммы.** `duty = round(4095 ×
  pct/100)`. «70%» = 2867 PWM. Подписи параметров = сырой PWM-сигнал (мысленная
  модель пользователя «70% = сигнал PWM»). Устранить ДВОЙНОЕ применение:
  сейчас Jetson `flora.py` делает `base_duty = value_max × pct/100` (linear) И
  firmware `gammaApply` применяет гамму ещё раз. После фикса гамма-перевода быть
  не должно ни на одной стороне (или ровно один линейный перевод %→duty).
- **D-02:** Убрать/обойти firmware `gammaApply` (FloraModule.cpp) и LUT — либо
  гамма = 1.0 (LUT становится линейным), либо прямой проход без LUT. Решение по
  реализации — за planner, но РЕЗУЛЬТАТ: `pct → duty` линейно, один раз.

### Safe-ceiling (R5b / Q2)
- **D-03:** Новый Config-параметр `flora.max_duty_pct` (в сыром PWM, 0–100).
  Глобальный потолок: КАЖДАЯ запись флоры в каналы (Jetson `set_channels`/RMS-стрим
  + firmware `writeAllChannelsRaw` в floraTick) клампится к `max_duty = 4095 ×
  max_duty_pct/100`. Defence-in-depth на обеих сторонах. Config-First (+ схема).
  Страница настроек — позже, отдельной фазой.

### Надёжность краёв
- **D-04 (R1):** Калибровочный скрипт `flora_line_identify.py` ДОЛЖЕН перевести
  флору в `enabled=false` на время прогона (POST `/api/flora/state {"state":"...",
  "enabled":false}`) и гарантированно вернуть `enabled=true` в конце И в обработчике
  Ctrl+C/cleanup. `external` НЕ годится: паузы между каналами (TTS-анонс) > watchdog
  500 мс → firmware уходит в breathe и снова дерётся. `enabled=false` глушит
  floraTask без watchdog.
- **D-05 (R2):** `flora.py::_on_answer_end` — добавить guard `if not
  self._answer_active: return` в начале. Иначе поздний `tts_finished` после barge-in
  перетрёт пост-barge-in состояние (accent/attentive) на breathe.
- **D-06 (R3):** Деградированный `/speak`-путь (TTS без экспонирования WAV) не должен
  показывать breathe во время ответа. Реализация на усмотрение planner: либо
  `_on_answer_start` различает streaming vs `/speak` и для `/speak` ставит
  steady-плато (как раньше attentive), либо External-watchdog для answer-state
  оседает в плато, не в breathe. Цель: во время речи Адама свет НЕ «дышит».
- **D-07 (R4):** External-watchdog не должен срабатывать преждевременно между
  `tts_started` и первым RMS-кадром. Решение: рефреш `lastExternalPcaWriteMs` на
  `tts_started` (firmware уже рефрешит при входе в External — проверить достаточность)
  и/или `external_timeout_ms` с запасом. Не ломать авто-recovery при реальном обрыве.

### Прочее
- **D-08 (R6):** idle-пресет не должен читаться как «выключено». После D-01 (без
  гаммы) idle base/peak станут видимее; дополнительно — поднять базу idle ИЛИ при
  простое оседать в `breathe` (не `idle`). Решение — planner.
- **D-09 (R7):** `/api/agent/scene` (Orchestrator) и manual `/api/pca9685/*` (raw
  endpoints) — пока флора `enabled`, ручные записи дерутся с floraTask. Загейтить за
  `flora.enabled==false` ИЛИ ввести явный override (например авто-`enabled=false` на
  время manual-записи). Минор; не ломать maintenance-доступ.
- **D-10 (R8):** `enabled=false` без recovery не должен оставить флору тёмной при
  сбое. Минимум: гарантия re-enable в скрипте (D-04). Опц.: firmware-таймаут на
  disabled→re-enable. Решение — planner (минимальное достаточно).
- **D-11 (R9):** `flora.py feed_speech_wav` — вынести `_rms_envelope` в
  `asyncio.to_thread` (или предрасчёт), чтобы не блокировать event-loop. Минор.

### Claude's Discretion
- Точная реализация D-02 (gamma=1.0 LUT vs прямой проход), D-06, D-08 — planner.
- Приоритет/волны: R1/R2 — блокеры (R1 разблокирует тест линий); R5/safe-ceiling —
  средний; R3/R4/R6 — край; R7/R8/R9 — минор.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Debug-анализ (источник истины по багам)
- `.planning/debug/flora-stops-on-state-change.md` — root cause + Parts A/B/C
  (УЖЕ применены), confirmed conflicts C1–C7, и контекст для R1–R9.

### Затрагиваемый код
- `Subsystem/AdamsServer/src/io/FloraModule.cpp` — `gammaApply`/`buildGammaLut`
  (R5/D-02), `kPresetDefaults` idle (R6/D-08), `floraTick` (clamp/D-03), External
  watchdog (R4/D-07).
- `Subsystem/AdamsServer/config/AdamsConfig.h` — `kFloraGamma`, idle defaults,
  `kFloraExternalTimeoutMs`.
- `System/adam/flora.py` — `_build_params` (pct→duty, R5/D-02), `_on_answer_start`
  (R3/D-06), `_on_answer_end` (R2/D-05), `feed_speech_wav`/`_rms_envelope` (R9/D-11),
  `_envelope_to_duties`/`_rms_stream` (safe-ceiling clamp D-03).
- `System/Orchestrator.py` — `/api/agent/scene` (R7/D-09).
- `Subsystem/AdamsServer/src/web/WebServerModule.cpp` — `/api/pca9685/*` raw
  handlers (R7/D-09).
- `scripts/diagnostics/flora_line_identify.py` — enabled=false wrap (R1/D-04).
- `System/Config.json` + `System/Config.schema.json` — `flora.max_duty_pct` (D-03).

### Конвенции
- `CLAUDE.md` — Config-First; `_NO_PROXY_OPENER` для ESP HTTP; firmware = PlatformIO
  (`pio run`, не pip); не менять IP/порты; инварианты (LLM=plain text,
  half_duplex_mute). Firmware-верификация hardware-gated (ручной флэш).
- `.planning/ROADMAP.md` §Phase 30 — границы + FFIX-01..10.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets / patterns
- I2C-мьютекс `i2cBusLock/Unlock` (Pca9685Module.cpp) — уже есть; safe-ceiling clamp
  в floraTick встаёт перед `writeAllChannelsRaw`.
- `FloraParams.enabled` + `sFloraEnabled` + handler-parse `enabled` — уже есть (Part
  B); R1 (скрипт) и R7 (gate) переиспользуют этот путь.
- `_build_params` уже переводит `*_pct → *_duty` линейно — R5/D-02 это и есть «один
  линейный перевод»; нужно убрать ВТОРОЙ (firmware gamma).
- `MCUClient.set_flora_state` / `set_channels` — единственный путь к ESP, через
  `_NO_PROXY_OPENER`.

### Integration Points
- Safe-ceiling: два места клампа — `flora.py` (_envelope_to_duties + _build_params +
  _rms_stream) и firmware `floraTick`/`writeAllChannelsRaw`.
- Firmware-изменения → требуют `pio run` + ручной флэш + on-HW проверку.
</code_context>

<specifics>
## Specific Ideas

- Parts A/B/C из debug-сессии — УЖЕ в рабочем дереве (uncommitted). Эта фаза НЕ
  переделывает их; строит поверх.
- Приоритет реализации: R1 (разблокирует тест линий) и R2 — первыми.
- После R5 (без гаммы) перепроверить стартовые значения `breathe` 7/71/4000 на
  железе — они задумывались под перцептив; в сыром PWM могут читаться иначе.
</specifics>

<deferred>
## Deferred Ideas

- Страница настроек технофлоры (WebUI) — отдельная фаза (UI-фича).
- listening по RMS голоса зрителя (решение #3) — pending-фича, не баг.
- think_pulse гетерогенный (волны+мерцание по линиям) — ждёт калибровки линий
  (29-CHANNEL-MAP.md), pending-фича.

### Reviewed Todos (not folded)
None.
</deferred>

---

*Phase: 30-technoflora-reliability-brightness-fixes*
*Context gathered: 2026-06-07*
