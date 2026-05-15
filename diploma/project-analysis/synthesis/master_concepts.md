# Master Concepts — Diploma Architecture Registry

Дедуплицированный реестр концептов из глав 1–3 диплома, с привязкой к коду System/.

---

## Concept: QuasiSubjectivity
- **chapters:** [1.1.5, 2.1, 3.1, 3.4]
- **definition:** Достаточные условия для субъектоподобного режима поведения без полного сознания. Эффект устойчивости + включённости + нарративной связности + нормативной организации + воплощённости.
- **theoretical_role:** Инженерная планка субъектоподобного режима. Backbone верификации.
- **code_correspondence:** Эффект всей системы (composite); не один узел.
- **evidence_file:** все ключевые модули System/adam/
- **tension:** В дипломе — гуманитарный концепт; в коде — operational target без явной метрики.

---

## Concept: NarrativeIdentity
- **chapters:** [1.1.2, 1.1.5, 2.1.3]
- **definition:** Идентичность через связность истории во времени (Рикёр, ipse). Поддерживается памятью и повторением.
- **theoretical_role:** Источник устойчивости поведения.
- **code_correspondence:** `EpisodicMemory` + `SessionAccumulator` + persona files
- **evidence_file:** System/adam/memory.py, System/adam/episodic.py, Agent Adam Chip/About/*.md

---

## Concept: PerformativeIdentity
- **chapters:** [1.1.2, 2.1.3]
- **definition:** Идентичность как режим исполнения (Гоффман, Батлер). Поддерживается повторяемостью актов.
- **theoretical_role:** Anti-drift через повторяющиеся паттерны.
- **code_correspondence:** `TuningStore` + `PromptBuilder` + системный промпт
- **evidence_file:** System/adam/tuning.py, System/adam/prompt.py

---

## Concept: CognitiveLoop
- **chapters:** [1.2.2, 3.2.1, 3.3.4]
- **definition:** Cycle perception → memory → planning → action → reflection → update.
- **theoretical_role:** Runtime backbone агента.
- **code_correspondence:** `VoiceLoopController` (42 edges)
- **evidence_file:** System/Orchestrator.py

---

## Concept: EpisodicMemory (концепт)
- **chapters:** [1.2.3, 3.2.4]
- **definition:** Память отдельных эпизодов (turn'ов, событий). Salience-based retrieval.
- **theoretical_role:** Темпоральная связность.
- **code_correspondence:** `EpisodicMemory` (29 edges)
- **evidence_file:** System/adam/memory.py + System/adam/episodic.py

---

## Concept: AIIM_Framework
- **chapters:** [3.1.1, 3.2.3]
- **definition:** Artificially Integrated Identity Matrix (Вересова). 12 аспектов × 5 плоскостей × 4 уровня зрелости. Формула `[аспект](плоскость уровень состояние)Δприоритет`.
- **theoretical_role:** Формализация конфигурации идентичности.
- **code_correspondence:** `TuningStore` + persona files (косвенно — AIIM-формула не реализована буквально, но её роль выполняет Tuning.json + персона)
- **evidence_file:** Agent Adam Chip/Tuning.json + persona graph (graphify-out-persona/)
- **tension:** Диплом описывает AIIM-формулу явно, код реализует функционально-эквивалентную конфигурацию без буквального синтаксиса формулы.

---

## Concept: PromptAssembly (PromtBuilder)
- **chapters:** [3.2.3]
- **definition:** Иерархическая сборка запроса к LLM из 4+1 слоёв: system + persona + memory + perception + stimulus.
- **theoretical_role:** Balance между context richness и latency.
- **code_correspondence:** `PromptBuilder` (in prompt.py)
- **evidence_file:** System/adam/prompt.py

---

## Concept: ActionLayer (Commander)
- **chapters:** [3.2.6]
- **definition:** Постпроцессинг LLM-ответа: извлечение state markers ([радость], [грусть]), валидация против whitelist, перевод в команды МК.
- **theoretical_role:** Жёсткая редукция между языковым уровнем и физическим исполнением.
- **code_correspondence:** `ActionLayer` (in action.py) + `MCUClient` (device.py)
- **evidence_file:** System/adam/action.py, System/adam/device.py

---

## Concept: Embodiment / Technoflora
- **chapters:** [3.1.2, 3.3.2]
- **definition:** Распределённое тело агента: светофлора + аудиофлора + виброфлора.
- **theoretical_role:** Воплощённость как критерий квазисубъектности.
- **code_correspondence:** `MCUClient` (25) + ESP32 firmware + TTS playback
- **evidence_file:** System/adam/device.py + Subsystem/AdamsServer/

---

## Concept: SceneWorker (VLM)
- **chapters:** [3.2.2, 3.2.5]
- **definition:** Быстрая визуальная разведка через VLM (VILA1.5-3B). Условный вызов.
- **theoretical_role:** Визуальный perception channel.
- **code_correspondence:** `SceneWorker` (30 edges) + `CameraReader` (23)
- **evidence_file:** System/Orchestrator.py + System/adam/camera.py + System/adam/inference.py

---

## Concept: WakeWord + VAD
- **chapters:** [3.2.5]
- **definition:** Триггер активации голосового контура. VAD отсекает шум.
- **theoretical_role:** Граница события (perception → cognition).
- **code_correspondence:** OpenWakeWord ONNX + WebRTC VAD
- **evidence_file:** System/adam/wake_word.py (?) + System/adam/webrtc_vad.py

---

## Concept: ProactiveMode
- **chapters:** [3.1.2, 3.3.4]
- **definition:** Система инициирует действия без внешнего стимула. Снимает чисто реактивную природу.
- **theoretical_role:** Уровень автономизации (crit 1).
- **code_correspondence:** `SessionWatcher` (30) + background workers
- **evidence_file:** System/Orchestrator.py
- **tension:** Диплом описывает proactive mode развёрнуто (4 режима поведения); код имеет SessionWatcher и SceneWorker, но «спонтанные реплики без триггера» под вопросом.

---

## Concept: AntiDrift / EchoGate
- **chapters:** [2.1.3, 3.2.3, 3.4.2]
- **definition:** Механизмы удержания роли: фильтрация повторов, нормативные ограничения.
- **theoretical_role:** Устойчивость идентичности (crit 3).
- **code_correspondence:** `EchoGate` (15) + `LeadingNoiseFilter`
- **evidence_file:** System/adam/echoes_gate.py + System/adam/prompt.py

---

## Concept: PowerGate
- **chapters:** [3.2.2, 3.3.1]
- **definition:** Hardware constraint: exhibition mode требует MAXN + jetson_clocks.
- **theoretical_role:** Материальная воплощённость (Хейлз) — hardware shapes behavior.
- **code_correspondence:** `power.py`
- **evidence_file:** System/adam/power.py
- **tension:** В дипломе явно не упоминается; emerges из инженерной практики.

---

## Concept: MetricsAndEvents
- **chapters:** [3.4.1, 3.4.2–3.4.5]
- **definition:** Логирование удержания роли, длительности, задержки, интеракционности.
- **theoretical_role:** Эмпирическая база для оценки квазисубъектности.
- **code_correspondence:** `metrics.py` + `EventLog` (13) + JSONL + `/api/agent/turns`
- **evidence_file:** System/adam/metrics.py, System/adam/events.py
