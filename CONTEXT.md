# Adam Chip — Agent Handoff Context

> Этот файл — полный снимок состояния проекта для передачи контекста новому агенту.
> Дата последнего обновления: 2026-05-14

---

## Суть проекта

**Adam Chip** — выставочная ИИ-инсталляция. На столе — «останки таинственного киборга». Зрители подходят, говорят с ним голосом. Агент воспринимает пространство через камеру, слушает через микрофон, отвечает голосом (TTS), двигает сервоприводами через ESP32.

**Персонаж:** Адам Чип — INTP/5w4, ядро `se`/`co` по AIIM-кодировке. Говорит по-русски. Характер: замкнутый, странный, с чёрным юмором. Не раскрывает природу своего существования напрямую.

**Репозиторий:** github.com/7teenzzz/Adam-Chip  
**Рабочая директория:** `/home/i17jet/Agents/Adam-Chip`

---

## Аппаратура

| Устройство | Роль | Сеть |
|-----------|------|------|
| NVIDIA Jetson Orin NX Super 16GB | Inference node, orchestrator | Основной хост |
| ESP32-S3 N16R8 WROOM CAM | Периферия: моторы, сенсоры, звук | 192.168.0.171 |

**Jetson OS:** Ubuntu 22.04.5 LTS / JetPack  
**ESP32 SDK:** PlatformIO, прошивка в `Subsystem/AdamsServer/`

**Периферия ESP32:**
- PCA9685 — 16 каналов PWM (сервоприводы / соленоиды)
- INMP441 — микрофон uplink
- PCM5102A + PAM8403 — аудиовыход
- OV5640 — MJPEG камера (диагностика)
- TEMT6000 — датчик освещения
- BTE16-19 — датчик присутствия (rip)
- W5500 LITE — Ethernet SPI

---

## Inference Stack (актуальный)

| Компонент | Runtime | Модель | Endpoint |
|-----------|---------|--------|----------|
| **LLM** | llama.cpp (OpenAI-compat API) | `gemma-4-E4B-it-UD-Q4_K_XL` | http://127.0.0.1:8081/v1 |
| **VLM** | VILA 1.5-3b | `Efficient-Large-Model/VILA1.5-3b` | http://127.0.0.1:8084 |
| **ASR** | WhisperX (CUDA, Docker) | `medium`, ru-RU | http://127.0.0.1:8095 |
| **TTS** | Silero v5_5_ru | голос `eugene` | http://127.0.0.1:8082 |
| **Orchestrator** | FastAPI + asyncio | — | http://127.0.0.1:8080 |

**Wake word ASR:** `адам` (обязателен в exhibition mode)  
**LLM параметры:** temperature=0.7, max_tokens=40, num_ctx=8192  
**TTS output:** ALSA device `plughw:1,3`  
**Audio input:** PulseAudio (`pulse`)  
**VAD:** WebRTC VAD (CPU, stateless, агрессивность 2) в VoiceLoopController  
**Wake word:** OpenWakeWord — ONNX-модель `adam.onnx`, порог 0.35, debounce 3 детекции

---

## Python Orchestrator

**Точка входа:** `System/Orchestrator.py` (FastAPI + asyncio)

```
PYTHONPATH=System ADAM_MODE=maintenance ./.venv/bin/python System/Orchestrator.py
```

### Модули (System/adam/)

| Модуль | Назначение |
|--------|-----------|
| `config.py` | Загрузка Config.json + env overrides, `PROJECT_ROOT` |
| `inference.py` | Адаптеры LLM / VLM / ASR / TTS, ServiceHealth |
| `prompt.py` | PromptBuilder: персона + история + scene |
| `action.py` | ActionLayer: валидация MCU команд, safety constraints |
| `device.py` | MCUClient: HTTP к ESP32 |
| `memory.py` | MemoryStore: SQLite, notes, summaries |
| `episodic.py` | SessionAccumulator, salience scoring |
| `echoes_gate.py` | EchoGate: пул реплик (Echoes.md, Chinese_lines.md), turn/mood/cooldown |
| `tuning.py` | TuningStore: hot-reload Tuning.json |
| `metrics.py` | MetricsLog: timing, tokens, memory stats |
| `api_runtime.py` | Runtime API: config R/W, model discovery, SSE, camera snapshot |
| `events.py` | EventLog JSONL + in-memory ring buffer, async SSE streaming |
| `power.py` | PowerGate: nvpmodel + jetson_clocks enforcement |
| `media.py` | MediaHealth: video/audio device probing |
| `sound.py` | Локальный cue playback (ffplay/paplay) |
| `ui.py` | Web UI: agent_page, dash_page, debug_page |
| `system.py` | Systemd service control, docker health |
| `webrtc_vad.py` | WebRtcVadWrapper: CPU VAD для эндпоинтирования (10/20/30ms фреймы, агрессивность 0–3) |
| `wake_word.py` | OpenWakeWord интеграция: ONNX-модель `adam.onnx`, debounce, wake silence timeout |

### Speech Services (System/Speech/)

- `ASR_WhisperX.py` — WhisperX ASR сервис (CUDA, Docker, порт 8095)
- `ASR.py` — NVIDIA Riva adapter (legacy, резерв)
- `TTS.py` — Silero v5_5_ru HTTP сервис (порт 8082)

---

## Config.json (System/Config.json)

Актуальные значения на 2026-05-14:

```json
{
  "agent": { "mode": "maintenance", "history_turns": 2 },
  "power": { "required_mode_id": 0, "enforce_in_exhibition": true },
  "media": {
    "video": { "primary": "jetson_gstreamer", "video_device": "/dev/video0" },
    "audio": { "input_device": "pulse", "vad_threshold": 400, "webrtc_vad_aggressiveness": 2 },
    "scene_interval_sec": 4,
    "scene_stale_after_sec": 8
  },
  "services": {
    "llm": {
      "provider": "openai",
      "base_url": "http://127.0.0.1:8081/v1",
      "model": "gemma-4-E4B-it-UD-Q4_K_XL",
      "max_tokens": 40,
      "temperature": 0.7,
      "num_ctx": 8192
    },
    "asr": {
      "provider": "whisperx",
      "base_url": "http://127.0.0.1:8095",
      "model": "medium",
      "language": "ru",
      "command_endpointing_ms": 3000,
      "reply_window_sec": 4.0,
      "reply_absolute_deadline_sec": 12.0
    },
    "wake_word": {
      "provider": "openwakeword",
      "model_path": "data/wake_word/adam.onnx",
      "wake_word_required": true,
      "threshold": 0.35,
      "debounce_hits": 3,
      "wake_silence_timeout_sec": 6.0
    },
    "tts": { "speaker": "eugene", "output_device": "plughw:1,3", "sample_rate": 48000 }
  },
  "mcu": {
    "base_url": "http://192.168.0.171",
    "speaker_url": "http://192.168.0.171:81/speaker"
  },
  "safety": {
    "motor_default_duration_ms": 900,
    "motor_max_duration_ms": 2500,
    "motor_cooldown_ms": 250,
    "half_duplex_mute": true
  }
}
```

---

## ESP32 Firmware

**Директория:** `Subsystem/AdamsServer/`  
**Toolchain:** PlatformIO  
**Статический IP:** `192.168.0.171`

Ключевые API endpoints:
- `GET /api/status` — runtime status
- `POST /api/pca9685/scene` `{"scene":"boot_idle"}` — сцена моторики
- `POST /api/pca9685/channel` — один PWM канал (0–15, value 0–4095)
- `POST /api/sound/play?name=boot|success|tone` — системный звук
- `GET /api/audio/clip?ms=2000` — WAV clip с микрофона
- `WS /ws` — push телеметрия

Allowed scenes: `boot_idle`, `all_on`, `alternating`

**Flash с Windows:**
- `COM7` = USB TO SERIAL → прошивка
- `COM6` = USB OTG/CDC → логи
- `tools/flash_com7.ps1` — serial flash
- `tools/flash_ota.ps1 -Host 192.168.0.171` — OTA Wi-Fi

**НЕ коммитить:** `config/PrivateConfig.h` (Wi-Fi credentials)

---

## Персона и контент

**Директория:** `Agent Adam Chip/`

| Файл | Назначение |
|------|-----------|
| `About/Identity.md` | Характер, самоопределение |
| `About/Lore.md` | Нарратив, история, лор |
| `About/Abilities.md` | Возможности агента |
| `About/Echoes.md` | Пул готовых реплик (EchoGate) |
| `About/Chinese_lines.md` | Китайские реплики (отдельный EchoGate) |
| `Tuning.json` | Hot-reload параметры: mood weights, temperature |

**AIIM-кодировка личности:** ядро `se`/`co`, тип INTP/5w4. Детали — в `About/Identity.md`.

---

## Эпизодическая память

- **Диалоговая БД:** `data/adam/memory.sqlite3` — таблицы `dialogue_turns`, `notes`
- **Эпизоды:** `data/adam/memory/episodes/*.jsonl` — JSONL-файлы по дате; salience scoring при записи
- **Семантика:** `data/adam/memory/semantic.md` — кюрированные наблюдения (4 фиксированных раздела)
- **Events stream:** `data/adam/events.jsonl` — структурированный лог событий (ring buffer 500)
- **Метрики:** `data/adam/inference_metrics.jsonl` — latency per turn (asr_ms, llm_ms, tts_ms)
- **Консолидация:** `Engineering/consolidator.py` + `deploy/systemd/adam-consolidator.timer` (ежедневно)

---

## Systemd Services

```
adam-llm.service            llama.cpp inference (NVIDIA CUDA)
adam-tts-silero.service     Silero TTS HTTP
adam-asr-whisperx.service   WhisperX ASR (CUDA, Docker)
adam-orchestrator.service   FastAPI orchestrator (type=notify)
adam-exhibition.target      Exhibition target (wants orch + tts)
adam-consolidator.service   Memory consolidation
adam-consolidator.timer     Daily schedule
```

**Установка:** `./scripts/adam_install_systemd.sh`  
**Порядок запуска:** llm → tts → asr → orchestrator

---

## Ключевые принципы (инварианты)

1. **LLM = чистый русский текст** для TTS. JSON в LLM-ответе запрещён.
2. **Action layer независим** от голоса. Ошибка action → `no_action`, речь продолжается.
3. **Inference только на Jetson.** ESP32 — периферия, не AI-узел.
4. **Power gate** обязателен в exhibition: `nvpmodel -m 0` + `jetson_clocks`.
5. **WebRTC не использовать** в inference path.
6. **half_duplex_mute = true** — mic mute во время TTS playback.
7. **Wake word «адам»** — обязателен в exhibition mode.

---

## Env Variables

### Orchestrator (System/adam/config.py)

```bash
ADAM_MODE=maintenance|exhibition        # default: maintenance
ADAM_CONFIG=System/Config.json          # path to Config.json
ADAM_DATA_DIR=data/adam                 # data directory (memory, events, metrics)

# MCU / ESP32
ESP_BASE_URL=http://192.168.0.171
ESP_SPEAKER_URL=http://192.168.0.171:81/speaker

# LLM (llama.cpp OpenAI-compat)
ADAM_LLM_PROVIDER=openai
ADAM_LLM_BASE_URL=http://127.0.0.1:8081/v1
ADAM_LLM_MODEL=gemma-4-E4B-it-UD-Q4_K_XL

# TTS (Silero HTTP)
ADAM_TTS_BASE_URL=http://127.0.0.1:8082

# ASR (WhisperX)
ADAM_ASR_PORT=8095
ADAM_ASR_HOST=127.0.0.1

# VLM (VILA via nano_llm Docker)
ADAM_VLM_BASE_URL=http://127.0.0.1:8084
ADAM_VLM_MODEL=Efficient-Large-Model/VILA1.5-3b

# Media
ADAM_VIDEO_DEVICE=/dev/video0
ADAM_AUDIO_INPUT_DEVICE=pulse           # PulseAudio mic; hw:1,0 as fallback
ADAM_AUDIO_OUTPUT_DEVICE=default

# Sounds
ADAM_SUCCESS_SOUND=data/sounds/success.wav
ADAM_SOUNDS_ENABLED=1
```

### ASR WhisperX service (System/Speech/ASR_WhisperX.py)

```bash
ADAM_ASR_PORT=8095
ADAM_ASR_WHISPERX_MODEL=medium          # tiny|base|small|medium|large
ADAM_ASR_LANGUAGE=ru
ADAM_ASR_DEVICE=cuda                    # cuda|cpu|auto
ADAM_ASR_COMPUTE_TYPE=float16           # float32|float16|int8|auto
ADAM_ASR_SAMPLE_RATE=16000
ADAM_ASR_HOST=0.0.0.0
ADAM_MODELS_DIR=Subsystem/Models
HF_HOME=/hf_cache
```

### TTS Silero service (System/Speech/TTS.py)

```bash
ADAM_TTS_HOST=0.0.0.0
ADAM_TTS_PORT=8082
ADAM_TTS_OUTPUT_DEVICE=plughw:1,3      # ALSA: HDMI card 0
ADAM_TTS_PLAYBACK=1                    # 0 = disable local playback
ADAM_TTS_MODEL_PATH=                   # override model .pt path
ADAM_MODELS_DIR=Subsystem/Models
```

### VLM service (System/Speech/VLM.py)

```bash
ADAM_VLM_HOST=0.0.0.0
ADAM_VLM_PORT=8050
ADAM_VLM_MODEL=Efficient-Large-Model/VILA1.5-3b
ADAM_VLM_MAX_TOKENS=48
```

---

## Быстрая диагностика

```bash
# Состояние агента
curl -fsS http://127.0.0.1:8080/api/agent/status | python3 -m json.tool

# Power gate
curl -fsS http://127.0.0.1:8080/api/agent/gate | python3 -m json.tool

# Тестовый диалог
curl -fsS http://127.0.0.1:8080/api/agent/turn \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"Адам, ты меня слышишь?"}' | python3 -m json.tool

# ESP32 статус
curl -fsS http://192.168.0.171/api/status | python3 -m json.tool

# Сервисы
./scripts/adam_service_status.sh
./scripts/adam_healthcheck.sh
./scripts/adam_tts_smoke.sh
```

---

## Что НЕ делать

- ❌ JSON в LLM-ответе
- ❌ `media.video.primary` → ESP32 MJPEG для inference
- ❌ WebRTC в inference path
- ❌ pip install torch с dependency resolver (только Jetson wheel)
- ❌ коммитить `PrivateConfig.h`, `.env`
- ❌ exhibition mode без power gate
После установки NVIDIA PyTorch (Jetson wheel):
```bash
./.venv/bin/python -m pip install --no-deps "silero>=0.5.0"
./.venv/bin/python -m pip install --no-deps "whisperx"
```
(ctranslate2 для aarch64+CUDA — сборка из исходников: `scripts/adam_asr_cuda_check.sh`)

---

## Последние значимые изменения

- ASR мигрирован на WhisperX (CUDA, Docker) — порт 8095, модель medium, WebRTC VAD (CPU, stateless) вместо Silero VAD/RMS threshold; OpenWakeWord (ONNX) как детектор wake word
- fix(speaker): устранены ошибки воспроизведения (silent drop, tail cut, ring full, WAV validation)
- fix(pca9685+audio): исправлен PWM output, добавлены NVS persistence и stereo mic на ESP32
- fix(prompt): VLM-описание сцены оформлено как собственное зрение Адама; сенсоры — как воплощённое состояние
- Audio input: `hw:1,0` → `pulse` (PulseAudio); VAD threshold 650 → 400
- LLM: provider=openai (llama.cpp OpenAI-compat API), порт 8081, max_tokens 80 → 40
- scene_interval_sec: 8 → 4; mcu.speaker_url добавлен (порт 81)
- Добавлен скрипт `adam_asr_cuda_check.sh` для диагностики CUDA/WhisperX
