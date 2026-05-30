# Branch: V-S09.1-Audio_out

**Diverged from:** main @ e254a09
**Goal:** Phase 29 — Audio Out на ESP32 динамики. Перевести голос Адама с HDMI Jetson на динамики в корпусе персонажа: 2× MAX98357A I2S DAC+усилитель → 2 пары 8Ω динамиков последовательно-параллельно на канал (8Ω нагрузка), питание 3.3V.
**Status:** executing (Wave 1 / Plan 02)
**Merge target:** main
**Merge conditions:**

- Phase 29 артефакты созданы (`29-CONTEXT.md` → `29-PLAN.md` → execute → verify)
- Hardware смонтирован: 2× MAX98357A подключены к GPIO38/39/40, SD-пины ОБА → 3.3V (оба модуля играют одинаковое моно L=R; SD floating = shutdown/молчит — проверено трактом 2026-05-30), динамики 8Ω
- `services.tts.output_target = "esp32_speaker"` в Config.json, рестарт `adam-orchestrator.service` подтверждён
- `tuning.voice.volume` = 1.0 (100% = полная амплитуда Silero без digital clipping); cap `maximum` = 2.0 (>1.0 клиппит — потолок чистого звука 1.0)
- Smoke-тест на корпусе: `volume=1.0` без клиппинга, динамики не нагреваются 30 мин, 0 self-echo `asr_result`
- `docs/RUNBOOK_JETSON_EXHIBITION.md` дополнен секцией «Аудио-маршрут» с failover

**Modified areas:**

- `System/Config.json` — `services.tts.output_target=esp32_speaker` + `tuning.voice.volume=1.0`
- `System/Config.schema.json` — `tuning.voice.volume` default 0.5→1.0, max 2.0, описание под MAX98357A
- `System/adam/inference.py` — `speak()`/cue роутинг на ESP32 + soxr HQ resample (24000→44100)
- `System/Orchestrator.py` — `_play_cue_sound` (cue success/error на ESP32 по `output_target`)
- `System/adam/tuning.py` — `VoiceTuning.volume` default 1.0, `le=2.0`
- `System/requirements.txt` — добавлен `soxr`
- `docs/RUNBOOK_JETSON_EXHIBITION.md` — новая секция «Аудио-маршрут»
- `.planning/phases/29-audio-out-esp32-pcm5102a-pam8403-2-8-parallel/` — артефакты фазы
- `.planning/ROADMAP.md` + `.planning/STATE.md` — учёт Phase 29

**Не трогаем (готово в коде наследия):**

- `Subsystem/AdamsServer/src/audio/AudioModule.cpp` — I2S init совместим с MAX98357A без изменений (Philips 16-bit, без MCLK)
- `Subsystem/AdamsServer/src/web/WebServerModule.cpp` — `/speaker` endpoint готов

**Global changes:**

- `tuning.voice.volume` operating = 1.0 (100%), cap `maximum` = 2.0. UI slider берёт max из schema (2.0); значения >1.0 дают digital clipping — рабочий потолок чистого звука 1.0.
- Дефолт `output_target=esp32_speaker` после мёржа становится production-default. Для разработки без железа использовать `output_target=jetson_hdmi` override через env или edit Config.json.

**Notes for agents:**

- Phase 21A (Chat EQ Real Spectrum) была завершена на этой ветке ранее (commit `8e6f6bb` 2026-05-18). Те изменения в `wakeMeter.js` / `mic_reader.py` / `Config.json` (spectrum параметры) уже мёржены и не относятся к Phase 29.
- `_play_wav_bytes_to_esp32_sync` ждёт `duration_sec` после POST для синхронизации «TTS finished» с реальным окончанием I2S DMA. Не трогать без сильной причины.
- Hardware изменён с PCM5102A+PAM8403 на MAX98357A (2026-05-30). Plan 02 переписан, firmware не требует изменений — I2S протокол совместим.
- Barge-in на ESP-target в этой фазе **не работает** (firmware не имеет stop-endpoint). Accepted V1 limitation, зафиксирован в `29-CONTEXT.md` `<deferred>`.
- `half_duplex_mute=true` остаётся инвариантом. Физическая близость MAX98357A к мик INMP441 — без mute self-loop гарантирован.
- MAX98357A питается от 3.3V (отдельная линия от 5V моторов PCA9685) — spike-тест не нужен.
- Resample 24000→44100 для ESP идёт через `soxr` HQ (audioop.ratecv давал слышимый треск; A/B подтвердил soxr). Fallback на audioop, если soxr нет.
- Остаточный треск на тихом сигнале = шум питания class-D по линии 3.3V (НЕ ресемпл, НЕ клиппинг). Лечится hardware: развязка по питанию (100–470µF+0.1µF на VIN каждого модуля), отдельное чистое питание усилителей, звезда по земле, GAIN-пин. TODO hardware, вне кода.
