# Criterion 1 — Степень автономизации

## Theoretical Definition

Из раздела 2.1.1: уровень внутренней организационной независимости системы. Источник целеполагания. Четыре уровня: реактивный → контекстно-управляемый → проактивный → автогенеративный.

## Implementation Status: **PARTIAL**

Adam Chip достигает **уровня 2 (контекстно-управляемый)** уверенно и частично уровня 3 (проактивный) через фоновые worker'ы.

## Graphify Evidence

| Node | File | Degree | Role |
|---|---|---|---|
| `VoiceLoopController` | System/adam/webrtc_vad.py | 42 | Главный voice loop |
| `SessionWatcher` | System/Orchestrator.py | 30 | Фоновый watcher сессий |
| `SceneWorker` | System/Orchestrator.py | 30 | Периодический VLM-анализ |
| `EspAudioHealthMonitor` | System/Orchestrator.py | 32 | Health-monitoring background loop |

## Verification Trace

1. `graphify query "voice loop autonomy"` → `VoiceLoopController` + `SessionWatcher` + `SceneWorker`.
2. Reading `System/Orchestrator.py`: есть `SessionWatcher` (фоновая задача), `SceneWorker` (VLM каждые `scene_interval_sec`=4с), `EspAudioHealthMonitor` (polling).
3. Reading `Config.json`: `scene_interval_sec: 4`, `scene_stale_after_sec: 8` — фоновая активность настроена.
4. Wake word detection (`wake_word_required: true` в exhibition) — система НЕ инициирует turn без wake word.
5. Нет idle scheduler, генерирующего спонтанные реплики без wake word.

## Findings

**Реализовано:**
- Voice loop с асинхронной обработкой
- Periodic scene analysis (proactive perception)
- Background health monitoring
- Session accumulator (накопление состояния)

**Отсутствует/частично:**
- Спонтанная инициация реплик без wake word (proactive speech)
- Автогенеративная постановка задач (нет планировщика целей)
- LLM не вызывается без внешнего триггера

## Связь с главой 3 диплома

- **Раздел 3.1.2** заявляет «сочетание реактивного и проактивного режимов» — реализовано частично через perception, не через speech.
- **Раздел 3.3.4** описывает «проактивное проявление» — реализовано как scene monitoring, но не как спонтанная речь.
- **Метрика 3.4.4** (интеракционность и инициатива) — операционализирует этот критерий.

## Recommendations for Chapter 3 Writing

В разделе 3.4.4 честно описать: проактивность реализована на уровне perception (SceneWorker, SessionWatcher), но не на уровне speech (нет idle reply generator). Это инженерный компромисс из-за стоимости LLM inference на Jetson.
