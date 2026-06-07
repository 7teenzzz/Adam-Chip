# Evaluation Criteria — Verification Backbone

Восемь критериев квазисубъектности из раздела 2.1 диплома. Используются в Stage 2 как обязательный backbone верификации: каждый критерий должен иметь свой файл в `project-verification/by-criterion/` со статусом и graphify-evidence.

**Этот файл — статический.** Описания критериев — заглушки до момента извлечения реальных определений из главы 2 (Stage 1, ch02). После Stage 1 обновить колонку «определение» из `project-analysis/ch02/concepts/evaluation_criteria_extracted.md`.

---

## Crit 1 — Степень автономизации (2.1.1)

- **Определение (placeholder, уточнить после Stage 1):** способность системы инициировать действия и продолжать функционирование без внешнего стимула.
- **Метрика главы 3:** 3.4.4 (интеракционность, инициатива, временная эффективность)
- **Ожидаемые коды-узлы:** `VoiceLoopController`, `SessionWatcher`, `SceneWorker`
- **Verification направления:**
  - Автономный turn-loop без внешнего триггера
  - Background-воркеры (scene, audio health)
  - Idle behavior — есть ли действия без пользователя?

## Crit 2 — Тип агентности (2.1.2)

- **Определение (placeholder):** характеристика того, как агент представляет цели, намерения, планы (BDI / reactive / deliberative).
- **Раздел 3:** 3.1.2 (логика поведения агента)
- **Ожидаемые коды-узлы:** `ActionLayer`, `PromptBuilder`, `EchoGate`
- **Verification направления:**
  - Есть ли явная модель намерений?
  - Reactive ли поведение или присутствует планирование?
  - Как формулируются и удерживаются цели через turn-ы?

## Crit 3 — Устойчивость идентичности (2.1.3)

- **Определение (placeholder):** способность агента сохранять связную «личность» при множественных взаимодействиях.
- **Метрика главы 3:** 3.4.2 (удержание роли)
- **Ожидаемые коды-узлы:** `TuningStore`, `PromptBuilder`, `LeadingNoiseFilter`, AIIM Framework (persona graph)
- **Verification направления:**
  - System prompt как анкер идентичности
  - Anti-drift механизмы
  - AIIM persona configuration
  - Hot-reload tuning без потери identity

## Crit 4 — Режим нормативности (2.1.4)

- **Определение (placeholder):** правила и ограничения, формирующие «приемлемое» поведение агента.
- **Метрика главы 3:** 3.4.2 (нормативная устойчивость)
- **Ожидаемые коды-узлы:** `EchoGate`, `LeadingNoiseFilter`, `salience_score`, action validation в `ActionLayer`
- **Verification направления:**
  - Фильтрация эхо/повторов
  - Salience-формула как нормативный фильтр
  - Whitelist scene/action команд
  - Half-duplex mute как поведенческий инвариант

## Crit 5 — Темпоральная связность (2.1.5)

- **Определение (placeholder):** способность связывать события прошлого с настоящим, поддерживать narrative continuity.
- **Метрика главы 3:** 3.4.3 (память, темпоральная связность)
- **Ожидаемые коды-узлы:** `EpisodicMemory`, `SessionAccumulator`, `MemoryStore`, `Highlight`, consolidator
- **Verification направления:**
  - Реальная persistence (SQLite + JSONL) vs context retention
  - Episode-структуры с timestamps
  - Salience-driven retention
  - Daily consolidation

## Crit 6 — Интеракционность (2.1.6)

- **Определение (placeholder):** качество и связность диалогового цикла со зрителем.
- **Метрика главы 3:** 3.4.4 (интеракционность)
- **Ожидаемые коды-узлы:** `VoiceLoopController`, `WakeWordEngine`, `WebRtcVadWrapper`, `WhisperX`
- **Verification направления:**
  - Wake word + VAD как контур внимания
  - Half-duplex turn-taking
  - Reply window / endpointing
  - Latency budget

## Crit 7 — Воплощённость (2.1.7)

- **Определение (placeholder):** наличие сенсорно-моторного контура, связывающего агента с физическим миром.
- **Раздел 3:** 3.3.2 (перцептивный и моторный слои)
- **Ожидаемые коды-узлы:** `MCUClient`, `ActionLayer`, `CameraReader`, `SceneWorker`, ESP32 firmware
- **Verification направления:**
  - PCA9685 моторика (PWM 16 каналов)
  - INMP441 mic, OV5640 camera как perception
  - PCM5102A speaker как голос
  - Motor safety limits (cooldown, max duration)

## Crit 8 — Уровень эмерджентности (2.1.8)

- **Определение (placeholder):** появление поведенческих свойств, не заложенных явно в коде.
- **Метрика главы 3:** 3.4.5 (интерпретация и ограничения)
- **Ожидаемые коды-узлы:** cross-community connections в graphify, surprising connections в GRAPH_REPORT
- **Verification направления:**
  - Surprising connections из graphify-out
  - Unintended behavior patterns в event log
  - Когда LLM выходит за рамки запрошенного — emergence или artifact?

---

## Status template per criterion (для `project-verification/by-criterion/crit_NN_*.md`)

```markdown
# Crit N — <название>

## Theoretical Definition (from ch02)
<выдержка из извлечённого 2.1.N>

## Implementation Status: FULL / PARTIAL / MISSING / EMERGENT / DECLARED_ONLY

## Graphify Evidence
- node: `<NodeName>`
  source_file: `System/adam/...`
  edges: <count>
  relevant_neighbors: ...

## Verification Trace
1. Query: `/graphify query "<концепт>"`
2. Returned nodes: ...
3. Inspected files: ...

## Findings
- <что реализовано>
- <что отсутствует>
- <архитектурные компромиссы>

## Связь с главой 3
- Описано в разделе: 3.X.Y
- Метрика: 3.4.Z

## Recommendations for Chapter 3 writing
<какие тезисы делать в главе 3 для этого критерия>
```
