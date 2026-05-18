# Branch: V-S09.1-Audio_out

**Diverged from:** main @ e254a09
**Goal:** Phase 29 — Audio Out на ESP32 динамики. Перевести голос Адама с HDMI Jetson на динамики, физически живущие в корпусе персонажа: PCM5102A I2S DAC → резистивный делитель 1:6 → PAM8403 → 2 параллельных 8Ω-динамика на канал.
**Status:** discussing → planning
**Merge target:** main
**Merge conditions:**

- Phase 29 артефакты созданы (`29-CONTEXT.md` → `29-PLAN.md` → execute → verify)
- Hardware смонтирован: делитель 1:6 на каждый канал, PAM8403 на общем 5V с ESP через понижающий модуль, 2 динамика параллельно на канал, BTL правила соблюдены
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
- `Subsystem/AdamsServer/src/AudioModule.cpp` — PCM5102A I2S init готов
- `Subsystem/AdamsServer/src/WebServerModule.cpp` — `/speaker` endpoint готов

**Global changes:**

- `tuning.voice.volume.maximum` понижается с 2.0 до 1.0. UI tuning slider, если показывает max=2.0, нужно проверить после мёржа — он берёт max из schema, должен подхватиться.
- Дефолт `output_target=esp32_speaker` после мёржа становится production-default. Для разработки без железа использовать `output_target=jetson_hdmi` override через env или edit Config.json.

**Notes for agents:**

- Phase 21A (Chat EQ Real Spectrum) была завершена на этой ветке ранее (commit `8e6f6bb` 2026-05-18). Те изменения в `wakeMeter.js` / `mic_reader.py` / `Config.json` (spectrum параметры) уже мёржены и не относятся к Phase 29.
- `_play_wav_bytes_to_esp32_sync` ждёт `duration_sec` после POST для синхронизации «TTS finished» с реальным окончанием I2S DMA — это уже учитывает асинхронное дренирование PCM5102A. Не трогать без сильной причины.
- Barge-in на ESP-target в этой фазе **не работает** (firmware не имеет stop-endpoint). Это accepted V1 limitation, future phase зафиксирован в `29-CONTEXT.md` `<deferred>`.
- `half_duplex_mute=true` остаётся инвариантом. Физическая близость динамика к мик через корпус — без mute self-loop гарантирован.
- BTL ограничения PAM8403 жёсткие: `−OUT_x` ≠ GND, `−OUT_L` ≠ `−OUT_R`. Нарушение → мгновенный отказ усилителя.
