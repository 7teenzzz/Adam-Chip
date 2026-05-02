# Adam-Chip

github.com/7teenzzz/Adam-Chip

Adam Chip — художественно-исследовательская агентная система для локальной edge-среды. Цель проекта — создать выставочного ИИ-агента, который взаимодействует со зрителями от лица персонажа инсталляции, воспринимает пространство, говорит голосом и управляет моторным слоем.

Проект реализуется на базе:

- NVIDIA Jetson Orin NX Super 16 GB
  - ARMv8 Processor rev 1 (v8l) x 8
  - NVIDIA Tegra Orin GPU
  - Ubuntu 22.04.5 LTS
- ESP32S3 N16R8 WROOM CAM как низкоуровневый контроллер моторики, сенсоров и резервной диагностики

## Профессиональная Архитектура

Jetson — главный вычислительный узел:

- power gate: exhibition mode требует `MAXN/Super`;
- media acquisition: камера и микрофон подключаются напрямую к Jetson через CSI/USB/UVC/ALSA;
- ASR: NVIDIA Riva Streaming ASR, `ru-RU`;
- VLM: `nano_llm` + `Efficient-Large-Model/VILA1.5-3b`;
- LLM: Ollama-first, локальная `gemma3:4b`, с сохранённой возможностью заменить runtime;
- TTS: Silero `v5_5_ru`, голос `eugene`, быстрый локальный русский синтез;
- orchestrator: FastAPI + asyncio, память, события, prompt builder, action layer, Host UI.

ESP/MCU — низкоуровневый слой:

- `set_scene`;
- `set_channel`;
- `idle`;
- `sensor_snapshot`;
- `health`.

ESP32 camera/audio endpoints сохраняются как диагностика и резерв. Они не являются основным inference path для выставочного режима.

## Ключевой Принцип Диалога

LLM отвечает обычным русским текстом, пригодным для прямой озвучки. Она не обязана возвращать JSON.

Команды инсталляции создаёт отдельный action layer. Если action layer ошибся или выдал невалидную команду, голосовой ответ всё равно произносится, а моторика получает `no_action`.

## Структура

- `System/Orchestrator.py` — основной FastAPI orchestrator и Host UI.
- `System/adam/` — конфиг, power gate, media health, память, события, action layer, MCU client, inference adapters.
- `System/Speech/ASR.py` — adapter для NVIDIA Riva Streaming ASR.
- `System/Speech/TTS.py` — HTTP service для Silero TTS.
- `data/sounds/success.mp3` — локальный Jetson cue после успешной инициализации AI stack.
- `Subsystem/AdamsServer/data/sounds/boot.wav` — ESP boot cue source asset.
- `Subsystem/AdamsServer/data/sounds/success.wav` — ESP success cue source asset.
- `System/Config.json` — основной runtime config.
- `compose.yaml` — Docker Compose для orchestrator и optional Silero service.
- `deploy/systemd/` — production units для выставочного автозапуска.
- `scripts/adam_bootstrap_venv.sh` — создание project venv и установка базовых зависимостей.
- `scripts/adam_torch_doctor.sh` — проверка Jetson PyTorch/Silero внутри project venv.
- `scripts/adam_power_maxn.sh` — включение MAXN/Super и clocks.
- `scripts/adam_media_probe.sh` — проверка камер и аудиоустройств.
- `scripts/adam_install_systemd.sh` — установка systemd units.
- `scripts/adam_tts_doctor.sh` — проверка Jetson TTS dependencies/service/playback.
- `scripts/adam_tts_smoke.sh` — короткий smoke test локальной озвучки.
- `docs/RUNBOOK_JETSON_EXHIBITION.md` — эксплуатационный runbook.
- `Subsystem/AdamsServer/` — прошивка ESP32S3.

## Быстрый Запуск Orchestrator

```bash
./scripts/adam_bootstrap_venv.sh
./scripts/adam_power_maxn.sh
PYTHONPATH=System ADAM_MODE=maintenance ./.venv/bin/python System/Orchestrator.py
```

Открыть:

```text
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
  -d '{"transcript":"Привет, Адам. Ты меня слышишь?"}' | python3 -m json.tool
```

## Docker

```bash
cp .env.example .env
docker compose up --build adam-orchestrator
```

Optional Silero TTS service:

```bash
docker compose --profile speech-local up --build adam-tts-silero
```

## Production Boot

```bash
./scripts/adam_bootstrap_venv.sh
./scripts/adam_torch_doctor.sh
./scripts/adam_install_systemd.sh
sudo systemctl start adam-tts-silero.service
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
./scripts/adam_service_logs.sh adam-tts-silero.service
```

Проверка TTS:

```bash
./scripts/adam_torch_doctor.sh
./scripts/adam_tts_doctor.sh
./scripts/adam_tts_smoke.sh
```

PyTorch для Silero ставится в `./.venv` только Jetson-compatible способом под активный JetPack. После установки NVIDIA PyTorch ставить Silero без dependency resolver:

```bash
./.venv/bin/python -m pip install --no-deps "silero>=0.5.0"
```

NVIDIA Jetson PyTorch docs:

https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html
https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform-release-notes/pytorch-jetson-rel.html

## Media Policy

Основной видео-вход для AI:

- локальная CSI или USB/UVC камера на Jetson;
- GStreamer pipeline с `appsink`/shared frame buffer;
- удалённая камера допустима только как аппаратный H.264 RTSP источник.

Основной аудио-вход для ASR:

- USB microphone или microphone array напрямую в Jetson;
- ALSA capture;
- resampling до 16 kHz mono PCM перед VAD/ASR.

Текущие defaults ближайшего milestone:

- video: `/dev/video0`;
- audio input: `hw:0,0` (`WebCamera`);
- audio output: `default`.

WebRTC не используется в inference path. Его можно добавить только как операторский preview.

## Материалы

- Jetson AI Lab: https://www.jetson-ai-lab.com/
- NanoVLM / VILA archive: https://www.jetson-ai-lab.com/archive/tutorial_nano-vlm.html
- NanoOWL archive: https://www.jetson-ai-lab.com/archive/vit/tutorial_nanoowl.html
- NVIDIA Riva ASR: https://docs.nvidia.com/deeplearning/riva/user-guide/docs/asr/asr-overview.html
- Jetson Platform Services VLM: https://docs.nvidia.com/jetson/jps/inference-services/vlm.html
- Jetson Containers: https://github.com/dusty-nv/jetson-containers
- Silero Models: https://github.com/snakers4/silero-models
