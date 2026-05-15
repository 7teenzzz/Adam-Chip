# Subjectivity Framework — Концепты главы 1

Извлечение из главы 1: философские и технологические основания цифровой субъектности.

---

## Концепты от деконструкции (1.1.2)

### IntentionalConsciousness (Husserl)
- **Theoretical origin.** «Всякое сознание есть сознание о чём-то» — Гуссерль, 1913.
- **Computational interpretation.** Контекст не пуст — каждое внутреннее состояние агента направлено на объект (turn, сцену, память).
- **Runtime implication.** Prompt всегда содержит scene + history + persona, не голую инструкцию.
- **Architectural requirement.** Контекстная сборка через PromptBuilder.

### PerformativeIdentity (Goffman, Butler)
- **Theoretical origin.** Идентичность — режим исполнения, поддерживаемый повторением.
- **Computational interpretation.** Identity не fixed entity, а pattern поведенческих актов.
- **Runtime implication.** Каждый turn — performative act, удерживаемый персона-файлами + системным промптом.
- **Architectural requirement.** Anti-drift mechanisms (echo gate, leading noise filter).

### Dispositif (Foucault)
- **Theoretical origin.** Дискурс/власть формирует субъекта через нормативные практики.
- **Computational interpretation.** Системный промпт + action whitelist + safety constraints формируют поведенческий режим.
- **Runtime implication.** Limit space действия определён конфигурацией.
- **Architectural requirement.** Action layer как nominee нормативной рамки.

### NarrativeIdentity (Ricoeur)
- **Theoretical origin.** Самость (ipse) удерживается через связность истории, не через субстанцию (idem).
- **Computational interpretation.** Идентичность поддерживается памятью + историей turn'ов.
- **Runtime implication.** Без памяти агент теряет себя между сессиями.
- **Architectural requirement.** Episodic memory + session accumulator + long-term summaries.

---

## Концепты от постгуманизма (1.1.4)

### DistributedAgency (Latour)
- **Theoretical origin.** Действие распределено по сети акторов, не локализовано в одной точке.
- **Computational interpretation.** Behavior — эффект координации orchestrator + memory + tools + persona + perception.
- **Runtime implication.** Single-agent система может быть актор-сетью внутри себя.
- **Architectural requirement.** Event bus + multiple modules + observable coordination.

### EmbodiedCognition (Clark, Chalmers)
- **Theoretical origin.** Когнитивные процессы распределены по внешним компонентам (extended mind).
- **Computational interpretation.** Память на диске = расширение «мышления» агента.
- **Runtime implication.** Cognition outside the LLM (SQLite memory, JSONL events).
- **Architectural requirement.** External memory layer, persistent storage.

### MaterialityOfInformation (Hayles)
- **Theoretical origin.** Информация всегда воплощена в материальном носителе.
- **Computational interpretation.** Инсталляция = информация + физический носитель (Jetson + ESP32 + моторы).
- **Runtime implication.** Поведение зависит от hardware constraints (power, latency, audio devices).
- **Architectural requirement.** Hardware-aware orchestrator (power gate, device detection).

---

## Квазисубъектность (1.1.5)

### Quasisubjectivity
- **Definition.** Достаточные условия для субъектоподобного поведения без полного сознания.
- **Operationalization.** Эффект устойчивости + включённости + нарративной связности + нормативной организации + воплощённости.
- **Engineering target.** Не сознание, а инженерная планка субъектоподобного режима.

---

## Технические парадигмы (1.2)

### TransformerCore (1.2.1)
- **Role.** Базовый языковой модуль (LLM).
- **Implementation.** Gemma-4-E4B (llama.cpp) в Adam Chip.

### CognitiveLoop (1.2.2)
- **Role.** Cycle perception → memory → planning → action → reflection → update.
- **Implementation.** VoiceLoopController в Orchestrator.py.

### CompositionalArchitecture (1.2.3)
- **Role.** Агент собран из нескольких логик: model + memory + tools + reflection + affective layer.
- **Implementation.** System/adam/ модули (inference, memory, action, tuning, prompt, echoes_gate).

### AgentIdentityBehavior (1.2.4)
- **Role.** Идентичность через системный промпт + памяти + ограничения.
- **Implementation.** Persona files + TuningStore + PromptBuilder.

### MultiAgentSystems (1.2.5)
- **Role.** Распределённая координация.
- **Adam Chip status.** Single-agent (но с модульной composition).

---

## 8 cognitive cycle stages (1.2.2)

Из ch01:

1. **Восприятие** — input acquisition.
2. **Аффективная** оценка — emotional/salience weighting.
3. **Извлечение** памяти — retrieval.
4. **Интерпретация** — semantic parsing.
5. **Планирование** — action selection.
6. **Действие** — motor/speech execution.
7. **Рефлексия** — post-action evaluation.
8. **Обновление** — memory write + state update.

**Маппинг на Adam Chip:**
| Stage | Adam Chip компонент |
|---|---|
| Восприятие | CameraReader + WhisperX ASR + WebRTC VAD |
| Аффективная | (отсутствует как отдельный модуль — embedded в LLM) |
| Извлечение | EpisodicMemory.retrieve() + recent turns |
| Интерпретация | LLM (prefill в Gemma) |
| Планирование | LLM (генерация ответа + action) |
| Действие | TTS + MCUClient + ActionLayer |
| Рефлексия | (частично — через consolidator) |
| Обновление | EpisodicMemory.append() + JSONL event log |
