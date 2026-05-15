# 8 Criteria → Code Mapping

Маппинг 8 критериев квазисубъектности (раздел 2.1) на конкретные узлы кодового графа.

---

## Crit 1: Степень автономизации

- **code_nodes:** `VoiceLoopController`, `SessionWatcher`, `SceneWorker`, `EspAudioHealthMonitor`
- **evidence_files:** System/Orchestrator.py, System/adam/inference.py
- **coverage_estimate:** PARTIAL
- **reasoning:** Есть voice loop + scene worker + session watcher (background tasks), но проактивная инициация реплик без внешнего триггера не подтверждена. Cycle всё ещё инициируется wake word или таймером.

---

## Crit 2: Тип агентности

- **code_nodes:** `Orchestrator`, `VoiceLoopController`, `ActionLayer`, `PromptBuilder`, `EpisodicMemory`, `MCUClient`
- **evidence_files:** System/Orchestrator.py, System/adam/*.py, Subsystem/AdamsServer/
- **coverage_estimate:** FULL
- **reasoning:** Архитектура модульная: единый orchestrator + распределённая инфраструктура (memory, persona, tools). Соответствует типу «модульная агентность» из таблицы 4.

---

## Crit 3: Устойчивость идентичности

- **code_nodes:** `TuningStore`, `PromptBuilder`, `EchoGate`, persona graph
- **evidence_files:** System/adam/tuning.py, System/adam/prompt.py, System/adam/echoes_gate.py, Agent Adam Chip/About/
- **coverage_estimate:** FULL
- **reasoning:** Несколько уровней удержания роли: системный промпт + персона-файлы (Identity, Lore, Abilities) + TuningStore (hot-reload параметров) + EchoGate (anti-repeat). AIIM-формула буквально не реализована, но функциональная эквивалентность через Tuning.json.

---

## Crit 4: Режим нормативности

- **code_nodes:** `ActionLayer`, `EchoGate`, `LeadingNoiseFilter`, salience rules в `episodic.py`
- **evidence_files:** System/adam/action.py, System/adam/echoes_gate.py, System/adam/prompt.py, System/adam/episodic.py
- **coverage_estimate:** FULL
- **reasoning:** Нормативность через action whitelist (`allowed_scenes`), safety constraints (motor_max_duration_ms, cooldown, half_duplex_mute), echo gate (фильтрация повторов), salience scoring (правила приоритизации памяти). Соответствует «ограниченно-внутренний» тип нормативности.

---

## Crit 5: Темпоральная связность

- **code_nodes:** `EpisodicMemory`, `SessionAccumulator`, `MemoryStore`, `consolidator.py`
- **evidence_files:** System/adam/episodic.py, System/adam/memory.py, Engineering/consolidator.py
- **coverage_estimate:** FULL
- **reasoning:** Многоуровневая память: working history + episodic SQLite + JSONL events + persona files + daily consolidation. Поддерживает уровни «нарративная связность» и стремится к «процессуальная связность».

---

## Crit 6: Интеракционность

- **code_nodes:** `VoiceLoopController`, wake word engine, WebRTC VAD, `EspAudioHealthMonitor`
- **evidence_files:** System/Orchestrator.py, System/adam/webrtc_vad.py, System/adam/wake_word.py
- **coverage_estimate:** PARTIAL
- **reasoning:** Диалоговое взаимодействие реализовано (turn-based с контекстом). Кооперативное/координационное — нет (single-agent). Half-duplex muting защищает от echo feedback. Filler phrases снижают perceived latency.

---

## Crit 7: Воплощённость

- **code_nodes:** `MCUClient`, `ActionLayer`, `CameraReader`, `SceneWorker`, TTS playback (ALSA HDMI)
- **evidence_files:** System/adam/device.py, System/adam/action.py, System/adam/camera.py, Subsystem/AdamsServer/
- **coverage_estimate:** FULL
- **reasoning:** Физический уровень воплощённости (таблица 9): камера + аудио вход + TTS вывод + ESP32 motor layer + сенсоры. Соответствует «физическая» воплощённость.

---

## Crit 8: Уровень эмерджентности

- **code_nodes:** Cross-community connections (47 communities в graphify) + Event bus
- **evidence_files:** graphify-out/GRAPH_REPORT.md, System/adam/events.py
- **coverage_estimate:** PARTIAL
- **reasoning:** Локальный уровень — отчётливо (каждый модуль определяет своё поведение). Интеракционный — есть (LLM + memory + scene + tuning composition). Системный — частично (event bus, async coordination). Эмерджентные эффекты (например, «голос становится тише при отсутствии зрителя») зависят от множества модулей.
