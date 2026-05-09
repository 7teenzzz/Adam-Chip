# Adam-Chip

github.com/7teenzzz/Adam-Chip

Adam Chip — художественно-исследовательская агентная система для локальной edge-среды. Цель проекта — создать выставочного ИИ-агента, который взаимодействует со зрителями от лица персонажа инсталляции, воспринимает пространство, говорит голосом и управляет моторным слоем.

Проект реализуется на базе:

- **NVIDIA Jetson Orin NX Super 16 GB**
  - ARMv8 × 8 cores, NVIDIA Tegra Orin GPU
  - Ubuntu 22.04.5 LTS / JetPack
- **ESP32-S3 N16R8 WROOM CAM** — периферийный контроллер моторики и сенсоров
  - 16×12bit PWM: PCA9685
  - Camera & Mic: OV5640 + INMP441
  - Audio out: PCM5102A + PAM8403
  - ETH-SPI: W5500 LITE
  - Sensors: TEMT6000 (light), BTE16-19 (rip)

## Архитектура

```
Jetson (inference node)          ESP32-S3 (peripheral node)
  FastAPI orchestrator      ←→     192.168.0.172
  llama.cpp LLM                    PCA9685 PWM (motors)
  VILA VLM (scene)                 INMP441 mic uplink
  Whisper ASR (ru-RU)              PCM5102A speaker
  Silero TTS (eugene)              WebSocket telemetry push
  GStreamer video                  HTTP API (/api/*)
  ALSA audio                       MJPEG camera stream
  Episodic memory (SQLite)
  EchoGate (dialogue filtering)
  Hot-reloadable tuning
```

## Inference Stack

| Компонент | Runtime | Модель | Порт |
|-----------|---------|--------|------|
| LLM | llama.cpp (OpenAI-compat) | gemma-4-E4B-it-UD-Q4_K_XL | 8051 |
| VLM | VILA 1.5-3b | Efficient-Large-Model/VILA1.5-3b | 8050 |
| ASR | Whisper HTTP | tiny, ru-RU, wake word «адам» | 8095 |
| TTS | Silero v5_5_ru | голос eugene | 8090 |
| Orchestrator | FastAPI + asyncio | — | 8080 |

## Ключевой Принцип Диалога

LLM отвечает чистым русским текстом, пригодным для прямой озвучки. Никакого JSON в LLM-ответе — action layer работает отдельно.

## Структура

```
System/
  Orchestrator.py          Главная точка входа (FastAPI + asyncio)
  Config.json              Runtime конфиг
  adam/
    config.py              Загрузка Config.json + env overrides
    inference.py           LLM / VLM / ASR / TTS адаптеры
    prompt.py              Prompt builder (персона + история + сцена)
    action.py              Action layer — валидация MCU-команд
    device.py              HTTP клиент ESP32 MCU
    memory.py              SQLite диалоговая + эпизодическая память
    episodic.py            SessionAccumulator, salience scoring
    echoes_gate.py         Пул готовых реплик (Echoes / Chinese)
    tuning.py              Hot-reloadable параметры персоны
    metrics.py             Метрики: timing, tokens, memory
    api_runtime.py         Runtime API: config R/W, SSE, camera snapshot
    events.py              Event bus + JSONL log
    power.py               Jetson power gate (nvpmodel / jetson_clocks)
    media.py               Video/audio health checks
    sound.py               Jetson-side cue playback
    ui.py                  Web UI backend (agent / dash / debug pages)
    system.py              Systemd service control
  Speech/
    ASR_Whisper.py         Whisper HTTP сервис (основной ASR)
    ASR.py                 NVIDIA Riva adapter (резерв)
    TTS.py                 Silero TTS HTTP сервис
  Interlayers/             Legacy модули
  HostUI/ + WebUI/         Операторский web-интерфейс
data/
  adam/
    memory.sqlite3         Эпизодическая память
    events.jsonl           Поток событий
    notes/ summaries/      Заметки и суммари сессий
  sounds/success.mp3       Jetson init-cue
Subsystem/AdamsServer/     Прошивка ESP32-S3 (PlatformIO)
Agent Adam Chip/About/     Персона: Identity.md, Lore.md, Abilities.md
Agent Adam Chip/Tuning.json  Hot-reload параметры персоны
docs/RUNBOOK_JETSON_EXHIBITION.md  Production runbook
deploy/systemd/            Systemd units для выставочного запуска
scripts/                   Диагностика, деплой, управление
Engineering/consolidator.py  Консолидация памяти (daily cron)
```

## Быстрый Запуск Orchestrator

```bash
./scripts/adam_bootstrap_venv.sh
./scripts/adam_power_maxn.sh
PYTHONPATH=System ADAM_MODE=maintenance ./.venv/bin/python System/Orchestrator.py
```

Открыть:

```
http://JETSON_IP:8080
```

Проверить API:

```bash
curl -fsS http://127.0.0.1:8080/api/agent/status | python3 -m json.tool
curl -fsS http://127.0.0.1:8080/api/agent/gate | python3 -m json.tool
```

Тестовый диалоговый turn:

```bash
curl -fsS http://127.0.0.1:8080/api/agent/turn \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"Адам, ты меня слышишь?"}' | python3 -m json.tool
```

## Docker

```bash
cp .env.example .env
docker compose up --build adam-orchestrator
```

Optional сервисы:

```bash
docker compose --profile speech-local up --build adam-tts-silero
docker compose --profile speech-local up --build adam-asr-whisper
```

## Production Boot

```bash
./scripts/adam_bootstrap_venv.sh
./scripts/adam_torch_doctor.sh
./scripts/adam_install_systemd.sh

sudo systemctl start adam-llm.service
sudo systemctl start adam-tts-silero.service
sudo systemctl start adam-asr-whisper.service
sudo systemctl start adam-orchestrator.service

./scripts/adam_service_status.sh
./scripts/adam_set_mode.sh exhibition
```

Переключение режима:

```bash
./scripts/adam_set_mode.sh maintenance
./scripts/adam_set_mode.sh exhibition
```

Логи:

```bash
./scripts/adam_service_logs.sh adam-orchestrator.service
./scripts/adam_service_logs.sh adam-llm.service
./scripts/adam_service_logs.sh adam-tts-silero.service
```

## Диагностика

```bash
./scripts/adam_healthcheck.sh
./scripts/adam_media_probe.sh       # камеры и аудиоустройства
./scripts/adam_torch_doctor.sh      # Jetson PyTorch/Silero
./scripts/adam_tts_doctor.sh
./scripts/adam_tts_smoke.sh         # smoke test озвучки
./scripts/adam_service_status.sh
```

PyTorch для Silero ставится только Jetson-compatible способом. После установки NVIDIA PyTorch:

```bash
./.venv/bin/python -m pip install --no-deps "silero>=0.5.0"
```

## Firmware: сборка и прошивка (с Windows dev-машины)

```powershell
# Список портов
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -ListPorts

# Сборка + прошивка (COM7)
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1

# OTA по Wi-Fi
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_ota.ps1 -Host 192.168.0.172
```

COM-порты: `COM7` = прошивка, `COM6` = логи приложения

## Материалы для опоры

- Jetson AI Lab: https://www.jetson-ai-lab.com/
- NVIDIA Riva ASR: https://docs.nvidia.com/deeplearning/riva/user-guide/docs/asr/asr-overview.html
- Jetson Containers: https://github.com/dusty-nv/jetson-containers
- Silero Models: https://github.com/snakers4/silero-models
- NVIDIA PyTorch (Jetson): https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html
- Realtime VLM:
  - [text](https://www.jetson-ai-lab.com/archive/tutorial_nano-vlm.html)
  - [text](https://www.jetson-ai-lab.com/archive/tutorial_live-llava.html)