# Adam Chip — Claude Code Instructions

## Что это за проект

Выставочная ИИ-инсталляция: интерактивная диорама с «останками таинственного киборга» Адама Чипа. Агент взаимодействует со зрителями голосом, воспринимает пространство через камеру/микрофон, управляет моторным слоем.

**Язык общения в проекте: русский.** Комментарии в коде — английские (по необходимости).

## Аппаратная архитектура

```
NVIDIA Jetson Orin NX Super 16 GB   ←→   ESP32-S3 N16R8 WROOM CAM
  Ubuntu 22.04 / JetPack               Wi-Fi @ 192.168.0.171
  Основной inference node              Моторика, сенсоры, аудио-периферия
```

- Jetson — восприятие (камера CSI/USB → GStreamer), ASR, VLM, LLM, TTS, orchestrator
- ESP32 — PCA9685 PWM, INMP441 mic uplink, PCM5102 speaker, телеметрия, WebSocket push

## Ключевые принципы (не нарушать)

1. **LLM отвечает чистым русским текстом** для прямой озвучки. Никакого JSON в LLM-ответе.
2. **Action layer отдельно** от голосового ответа. Ошибка action layer → `no_action`, голос всё равно произносится.
3. **Jetson — единственный inference path.** ESP32 MJPEG и ESP32 mic — диагностика/резерв, не основной AI-поток.
4. **Power gate обязателен:** exhibition mode требует `nvpmodel -m 0` + `jetson_clocks`. Проверяется при старте.
5. **WebRTC не использовать в inference path.** Только как операторский preview если нужно.
6. **half_duplex_mute = true** — во время TTS playback микрофон mute, чтобы агент не слышал сам себя.

## Структура Python-слоя

```
System/
  Orchestrator.py          FastAPI + asyncio, главная точка входа
  adam/
    config.py              Загрузка Config.json + env overrides
    power.py               Jetson power gate (nvpmodel / jetson_clocks)
    media.py               GStreamer video, ALSA audio, VAD
    inference.py           Ollama LLM, VILA VLM, adapters
    prompt.py              Prompt builder (persona + history + scene + sensors)
    action.py              Action layer, валидация команд MCU
    device.py              HTTP client для ESP32 MCU
    memory.py              Диалоговая память агента
    events.py              Внутренняя event bus
    sound.py               Jetson-side cue playback
    ui.py                  Host UI backend helpers
    system.py              Health checks, systemd notify
  Speech/
    ASR.py                 NVIDIA Riva Streaming ASR adapter
    TTS.py                 Silero HTTP TTS service
  Interlayers/
    Commander.py           High-level command dispatcher
    PromtBuilder.py        Legacy prompt builder (переезжает в adam/prompt.py)
  HostUI/
    server.py              Operator web UI
  Config.json              Runtime config (см. ниже)
```

## Config.json — ключевые значения

```json
agent.mode          "maintenance" | "exhibition"
power.required_mode_id  0 (MAXN)
media.video.primary     "jetson_gstreamer"
media.audio.input_device  "hw:0,0"
services.llm.model      "gemma3:4b" (ollama)
services.tts.speaker    "eugene" (silero v5_5_ru)
services.asr.language_code  "ru-RU"
mcu.base_url        "http://192.168.0.171"
safety.half_duplex_mute  true
```

## ESP32 Firmware (Subsystem/AdamsServer/)

```
config/
  AdamsConfig.h          Основной конфиг прошивки
  PinsConfig.h           Пины ESP32-S3
  PrivateConfig.h        Wi-Fi credentials, IP — НЕ КОММИТИТЬ
  PrivateConfig.example.h  Шаблон
src/
  audio/                 INMP441 mic + PCM5102 speaker + системные звуки
  camera/                OV-camera + MJPEG streaming
  core/                  RuntimeState, BootDiagnostics, NetworkModule
  io/                    PCA9685, сенсоры
  web/                   HTTP API + Web UI (/, /ctrldash)
```

**ESP32 статический IP:** `192.168.0.171`

Ключевые firmware endpoints:
- `GET /api/status` — общий runtime status
- `POST /api/pca9685/scene` — команда сцены моторики
- `POST /api/pca9685/channel` — один PWM канал
- `POST /api/sound/play?name=boot|success|tone` — системные звуки
- `GET /api/audio/clip?ms=2000` — диагностический WAV-клип
- `WS /ws` — push телеметрия

## Запуск (Python orchestrator)

```bash
# Первичная настройка
./scripts/adam_bootstrap_venv.sh

# Применить MAXN power mode
./scripts/adam_power_maxn.sh

# Запуск в maintenance mode
PYTHONPATH=System ADAM_MODE=maintenance ./.venv/bin/python System/Orchestrator.py

# Проверка API
curl -fsS http://127.0.0.1:8080/api/agent/status | python3 -m json.tool

# Тестовый диалоговый turn
curl -fsS http://127.0.0.1:8080/api/agent/turn \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"Привет, Адам. Ты меня слышишь?"}' | python3 -m json.tool
```

## Docker

```bash
cp .env.example .env
docker compose up --build adam-orchestrator
# + optional TTS service:
docker compose --profile speech-local up --build adam-tts-silero
```

## Production systemd

```bash
./scripts/adam_install_systemd.sh
sudo systemctl start adam-tts-silero.service
sudo systemctl start adam-orchestrator.service
./scripts/adam_set_mode.sh exhibition
```

## Диагностика

```bash
./scripts/adam_healthcheck.sh
./scripts/adam_media_probe.sh       # камеры и аудиоустройства
./scripts/adam_torch_doctor.sh      # Jetson PyTorch/Silero
./scripts/adam_tts_doctor.sh
./scripts/adam_tts_smoke.sh         # smoke test озвучки
./scripts/adam_service_status.sh
./scripts/adam_service_logs.sh adam-orchestrator.service
```

## Firmware: сборка и прошивка (с Windows dev-машины)

```powershell
# Список портов
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -ListPorts

# Сборка + прошивка
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1

# OTA по Wi-Fi
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_ota.ps1 -Host 192.168.0.171
```

**COM-порты ESP32:**
- `COM7` = USB TO SERIAL → прошивка
- `COM6` = USB OTG/CDC → логи приложения

## Что НЕ делать

- Не добавлять JSON в LLM-ответ — это ломает философию action layer
- Не переключать media.video.primary на ESP32 MJPEG для inference
- Не добавлять WebRTC в inference path
- Не ставить NVIDIA PyTorch через pip с dependency resolver — только Jetson-совместимый wheel
- После установки NVIDIA PyTorch: `pip install --no-deps "silero>=0.5.0"`
- Не коммитить `config/PrivateConfig.h` и `.env`
- Не запускать exhibition mode без предварительной проверки power gate

## Env variables (override Config.json)

```
ADAM_MODE              maintenance | exhibition
ADAM_CONFIG            путь к Config.json
ADAM_DATA_DIR          data dir для агента
ESP_BASE_URL           http://192.168.0.171
ADAM_LLM_MODEL         gemma3:4b (или замена)
ADAM_LLM_BASE_URL      http://127.0.0.1:11434
ADAM_TTS_BASE_URL      http://127.0.0.1:8090
ADAM_ASR_HOST          127.0.0.1
ADAM_ASR_PORT          50051
ADAM_VLM_BASE_URL      http://127.0.0.1:8050
ADAM_VIDEO_DEVICE      /dev/video0
ADAM_AUDIO_INPUT_DEVICE  hw:0,0
```
