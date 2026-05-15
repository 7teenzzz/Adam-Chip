# Code Graph — Community Labels

Разметка 47 communities из `graphify-out/` на основе их god-nodes. Соответствие концептам диплома указано в скобках.

## Активно-используемые сообщества (10 ключевых)

| ID (suggested) | Label | God-nodes | Связь с дипломом |
|---|---|---|---|
| C-Orchestration | Voice Loop Orchestration | Orchestrator.py (85), VoiceLoopController (42), SessionWatcher (30), EspAudioHealthMonitor (32) | 3.2.1 (общая архитектура), Crit 1 |
| C-Memory | Episodic Memory Layer | EpisodicMemory (29), MemoryStore (14), SessionAccumulator (23) | 3.2.4 (память), Crit 5 |
| C-Identity | Identity & Anti-drift | TuningStore (17), tuning.py (24), EchoGate (15) | 3.2.3 (системный промпт), Crit 3, Crit 4 |
| C-MCU | Motor Control | MCUClient (25), device.py | 3.2.6 (командный контур), Crit 7 |
| C-Perception | Camera + Scene Worker | CameraReader (23), SceneWorker (30), VLMClient (14) | 3.2.5 (визуальный контур), Crit 7 |
| C-ASR | Speech Recognition | WhisperASRClient (15), ASR_WhisperX.py (15) | 3.2.5 (речевой вход), Crit 6 |
| C-TTS | Speech Synthesis | TTSClient (15) | 3.2.5 (речевой выход), Crit 7 |
| C-Events | Events & Metrics | EventLog (13), api_runtime.py (17), metrics.py | 3.4 (метрики), Crit 8 |
| C-Prompt | Prompt Builder | prompt.py (PromptBuilder), LeadingNoiseFilter | 3.2.3, 3.2.4, Crit 3 |
| C-Inference | LLM Inference | inference.py (13), BaseModel (15) | 3.2.2 (программный стек) |

## Малые сообщества (11+ thin)

Остальные сообщества низкой связности — служебные модули, конфигурации, утилиты. Не имеют прямых соответствий в дипломе на уровне концептов.

## Cross-community connections (эмерджентность, Crit 8)

Связи между сообществами:
- `C-Orchestration → C-Memory` (через _run_dialogue_turn_locked)
- `C-Orchestration → C-Perception` (через SceneWorker)
- `C-Orchestration → C-ASR / C-TTS` (через voice loop)
- `C-Prompt → C-Identity` (через TuningStore чтение)
- `C-Prompt → C-Memory` (через retrieval)
- `C-Events → все` (event bus собирает события из всех модулей)

**Это и есть эмерджентный уровень из критерия 8**: поведение не локально в одном модуле, а возникает на пересечениях.
