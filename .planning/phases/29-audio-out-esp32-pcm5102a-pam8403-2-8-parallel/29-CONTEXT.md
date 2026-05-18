# Phase 29 — Audio Out на ESP32 динамики (PCM5102A → PAM8403 → 2×8Ω parallel)

**Date:** 2026-05-18
**Branch:** `V-S09.1-Audio_out`
**Goal (from ROADMAP):** перевести голос Адама с HDMI Jetson на динамики, физически живущие в корпусе персонажа, через PAM8403 + PCM5102A I2S DAC, с параллельной парой 8Ω-динамиков на каждом канале.

---

<domain>

**Что фаза делает:** включает в production уже-написанный софтверный маршрут TTS → ESP32 `/speaker` endpoint + первый раз монтирует и калибрует hardware-цепочку PCM5102A → резистивный делитель → PAM8403 → 2 параллельных динамика на канал.

**Что фаза НЕ делает:**

- Не пишет новый Python/C++ код для TTS-маршрута — `_play_wav_bytes_to_esp32_sync` уже существует (см. `<code_context>`)
- Не модифицирует ESP firmware (PCM5102A init, `/speaker` handler — готовы)
- Не добавляет фоновые звуки / эмбиент / системные нотификации — только основной TTS Адама
- Не решает barge-in проблему (см. `<deferred>`)

</domain>

<canonical_refs>

**MUST read before planning:**

- `.planning/ROADMAP.md` — Phase 29 entry в активном milestone
- `BRANCH.md` (корень repo) — цель ветки V-S09.1-Audio_out
- `System/adam/inference.py:348-404` — `_play_wav_bytes_to_esp32_sync` (готовая функция отправки на ESP)
- `System/adam/inference.py:406-413` — комментарий про barge-in limitation на ESP32 target
- `System/Config.json` — `services.tts.output_target`, `mcu.speaker_url`, `tuning.voice.volume`
- `System/Config.schema.json` — описание этих ключей
- `Subsystem/AdamsServer/src/AudioModule.cpp` — PCM5102A I2S init, `initSpeakerPlayback()` ~line 343
- `Subsystem/AdamsServer/src/WebServerModule.cpp` — `/speaker` endpoint на port 81
- `Subsystem/AdamsServer/include/AdamsConfig.h` — `kSpeakerSampleRate = 44100`
- `Subsystem/AdamsServer/include/PinsConfig.h` — I2S pins (BCLK=GPIO38, LRCK=GPIO39, DATA=GPIO40)
- `docs/RUNBOOK_JETSON_EXHIBITION.md` — здесь добавится секция «Аудио-маршрут»
- `CLAUDE.md` § Gotchas — `_NO_PROXY_OPENER`, аудио устройства, ESP32 IP
- PAM8403 datasheet (Diodes DS36439 Rev 1.3) — https://www.diodes.com/assets/Datasheets/PAM8403.pdf
- PCM5102A datasheet (Texas Instruments) — https://www.ti.com/lit/ds/symlink/pcm5102a.pdf

</canonical_refs>

<code_context>

**Reusable assets уже готовые (не дублировать в плане):**

- `System/adam/inference.py:_play_wav_bytes_to_esp32_sync` — берёт WAV-байты, ресемплирует через `_prepare_wav_for_esp32_speaker` 24000→44100 mono 16-bit, POST на `mcu.speaker_url`, блокирует на `duration_sec - elapsed` для синхронизации «TTS finished» с реальным окончанием I2S DMA
- `System/adam/inference.py:_NO_PROXY_OPENER` — bypass v2ray прокси для ESP-запросов
- `Subsystem/AdamsServer/src/AudioModule.cpp:initSpeakerPlayback()` — настраивает I2S_NUM_1 в Philips I2S mode, 16-bit, stereo, выдаёт mono → L=R на DAC
- `Subsystem/AdamsServer/src/WebServerModule.cpp:/speaker handler` — валидирует WAV header (`sampleRate != kSpeakerSampleRate` → HTTP 400), кладёт PCM в ring buffer для I2S DMA

**Конфиг ключи (существуют, будут изменены/использованы):**

- `services.tts.output_target` — текущее `"jetson_hdmi"` → переключим на `"esp32_speaker"` в Wave 4 (требует рестарт `adam-orchestrator.service`, не hot-reload — читается в `Inference.__init__`)
- `services.tts.output_device` — игнорируется когда target=esp32_speaker
- `mcu.speaker_url` — `http://10.10.10.171:81/speaker` (уже корректен)
- `tuning.voice.volume` — текущее 1.1 → стартуем с 0.5, ramp в Wave 5
- `safety.half_duplex_mute` — `true`, остаётся обязательным
- `services.asr.post_tts_discard_window_ms` — 2500, проверим в Wave 6, возможно поднимем из-за физической близости динамика к мик

</code_context>

<decisions>

### Hardware topology

- **Динамики:** параллельная пара `8 ∥ 8 = 4 Ω` на каждый канал (4 × 1W 2209). PAM8403 datasheet специфицирует 4Ω как минимум; на 4Ω при 5V даёт до 3.2 W/канал → 1.6 W на каждый параллельный 8Ω-динамик. **Software-cap `tuning.voice.volume ≤ 1.0` обязателен** иначе rating 1W превышен. Серия 16Ω отвергнута (не специфицирована, тише на 3 dB).
- **Аттенюатор:** резистивный делитель **1:6** между PCM5102A LOUT/ROUT и PAM8403 INL/INR. Схема (на канал, повторить для L и R):
  ```
  PCM5102A LOUT ──[R1=10 кОм]──┬── PAM8403 INL
                                │
                              [R2=2 кОм]
                                │
                               GND
  ```
  Без делителя: PCM5102A 2.1 Vrms × PAM8403 gain ×16 = hard clip. С делителем: 2.1 × 2/12 ≈ 0.35 Vrms — на грани линейной зоны PAM8403. BOM: 2× 10 кОм + 2× 2 кОм, 1/4 W, 5% точность.
- **BTL-ограничения (НЕ НАРУШАТЬ):**
  - `−OUT_L` ≠ `−OUT_R` (никогда не соединять)
  - Любой `−OUT_x` ≠ GND
  - Оба плюса между собой не соединять
  - Каждый канал — изолированная пара проводов от PAM8403 к двум параллельным динамикам
- **Питание PAM8403:** общая 5V ветка с ESP, через тот же понижающий модуль. **Risk note:** при бросках тока PCA9685/моторов возможен шум в аудио. Mitigation в Wave 1: 100 мкФ электролит + 100 нФ керамика на пинах VDD PAM8403 близко к корпусу (демпфер). Если шум всё равно слышен — Wave 1 ревизит: разделить ветки или поставить LC-фильтр (10–47 мкГн дроссель + 470 мкФ).

### Software / Config

- **`services.tts.output_target` flip:** `"jetson_hdmi"` → `"esp32_speaker"`. **Только после** успешного Wave 3 (loopback test) и Wave 2 (volume cap). Требует рестарт `adam-orchestrator.service`.
- **`tuning.voice.volume` стартовое:** `0.5` (консервативный первый ramp).
- **`tuning.voice.volume.maximum` в schema:** понизить **с 2.0 до 1.0** (defense-in-depth, UI санитизация). Описание обновить — упомянуть hardware-chain и rating динамиков.
- **`half_duplex_mute=true`:** остаётся, инвариант. Физическая близость динамика к мик через корпус — без mute self-loop гарантирован.
- **`post_tts_discard_window_ms`:** оставляем 2500, проверим Wave 6 на эмпирику нового self-echo lag (раньше Adam звучал в стороне, теперь — из корпуса).

### Operational

- **Failover:** `output_target` можно вернуть на `jetson_hdmi` через `/api/config` (или ручной edit Config.json + restart). Зафиксировать в RUNBOOK как процедуру отката, если ESP-аудио не работает на выставке.
- **Documentation:** компактная заметка про делитель 1:6 (ASCII-схема + BOM `2×10 кОм + 2×2 кОм`) живёт в этом `29-CONTEXT.md`, без отдельного HARDWARE.md.
- **`commit-push phase-29 audio-out`:** Wave 7, после verify.

### Acceptance signal

Голос Адама звучит через корпус ESP-динамиков, не клиппит на `volume=1.0`, не сжигает динамики после 30 минут, self-echo не приводит к ложным `asr_result` событиям.

</decisions>

<deferred>

**Future phases (не делать сейчас, занести в backlog):**

- **Barge-in на ESP32 target.** Сейчас `Inference.interrupt_playback()` не может прервать аудио уже отправленное в I2S DMA — ESP firmware не имеет stop-endpoint. На HDMI работало через `process.terminate()`. Принимаем как acceptable limitation V1; нужно: добавить `POST :81/api/speaker/stop` в firmware → вызывать из `interrupt_playback()` в ветке esp32_speaker. Это +1 firmware-фаза.
- **Громкость через UI tuning slider.** UI tuning панель уже редактирует `tuning.voice.volume`, но после смены ceiling до 1.0 — проверить, что слайдер обновил max (это backend valid через schema, frontend может всё ещё показывать 2.0 как verge). Минорный UI refresh.
- **Стерео-эффекты для будущих сцен.** Сейчас mono Silero → L=R. Если будущая фаза «scene_director audio cues» добавит стерео-сигналы, нужно изменить I2S firmware режим и тип WAV header. Не сейчас.
- **Окружающий звук / эмбиент.** Не в этой фазе. Если когда-то — отдельный mixer на ESP или AudioGraph на Jetson.

</deferred>

<verify>

**Phase 29 considered DONE when:**

- [ ] Wave 1: омметр показывает 4 Ω на каждой паре `+OUT_x` / `−OUT_x`; нет КЗ минусов на GND
- [ ] Wave 1: PAM8403 питается без видимого спайка при включении моторов (осциллограф или хотя бы слух)
- [ ] Wave 3: `curl -X POST :81/speaker --data-binary @test_440hz.wav` → HTTP 200, чистый синус без хрипа, без модуляции от моторов
- [ ] Wave 4: `output_target=esp32_speaker` + live `/api/agent/turn` → голос разборчивый
- [ ] Wave 5: `tuning.voice.volume=1.0` — нет клиппинга на длинных гласных
- [ ] Wave 5: динамики не нагреваются после 30 мин непрерывного диалога
- [ ] Wave 6: 10 последних `tts_finished` в `events.jsonl` все `target=esp32_speaker ok=true` (требует Wave 4 task: добавить `target` field в payload `tts_finished` в `Orchestrator.py`)
- [ ] Wave 6: 0 `asr_result` событий с timestamp в окне `[tts_start, tts_end + post_tts_discard_window_ms]`
- [ ] Wave 7: `docs/RUNBOOK_JETSON_EXHIBITION.md` обновлён, секция «Аудио-маршрут» с failover инструкцией
- [ ] `Config.schema.json` `tuning.voice.volume.maximum = 1.0`, описание обновлено

</verify>
