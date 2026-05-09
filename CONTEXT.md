# Adam Chip — Agent Handoff Context

> Этот файл — полный снимок состояния проекта для передачи контекста новому агенту.
> Дата последнего обновления: 2026-05-07

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
| ESP32-S3 N16R8 WROOM CAM | Периферия: моторы, сенсоры, звук | 192.168.0.172 |

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
| **LLM** | llama.cpp (OpenAI-compat API) | `gemma-4-E4B-it-UD-Q4_K_XL` | http://127.0.0.1:8051/v1 |
| **VLM** | VILA 1.5-3b | `Efficient-Large-Model/VILA1.5-3b` | http://127.0.0.1:8050 |
| **ASR** | Whisper HTTP | `tiny`, ru-RU | http://127.0.0.1:8095 |
| **TTS** | Silero v5_5_ru | голос `eugene` | http://127.0.0.1:8090 |
| **Orchestrator** | FastAPI + asyncio | — | http://127.0.0.1:8080 |

**Whisper wake word:** `адам` (обязателен в exhibition mode)  
**LLM параметры:** temperature=0.7, max_tokens=80, num_ctx=8192  
**TTS output:** ALSA device `plughw:0,3`  
**Audio input:** ALSA `hw:1,0`

> NVIDIA Riva ASR — legacy адаптер (`Speech/ASR.py`), не активен по умолчанию (port 50051).

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

### Speech Services (System/Speech/)

- `ASR_Whisper.py` — Whisper HTTP сервис (основной)
- `ASR.py` — NVIDIA Riva adapter (legacy)
- `TTS.py` — Silero v5_5_ru HTTP сервис

---

## Config.json (System/Config.json)

Актуальные значения на 2026-05-07:

```json
{
  "agent": { "mode": "maintenance", "history_turns": 2 },
  "power": { "required_mode_id": 0, "enforce_in_exhibition": true },
  "media": {
    "video": { "primary": "jetson_gstreamer" },
    "audio": { "input_device": "hw:1,0", "vad_threshold": 650 },
    "scene_interval_sec": 8
  },
  "services": {
    "llm": { "model": "gemma-4-E4B-it-UD-Q4_K_XL", "base_url": "http://127.0.0.1:8051/v1", "max_tokens": 80 },
    "asr": { "provider": "whisper", "base_url": "http://127.0.0.1:8095", "wake_words": "адам" },
    "tts": { "speaker": "eugene", "output_device": "plughw:0,3" }
  },
  "mcu": { "base_url": "http://192.168.0.172" },
  "safety": { "half_duplex_mute": true, "motor_max_duration_ms": 2500 }
}
```

---

## ESP32 Firmware

**Директория:** `Subsystem/AdamsServer/`  
**Toolchain:** PlatformIO  
**Статический IP:** `192.168.0.172`

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
- `tools/flash_ota.ps1 -Host 192.168.0.172` — OTA Wi-Fi

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

- **SQLite БД:** `data/adam/memory.sqlite3`
- **Events stream:** `data/adam/events.jsonl`
- **Notes/Summaries:** `data/adam/notes/`, `data/adam/summaries/`
- **Консолидация:** `Engineering/consolidator.py` + `deploy/systemd/adam-consolidator.timer` (daily)

---

## Systemd Services

```
adam-llm.service            llama.cpp inference (NVIDIA CUDA)
adam-tts-silero.service     Silero TTS HTTP
adam-asr-whisper.service    Whisper ASR HTTP
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

```bash
ADAM_MODE=maintenance|exhibition
ADAM_CONFIG=System/Config.json
ADAM_DATA_DIR=data/adam
ESP_BASE_URL=http://192.168.0.172
ADAM_LLM_MODEL=gemma-4-E4B-it-UD-Q4_K_XL
ADAM_LLM_BASE_URL=http://127.0.0.1:8051/v1
ADAM_TTS_BASE_URL=http://127.0.0.1:8090
ADAM_ASR_HOST=127.0.0.1
ADAM_ASR_PORT=50051
ADAM_VLM_BASE_URL=http://127.0.0.1:8050
ADAM_VIDEO_DEVICE=/dev/video0
ADAM_AUDIO_INPUT_DEVICE=hw:1,0
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
curl -fsS http://192.168.0.172/api/status | python3 -m json.tool

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
- ❌ менять LLM на Ollama без обновления `base_url` в Config.json

После установки NVIDIA PyTorch (Jetson wheel):
```bash
./.venv/bin/python -m pip install --no-deps "silero>=0.5.0"
```

---

## Последние значимые изменения

- LLM мигрирован с Ollama (`gemma3:4b`) на llama.cpp (`gemma-4-E4B-it-UD-Q4_K_XL`, порт 8051)
- ASR мигрирован с NVIDIA Riva на Whisper (`Speech/ASR_Whisper.py`, порт 8095)
- ESP32 IP изменён: `192.168.0.171` → `192.168.0.172`
- Добавлены модули: `echoes_gate.py`, `tuning.py`, `metrics.py`, `episodic.py`, `api_runtime.py`
- Добавлена эпизодическая память с SQLite + ежедневной консолидацией
- Оператор Web UI (`/`, `/dash`, `/debug`) реализован в `adam/ui.py`
- Добавлен Whisper wake word `адам` как обязательное условие в exhibition mode
- Audio input device: `hw:0,0` → `hw:1,0`
