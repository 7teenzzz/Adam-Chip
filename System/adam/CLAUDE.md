# System/adam — карта Python-модулей оркестратора

## Правила доступа (обязательно)

- **Config:** только `Settings.load()` или `settings.section("name")` — никогда `DEFAULT_CONFIG` напрямую
- **Сервисы:** только через `inference.py` — не вызывать LLM/TTS/ASR/VLM из других модулей напрямую
- **События:** `events.EventBus` — не `print()`, не `logging.getLogger()`
- **Hot-reload:** `tuning.py` значения читать каждый turn, не кешировать в `__init__`

## Модули (23)

`config.py` — загрузка Config.json, класс Settings, DEFAULT_CONFIG fallback
`inference.py` — адаптеры LLM / VLM / ASR / TTS; единственный выход к сервисам
`prompt.py` — сборка системного промпта из персоны + истории + сцены
`action.py` — ActionLayer: валидация MCU-команд от LLM, safety constraints
`device.py` — HTTP-клиент ESP32: /api/scene, /api/pwm, /api/audio
`memory.py` — SQLite диалоговая память: сохранение turn'ов
`episodic.py` — SessionAccumulator, episodic summary, salience scoring
`echoes_gate.py` — пул готовых реплик Echoes/Chinese_lines, fallback
`tuning.py` — hot-reloadable параметры персоны из Agent Adam Chip/Tuning.json
`metrics.py` — per-turn latency log: inference_metrics.jsonl
`api_runtime.py` — Runtime API: config R/W, SSE /api/events, camera snapshot
`events.py` — EventBus: async pub/sub + JSONL append (data/adam/events.jsonl)
`log_viewer.py` — always-on HTTP сервис порт 8083, read-only logs
`power.py` — Jetson power gate: nvpmodel / jetson_clocks проверка
`media.py` — CameraReader, SceneDescriptionBuffer, ESP32 MJPEG fallback
`camera.py` — низкоуровневый захват кадров, subprocess GStreamer
`sound.py` — Jetson-side cue playback (success.wav, boot.wav)
`ui.py` — Web UI backend: agent / dash / debug страницы
`system.py` — systemd service control через systemctl
`wake_word.py` — OpenWakeWord ONNX детектор, CPU-only, <5ms/frame
`wake_calibration.py` — калибровка wake word: noise profile helpers
`webrtc_vad.py` — WebRTC VAD wrapper, CPU-only, без PyTorch
`System/Orchestrator.py` — главная точка входа (FastAPI + asyncio event loop)
