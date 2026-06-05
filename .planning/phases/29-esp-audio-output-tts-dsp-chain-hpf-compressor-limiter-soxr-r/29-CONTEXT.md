# Phase 29: ESP Audio Output — TTS DSP chain - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Программная DSP-цепочка обработки TTS-аудио (голос Адама, Silero v5_5_ru, 24000 Гц моно) **перед отправкой на ESP32-спикеры** (2× MAX98357A стерео), чтобы звучало **громче и чище** на маломощных динамиках (3 Вт, 200 Гц–20 кГц, 4 Ом, питание 3.3 В) — без клиппинга.

Хук — в существующий путь отправки TTS на ESP (не realtime, офлайн-обработка WAV каждого предложения). Все параметры — в Config.json + Config.schema.json, hot-reload как `tuning.voice.volume`.

**Слайс 1 (сделан, commit `2b27ac3`):** `services.tts.output_target` → `esp32_speaker`, route TTS на ESP `/speaker`, надёжность воспроизведения 100% подтверждена.

**Эта фаза = слайс 2:** DSP-цепочка.

**In scope:** high-pass фильтр, soxr-ресемпл (замена `audioop.ratecv`), брикуолл-лимитер, фиксированный makeup-gain, soft-knee компрессор, presence-EQ ~3 кГц. Всё параметризовано в Config.

**Out of scope (не трогать):** UI-управление громкостью TTS (это Phase 21); миграция питания усилителей на 5 В (deferred, железо); перевод firmware speaker на 48 кГц (deferred); инвариант `half_duplex_mute=true` и `_REPLY_GUARD_SEC=0.6` — НЕ менять.
</domain>

<decisions>
## Implementation Decisions

### Этапность внедрения
- **D-01:** Внедрять в **2 отдельных плана/коммита, слушать между ними.** Не всё сразу — чтобы понимать, что именно дало эффект.
- **D-02:** **Этап A** = HPF + soxr-ресемпл + лимитер + фиксированный makeup-gain. Безопасные победы, без подбора на вкус.
- **D-03:** **Этап A enabled по умолчанию** при лендинге — следующий запуск оркестратора уже звучит чище/громче с гарантией нуля клиппинга.
- **D-04:** **Этап B** = soft-knee компрессор + presence-EQ. Тюнинг на слух через hot-reload после прослушки Этапа A.

### Характер громкости
- **D-05:** Компрессия **мягкая/естественная**: ratio ~2:1, soft knee. Сохранить живость голоса, минимум окраски. Не «broadcast». Всегда можно поднять hot-reload'ом, если на 3.3 В не хватит громкости.

### Стабильность уровня между фразами
- **D-06:** **Фиксированный порог/gain, БЕЗ пофразной нормализации.** TTS идёт пофразно; пофразная нормализация дала бы «накачку»/пыхтение между предложениями. Silero ровный по уровню сам по себе.
- **D-07 (сводимость с D-02):** Поскольку выбран фикс-gain, в Этапе A **пик-нормализация НЕ применяется** — вместо неё фиксированный makeup-gain + лимитер. Лимитер (~−1 dBFS) гарантирует ноль клиппинга независимо от уровня входа.

### Presence-EQ
- **D-08:** Presence-EQ (лёгкий +2–3 дБ ~3 кГц) **включить в Этап B**, toggle-флагом. Мелкие динамики (нижний срез 200 Гц) реально выигрывают в разборчивости. Если после компрессии разборчивости достаточно — отключить флагом.

### Claude's Discretion
- Точные дефолтные значения параметров (частота HPF в районе 180 Гц, порог компрессора, attack/release, makeup в дБ, потолок лимитера ~−1 dBFS, частота/Q/гейн presence-EQ) — на усмотрение Claude, выставить консервативно, далее подстройка на слух. Все обязаны быть в Config.json (Config-First).
- Структура ключей в Config.json (отдельная секция, напр. `tuning.voice.dsp` или `services.tts.dsp`) — на усмотрение, по аналогии с существующими паттернами.
- Замена `audioop.ratecv` на soxr в `_prepare_wav_for_esp32_speaker` — реализационная деталь.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Hook points (где живёт обработка)
- `System/Orchestrator.py` — `_apply_wav_volume` (def ~line 172; вызовы в `_stream_llm_and_speak` ~2793/2844). Нынешний `audioop.mul` делает **hard-clip** — его заменяет цепочка с лимитером. Точка применения volume gain.
- `System/adam/inference.py` — `_prepare_wav_for_esp32_speaker` (~line 75; `audioop.ratecv` 24k→44.1k на ~line 90). Сюда вставляется soxr-ресемпл. `_play_wav_bytes_to_esp32_sync` (~line 348) — отправка на ESP, дисциплина «одна фраза → ждать проигрывания».

### Config (Config-First — обязательно)
- `System/Config.json` + `System/Config.schema.json` — все DSP-параметры сюда, hot-reload как `tuning.voice.volume`.
- `System/adam/tuning.py` — pydantic-модель `voice` (volume Field). Паттерн для DSP-параметров.

### Инварианты / ограничения
- `System/CLAUDE.md` (gotchas: аудио-устройства, ESP IP, half-duplex), `.planning/REQUIREMENTS.md` — REQ-NO-SELF-ECHO-VAD (`_REPLY_GUARD_SEC=0.6`), `half_duplex_mute=true` инвариант. Громче голос → сильнее самоэхо в ESP-микрофон, эти защиты остаются.
- `BRANCH.md` (ветка ESP-Audio-Out) — находки слайса 1: overflow=benign backpressure, дисциплина воспроизведения, восстановление `:81`, потолок 3.3 В ~1.4 Вт.

### Hardware
- Динамики: 3 Вт, 200 Гц–20 кГц, 65 дБ, 4 Ом. Питание усилителей сейчас 3.3 В (потолок ~1.4 Вт) — определяет, что software-громкость >потолка только клиппит; реальный запас = 5 В (deferred).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_apply_wav_volume(wav, gain)` — уже парсит WAV, находит data-chunk, применяет gain через audioop, fail-safe (возвращает вход при ошибке). Расширяется до полной цепочки; fail-safe паттерн сохранить — TTS никогда не должен замолкать из-за бага в DSP.
- `tuning_store` + `_current_volume()` hot-reload паттерн (Orchestrator.py ~2684) — DSP-параметры читать так же, per-turn/per-chunk.
- venv: `numpy`, `scipy`, `soxr`, `librosa` уже установлены — новых зависимостей не нужно.

### Established Patterns
- Config-First: числовые параметры только в Config.json + schema, env-override через `ADAM_CONFIG_OVERRIDE`.
- Fail-safe в аудио-пути: при любой ошибке обработки вернуть исходный сигнал, не молчание.

### Integration Points
- Обработка применяется офлайн к WAV каждого предложения в `_stream_llm_and_speak` ДО `_prepare_wav_for_esp32_speaker`/отправки. Задержка ~единицы мс на Jetson, на пайплайн не влияет.
- soxr-ресемпл заменяет `audioop.ratecv` только в ESP-пути (`_prepare_wav_for_esp32_speaker`); HDMI-путь (`output_target=jetson_hdmi`) этот ресемпл не использует.
</code_context>

<specifics>
## Specific Ideas

- Цепочка (порядок): `Silero 24k → HPF ~180Hz → [Этап B: компрессор soft-knee → presence-EQ] → makeup gain → лимитер −1dBFS → soxr 24k→44.1k → ESP`.
- Тестовая оснастка слайса 1 для прослушки «до/после» (не в репо): `/tmp/esp_send_throttled.py`, `/tmp/esp_repeat_test.py`. TTS для теста: `PYTHONPATH=System ./.venv/bin/python -m Speech.TTS` (порт 8082, `/wav` отдаёт сырой WAV).
- Verify Этапа A: на слух (чище, без клиппинга) + метрика «пик ≤ −1 dBFS гарантирован лимитером» + надёжность воспроизведения не деградировала (3/3 как в слайсе 1).
</specifics>

<deferred>
## Deferred Ideas

- **Миграция питания усилителей на 5 В** — реальный потолок громкости (3.3 В ≈ 1.4 Вт). Железо, не софт. Пользователь отложил.
- **Firmware speaker → 48 кГц** — тогда 24k→48k ровно ×2, самый чистый апсемпл. Правка I2S-тактирования в прошивке, отдельно.
- **Агрессивная/broadcast компрессия** — если мягкой не хватит на 3.3 В, поднять ratio/makeup hot-reload'ом (не отдельная фаза, просто тюнинг).

### Reviewed Todos (not folded)
- `fix-esp32-stream-drain-during-mute.md` (todo match score 0.4) — про закрытие ESP audio-стрима во время mute (mic-сторона/drain task), НЕ про TTS-вывод DSP. Вне scope этой фазы (касается захвата звука, а не воспроизведения). Оставлен в бэклоге.
</deferred>

---

*Phase: 29-esp-audio-output-tts-dsp-chain*
*Context gathered: 2026-06-01*
