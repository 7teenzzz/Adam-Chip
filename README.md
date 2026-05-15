# Adam-Chip

Adam Chip — художественно-исследовательская агентная система для локальной edge-среды. Цель проекта — создать выставочного ИИ-агента, который взаимодействует со зрителями от лица персонажа инсталляции, воспринимает пространство, говорит голосом и управляет моторным слоем.

Проект реализуется на базе:

- **NVIDIA Jetson Orin NX Super 16 GB**
  - ARMv8 × 8 cores, NVIDIA Tegra Orin GPU with ARM architecture
  - Ubuntu 22.04.5 LTS / JetPack
- **ESP32-S3 N16R8 WROOM CAM** — периферийный контроллер моторики и сенсоров
  - 16×12bit PWM: PCA9685
  - Camera & Mic: OV5640 + 2x INMP441
  - Audio out: PCM5102A + PAM8403
  - ETH-SPI: W5500 LITE
  - Sensors: TEMT6000 (light), BTE16-19 (rip)

## Архитектура

```
Jetson (inference node)             ESP32-S3 (peripheral node)
  FastAPI orchestrator      ←→        192.168.0.171
  llama.cpp LLM                       PCA9685 PWM (motor layer)
  VILA VLM (scene)                    INMP441 mic uplink
  WhisperX ASR (ru-RU)                PCM5102A speaker  ← POST :81/speaker
  WebRTC VAD (endpointing)            WebSocket telemetry push
  Silero TTS (eugene)                 HTTP API (/api/*)
  GStreamer video                     MJPEG camera stream
  ALSA audio
  Episodic memory (SQLite + JSONL)
  EchoGate (dialogue filtering)
  Hot-reloadable tuning
```

## Inference Stack

| Компонент | Runtime | Модель | Порт |
|-----------|---------|--------|------|
| LLM | llama.cpp (OpenAI-compat) | gemma-4-E4B-it-UD-Q4_K_XL | 8081 |
| VLM | nano_llm (Docker) | VILA 1.5-3b | 8084 |
| ASR | WhisperX (CUDA, Docker) | small, ru-RU, wake word «адам» | 8095 |
| TTS | Silero v5_5_ru | голос eugene | 8082 |
| Orchestrator | FastAPI + asyncio | — | 8080 |
| Log Viewer | FastAPI (always-on) | — | 8083 |

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
    api_runtime.py         Runtime API: config R/W, SSE, camera snapshot, /api/events
    events.py              Event bus + JSONL log
    log_viewer.py          Always-on read-only log HTTP сервис (порт 8083)
    power.py               Jetson power gate (nvpmodel / jetson_clocks)
    media.py               Video/audio health checks
    sound.py               Jetson-side cue playback
    ui.py                  Web UI backend (agent / dash / debug pages)
    system.py              Systemd service control
  Speech/
    ASR_WhisperX.py        WhisperX ASR сервис (CUDA, Docker, порт 8095)
    ASR.py                 NVIDIA Riva adapter (legacy, резерв)
    TTS.py                 Silero TTS HTTP сервис (порт 8082)
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
docker compose --profile speech-local up --build adam-asr-whisperx
```

## Production Boot

```bash
./scripts/adam_bootstrap_venv.sh
./scripts/adam_torch_doctor.sh
./scripts/adam_install_systemd.sh

sudo systemctl start adam-logviewer.service   # always-on, до остальных
sudo systemctl start adam-llm.service
sudo systemctl start adam-tts-silero.service
sudo systemctl start adam-asr-whisperx.service
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
./scripts/adam_service_logs.sh adam-asr-whisperx.service
```

## Диагностика

```bash
./scripts/adam_healthcheck.sh
./scripts/adam_media_probe.sh       # камеры и аудиоустройства
./scripts/adam_torch_doctor.sh      # Jetson PyTorch/Silero
./scripts/adam_asr_cuda_check.sh    # CUDA/WhisperX диагностика
./scripts/adam_tts_doctor.sh
./scripts/adam_tts_smoke.sh         # smoke test озвучки
./scripts/adam_service_status.sh
```

PyTorch для Silero ставится только Jetson-compatible способом. После установки NVIDIA PyTorch:

```bash
./.venv/bin/python -m pip install --no-deps "silero>=0.5.0"
```

## Логи Pipeline

### Log Viewer (браузер, всегда доступен)

Самостоятельный сервис на порту **8083** — работает даже когда оркестратор упал.

```text
http://JETSON_IP:8083/          # дашборд: события, метрики, статус сервисов
http://JETSON_IP:8083/events    # JSON: последние N событий
http://JETSON_IP:8083/metrics   # JSON: latency per turn (proxy → оркестратор или файл)
http://JETSON_IP:8083/journal   # JSON: journalctl для любого adam-* сервиса
http://JETSON_IP:8083/services  # JSON: systemctl статус всех adam-* юнитов
```

Из основного UI (`:8080`) панель **Логи** показывает статус сервисов и открывает Log Viewer.

### Скрипт adam_pull_logs.py (терминал, удалённо с Windows / macOS)

Каждый диалоговый turn получает `turn_id` — короткий UUID, который связывает все события ASR → LLM → TTS → Action в один trace.

Скрипт написан на чистом Python 3, без внешних зависимостей — работает на Windows и macOS одинаково.

**Windows (PowerShell):**

```powershell
$env:JETSON_URL = "http://192.168.0.X:8080"
python scripts/adam_pull_logs.py --last 5
```

**macOS / Linux:**

```bash
export JETSON_URL="http://192.168.0.X:8080"
python3 scripts/adam_pull_logs.py --last 5
```

**Примеры:**

```bash
# Последние 5 turn-ов, все этапы
python3 scripts/adam_pull_logs.py --last 5

# Только ASR
python3 scripts/adam_pull_logs.py --last 10 --stage asr

# Live tail событий (Ctrl+C для остановки)
python3 scripts/adam_pull_logs.py --follow

# Live tail только TTS
python3 scripts/adam_pull_logs.py --follow --stage tts

# JSON для офлайн анализа
python3 scripts/adam_pull_logs.py --last 20 --out json > turns.json
```

Доступные `--stage`: `oww`, `vad`, `asr`, `llm`, `tts`, `action`, `vlm`, `all`

API-эндпоинты для curl/Postman:

```bash
# Сгруппированные turn-ы с латентностями и событиями
curl -fsS 'http://JETSON:8080/api/agent/turns?limit=5' | python3 -m json.tool

# Все события одного turn
curl -fsS 'http://JETSON:8080/api/agent/events?turn_id=abc12345' | python3 -m json.tool

# Фильтрация по типу события
curl -fsS 'http://JETSON:8080/api/agent/events?types=asr_result,adam_reply&limit=20' | python3 -m json.tool
```

## Firmware: сборка и прошивка (с Windows dev-машины)

```powershell
# Список портов
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -ListPorts

# Сборка + прошивка (COM7)
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1

# OTA по Wi-Fi
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_ota.ps1 -Host 192.168.0.171
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