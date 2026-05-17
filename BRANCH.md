# Branch: V-S08.1-code_rev_ref_opt

**Diverged from:** main @ 86fe6b7 (via V-S07.3-ESP32_mic_fix @ edfe738)
**Goal:** Code review + рефакторинг + оптимизация запуска Адама и голосового пайплайна. Целостность, модульность, удаление дублирования и неиспользуемого кода. Соответствие эталонной логике (см. discuss-сессию в issue/тикете).
**Status:** experimenting
**Merge target:** main
**Merge conditions:**
- Адам стабильно отвечает на все запросы пользователя на длинных сессиях (нет zombie, нет утечек)
- Голосовой пайплайн чёткий: STANDBY → LISTENING → ANSWER → REPLY с эталонными таймингами (6с / 5с / 15с / 10с)
- VoiceLoopController освобождён от legacy ESP-fallback-каскада; ESP — единственный путь через MicReader, `_run_local` оставлен только для maintenance
- UI-статусы «Инициализация / Ожидаю обращения / Слушаю / Распознаю / Думаю / Говорю» отображаются корректно
- Эквалайзер показывает реальный сигнал только после входа в STANDBY, во время инициализации — placeholder

**Modified areas:**
- System/Orchestrator.py — VoiceLoopController (удалить legacy ESP-fallback), вынести `_REPLY_GUARD_SEC`/`_STANDBY_GUARD_SEC` в Config, упростить `_vad_loop`
- System/Config.json — `wake_silence_timeout_sec=6`, `reply_silence_timeout_sec=5`, новый `reply_max_segment_ms=10000`, `filler_enabled=false` по умолчанию, два guard-параметра
- System/Config.schema.json — описания нового/изменённых полей
- System/adam/mic_reader.py — потенциально удалить дублирование с VoiceLoopController после рефакторинга
- System/WebUI/static/js/panels/chat.js — проверить mapping voice_state + ANSWER-events → UI-статусы
- System/WebUI/static/js/widgets/wakeMeter.js — проверить gating эквалайзера на pipelineReady

**Global changes:** да — изменяются runtime-тайминги голосового пайплайна, default filler выключен, удалены legacy fallback-поля из status API. UI-консюмерам не ломаем, но переходные SSE-поля (`esp_bg_retry_active`, `force_esp_retry_available`, `esp_mic_fallback`) пропадают.

**Notes for agents:**
- Read `.planning/phases/08-voice-pipeline-refactor/REVIEW.md` for the full code-review findings before touching anything.
- Read `.planning/phases/08-voice-pipeline-refactor/PLAN.md` for the atomic-commit task breakdown.
- Эталонная логика (источник истины) — в discuss-сессии этого ветка (см. messages в pr/тикете).
- При мёрже в main удалить этот файл (`git rm BRANCH.md`).
