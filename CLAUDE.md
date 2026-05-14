# Adam Chip — Claude Code Instructions

See @README.md for project overview and @CONTEXT.md for full system state (inference stack, endpoints, modules, Config.json snapshot).

**Язык общения с пользователем: русский.** Code comments: English.

## Non-obvious invariants — MUST NOT violate

1. **LLM = чистый русский текст.** Никакого JSON, markdown, code blocks в ответе LLM. Action layer работает отдельно парсингом вне LLM.
2. **Action failure ≠ silence.** Если action layer падает → `no_action`, голос всё равно произносится.
3. **Inference только на Jetson.** ESP32 MJPEG и ESP32 mic — диагностика/резерв, не AI-поток.
4. **Power gate** — exhibition mode требует `nvpmodel -m 0` + `jetson_clocks`. Проверяется автоматически при старте.
5. **half_duplex_mute = true** — mic всегда заглушается во время TTS playback.
6. **Wake word «адам»** — в exhibition mode ASR не реагирует без него.

## Gotchas (non-obvious)

- **Gemma 4 E4B — thinking model.** Без флага `--reasoning off` весь output уходит в `reasoning_content`, поле `content` пустое. Флаг прописан в `deploy/systemd/adam-llm.service` — не убирать.
- **SWA cache (ожидаемо медленно).** Gemma 4 E4B = hybrid attention (global + sliding window 512). KV-кэш сбрасывается между turn'ами → full prefill ~2781 токенов каждый раз → ~9с на turn. Это норма, не баг.
- **curl + v2ray proxy.** v2ray (порт 10808) перехватывает localhost-запросы. При диагностике всегда: `curl --noproxy '*' http://127.0.0.1:…`
- **Silero + Jetson PyTorch.** Порядок обязателен: сначала Jetson-compatible wheel PyTorch, потом `pip install --no-deps "silero>=0.5.0"`. Dependency resolver ломает Jetson PyTorch.
- **WhisperX + Jetson CUDA.** `ctranslate2` для aarch64 нужно собирать из исходников с флагом CUDA — pip-пакет CPU-only. Скрипт диагностики: `scripts/adam_asr_cuda_check.sh`. Аналогично Silero: сначала Jetson-compatible PyTorch, затем `pip install --no-deps "whisperx"`. VAD в пайплайне — WebRTC VAD (`webrtc_vad.py`, CPU-only, без PyTorch), не Silero.
- **LLM model ID mismatch.** llama-server отдаёт имя модели с `.gguf` суффиксом, в Config.json без суффикса — это нормально, сервер игнорирует поле `model` в запросах.
- **Аудио устройства.** TTS output = `plughw:1,3` (HDMI, card 1 HDA NVIDIA). Mic input = `pulse` (PulseAudio → WebCamera card 3). hw:1,0 (Jetson APE I2S) физически не работает — не отдаёт PCM данные. hw:0,0 для input — неправильно.
- **ESP32 IP.** Статический IP = `192.168.0.171`.

## Never do

- Не добавлять JSON/code в LLM-ответ
- Не коммитить `Subsystem/AdamsServer/config/PrivateConfig.h` и `.env`
- Не запускать exhibition mode без проверки power gate
- Не ставить PyTorch через pip с dependency resolver на Jetson

## Quick start

```bash
./scripts/adam_bootstrap_venv.sh
./scripts/adam_power_maxn.sh
PYTHONPATH=System ADAM_MODE=maintenance ./.venv/bin/python System/Orchestrator.py
# Verify:
curl --noproxy '*' -fsS http://127.0.0.1:8080/api/agent/status | python3 -m json.tool
```
