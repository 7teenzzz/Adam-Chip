# Branch: V-S09.1-Audio_out

**Diverged from:** main @ e254a09
**Goal:** Phase 29 — Audio Out на ESP32 динамики. Перевести голос Адама с HDMI Jetson на динамики в корпусе персонажа: 2× MAX98357A I2S DAC+усилитель → 2 пары 8Ω динамиков последовательно-параллельно на канал (8Ω нагрузка), питание 3.3V.
**Status:** executing (Wave 1 / Plan 02)
**Merge target:** main
**Merge conditions:**

- Phase 29 артефакты созданы (`29-CONTEXT.md` → `29-PLAN.md` → execute → verify)
- Hardware смонтирован: 2× MAX98357A подключены к GPIO38/39/40, SD-пины настроены (LEFT floating, RIGHT → 3.3V), динамики 8Ω
- `services.tts.output_target = "esp32_speaker"` в Config.json, рестарт `adam-orchestrator.service` подтверждён
- `tuning.voice.volume.maximum` опущен с 2.0 до 1.0 в Config.schema.json
- Smoke-тест на корпусе: `volume=1.0` без клиппинга, динамики не нагреваются 30 мин, 0 self-echo `asr_result`
- `docs/RUNBOOK_JETSON_EXHIBITION.md` дополнен секцией «Аудио-маршрут» с failover

**Modified areas:**

- `System/Config.json` — `services.tts.output_target` + `tuning.voice.volume` (стартовое 0.5)
- `System/Config.schema.json` — `tuning.voice.volume.maximum` 2.0→1.0 + описание hardware-chain
- `docs/RUNBOOK_JETSON_EXHIBITION.md` — новая секция «Аудио-маршрут»
- `.planning/phases/29-audio-out-esp32-pcm5102a-pam8403-2-8-parallel/` — артефакты фазы
- `.planning/ROADMAP.md` + `.planning/STATE.md` — учёт Phase 29

**Не трогаем (готово в коде наследия):**

- `System/adam/inference.py:_play_wav_bytes_to_esp32_sync` — путь TTS → ESP уже реализован
- `Subsystem/AdamsServer/src/audio/AudioModule.cpp` — I2S init совместим с MAX98357A без изменений (Philips 16-bit, без MCLK)
- `Subsystem/AdamsServer/src/web/WebServerModule.cpp` — `/speaker` endpoint готов

**Global changes:**

- `tuning.voice.volume.maximum` понижается с 2.0 до 1.0. UI tuning slider, если показывает max=2.0, нужно проверить после мёржа — он берёт max из schema, должен подхватиться.
- Дефолт `output_target=esp32_speaker` после мёржа становится production-default. Для разработки без железа использовать `output_target=jetson_hdmi` override через env или edit Config.json.

**Notes for agents:**

- Phase 21A (Chat EQ Real Spectrum) была завершена на этой ветке ранее (commit `8e6f6bb` 2026-05-18). Те изменения в `wakeMeter.js` / `mic_reader.py` / `Config.json` (spectrum параметры) уже мёржены и не относятся к Phase 29.
- `_play_wav_bytes_to_esp32_sync` ждёт `duration_sec` после POST для синхронизации «TTS finished» с реальным окончанием I2S DMA. Не трогать без сильной причины.
- Hardware изменён с PCM5102A+PAM8403 на MAX98357A (2026-05-30). Plan 02 переписан, firmware не требует изменений — I2S протокол совместим.
- Barge-in на ESP-target в этой фазе **не работает** (firmware не имеет stop-endpoint). Accepted V1 limitation, зафиксирован в `29-CONTEXT.md` `<deferred>`.
- `half_duplex_mute=true` остаётся инвариантом. Физическая близость MAX98357A к мик INMP441 — без mute self-loop гарантирован.
- MAX98357A питается от 3.3V (отдельная линия от 5V моторов PCA9685) — spike-тест не нужен.
