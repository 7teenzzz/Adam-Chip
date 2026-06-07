# Phase 8: Reply-Echo-Hang debug — устранить заморозку voice_loop после reply window - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

**В скоупе:**
1. Рефактор `reply` mode в `_vad_loop` (`System/Orchestrator.py`): сделать логику reply **идентичной** listening + один таймер 4 сек на silence → standby.
2. Удалить структурную избыточность: дублированный блок accumulation/endpointing (Orchestrator.py:973–987 vs 955–972), второй таймер `reply_absolute_deadline_sec`.
3. Сохранить `_REPLY_GUARD_SEC=0.6` как защитный буфер (на всякий случай — не убирать).
4. Сохранить инвариант `half_duplex_mute=true` (mic заглушается во время TTS).
5. Защита от бесконечной диктовки в reply — через тот же `max_segment_ms` что в listening (не отдельный параметр).
6. Добавить диагностические event-логи переходов `voice_state` и heartbeat loop для отслеживания возможного повторения 6-минутного hang.
7. Cleanup Config.json + Config.schema.json: удалить `services.asr.reply_absolute_deadline_sec`.

**Вне скоупа (отложено):**
- SIGUSR1 → asyncio task stack dump mechanism (полезен но раздувает scope, см. Deferred).
- Расследование акустического эха — гипотеза опровергнута (Адам молчал во время hang).
- Изменение wake word / ASR / VLM / TTS логики.
- Изменение Phase 7 MicReader (стабилен).

**Корневая причина по результату обсуждения:**
ROADMAP исходно фиксировал акустическое эхо как root cause. После проверки логов (Адам **молчал** в момент hang 21:04:15) — гипотеза опровергнута. Новая гипотеза: **избыточность и расхождение `reply` mode с `listening` mode**, плюс отдельный возможный deadlock в voice_loop после `reply_window_expired → standby`.

**Финальные REQ-IDs Phase 8 (зафиксированы в `.planning/REQUIREMENTS.md`):**
- `REQ-NO-HANG-AFTER-REPLY` — voice_loop не замораживается после reply→standby (heartbeat + reaction на wake word).
- `REQ-NO-SELF-ECHO-VAD` — `_REPLY_GUARD_SEC=0.6` сохранён как defence-in-depth; `half_duplex_mute=true` остаётся инвариантом.
- `REQ-REPLY-MATCHES-LISTENING` — reply mode идентичен listening + единственное отличие — таймер silence 4.0 сек → standby; общий `max_segment_ms`; `reply_absolute_deadline_sec` удалён из Config.json+schema.
- `REQ-DIAGNOSTIC-LOGS-VOICE-STATE` — `voice_state_changed` + `voice_loop_heartbeat` события в `_vad_loop`. SIGUSR1 dump deferred.

Исходный `REQ-DIAGNOSTIC-DUMP-ON-DEMAND` из ROADMAP заменён на более конкретный `REQ-DIAGNOSTIC-LOGS-VOICE-STATE` (логи всегда, не on-demand). SIGUSR1 task stack dump on-demand — отдельная фаза.

</domain>

<decisions>
## Implementation Decisions

### Reply mode семантика
- **D-01:** Логика `reply` mode = **identical to `listening`** + единственное отличие: если `speech_ms == 0` дольше **4 секунд** после входа в reply → переход в `standby`. Это полностью убирает «второй режим» с отдельными правилами.
- **D-02:** Защита от бесконечной диктовки в reply — **тот же `max_segment_ms`** (= 9000ms из `media.audio.max_segment_ms`) что и в listening. Отдельный `reply_absolute_deadline_sec` не нужен.
- **D-03:** Reply silence timeout = **4.0 сек** (близко к текущему `reply_window_sec=3.75`, округляем до 4.0).

### Защитный буфер
- **D-04:** `_REPLY_GUARD_SEC = 0.6` **сохранить** даже несмотря на то что эха быть не должно. Пользователь явно потребовал не убирать — буфер защищает от потенциальных будущих сценариев (если когда-нибудь появится акустический контур). Описать его в коде как defence-in-depth, не как echo-suppression.

### Структурная чистка
- **D-05:** Удалить дубликат accumulation/endpointing-ветки в `_vad_loop` (`Orchestrator.py:973–987`). Reply и listening должны идти через **один и тот же** код accumulation. Сейчас listening попадает в свой `if` (955–972), а reply — в `elif effective_voiced` блок (973–987), который почти полностью дублирует listening.
- **D-06:** Удалить из Config.json и Config.schema.json поле `services.asr.reply_absolute_deadline_sec`. Также удалить `self._reply_absolute_deadline_sec` из Orchestrator (`__init__`).
- **D-07:** `reply_window_sec=3.75` → переименовать/задать в Config.json новое имя или оставить `reply_window_sec` со значением `4.0`. Решение по неймингу — на планировщике; ключевое: один таймер, дефолт 4.0 сек.

### Диагностика 6-минутного hang
- **D-08:** Hang **перманентный** (не временный glitch — оркестратор не восстановился сам, пользователь выключил его вручную). Это deadlock или зависшая coroutine, не задержка.
- **D-09:** Добавить детальные диагностические события в `_vad_loop`:
  - `voice_state_changed` на каждом `_set_voice_state` (from → to, reason, timestamp).
  - `voice_loop_heartbeat` периодически (например раз в 5 сек) — чтобы было видно живёт ли loop вообще.
  - Логировать что именно происходит сразу после `reply_window_expired` → `_set_voice_state("standby")` → `continue` (вход в новую итерацию while).
- **D-10:** SIGUSR1 → asyncio task stack dump — **НЕ в этой фазе**. Если после рефактора + логов hang повторится — открыть отдельную фазу под диагностический mechanism.

### Сценарий исследования
- **D-11:** Сначала рефактор + логи. Тестировать в обычном maintenance/exhibition режиме. Если 6-минутный hang **не воспроизводится** — закрываем фазу. Если воспроизводится — анализируем новые логи переходов (`voice_state_changed`, `voice_loop_heartbeat`) и открываем follow-up фазу под точечный фикс с накопленной диагностикой.

### Инвариант, который НЕЛЬЗЯ нарушать
- **D-12:** `half_duplex_mute=true` — mic всегда заглушается во время TTS. Рефактор reply mode не должен это трогать. (CLAUDE.md invariant.)

### Claude's Discretion
- Точный нейминг новых параметров / переименование `reply_window_sec` → решает планировщик.
- Конкретная структура диагностических событий (поля, периодичность heartbeat) → планировщик и executor.
- Внутренняя организация рефактора `_vad_loop` (выделять helper-функцию или править inline) → executor.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope
- `.planning/ROADMAP.md` §Phase 8 — формулировка цели и tentative deliverables (учитывая что эхо-гипотеза опровергнута в этом обсуждении).
- `.planning/STATE.md` — текущий статус (Phase 7 ✓, Phase 8 открыта).
- `.planning/phases/07-esp32-mic-pipeline-refactor-micreader-keep-alive/07-SUMMARY.md` — какой mic stream Phase 8 получает «по наследству» (стабильный, не трогать).

### Code anchors (must-read)
- `System/Orchestrator.py:818–999` — основной `_vad_loop`. Конкретно:
  - 818: инициализация `_was_endpointing`
  - 898–930: блок `if self._voice_state == "reply"` (включая `_REPLY_GUARD_SEC` guard, `reply_window_sec` и `reply_absolute_deadline_sec` логику, `_set_voice_state("standby")` после expired).
  - 932–945: блок listening 3s silence timeout (после wake word).
  - 947–987: accumulation + endpointing — содержит **дубликат** между listening (955–972) и reply (973–987).
  - 988–999: общий блок сабмита segment (drain → ASR).
- `System/Orchestrator.py:119` — `runtime_state["last_tts_finished_at"]` (используется guard window).
- `System/Orchestrator.py:376–423` — инициализация reply-параметров (`_reply_window_sec`, `_reply_absolute_deadline_sec`, `_REPLY_GUARD_SEC`, `_reply_window_expired_action`).
- `System/Orchestrator.py:2691, 2835, 2862, 2881, 2884, 2890–2900` — lifecycle событий `tts_started` / `tts_finished` и обновление `last_tts_finished_at`.

### Config surface
- `System/Config.json` §`services.asr` — поля `reply_window_sec`, `reply_absolute_deadline_sec`, `reply_window_expired_action`, `silence_after_speech_ms`.
- `System/Config.schema.json` §`services.asr` — описания тех же полей. После рефактора `reply_absolute_deadline_sec` удаляется из обоих.
- `System/Config.json` §`media.audio.max_segment_ms` (= 9000) — параметр который теперь применяется к reply тоже (не вводить новый).
- `System/Config.json` §`safety.half_duplex_mute` — инвариант true, не трогать.

### Invariants
- `CLAUDE.md` §«Non-obvious invariants» — особенно п.5 (`half_duplex_mute=true`).
- `CLAUDE.md` §«Gotchas» — про прокси при тестах ESP32 (если будем гонять reply test loop с реальным ESP32 mic).

### Reference symptom (test session)
- ROADMAP Phase 8 §Symptoms — содержит точный timeline session 2026-05-17 00:08:50–00:09:20 с 6-минутной тишиной в `events.jsonl`. Уточнение из обсуждения: в момент hang (21:04:15) Адам **молчал** — TTS не воспроизводился, акустического эха не было.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`event_log.append(...)`** — стандартный механизм событий. Использовать для новых `voice_state_changed` и `voice_loop_heartbeat` без изобретения нового канала.
- **`_set_voice_state(state, reason)`** — единая точка перехода voice_state. Здесь же добавлять `event_log.append("voice_state_changed", ...)`.
- **`time.perf_counter()`** — уже используется по всему loop (`_reply_start`, `_wake_detected_at`, `last_tts_finished_at`). Для heartbeat использовать его же, не `time.time()`.

### Established Patterns
- **Один таймер на режим** — pattern из listening: `elapsed = time.perf_counter() - self._wake_detected_at; if elapsed >= self._wake_silence_timeout_sec: → standby`. Применить тот же шаблон в reply: `if speech_ms == 0 and elapsed >= self._reply_silence_timeout_sec: → standby`.
- **Атомарные `continue` после смены state** — после каждого `_set_voice_state` идёт `continue`. Сохранить.
- **`_was_endpointing` flag** — управляется единственной парой `True/False` ветками. Не дублировать.

### Integration Points
- **WebUI** — `WebUI/chat.js`, `WebUI/wakeMeter.js` уже подписаны на event_log через SSE/poll. Новые события `voice_state_changed` / `voice_loop_heartbeat` могут отображаться в дебаг-панели, но менять UI в этой фазе НЕ нужно (отдельная фаза если понадобится).
- **`scripts/adam_pull_logs.py`** — стандартный CLI для pull events; новые stage-метки нужно учесть (или пропустить — это диагностика, не обязательный stage).
- **`System/adam/api_runtime.py`** `/api/agent/turns`, `/api/agent/events` — UI уже использует. Новые события автоматически попадут.

</code_context>

<specifics>
## Specific Ideas

- **Точная цитата пользователя про reply (зафиксировать в плане):** «правильная логика reply должна быть идентична логике listening, кроме временного ограничения (через 4 секунды после перехода в режим reply, если пользователь не сделал следующий запрос, то переходим в режим standby).»
- **Точная цитата про buffer:** «нужно сохранить `_REPLY_GUARD_SEC=0.6`. убрать дублирование accumulation/endpointing. двойной таймаут — правильная логика (если 4 секунд молчания то переходим в standby, второй таймаут должен работать также как в listening: если пользователь начал говорить запрос, есть максимально возможное окно для запроса — защита от бесконечной диктовки).»
- **Подтверждение про hang:** «в 21:04:15 оркестратор завис, а спустя 6 минут я выключил адама» — то есть hang **перманентный** до ручного выключения. Это не временный glitch и не сам восстановившееся состояние.
- **Подтверждение про эхо:** «в момент когда оркестратор завис ничего не воспроизводилось (адам молчал)» — эхо как root cause опровергнуто, hang случился вне TTS-окна.

</specifics>

<deferred>
## Deferred Ideas

- **SIGUSR1 → asyncio task stack dump mechanism** — диагностический инструмент для будущих hang-исследований. Полезен (общий tool), но раздувает scope текущей фазы. Открыть отдельную фазу если рефактор+логи не вскроют первопричину hang.
- **WebUI отображение `voice_state_changed` в дебаг-панели** — может быть удобно для exhibition мониторинга. Кандидат на UI-фазу.
- **Унификация `max_segment_ms` / `max_command_segment_ms`** — сейчас есть два схожих параметра: `media.audio.max_segment_ms=9000` и `media.audio.max_command_segment_ms=15000`. Их слияние — рефакторинг конфига, не относится к hang-фиксу. В бэклог.
- **Эхо-кэнсэлер / AEC** — если в будущем добавится физический контур speaker↔mic, может понадобиться. Сейчас неактуально (mic+speaker разнесены, TTS играет не во время listening/reply).

</deferred>

---

*Phase: 8-reply-echo-hang-debug-voice-loop-reply-window*
*Context gathered: 2026-05-17*
