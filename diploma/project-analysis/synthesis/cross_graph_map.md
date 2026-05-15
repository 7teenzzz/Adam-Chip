# Cross-Graph Map — Theory ↔ Code

Таблица соответствий: концепт диплома → узел кодового графа (`graphify-out/`).

| # | Теория (концепт диплома) | Код (node) | Source file | Degree | Confidence |
|---|---|---|---|---|---|
| 1 | Когнитивный цикл | `VoiceLoopController` | System/Orchestrator.py | 42 | HIGH |
| 2 | Эпизодическая память | `EpisodicMemory` | System/adam/memory.py | 29 | HIGH |
| 3 | Сессионная память | `SessionAccumulator` | System/adam/episodic.py | 23 | HIGH |
| 4 | Anti-drift / echo гейт | `EchoGate` | System/adam/echoes_gate.py | 15 | HIGH |
| 5 | Долговременная память (Bio.md) | `TuningStore` + persona files | System/adam/tuning.py | 17 | HIGH |
| 6 | Командный контур (Commander) | `ActionLayer` (action.py) | System/adam/action.py | — | HIGH |
| 7 | Связь с МК (Communication) | `MCUClient` | System/adam/device.py | 25 | HIGH |
| 8 | Визуальная разведка (VLM) | `SceneWorker` + `VLMClient` | System/Orchestrator.py + System/adam/inference.py | 30 + 14 | HIGH |
| 9 | Камера | `CameraReader` | System/adam/camera.py | 23 | HIGH |
| 10 | ASR | `WhisperASRClient` | System/adam/inference.py | 15 | HIGH |
| 11 | TTS | `TTSClient` | System/adam/inference.py | 15 | HIGH |
| 12 | Память (хранилище) | `MemoryStore` | System/adam/memory.py | 14 | HIGH |
| 13 | Event bus / JSONL | `EventLog` | System/adam/events.py | 13 | HIGH |
| 14 | Health monitoring (ESP32 mic) | `EspAudioHealthMonitor` | System/Orchestrator.py | 32 | MEDIUM |
| 15 | Session watcher (proactive) | `SessionWatcher` | System/Orchestrator.py | 30 | MEDIUM |
| 16 | Системный промпт / PromtBuilder | `prompt.py` PromptBuilder | System/adam/prompt.py | — | HIGH |
| 17 | Метрики (3.4) | `metrics.py` | System/adam/metrics.py | — | MEDIUM |
| 18 | Power gate (exhibition) | `power.py` | System/adam/power.py | — | EMERGENT (не в дипломе явно) |
| 19 | AIIM конфигурация | `Tuning.json` + persona graph | Agent Adam Chip/Tuning.json | — | MEDIUM (functional eq, not formula) |
| 20 | Wake word | wake_word config | System/adam/wake_word.py (?) | — | MEDIUM |

**Конфиденс:**
- HIGH — узел существует, имя совпадает по смыслу, ≥10 edges.
- MEDIUM — узел существует, но связь не очевидна или имя расходится.
- EMERGENT — концепт реализован, но в дипломе не заявлен.

---

## Communities в graphify-out/ (47 total, требуют ручной разметки)

Общие группы (на основе god-nodes):
- **Voice loop community** (Orchestrator, VoiceLoopController, SessionWatcher, EspAudioHealthMonitor)
- **Memory community** (EpisodicMemory, SessionAccumulator, MemoryStore)
- **Perception community** (CameraReader, SceneWorker, VLMClient, WhisperASRClient)
- **MCU community** (MCUClient, ActionLayer, device.py)
- **Identity/Persona community** (TuningStore, PromptBuilder, EchoGate)
- **Events community** (EventLog, api_runtime)
