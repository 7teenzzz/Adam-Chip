# Phase 11 — Voice Pipeline Refactor: Master Plan

**Branch:** `V-S08.1-code_rev_ref_opt`
**Goal:** довести voice pipeline до соответствия эталонной логике; устранить дублирование, удалить мёртвый код, повысить стабильность.
**Source:** [REVIEW.md](REVIEW.md) — full code-review findings
**Status:** ready for execution

## Reference logic (источник истины)

| Стадия | Параметр | Значение |
| --- | --- | --- |
| STANDBY | wake word | «адам» (OWW) |
| LISTENING | silence → STANDBY | **6 сек** |
| LISTENING | end-of-utterance silence | 1.5 сек |
| LISTENING | max segment | 15 сек |
| REPLY | guard после TTS | 0.6 сек |
| REPLY | silence → STANDBY | **5 сек** |
| REPLY | end-of-utterance silence | 1.5 сек |
| REPLY | max segment | **10 сек** |
| Mic OFF | до STANDBY | UI-only gate (MicReader дренирует socket всё время) |
| filler | по умолчанию | **выключен** |

## Plans

| # | Plan | Файлы | Объём |
| --- | --- | --- | --- |
| **11-01** | Config defaults + schema (эталонные тайминги + filler off) | Config.json, Config.schema.json | ~50 LOC |
| **11-02** | Удалить legacy ESP-fallback каскад из VoiceLoopController | Orchestrator.py | ~-200 LOC |
| **11-03** | Удалить /api/voice/force_esp_retry endpoint + UI «Подключиться к ESP» | Orchestrator.py, settings.js | ~-150 LOC |
| **11-04** | Cleanup статуса + удалить deprecated `_command_endpointing_ms` алиас | Orchestrator.py | ~-30 LOC |
| **11-05** | Переименовать `wake_word.wake_silence_timeout_sec` → `services.asr.listening_silence_timeout_sec` (с deprecated alias) | Config.json, Config.schema.json, Orchestrator.py, settings.js | ~40 LOC |
| **11-06** | Verification: smoke test full pipeline | (тест-сценарий) | — |

## Execution order

11-01 → 11-02 → 11-03 → 11-04 → 11-05 → 11-06.

11-01 — самое раннее, потому что values читаются в `__init__` `VoiceLoopController`. Если запустить рефакторинг до правки Config, новые поля будут читаться с дефолтами кода.

11-02 и 11-03 связаны (force_esp_retry зависит от _esp_mic_fallback). Делать строго по порядку.

## Out of scope

- MicReader (Phase 7 завершён, архитектура чистая)
- Speech-сервисы (TTS/ASR/VLM — отдельные процессы, internal logic solid)
- `_stream_llm_and_speak` concurrent pipeline (работает корректно)
- LeadingNoiseFilter / sanitize_reply
- Memory system / EchoesGate
- power_gate
- adam_start.sh — соответствует эталону

## Risks

- **R1:** правка Config.json default'ов сломает текущие endpointing tests (некоторые могут полагаться на 3/4 значения). → **Mitigation:** 11-06 включает прогон существующих тестов.
- **R2:** удаление legacy ESP-fallback может затронуть hot-reload в `_rebuild_clients` line 3367-3389. → **Mitigation:** просмотр всех ссылок на удаляемые поля перед изменением.
- **R3:** UI button «Подключиться к ESP» уже знают операторы. → **Mitigation:** удаление с пометкой в BRANCH.md и commit message.
- **R4:** удаление SSE-полей `force_esp_retry_available` / `esp_bg_retry_active` ломает старых UI-клиентов, если они кешированы. → **Mitigation:** hard-reload UI на первом старте после деплоя.

## Deferred ideas (не в этой фазе)

- Endpointing debounce helper-класс (Q4: оставлено inline)
- Guard secs в Config (Q3: оставлено хардкодом)
- `_run_local` retry-backoff в Config (Q2: оставлено хардкодом)

## Success criteria (Done definition)

После 11-06:
1. `voice_loop` стартует за ≤ 5 retries × 2 сек ✓ (уже работает)
2. В LISTENING если молчать 6 секунд — возврат в STANDBY (event `wake_silence_timeout`)
3. В REPLY если молчать 5 секунд — возврат в STANDBY (event `reply_window_expired`)
4. В REPLY max 10 секунд диктовки → автоматическое endpointing
5. UI статусы корректно меняются: Инициализация → Ожидаю обращения → Слушаю → Распознаю → Думаю → Говорю → Слушаю
6. Эквалайзер показывает реальный сигнал только после входа в STANDBY
7. `VoiceLoopController` не содержит legacy ESP-fallback полей
8. `/api/voice/force_esp_retry` отсутствует
9. Filler по умолчанию выключен (`filler_enabled=false`)
10. Существующие тесты в `tests/` зелёные
