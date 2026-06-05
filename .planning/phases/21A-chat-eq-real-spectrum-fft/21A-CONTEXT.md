# Phase 21A: Chat EQ Real Spectrum — реальный FFT в виджете эквалайзера - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Заменить «иллюзию спектра» в виджете эквалайзера на странице чата (`System/WebUI/static/js/widgets/wakeMeter.js`) на реальный частотный спектр FFT, рассчитанный на сервере поверх того же аудио-потока, который слышат OWW/ASR. Передать спектр на фронт через расширение существующего события `audio_level`, отрисовать бары без сглаживания с градиентом цвета по уровню (зелёный → жёлтый → красный) и попутно починить SSE-утечку виджета.

**Что НЕ входит в фазу:**

- Перегруппировка операторского UI (остаётся в Phase 21)
- Настройка silence timeout через UI (остаётся в Phase 21)
- Управление громкостью TTS из UI (остаётся в Phase 21)
- Изменение логики OWW score (циан) и threshold (оранжевый пунктир) — рендерятся как сейчас
- Изменение поведения VU-meter (узкая шкала справа) — он индикатор VU, не спектра
- Web Audio API на клиенте (исключён: будет микрофон ноутбука оператора, не Адама)

</domain>

<decisions>
## Implementation Decisions

### Источник и архитектура FFT

- **D-01:** FFT считается на Jetson (backend), не на клиенте. Источник аудио — тот же буфер `mono_chunk`, который уже идёт в `audioop.rms()` внутри `MicReader._emit_audio_level` ([mic_reader.py:493-527](../../../System/adam/mic_reader.py#L493-L527)). Это гарантирует, что эквалайзер показывает ровно то, что слышит OWW/ASR.
- **D-02:** Web Audio API на клиенте отвергнут: `getUserMedia` возьмёт микрофон оператора, не Адама — будет лгать.

### Формат события

- **D-03:** Расширение существующего `audio_level` опциональным полем `bands: number[24]` (нормализованные [0..1]), а не новое событие `audio_spectrum`. Старые consumer'ы фронта (`vuColorTriplet` в chat.js, settings.js wakeMeter) игнорируют неизвестные поля JSON — backward-совместимо.
- **D-04:** Cadence эмита `audio_level` повышается с 10 Hz (каждый 5-й 20-ms фрейм) до **25 Hz** (каждый 2-й фрейм). Объём `events.jsonl` вырастет в 2.5× — это известная цена. Если в фазе обнаружится, что нагрузка на logging критична, рассмотреть downsampling в `_emit` (writing-side), сохранив SSE-cadence 25 Hz. Решение об этом принимает планировщик.

### Параметры FFT (все в Config.json)

- **D-05:** Число bands = **24**. Параметр `media.audio.spectrum_bands` в Config.json.
- **D-06:** Cadence = **25 Hz**. Параметр `media.audio.spectrum_cadence_hz` в Config.json (для согласованности с переменной cadence `audio_level`).
- **D-07:** Частотный диапазон = **80 Hz – 8000 Hz** (полный до Nyquist при 16 kHz sample_rate). Параметры `media.audio.spectrum_min_hz`, `media.audio.spectrum_max_hz`.
- **D-08:** Шкала bands = **log-частотная** (равные октавы). Каждый бар = одна частотная полоса, рассчитанная как `exp(log(min_hz) + i*(log(max_hz)-log(min_hz))/N)`. Параметр `media.audio.spectrum_scale = "log"` (на будущее, если решим добавить mel/lin — пока единственное значение).
- **D-09:** Нормализация = **dBFS-маппинг**. Pipeline: `mag → 20*log10(mag/MAX) → clamp([floor_db, 0]) → linear remap to [0..1]`. Параметры `media.audio.spectrum_floor_db = -60`, `media.audio.spectrum_ceiling_db = 0`. Пиковая нормализация (rolling-max auto-gain) отвергнута — теряет смысл «красный пик».

### Фронтенд

- **D-10:** Бары рендерятся **без peak-hold, без decay, без wobble**. Значение бара i = последнее пришедшее `bands[i]` из `audio_level`. На тишине бары плоско лежат на дне (или на floor-уровне ≈ 0). Решение пользователя: «максимально честно».
- **D-11:** Цвет бара — градиент по его собственному уровню: **зелёный (0..0.6) → жёлтый (0.6..0.85) → красный (0.85..1.0)**. Границы цветовых зон — параметры в Config.json: `media.audio.spectrum_color_yellow_at`, `media.audio.spectrum_color_red_at` (или эквиваленты). Mic_source в эквалайзере НЕ отражается — он индицируется в соседнем VU-meter и в `Mic:` badge.
- **D-12:** OWW score (циан, decay 0.86) и threshold (оранжевый пунктир) — рисуются как сейчас, без изменений в логике. Сохраняется и draggable-вариант в `settings.js`.
- **D-13:** Удаляются: `EQ_SHAPE` (Gaussian-форма), `audioLevel * 4.0` (magic), `sin(Date.now() * 0.0015 + i*0.85)` wobble, `peaks[i] * 0.87` decay для баров. Все эти строки заменяются прямым чтением `bands[i]` из SSE payload.
- **D-14:** SSE-утечка: `dispose()` в `wakeMeter.js` уже отписывает `subscribeEvents`, но нужно убедиться, что host-panels (`chat.js`, `settings.js`) гарантированно вызывают `dispose()` в cleanup-callback при unmount. Проверить и при необходимости добавить идемпотентность к `dispose()`.

### Конфиг (Config-First) и hot-reload

- **D-15:** Все новые параметры (D-05 — D-09, D-11) идут в `System/Config.json` секцию `media.audio.*` (для FFT-параметров со стороны источника) с описанием в `System/Config.schema.json`. Доступ — только через `settings.section("media").audio` или `Settings.load()` (см. правило в [System/adam/CLAUDE.md](../../../System/adam/CLAUDE.md)).
- **D-16:** Параметры FFT должны быть hot-reloadable — изменение в Config.json без рестарта Orchestrator. Это проверяется в verification.

### Стерео

- **D-17:** Эквалайзер показывает mono-FFT (down-mixed из stereo при `channels=2`). Один визуальный спектр на оба канала — стерео-разделение остаётся в VU-meter рядом. `bands[]` всегда одной длины (mono).

### Claude's Discretion

- Конкретная реализация FFT: numpy `np.fft.rfft` vs scipy. Решение в plan-phase.
- Способ группировки FFT-bins в 24 log-частотных band'а (precomputed binning table, обновляемая при hot-reload параметров): структура и инициализация — на планировщике.
- Конкретные ключи Config.json для границ цветовых зон (один объект `spectrum_color_thresholds: {yellow, red}` или плоские ключи) — на планировщике.
- Решение, ускорять ли все `audio_level` до 25 Hz или эмитить bands только в N-м из M фреймов (т.е. два под-cadence в одном эмиттере), — открыто. Default позиция: ускорить `audio_level` целиком до 25 Hz; пересмотреть если нагрузка на `events.jsonl` критична.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Адам-проект — обязательные документы

- [CLAUDE.md](../../../CLAUDE.md) — инварианты проекта (LLM=чистый русский текст, half_duplex_mute, Config-First, Repository Cleanliness)
- [System/adam/CLAUDE.md](../../../System/adam/CLAUDE.md) — правила доступа: `Settings.load()`/`settings.section()` для Config, `EventBus` для событий, hot-reload через `tuning.py`
- [docs/AGENT-PROTOCOL.md](../../../docs/AGENT-PROTOCOL.md) — поведение агента (Config gap = stop, Branch gap = warn)
- [System/Config.json](../../../System/Config.json) — действующий конфиг с секцией `media.audio.*`
- [System/Config.schema.json](../../../System/Config.schema.json) — JSON-Schema всех параметров, новые ключи должны быть задокументированы здесь

### Затрагиваемые файлы (read-before-plan)

- [System/adam/mic_reader.py](../../../System/adam/mic_reader.py) §`_emit_audio_level` (lines 493-527) — точка эмита `audio_level`, куда добавляется FFT
- [System/adam/events.py](../../../System/adam/events.py) — EventBus + JSONL-лог; пайплайн событий
- [System/WebUI/static/js/widgets/wakeMeter.js](../../../System/WebUI/static/js/widgets/wakeMeter.js) — рефакторится: бары переписываются под `bands[]`, SSE-leak проверяется
- [System/WebUI/static/js/panels/chat.js](../../../System/WebUI/static/js/panels/chat.js) §90-204 — host-панель: подсказка под виджетом обновится, cleanup проверяется
- [System/WebUI/static/js/panels/settings.js](../../../System/WebUI/static/js/panels/settings.js) — draggable-вариант: не должен сломаться, цветовая логика должна работать одинаково в read-only и draggable
- [System/WebUI/static/js/api.js](../../../System/WebUI/static/js/api.js) §`subscribeEvents` — единая обёртка EventSource

### Связь с другими фазами

- [.planning/ROADMAP.md](../../ROADMAP.md) §Phase 21 — UI Rebuild (Phase 21A — её слайс)
- [.planning/ROADMAP.md](../../ROADMAP.md) §Phase 21A — собственная запись с deliverables и requirements

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`MicReader._emit_audio_level`** ([mic_reader.py:493](../../../System/adam/mic_reader.py#L493)) — уже знает: где взять mono PCM (parameter `mono_chunk`), как нормализовать (sqrt-сжатие через `normalize_factor`), как стереть/добавить stereo-поля. FFT встаёт прямо в эту функцию: считаем после `audioop.rms()`, добавляем `bands` в `payload`.
- **`MicReader._level_emit_loop`** — fallback при стоявшем drain (каждые 200 ms). При смене cadence audio_level до 25 Hz логика watchdog не меняется (он сравнивает с `_last_level_emit_t`, не cadence).
- **`EventBus._emit`** ([events.py](../../../System/adam/events.py)) — единая точка публикации SSE. Никаких изменений не требуется: добавляем поле в существующий event type.
- **`subscribeEvents`** в [api.js](../../../System/WebUI/static/js/api.js) — обёртка EventSource. Используется и `wakeMeter` (свой собственный subscribe), и через `state.subscribe('last_events')`. Дублирование осознанное — `wakeMeter` хочет работать на любой панели независимо от host plumbing.

### Established Patterns

- **Config-First:** в системе действует жёсткое правило, см. [CLAUDE.md](../../../CLAUDE.md). Все числовые параметры FFT (24 bands, 25 Hz, -60 dBFS floor, цветовые границы) идут в Config.json + Config.schema.json.
- **Hot-reload через `tuning.py`/`Settings`:** значения читаются каждый turn, не кешируются в `__init__`. FFT-параметры — статические по природе (число bands, частотный диапазон) — но в коде должны читаться лениво на случай hot-reload.
- **EventBus + JSONL:** все события дублируются в `data/adam/events.jsonl`. Удвоение cadence `audio_level` ровно во столько же раз увеличит этот файл — учитывается в emission rotation/sampling если потребуется.
- **Backward-compat SSE payload:** добавление optional-полей в существующий event type — стандартный путь. JS-consumer'ы игнорируют неизвестные ключи в `ev.payload` автоматически.
- **WebSocket нет**: вся live-связь — через SSE (`/api/events`). Это упрощает: bands[] как обычный JSON-массив в payload.

### Integration Points

- **Backend:** одна точка — `MicReader._emit_audio_level`. Cadence-регулятор (счётчик фреймов) уже там — в `_drain_loop`, изменяется одна константа/Config-ключ.
- **Frontend (виджет):** одна точка — `wakeMeter.js` `draw()` функция. Поток `bands[]` приходит в `subscribeEvents → if (ev.type === 'audio_level')` handler, сохраняется в `state.bands`, читается в `draw()` каждый RAF.
- **Frontend (host):** chat.js — обновить только подсказку под виджетом. settings.js — проверить, что draggable не сломался.
- **Config:** новые ключи в `media.audio.*`. Никакого взаимодействия с другими секциями (services, mcu, tuning).

</code_context>

<specifics>
## Specific Ideas

- Пользователь явно потребовал «максимально честно» — это переводится в: бары без сглаживания, dBFS-нормализация (физически верная), log-частотная шкала (отражает реальную природу звука), полный спектр до Nyquist (а не «удобный» voice-range), event-name остаётся `audio_level` (не маскируем правду через отдельный имитирующий event).
- Цветовое решение «зелёный → жёлтый → красный по уровню бара» — пользовательская формулировка «чем сильнее пикует — тем краснее». Это пик-индикатор как у профессиональных VU-meter'ов и сонограмм.
- Mic_source в эквалайзере НЕ дублируется в цвет (пользователь явно отверг этот вариант): пусть «бренный» VU-meter сбоку говорит об источнике, а спектр — только о звуке.

</specifics>

<deferred>
## Deferred Ideas

### Из Phase 21 (UI Rebuild) — НЕ в этой фазе

- Перегруппировка параметров UI по доменным блокам (ESP / Agent / Identity)
- UI-настройка silence timeout (command_endpointing_ms, reply_window_sec)
- Управление громкостью TTS (output device volume)

### Возможные follow-up из обсуждения

- **Sampling логирования audio_level в jsonl.** Если 25 Hz × подробный payload (bands[24]) окажется тяжёлым для `events.jsonl`, добавить writing-side sampler (например, в `events.py`: писать в файл каждое N-е событие data-type'ов high-frequency). SSE-cadence остаётся 25 Hz. — в backlog.
- **Mel-шкала или полосы по формантам речи.** Текущее решение — log-частотная. Если визуально не зайдёт — в backlog.
- **Спектрограмма-водопад (waterfall) вместо bars.** Альтернативный вид. Не входит в Phase 21A, может стать отдельной фазой.
- **Per-channel FFT (отдельный спектр L/R).** Стерео-источник есть, но визуальное решение mono. Можно расширить в будущем — backlog.

</deferred>

---

*Phase: 21A-Chat EQ Real Spectrum*
*Context gathered: 2026-05-18*
