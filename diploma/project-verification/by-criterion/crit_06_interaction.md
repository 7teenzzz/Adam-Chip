# Criterion 6 — Интеракционность

## Theoretical Definition

Из раздела 2.1.6: характер взаимодействия. Четыре типа: реактивное → диалоговое → кооперативное → координационное.

## Implementation Status: **PARTIAL** (диалоговое, без кооперации)

Adam Chip — **диалоговое взаимодействие** уверенно; кооперативное и координационное отсутствуют (single-agent).

## Graphify Evidence

| Node | File | Role |
|---|---|---|
| `VoiceLoopController` | System/adam/webrtc_vad.py | 42 — voice loop |
| `WakeWordEngine` | System/adam/wake_word.py | Wake word detection |
| `WhisperASRClient` | System/adam/inference.py | 15 — ASR |
| `TTSClient` | System/adam/inference.py | 15 — TTS |
| `webrtc_vad.py` | System/adam/webrtc_vad.py | VAD |
| `SessionAccumulator` | System/adam/episodic.py | 23 — context retention |

## Verification Trace

1. Voice pipeline: WakeWord → VAD → ASR → LLM → TTS + MCU. Подтверждено в `Orchestrator.py`.
2. `Config.json` → `agent.history_turns: 2` — контекст диалога удерживается.
3. `Config.json` → `services.asr.reply_window_sec: 3.75` — система ждёт продолжения речи.
4. `Config.json` → `safety.half_duplex_mute: true` — mic заглушается во время TTS.
5. `Config.json` → `services.tts.filler_enabled: true` + `filler_phrase: "Хм..."` — снижение perceived latency.
6. Wake word required в exhibition mode → реактивное активирование.

## Findings

**Соответствует «диалоговому взаимодействию» (таблица 8):**

- ✅ Удержание контекста (SessionAccumulator + history_turns)
- ✅ Обмен репликами (full voice loop)
- ✅ Half-duplex (защита от echo feedback)
- ✅ Filler phrases (snижают «мёртвое» ожидание)
- ❌ Кооперативное — нет (нет совместных задач)
- ❌ Координационное — нет (single-agent)
- ⚠️ Реактивный режим — wake word required в exhibition

## Связь с главой 3

- **Раздел 3.2.5** (перцептивный/речевой контуры) — полностью соответствует.
- **Раздел 3.3.4** (сценарий взаимодействия) — описывает 4 режима.
- **Метрика 3.4.4** (интеракционность и инициатива) — операционализирует.

## Recommendations for Chapter 3

В разделе 3.2.5 явно описать pipeline: WakeWord → VAD → ASR → LLM → TTS + MCU, с указанием Config-параметров. В разделе 3.4.4 — метрики: average dialogue length, response latency, wake_word_accuracy, half_duplex_violations.
