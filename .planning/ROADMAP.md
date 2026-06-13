# Adam-Chip — Roadmap

**Project:** Adam Chip — выставочный ИИ-агент на Jetson Orin NX
**Goal:** Поддерживать систему в рабочем, документированном и выставочно-готовом состоянии
**Requirements:** [REQUIREMENTS.md](REQUIREMENTS.md)

---

## Phase 1: Doc Refactor — Концепция C + A

**Goal:** Устранить несоответствия между документацией и кодом; удалить дублирование; ввести Config.schema.json как единый источник истины для параметров; сократить поверхность документации до минимума (Концепция C + элемент A).

**Requires:** Аудит документации выполнен (завершён 2026-05-15)

**Delivers:**

- Исправлены все критические несоответствия (ASR model, wake word params, RUNBOOK)
- CONTEXT.md удалён (содержимое поглощено README.md там, где нужно)
- README.md упрощён: только архитектура и быстрый старт, без числовых параметров
- CLAUDE.md очищен: только инварианты и gotchas, без числовых параметров
- docs/RUNBOOK_JETSON_EXHIBITION.md обновлён: убраны Ollama-defaults, исправлен audio device
- System/Config.schema.json создан с описаниями каждого параметра (элемент A)
- DEFAULT_CONFIG в System/adam/config.py синхронизирован с реальным Config.json

**Mode:** standard

**Requirements:** DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06, DOC-07

**Plans:** 4 plans

**Completed:** 2026-05-15 (3 atomic commits: `863c204`, `8fcc58d`, `e02811e` range, + doc refactor commits)

Plans:

- [x] 01-01-PLAN.md — Quick fixes: исправить ASR model, threshold, debounce в CONTEXT.md/README.md; удалить Ollama-defaults из RUNBOOK
- [x] 01-02-PLAN.md — Config schema: создать System/Config.schema.json с JSON Schema описаниями всех параметров
- [x] 01-03-PLAN.md — Structural refactor: заменить CONTEXT.md указателем; упростить README.md и CLAUDE.md
- [x] 01-04-PLAN.md — Code sync: синхронизировать DEFAULT_CONFIG в config.py с Config.json

---

## Phase 2: Progressive Disclosure — навигация для нового агента

**Goal:** Сделать документацию прогрессивно раскрывающейся: новый агент/аккаунт должен прочитать минимум файлов (CLAUDE.md → README.md → STATE.md) и получить полное понимание текущего состояния проекта, со ссылками на более детальные слои.

**Requires:** Phase 1 завершена

**Delivers:**

- STATE.md обновлён: Phase 1 помечена ✓ COMPLETE с кратким итогом
- ROADMAP.md обновлён: Phase 1 помечена ✓ done с датой
- CLAUDE.md получает раздел "Reading Order" с иерархией файлов и ссылками
- README.md получает секцию "Текущее состояние" со ссылкой на STATE.md
- `.planning/phases/01-doc-refactor-c-a/01-SUMMARY.md` создан — однострочный итог фазы
- Все файлы Level 0–4 имеют перекрёстные ссылки

**Mode:** standard

**Requirements:** NAV-01, NAV-02, NAV-03, NAV-04, NAV-05, NAV-06

**Plans:** 1 plan

Plans:

- [ ] 02-01-PLAN.md — STATE.md + ROADMAP.md update, 01-SUMMARY.md, Reading Order в CLAUDE.md, "Текущее состояние" в README.md

---

## Phase 3: Branch Coordination — контекст для мульти-агентной работы

**Goal:** Дать любому агенту или разработчику, переключившемуся на любую ветку, мгновенное понимание: зачем эта ветка, что в ней трогается, когда можно мёржить. Обеспечить глобальную видимость активных веток для команды (2 разработчика × 2 Claude-аккаунта).

**Requires:** Phase 2 завершена

**Delivers:**

- `docs/BRANCH-template.md` — шаблон BRANCH.md с конвенцией использования (создание при ветвлении, удаление после мёржа без архивирования)
- `.planning/ACTIVE.md` — таблица активных веток: ветка / статус / modified areas / merge blocker
- `CLAUDE.md` обновлён: Reading Order получает строку про BRANCH.md для не-main веток
- `STATE.md` обновлён: ссылка на ACTIVE.md

**Принципы:**

- Имя ветки = идентификатор (нет поля Owner, нет личных имён)
- BRANCH.md удаляется после мёржа без архива
- Только шаблон + конвенция, без ретроактивного заполнения существующих веток

**Mode:** standard

**Requirements:** BR-01, BR-02, BR-03, BR-04

**Plans:** 1 plan

Plans:

- [ ] 03-01-PLAN.md — BRANCH-template.md, ACTIVE.md (git-verified), CLAUDE.md BRANCH.md note, STATE.md ACTIVE.md ссылка

---

## Phase 4: Context Automation — per-directory CLAUDE.md и git hooks

**Goal:** Дать агенту автоматический контекст при переключении директорий и веток: per-directory CLAUDE.md загружается Claude Code без инструкций, git hook создаёт BRANCH.md при ветвлении без ручного шага.

**Requires:** Phase 3 завершена (`docs/BRANCH-template.md` нужен для post-checkout hook)

**Delivers:**

- `Subsystem/AdamsServer/CLAUDE.md` — ESP32 tech context: PlatformIO, запрещённые файлы, OTA, IP, порты
- `System/adam/CLAUDE.md` — карта 23 модулей, `Settings.load()` как единственный entrypoint, service adapter pattern
- `Agent-Adam-Chip/CLAUDE.md` — порядок загрузки персоны, правила редактирования
- `.githooks/post-checkout` — scaffold BRANCH.md при создании не-main ветки
- `.githooks/pre-commit` — warning если BRANCH.md отсутствует на не-main ветке
- root `CLAUDE.md` Quick start обновлён: команда `git config core.hooksPath .githooks`

**Принципы:**

- Per-directory CLAUDE.md только там, где контекст принципиально отличается от root (3 директории, не все)
- Hooks на POSIX sh — работают на Windows (Git's sh.exe) и Ubuntu
- Warnings only, не блоки

**Mode:** standard

**Requirements:** CTX-01, CTX-02, CTX-03, CTX-04, CTX-05, CTX-06

**Plans:** 1 plan

Plans:

- [ ] 04-01-PLAN.md — 3 per-directory CLAUDE.md (ESP32, Python agents, persona) + 2 POSIX sh git hooks + CLAUDE.md Quick start update

---

## Phase 5: Agent Protocol — поведение агента-разработчика

**Goal:** Сделать поведение любого Claude-агента на этом проекте предсказуемым и самодостаточным: агент сам уточняет недостающую информацию, предупреждает о гэпах контекста, использует GSD-принципы при планировании — без инструкций от человека каждый раз.

**Requires:** Phase 2 завершена (Reading Order в CLAUDE.md); Phase 3 завершена (BRANCH.md template для AGT-03 Branch gap); Phase 4 завершена (per-directory CLAUDE.md дополняют AGT-02, не дублируют)

**Delivers:**

- `docs/AGENT-PROTOCOL.md` — полный протокол поведения: режимы работы, триггеры уточнения, классификация гэпов, протокол планирования с inline GSD-форматом
- `CLAUDE.md` обновлён: добавлена ссылка `@docs/AGENT-PROTOCOL.md` и одна строка-подпись

**Принципы:**

- Протокол живёт в отдельном файле — CLAUDE.md остаётся lean entry point
- Только предупреждения, не блоки — агент не должен останавливать работу
- Триггеры конкретные, не «когда неуверен» — привязаны к реальным ситуациям проекта

**Mode:** standard

**Requirements:** AGT-01, AGT-02, AGT-03, AGT-04, AGT-05

**Plans:** 1 plan

Plans:

- [ ] 05-01-PLAN.md — Создать docs/AGENT-PROTOCOL.md (4 секции) и обновить CLAUDE.md с @-референсом

---

## Phase 6A: Memory Foundation — устранение критических дефектов ✓ COMPLETE (2026-05-15)

**Branch:** `Memory-upgrade`

**Goal:** Устранить критические проблемы пайплайна памяти без новых зависимостей.

**Delivers:**

- A1: `Engineering/consolidator.py` — заменён `call_ollama()` на `call_llm()` (llama.cpp OpenAI-compat API)
- A2: Rule-based fallback консолидации при недоступном LLM
- A3: `EpisodicMemory.trim_gate_logs()` — обрезка echoes_used.jsonl + chinese_used.jsonl (параметр `gate_log_max_days`)
- A4: Хардкод вынесен из `echoes_gate.py` в Tuning.json (`score_boost`, `tag_short_cutoff`, `default_entry_weight`)
- A5: `SessionAccumulator.note_turn()` — автотематизация по кластерам из `Tuning.json → memory.theme_clusters`
- A6: `TfIdfMatcher` — TF-IDF поиск для выбора эхо-фрагментов (переключение через `matcher_type`)
- A7: `EpisodicMemory.quick_patch_diary()` — немедленная консолидация если `salience >= instant_threshold`
- A8: `EpisodicMemory.is_recurring()` — обнаружение повторных посетителей (параметры в Tuning.json)

**Commit:** Wave 6A → `f6b2c5a`

---

## Phase 6B: Memory Search, Logging & Quality ✓ COMPLETE (2026-05-15)

**Branch:** `Memory-upgrade`

**Goal:** Векторный поиск по эпизодам (BM25 + FAISS CPU Wave 1), метрики памяти, API, тесты.

**Delivers:**

- B1: `System/adam/memory_search.py` — `BM25Index` (чистый Python, BM25 Okapi)
- B2: `FaissEpisodeIndex` — FAISS CPU + TF-IDF векторы (Wave 1); graceful fallback без faiss-cpu
- B3: `System/adam/memory_metrics.py` — `MemoryMetrics` JSONL-логгер; интеграция в Orchestrator.py + consolidator.py
- B4: `GET /api/memory/status` в `api_runtime.py` — diary_chars, episodes, echoes pool, last_consolidation, metrics_last_24h
- B5: `tests/test_memory_pipeline.py` — 34 теста (unit + E2E), все зелёные
- B6: ROADMAP.md + STATE.md обновлены

**Wave 2 (Backlog):** Neural search — заменить TF-IDF в `FaissEpisodeIndex` на llama.cpp `/embeddings`.
Условие запуска: свободная VRAM ≥ 4 GB при работающем Gemma 4 E4B (~16 GB VRAM Jetson Orin NX 16 GB).

---

## Phase 7: ESP32 Mic Pipeline Refactor — MicReader keep-alive ✓ COMPLETE (2026-05-17)

**Branch:** `V-S07.3-ESP32_mic_fix`

**Goal:** Извлечь работу с ESP32 audio-stream в долгоживущую задачу `MicReader` по аналогу `CameraReader`. Поток открывается до warmup TTS, держится keep-alive весь срок жизни Orchestrator, drainer всегда активен, переоткрытие на exception с экспоненциальным backoff. Voice loop читает chunks из shared queue вместо прямого управления stream. Local fallback отключён по умолчанию.

**Requires:** ESP32 firmware готова к стабильной работе на :81 (после reboot — проверено).

**Delivers:**

- `System/adam/mic_reader.py` (новый модуль) — `MicReader` task: open stream → drain bytes → put в `asyncio.Queue` → reconnect on exception (backoff). Никогда не fallback на local mic, если `disable_local_fallback=true`.
- `System/Orchestrator.py` — `_run_esp32` упрощён до consumer'а на Queue; lifecycle stream вынесен из voice_loop в MicReader. Удалён `_audio_level_monitor` (его роль перенимает MicReader).
- Boot sequence: MicReader стартует в lifespan **до** `_orchestrated_startup`, к моменту warmup TTS поток уже active. Drainer работает всё время, в том числе во время warmup.
- `voice_state="boot_warmup"` (новое значение): voice_loop читает из Queue но не сканирует OWW и не делает endpointing. После warmup → standby.
- `System/Config.json` + `Config.schema.json` — новые ключи: `services.asr.disable_local_fallback` (default true), `esp_open_timeout_sec` (default 8), `esp_probe_after_fails` (default 2), `esp_retry_backoff_sec` (default [2,4,8,15]).
- UI ([chat.js](../System/WebUI/static/js/panels/chat.js), [wakeMeter.js](../System/WebUI/static/js/widgets/wakeMeter.js)): корректное отображение «⌛ Инициализация» во время boot_warmup, плашка Mic и эквалайзер остаются placeholder пока voice_state ≠ standby/listening/reply. После warmup → 💤 Ожидаю обращения + активный эквалайзер + 🟢 Mic: ESP32 stereo.

**Mode:** standard

**Requirements:** ESP-mic должен открыться к моменту warmup TTS; никаких `voice_loop_error stage=esp32_mic` в первые 60 сек после старта; recovery после disconnect <5 сек; никаких переходов на local mic пока `disable_local_fallback=true`.

**Requirement IDs:** REQ-ESP-OPEN-BEFORE-WARMUP, REQ-NO-ESP-ERRORS-AT-BOOT, REQ-RECOVERY-UNDER-5SEC, REQ-NO-LOCAL-FALLBACK, REQ-UI-INIT-STATUS, REQ-UI-STANDBY-LIVE

**Plans:** 4 plans

Plans:

- [x] 07-01-PLAN.md — Config + Schema: 4 new asr keys (`disable_local_fallback`, `esp_open_timeout_sec`, `esp_probe_after_fails`, `esp_retry_backoff_sec`) — commit `f5529b5`
- [x] 07-02-PLAN.md — MicReader module: new `System/adam/mic_reader.py` with class MicReader (producer + audio_level emitter + drain-on-mute) — commit `d67d6d4`
- [x] 07-03-PLAN.md — Orchestrator integration: wire MicReader; delete `_run_esp32`, `_esp32_drain_during_mute`, `_audio_level_monitor`; introduce `boot_warmup` state; rearrange `_orchestrated_startup` — commit `0c358a8`
- [x] 07-04-PLAN.md — UI integration: chat.js boot_warmup label/placeholder, wakeMeter.js pipelineReady gating on voice_state_change(to=standby) — commit `7177d58`

**Verified on user test session 2026-05-17 00:01:05 — 00:10:40 MSK:** mic stream active +108 ms after orchestrator_started, **0** `voice_loop_error stage=esp32_mic`, all 1695 audio_level events `source=esp32_stereo`. See `.planning/phases/07-esp32-mic-pipeline-refactor-micreader-keep-alive/07-SUMMARY.md`.

---

## Phase 8: Reply-Echo-Hang debug — устранить заморозку voice_loop после reply window

**Branch:** TBD (suggest `V-S07.4-reply-echo-hang`)

**Goal:** Устранить полную заморозку Orchestrator (event_log замолкает на 6+ минут), наблюдаемую после `reply_window_expired` с `reason=absolute_deadline`. Корневая причина — повторное срабатывание `endpointing_started` (8 раз за 7 сек) в reply mode из-за акустического эха собственной TTS Адама через ESP32 mic, что не даёт VAD'у закрыть endpointing до hard cutoff. Это pre-existing bug, выявленный после стабилизации mic stream в Phase 7.

**Requires:** Phase 7 завершена (стабильный mic stream — необходимое условие чтобы воспроизвести bug; на flaky stream он маскировался).

**Symptoms (test session 2026-05-17 00:08:50–00:09:20):**

- В reply window между 21:03:38 и 21:03:45 (UTC) 8 событий `endpointing_started` с интервалом 5–26 ms — VAD скачет voiced↔silenced на хвосте TTS-эхо.
- 21:03:52 — `reply_window_expired absolute_deadline elapsed=16.6s` (hard cutoff).
- 21:04:00 — последний нормальный `esp32_audio_health`.
- 21:04:15.979 — последний event (`audio_level state=standby source=esp32_stereo`).
- Далее — **6 минут полной тишины** в `events.jsonl`. Пользователь делал запросы 00:08:50–00:09:20 (UTC 21:08:50+), реакции не было; UI VU/equaliser замёрз.

**Investigation hypotheses:**

- `_REPLY_GUARD_SEC` (0.6 s) недостаточно для затухания акустического эха ESP32 speaker → ESP32 mic (расстояние, реверберация). Hard cutoff попадает не на тишину, а на хвост эха.
- Endpointing flicker (`_was_endpointing` flag toggling каждые 20 ms) создаёт спам в event_log; lock contention в `event_log.append` (синхронный `with self._lock: handle.write`) может затянуть main loop.
- Возможна другая бесконечная задача / deadlock между `_vad_loop` consumer и MicReader producer при определённом sequence событий после hard cutoff.

**Tentative deliverables:**

- Воспроизведение hang в контролируемом scenario (e.g. force_TTS playback с loopback mic).
- Увеличение `_REPLY_GUARD_SEC` до 1.0–1.5 s (или config-параметр).
- Debounce на `_was_endpointing` flag — не эмитить `endpointing_started` чаще раза в 200 ms.
- Возможно: half-duplex hard mute на reply mode (не просто `_REPLY_GUARD_SEC`, а полный suppress voiced detection пока `time.perf_counter() - last_tts_finished_at < N`).
- Async stack snapshot mechanism для будущей диагностики hang (e.g. SIGUSR1 → dump all task stacks).

**Mode:** debug → standard fix

**Requirement IDs:** REQ-NO-HANG-AFTER-REPLY, REQ-NO-SELF-ECHO-VAD, REQ-REPLY-MATCHES-LISTENING, REQ-DIAGNOSTIC-LOGS-VOICE-STATE

---

## Phase 9: VAD debounce + UI smoothness + chat panel cleanup

**Branch:** TBD (suggest `V-S07.4-vad-debounce-ui`)

**Goal:** Устранить VAD-флапп (40 emissions endpointing_started на одну фразу), сделать audio_level и heartbeat независимыми от блокировок `_vad_loop`, обновить UI чат-панели (убрать дублирующиеся надписи и калибровку, переставить mic plate, выровнять высоты эквалайзера и VU-меттера). Дополнительно — отчёт по конфигурации ESP32 mic (sample rate, bit depth).

**Requires:** Phase 8 завершена (рефактор reply mode, heartbeat). Phase 9 расширяет тот же файл `Orchestrator.py` + `mic_reader.py` + `WebUI/static/js/`.

**Tentative deliverables:**

- Debounce на `endpointing_started`: требовать N (default 5 ≈ 100 ms) подряд silence-кадров перед эмиссией. Параметр в Config.
- Heartbeat вынести из `_vad_loop` в отдельную asyncio-task (живёт независимо от блокировок ASR/TTS).
- `audio_level` continuous emission: добавить wall-clock task в `MicReader`, эмитит каждые ~100 ms из последних известных уровней — даже если drain_loop стал на reconnect/stall. Существующий event-emit per-frame оставляется в виде primary path; новый task — fallback от sticking.
- WebUI chat panel (System/WebUI/static/js/panels/chat.js + widgets/wakeMeter.js):
  - Убрать текстовые подписи (`t=0.08 s=0.00 max=0.00`) из эквалайзера.
  - Убрать кнопку «Калибровать» из chat — остаётся только на странице настроек.
  - Перенести `micSourceBadge` на место кнопки Калибровать (над эквалайзером, выровнено по правому краю).
  - VU-метр (vuCanvas) высота 96 px (под высоту эквалайзера).
- Verification report: ESP32 sample rate (16 kHz vs рекомендация 44.1/48), bit depth (16 vs 16 — соответствует).

**Note:** WebUI уже использует SSE (`/api/agent/stream`) — отдельный fix не нужен. Polling `/api/agent/status` 4-сек интервалом — для общей health-данных, не для UI VU/equalizer.

**Mode:** debug + UI polish

**Requirement IDs:** REQ-VAD-DEBOUNCE, REQ-AUDIO-LEVEL-CONTINUOUS, REQ-HEARTBEAT-INDEPENDENT, REQ-UI-CHAT-CLEANUP, REQ-ESP32-AUDIO-REPORT

---

## Phase 10: Flush stale audio on safe state transitions (V-S07.1 backport)

**Branch:** TBD (suggest `V-S07.5-flush-on-transition`)

**Goal:** Восстановить принципы V-S07.1 `_drain_esp32_backlog` в архитектуре V-S07.3 (MicReader-стрим), но **только в безопасных точках** где пользователь точно не говорит. Устранить feeding stale TCP-buffered аудио в WhisperX после долгих mute-окон и reply EXPIR.

**Requires:** Phase 9 завершена; реверт Phase 10 v1 (commit 5664121) изучен — v1 ошибочно вызывал flush на wake_word, что съедало первые 200ms запроса пользователя (Test 5: 33% success vs 64% baseline).

**Root cause (от Phase 9 анализа):**
V-S07.1 после `_transcribe_and_dispatch` явно вызывал `_drain_esp32_backlog(read_fn, frame_bytes, mute_start)` — отбрасывал stale байты из raw socket. V-S07.3 (Phase 7 refactor) этот шаг удалил, предполагая что MicReader's `_drain_loop` всегда успевает читать socket в фоне. На практике `_drain_loop` стопится на 200-500 мс из-за CPU нагрузки и W5500 SPI конкуренции с MJPEG → kernel TCP буфер ESP32 накапливает 1-3 сек аудио → flood приходит в queue и засоряет speech_frames.

**Принципы из V-S07.1, адаптированные для MicReader-стрима:**

1. **Drain после `_transcribe_and_dispatch`** (V-S07.1 эквивалент): после возврата transcribe, перед transition в reply/standby. Безопасно потому что (a) пользователь не говорит когда Адам только что озвучил ответ, (b) `_REPLY_GUARD_SEC=0.6` сразу за этим прикроет любой overlap.

2. **Drain на `reply_silence_timeout`**: пользователь только что не успел ответить, в TCP буфере могут быть стале-фрагменты из reply window. Безопасно потому что (a) пользователь по определению молчал, (b) `_STANDBY_GUARD_SEC=0.3` сразу блокирует OWW на 300 мс.

3. **Защита TCP-буфера ESP32** (не Drain socket напрямую как V-S07.1, а через MicReader): после `flush_queue()` ставится `_discard_until_ts` — drain_loop ПРОДОЛЖАЕТ читать socket (kernel TCP buffer дренируется, W5500 SPI не переполняется), но скип `_put_or_drop` 200 мс. Это адаптация V-S07.1 под MicReader-стрим — собственный socket-read MicReader'а сохраняется, drain происходит на уровне queue.

**Чего НЕ делается:**

- Flush на `wake_word_detected` — Phase 10 v1 показал что это убивает первые 200 мс речи пользователя (regression 64%→33% success).
- Прямое чтение socket из `_vad_loop` — это бы сломало MicReader-стрим архитектуру (пользователь запретил).

**Deliverables:**

- `MicReader.flush_queue(discard_window_ms=200.0)` — публичный метод.
- `_discard_until_ts` поле + gate в `_drain_loop` (mirror of mute-gate).
- 2 вызова в Orchestrator: post-transcribe + reply_silence_timeout. БЕЗ wake.
- Событие `mic_queue_flushed {frames, ms, trigger, discard_window_ms}` для диагностики.

**Mode:** debug fix — устраняет регрессию Phase 7 refactor без регрессии Phase 10 v1.

**Requirement IDs:** REQ-FLUSH-ON-SAFE-TRANSITIONS

---

## Phase 11: Voice Pipeline Refactor — соответствие эталонной логике

**Branch:** `V-S08.1-code_rev_ref_opt`

**Goal:** Довести voice pipeline до соответствия эталонной логике (STANDBY → LISTENING → ANSWER → REPLY с таймингами 6с/5с/15с/10с); устранить дублирование, удалить мёртвый код, повысить стабильность. Источник: [REVIEW.md](phases/11-voice-pipeline-refactor/REVIEW.md).

**Requires:** Phase 7 завершена ✓ (MicReader keep-alive), Phase 10 завершена ✓ (flush-on-safe-transitions).

**Reference logic (источник истины):**

| Стадия | Параметр | Значение |
| --- | --- | --- |
| STANDBY | wake word | «адам» (OWW) |
| LISTENING | silence → STANDBY | 6 сек |
| LISTENING | end-of-utterance silence | 1.5 сек |
| LISTENING | max segment | 15 сек |
| REPLY | guard после TTS | 0.6 сек |
| REPLY | silence → STANDBY | 5 сек |
| REPLY | end-of-utterance silence | 1.5 сек |
| REPLY | max segment | 10 сек |
| Mic OFF | до STANDBY | UI-only gate (MicReader дренирует socket всё время) |
| filler | по умолчанию | выключен |

**Plans:** 6 plans

- [ ] 11-01-PLAN.md — Config defaults + schema (эталонные тайминги + filler off)
- [ ] 11-02-PLAN.md — Удалить legacy ESP-fallback каскад из VoiceLoopController (~-200 LOC)
- [ ] 11-03-PLAN.md — Удалить `/api/voice/force_esp_retry` endpoint + UI «Подключиться к ESP» (~-150 LOC)
- [ ] 11-04-PLAN.md — Cleanup статуса + удалить deprecated `_command_endpointing_ms` алиас (~-30 LOC)
- [ ] 11-05-PLAN.md — Переименовать `wake_word.wake_silence_timeout_sec` → `services.asr.listening_silence_timeout_sec` (с deprecated alias)
- [ ] 11-06-PLAN.md — Verification: smoke test full pipeline

**Mode:** standard (refactor)

**Requirement IDs:** REQ-VOICE-REFERENCE-TIMINGS, REQ-NO-LEGACY-FALLBACK, REQ-NO-FORCE-ESP-RETRY, REQ-CONFIG-FIRST-VOICE

---
## Phase 12: Comprehensive Diploma Analysis

**Branch:** `diploma-chapter3` (работа над дипломом ведётся здесь)

**Goal:** Глубокий комплексный аудит всех 4 глав диплома (ch00-ch03) на 5 измерений: соответствия, расхождения, дублирование, упущения, терминологическая стабильность. Создать структурированный отчёт с приоритизированным списком правок.

**Requires:** Phase 6B завершена

**Delivers:**

- Перестроенный graphify-граф диплома (`Knowledge-graphs/diploma/`)
- `STRUCTURE.md` — извлечённая структура каждой главы (4 parallel subagents)
- `TERMINOLOGY-MATRIX.md` — карта ключевых терминов (AIIM, субъектность, квазисубъектность, агентность, идентичность, память, контекст): где введён, где используется, синонимические дрейфы
- `DUPLICATIONS.md` — концепты, описанные несколько раз с разной формулировкой
- `GAPS.md` — упущения: концепты, упомянутые но не раскрытые / заявленные но не доведённые
- `XREF-AUDIT.md` — проверка cross-references внутри диплома (главы ↔ разделы ↔ источники)
- `07-SUMMARY.md` — приоритизированная матрица: глава × проблема × серьёзность × рекомендация

**Mode:** standard (full GSD cycle: discuss → plan → execute)

---

## Phase 13: Theory-Code Verification

**Branch:** `diploma-chapter3` (анализ остаётся в дипломной ветке)

**Goal:** Для каждого теоретического концепта диплома найти runtime-evidence в коде и классифицировать соответствие. Расширить начатый `diploma/ANALYSIS-THEORY-vs-CODE.md` на все 4 главы.

**Requires:** Phase 12 завершена

**Delivers:**

- `THEORY-CODE-MATRIX.md` — полная матрица: концепт × файлы кода × классификация (FULL / PARTIAL / MISSING / EMERGENT / CONTRADICTED)
- `CROSS-GRAPH-FINDINGS.md` — перекрёстные запросы по 3 графам (code, persona, esp32)
- `EMERGENT-FEATURES.md` — фичи, есть в коде, но не описаны в дипломе (LeadingNoiseFilter, проактивные SceneWorker/SessionWatcher, ...)
- `CONTRADICTIONS.md` — диплом утверждает X, код делает Y (Commander.py mood tags vs keyword matching)
- Для каждого CONTRADICTED — решение: (A) поправить диплом, (B) поправить код, (C) задокументировать как упрощение
- `08-SUMMARY.md` — % coverage диплома кодом

**Mode:** standard (full GSD cycle, subagent: gsd-codebase-mapper)

**Plans:** 6 plans

- [ ] 08-01-PLAN.md — Wave 0 graphify check + Wave 1.1 verify 16 philosophical terms
- [ ] 08-02-PLAN.md — Wave 1.2 verify 9 AIIM terms against persona graph
- [ ] 08-03-PLAN.md — Wave 1.3 verify 18 technical terms against code graph + Config.json
- [ ] 08-04-PLAN.md — Wave 1.4 verify 5 artistic terms against esp32 graph + Lore
- [ ] 08-05-PLAN.md — Wave 2 synthesis (THEORY-CODE-MATRIX + CONTRADICTIONS + EMERGENT + CROSS-GRAPH)
- [ ] 08-06-PLAN.md — Wave 3 final 08-SUMMARY.md

---

## Phase 14: Next-Phases Planning

**Branch:** `diploma-chapter3`

**Goal:** На основе аудита диплома (Ф7) и матрицы соответствия (Ф8) сформировать конкретные технические фазы для следующих волн разработки. Привязать их к активным веткам.

**Requires:** Phases 7, 8 завершены

**Delivers:**

- `CANDIDATES.md` — длинный список потенциальных фаз из Ф7+Ф8
- `09-PRIORITIZATION.md` — матрица impact × effort × strategic value
- `09-PHASE-DRAFTS.md` — phase drafts для топ-5-8 кандидатов в формате (Goal / Delivers / Requires / Mode)
- Интеграция с активными ветками:
  - `Memory-upgrade` → Phase 15C: Memory Wave 2 (Neural search)
  - `dynamic-aiim` → Phase 15F: AIIM Dynamic (рефлексивный уровень)
  - `VLM-upgrade` → Phase 15G: Vision Upgrade
  - `Identity-tuning` → Phase 15H: Identity Calibration
- `09-SUMMARY.md` — итог: 5-8 рекомендуемых фаз для добавления в Roadmap

**Mode:** standard

**Requirements:** PLAN9-01, PLAN9-02, PLAN9-03, PLAN9-04, PLAN9-05, PLAN9-06, PLAN9-07, PLAN9-08, PLAN9-09, PLAN9-10

**Plans:** 4 plans

**Completed:** 2026-05-17 (13 фаз спроектированы, 32 REQUIREMENTS-IDs, dependency graph, 4 артефакта)

Plans:

- [x] 09-01-PLAN.md — CANDIDATES.md: реестр ~13 кандидатов из Ф8 §4.1 + Backlog + активных веток
- [x] 09-02-PLAN.md — 09-PRIORITIZATION.md: матрица 4 критериев (Impact/Effort/Strategic/Exhibition) + P0–P3 группы
- [x] 09-03-PLAN.md — 09-PHASE-DRAFTS.md: полные ROADMAP-style drafts для P0 (10A/10B/11) + компактные для P1–P3
- [x] 09-04-PLAN.md — 09-SUMMARY.md: финальные рекомендации для Phase 15 (что копировать + открытые вопросы + milestone-предложение)

---

## Phase 15: Roadmap Global Update

**Branch:** `diploma-chapter3` (изменения в `.planning/` остаются в дипломной ветке до мёржа)

**Goal:** Обновить ROADMAP.md и REQUIREMENTS.md с глобальной картой будущих фаз; добавить milestone-структуру; привязать активные ветки к фазам.

**Requires:** Phase 14 завершена

**Delivers:**

- `.planning/ROADMAP.md` дополнен фазами из Ф9 (5-8 новых фаз)
- `.planning/REQUIREMENTS.md` расширен новыми REQUIREMENTS-IDs
- `.planning/MILESTONES.md` — группировка фаз в milestones (M1 Memory & Search, M2 AI Quality, M3 Diploma Finalization, M4 Production-ready)
- `.planning/roadmap-visual.md` — Mermaid Gantt-chart с активными ветками и зависимостями
- `.planning/ACTIVE.md` обновлён: каждая активная ветка получает owner phase ID, definition of done, целевую дату мёржа
- `docs/BRANCH-template.md` обновлён: обязательное поле «Roadmap Phase: Phase N»
- `CLAUDE.md` (root) обновлён: ссылка на ROADMAP в Reading Order
- `docs/AGENT-PROTOCOL.md` обновлён: Branch gap триггер — «Проверь, есть ли Phase в Roadmap для текущей ветки»
- Backlog обновлён: перенос Memory Wave 2, Proactive Speech, AIIM Dynamic, UI rebuild в актуальные фазы
- `.planning/STATE.md` обновлён: новая активная фаза

**Mode:** standard

---

## Phase 15A: Diploma Convergence Pass

**Branch:** `diploma-chapter3` (existing — текущая ветка, продолжение)

**Goal:** Применить все оставшиеся текстовые правки диплома из Phase 13 (4 A-path + 7 C-path + 10 оставшихся EMERGENT), финализировать диплом и подготовить ветку `diploma-chapter3` к мёржу в `main`.

**Requires:**

- Phase 13 завершена ✓ (08-SUMMARY.md создан, топ-3 EMERGENT применены)
- Phase 14 завершена ✓ (09-SUMMARY.md создан)

**Delivers:**

- Правка ch01.1.1.4 — мета-параграф «AIIM как философский мост Брайдотти↔Латур↔код» (EMERGENT #13, F-04)
- Правка ch03.3.2.3 — раздел «Динамическая модуляция AIIM» с TuningStore hot-reload (EMERGENT #2, F-05) + centralность AIIM как god-node (EMERGENT #1) + future-work «Профили активации AIIM» (EMERGENT #4)
- Правка ch03.3.3.4 — полная state-diagram Voice Loop FSM с Config-параметрами (EMERGENT #9, F-06, Mermaid)
- Правка ch03.3.2.6 — таблица 5 mood-состояний + Mood enum (EMERGENT #3, #8, path A Α-24)
- Правка ch03.3.4 — формула salience scoring + сигналы входа (EMERGENT #7, path B Τ-36 diploma side)
- Правка ch03.3.2.2 — раздел SceneWorker background pattern + pull-mode VLM (EMERGENT #6, path A Χ-46)
- Ремарки и footnotes: C-paths Φ-13, Τ-28, Α-25 + EMERGENT #10/#12/#5 (7 C-path упрощений)
- Готовность к мёржу: `diploma-chapter3` → `main`

**Requirements:** DIPL-09, DIPL-10, DIPL-11, DIPL-12, DIPL-13, DIPL-14, DIPL-15

**Mode:** standard | **Priority:** P0

---

## Phase 15B: Config-First Refactor

**Branch:** `config-refactor` (new — создаётся при старте фазы)

**Goal:** Вынести все хардкодированные числовые параметры в `Config.json` / `Config.schema.json` и устранить BUG F-07 (рассинхронизацию `history_turns=2` vs `limit=8`), закрыв Pattern 4 из Phase 13.

**Requires:**

- Phase 13 завершена ✓ (F-07 BUG, Τ-30/31/36 задокументированы)
- Не блокируется другими фазами (независима)

**Delivers:**

- Новый Config-ключ `agent.session_turn_limit` (limit=8 из `prompt.py` → Config) — устраняет Τ-30
- Новый Config-ключ `memory.episodic_decay_days` (14d из `episodic.py` → Config) — устраняет Τ-31
- Новый Config-ключ `memory.salience_weights` (dict из `episodic.py` → Config) — устраняет Τ-36
- Два явных ключа вместо рассинхрона: `agent.prompt_history_limit` (=8) и `agent.context_history_turns` (=2) — устраняет F-07
- Обновлённые `System/Config.json` и `System/Config.schema.json` с descriptions
- Рефакторинг `prompt.py`, `episodic.py`, `Engineering/consolidator.py` (чтение из конфига)
- Unit-тесты для каждого нового Config-ключа (с env-override `ADAM_CONFIG_OVERRIDE`)
- Разблокирует Phase 21 (UI Rebuild) и Phase 23 (Structural Refactor)

**Requirements:** CFG-01, CFG-02, CFG-03, CFG-04

**Mode:** standard | **Priority:** P0

---

## Phase 16: AIIM Dynamic — Рефлексивный уровень идентичности

**Branch:** `dynamic-aiim` (existing)

**Goal:** После каждой сессии консолидатор анализирует паттерны взаимодействия и автоматически корректирует параметры `Tuning.json` (drive, verbosity, доминирующие аспекты) в пределах заданных magnitude limits, реализуя рефлексивный уровень AIIM.

**Requires:**

- Phase 18 (Memory Consolidation) — желательно; integration hook требует работающего consolidator (можно вести параллельно)
- Phase 15A (Diploma Convergence Pass) — согласование diploma-side описания AIIM Dynamic (DIPL-10)

**Delivers:**

- Новый модуль `System/adam/aiim_reflection.py` с функцией `adjust_tuning(session_summary, current_tuning) -> dict`
- Whitelist параметров для автокоррекции в `Config.json::aiim.adjustable_params` (drive, verbosity, aspect_weights)
- Magnitude limits per parameter в `Config.json::aiim.magnitude_limits` — защита от дрейфа
- Интеграция в consolidator hook: после каждой консолидации вызывается `aiim_reflection.adjust_tuning`
- API endpoint `GET /api/agent/aiim/last-adjustment` — последнее корректирующее воздействие с delta и timestamp
- Регрессионный тест: суммарный дрейф параметров за N сессий ≤ magnitude_limit
- Разблокирует Phase 17 (RDI metric source — рефлексивный уровень даёт данные для метрики)

**Requirements:** AIIM-01, AIIM-02, AIIM-03, AIIM-04

**Mode:** standard | **Priority:** P0

---

## Phase 18: Memory Consolidation

**Branch:** `memory-consolidation` (new — отдельно от `Memory-upgrade`, чтобы изолировать риски)

**Goal:** Интегрировать `Engineering/consolidator.py` в Orchestrator runtime с daily cron или post-session trigger, создав работающий механизм консолидации эпизодической памяти.

**Requires:**

- Phase 6A завершена ✓ (consolidator.py создан с llama.cpp API + rule-based fallback)
- Независима от других активных фаз

**Delivers:**

- Интеграция `consolidator.py` в Orchestrator runtime (daily cron scheduler или post-session event hook)
- Daily cron scheduler или Orchestrator event hook для запуска консолидации после сессии
- Корректный flow флага `Episode.consolidated: bool` — от `episodic.py` до diary
- Тесты интеграции: консолидация запускается корректно, флаги проставляются
- Разблокирует Phase 17 (LMRR metric source), Phase 20 (prereq), Phase 24 (context history)

**Requirements:** MEM-01, MEM-02, MEM-03

**Mode:** standard | **Priority:** P1 | **Net-unlock: 3 фазы**

---

## Phase 26: Identity Calibration Финализация

**Branch:** `Identity-tuning` (existing)

**Goal:** Завершить разработку в `Identity-tuning` (Φ-13 path C, Α-24 path A, калибровка 5 mood-состояний) и выполнить merge в `main`.

**Requires:**

- Phase 15A (Diploma Convergence Pass) — согласование diploma-side правок Α-24 и Φ-13

**Delivers:**

- Финализация кода в ветке `Identity-tuning` (Φ-13 path C параграф + Α-24 mood калибровка)
- Code review пройден (`/gsd-code-review`)
- Merge `Identity-tuning` → `main` выполнен
- Регрессионный тест диалогового pipeline после мёржа (тон и поведение агента)
- Согласованность Φ-13 path C параграфа (diploma) с Identity.md изменениями

**Requirements:** ID-01, ID-02, ID-03

**Mode:** standard | **Priority:** P1 | **Effort:** L (code review + merge)

---

## Phase 19: Mood LLM-driven

**Branch:** `mood-llm` (new — создаётся при старте фазы)

**Goal:** Доработать `action.py` для парсинга явных mood-маркеров из LLM-ответа вместо текущего keyword matching по `reply_text`.

**Requires:**

- Независима (улучшает NVR метрику Phase 17)

**Delivers:**

- Доработка `action.py`: парсинг явных mood-маркеров из структуры LLM-ответа (не keyword matching)
- Обновлённый системный промпт: шаблон для генерации mood-маркеров в формате, парсируемом action.py
- A/B тест: сравнение качества mood detection (keyword vs LLM-маркеры)
- Тесты для нового парсера

**Requirements:** MOOD-01, MOOD-02

**Mode:** standard | **Priority:** P2 | **Риск:** изменение промпта влияет на качество ответов — A/B тест обязателен

---

## Phase 20: Memory Wave 2 (Neural Search)

**Branch:** `Memory-upgrade` (existing, Wave 2)

**Goal:** Заменить TF-IDF векторизацию в `FaissEpisodeIndex` на llama.cpp `/embeddings` endpoint для семантического поиска по эпизодической памяти.

**Requires:**

- Phase 18 (Memory Consolidation) завершена — prereq
- Свободная VRAM ≥ 4 GB при работающем Gemma 4 E4B

**Delivers:**

- Замена TF-IDF → llama.cpp `/embeddings` в `FaissEpisodeIndex` (интерфейс `.build()/.search()/.save()/.load()` не меняется)
- VRAM check при запуске Wave 2 (≥4 GB свободной VRAM при работающем LLM)
- Тесты семантического поиска (релевантность vs keyword matching)
- Обновлённый `memory_search.py` с embeddings backend

**Requirements:** MEMN-01, MEMN-02

**Mode:** standard | **Priority:** P2

---

## Phase 22: Remote Access

**Branch:** `remote-access` (new — создаётся при старте фазы)

**Goal:** Расширить `scripts/adam_pull_logs.py` и API до полноценного удалённого мониторинга pipeline-этапов с фильтрацией по turn_id / stage / временному диапазону.

**Requires:**

- Независима (частично реализована: `adam_pull_logs.py` + `/api/agent/turns` + `/api/agent/events`)

**Delivers:**

- Расширение `adam_pull_logs.py`: фильтрация по stage, временному диапазону, turn_id
- Расширение `/api/agent/events` API: дополнительные фильтры
- Опциональная базовая auth (token) для удалённого API при exposition за пределами локальной сети
- Документация новых параметров CLI и API

**Requirements:** REM-01, REM-02

**Mode:** standard | **Priority:** P2 | **Effort:** M (без архитектурных изменений)

---

## Phase 25: VLM Upgrade Финализация

**Branch:** `VLM-upgrade` (existing)

**Goal:** Завершить разработку в ветке `VLM-upgrade` и выполнить merge в `main`.

**Requires:**

- Независима (Phase 13 не выявила блокеров)

**Delivers:**

- Финализация кода в ветке `VLM-upgrade`
- Code review пройден (`/gsd-code-review`)
- Merge `VLM-upgrade` → `main` выполнен
- Регрессионный тест: scene_worker_enabled, scene_interval_sec, scene_stale_after_sec корректно читаются из Config.json
- После мёржа Phase 20 может использовать VLM embeddings

**Requirements:** VLM-01, VLM-02

**Mode:** standard | **Priority:** P2 | **Effort:** L (code review + merge)

---

## Phase 24: Proactive Speech

**Branch:** `proactive-speech` (new — создаётся при старте фазы)

**Goal:** Добавить idle-scheduler — фоновый процесс, который при наличии посетителей и тишине дольше N секунд вызывает LLM с промптом-затравкой и воспроизводит ответ без wake word.

**Requires:**

- Phase 18 (Memory Consolidation) завершена — контекст истории сессий

**Delivers:**

- idle-scheduler в Orchestrator: при тишине > N секунд и наличии посетителей (VLM engagement) вызывать LLM
- Промпт-затравка для спонтанных реплик (без wake word) — отдельный системный промпт в Config или Tuning.json
- Rate limiter (не чаще M минут) + соблюдение half_duplex_mute инварианта (idle не перекрывает активный диалог)
- Config-параметры: `proactive.idle_threshold_sec`, `proactive.rate_limit_min`, `proactive.enabled`
- Связана с Phase 17 SIAR метрика (Spontaneous Initiative Activity Ratio)

**Requirements:** PROAC-01, PROAC-02, PROAC-03

**Mode:** standard | **Priority:** P2 | **Exhibition:** H — высокая ценность для выставки

---

## Phase 21: UI Rebuild

**Branch:** `ui-rebuild` (new — создаётся при старте фазы)

**Goal:** Пересобрать операторский веб-интерфейс (`:8080`) с перегруппировкой параметров по доменным блокам (ESP / Agent / Identity), визуализацией уровня микрофона, настройкой silence timeout и управлением громкостью.

**Requires:**

- Phase 15B (Config-First Refactor) завершена — параметры должны быть в Config.json до UI-привязки

**Delivers:**

- Перегруппировка операторского UI по доменным блокам: ESP (камера/mic/PCA9685/PCM5102A), Agent (ASR/VLM/LLM/TTS), Adam Identity
- Real-time визуализация уровня микрофона (mic эквалайзер / VU-meter)
- Настройка silence timeout (command_endpointing_ms, reply_window_sec) через UI без рестарта
- Управление громкостью TTS (output device volume) через UI
- **Open question:** поднять до P2 если дата выставки близко (см. [09-PRIORITIZATION.md R-03](phases/14-next-phases-planning/09-PRIORITIZATION.md))

**Requirements:** UI-01, UI-02, UI-03, UI-04

**Mode:** standard | **Priority:** P3

---

## Phase 21A: Chat EQ Real Spectrum — реальный FFT в виджете эквалайзера

**Branch:** `V-S09.1-Audio_out` (existing)

**Goal:** Заменить «иллюзию спектра» в виджете эквалайзера на странице чата (`wakeMeter.js`) на реальный частотный спектр FFT, посчитанный на сервере поверх того же аудио-потока, который слышат OWW/ASR. Сохранить отображение OWW score (голубая линия) и threshold (оранжевый пунктир) без изменений.

**Requires:**

- Phase 7 (ESP32 Mic Pipeline Refactor — MicReader keep-alive) ✓ — источник синхронизированного аудио-стрима
- Не требует Phase 15B (Config-First Refactor): новые ключи добавляются сразу в правильный Config-First формат

**Delivers:**

- Серверный FFT на Jetson поверх того же буфера аудио-кадров, которые уже идут в RMS `audio_level`. Источник — `MicReader` или отдельный audio-worker; решение в фазе discuss/plan
- Новое SSE-событие `audio_spectrum` (или расширение `audio_level` полем `bands[]`) с N log-частотных band-энергий, нормализованных в [0..1]
- Cadence публикации спектра — отдельный параметр Config.json (целевая частота отрисовки на UI ≈ 20–30 Hz; backend cadence не выше, чтобы не насыщать SSE)
- Новые ключи в `System/Config.json` + `System/Config.schema.json`: число bands, cadence публикации (Hz), частотный диапазон, шкала (lin/log), нормализация
- Рефакторинг `System/WebUI/static/js/widgets/wakeMeter.js`:
  - удалена фиксированная `EQ_SHAPE`-форма и хардкод `audioLevel * 4.0` / `sin(Date.now())`-wobble / decay `0.87`
  - бары рендерятся напрямую из последнего пришедшего `bands[]` — **без peak-hold, без decay** (решение пользователя: «максимально честно»)
  - градиент цвета бара по его собственному уровню: зелёный → жёлтый → красный (peak indicator + visual clipping hint)
  - OWW score (циан) и threshold (оранжевый пунктир) — без изменений в логике
  - починена потенциальная SSE-утечка: `dispose()` гарантированно отписывает EventSource при перерендере хост-панели
- Подсказка под виджетом в `chat.js` обновлена: текст объясняет, что зелёные бары — реальный спектр микрофона
- Обновлён draggable-вариант в `settings.js`: drag-to-tune threshold продолжает работать как раньше
- Smoke-тест: на чат-панели бары следуют за голосом, при громком пике становятся красными, при тишине плоско; SSE-соединение одно на mount/unmount цикл

**Requirements:** UI-EQ-01 (FFT backend), UI-EQ-02 (новое SSE-событие), UI-EQ-03 (рендер без сглаживания), UI-EQ-04 (градиент цвета по уровню), UI-EQ-05 (fix SSE leak), UI-EQ-06 (Config-First параметры FFT)

**Mode:** standard | **Priority:** P2 | **Effort:** M (3–5 дней) | **Exhibition:** M

**Plans:** 8/8 plans complete

Plans:
- [x] 21A-01-PLAN.md — Wave 0 test stubs: tests/test_mic_reader_spectrum.py + conftest fixtures (UI-EQ-01/02/06)
- [x] 21A-02-PLAN.md — Config keys + schema: 8 spectrum_* keys in media.audio (UI-EQ-06)
- [x] 21A-03-PLAN.md — MicReader FFT pipeline + 25 Hz cadence + hot-reload (UI-EQ-01/02/06)
- [x] 21A-04-PLAN.md — events.jsonl writing-side sampler (UI-EQ-02; mitigates 417 MB growth)
- [x] 21A-05-PLAN.md — wakeMeter.js refactor: bands[24] render, color gradient, idempotent dispose (UI-EQ-03/04/05)
- [x] 21A-06-PLAN.md — chat.js hint + settings.js draggable audit (UI-EQ-03)
- [x] 21A-07-PLAN.md — Manual smoke test against live Orchestrator → SMOKE-RESULTS.md (verdict: PASS)
- [x] 21A-08-PLAN.md — Hotfix: MicReader auto-restart watchdog on ESP `:81` deadlock (UI-EQ-RESILIENCE)

**Связь с Phase 21:** Phase 21A — фокусный слайс Phase 21 (UI Rebuild). Закрывает один из её deliverables («Real-time визуализация уровня микрофона»). При запуске Phase 21 этот пункт уже будет закрыт; Phase 21 продолжит с остальными deliverables (перегруппировка UI, silence timeout, volume control).

---

## Phase 23: Structural Refactor

**Branch:** `refactor` (new — создаётся при старте фазы, требует feature-freeze)

**Goal:** Провести структурный рефакторинг кодовой базы: пересмотр директорий `System/`, `Subsystem/`, `Engineering/`, единый реестр параметров и глубокий Config-аудит поверх Phase 15B.

**Requires:**

- Phase 15B (Config-First Refactor) завершена и смёржена
- Feature-freeze других веток на время рефакторинга

**Delivers:**

- Единый реестр всех параметров системы (глубокий аудит поверх Phase 15B — второй слой параметров)
- Пересмотр директорной структуры `System/`, `Subsystem/`, `Engineering/` — логическая группировка по доменам
- Все тесты зелёные после рефакторинга
- systemd units проверены и обновлены под новую структуру (если нужно)

**Requirements:** REF-01, REF-02

**Mode:** standard | **Priority:** P3 | **Риск:** H — масштабный рефакторинг; необходим feature-freeze

---

## Phase 17: Metrics & Evaluation Framework

**Branch:** новая (`metrics-framework`) — создаётся после стабилизации основных веток

**Goal:** Реализовать автоматический сбор и расчёт метрик качества работы агента, заявленных в дипломе (3.4): RAS, RDI, NVR, RI, CRS, LMRR, SCS, SIAR. Закрывает диплом-задачи №3 (формализация критериев устойчивости роли) и №6 (демонстрация в реальном времени + оценка).

**Requires:**

- Стабилизация активных веток: `Memory-upgrade`, `Identity-tuning`, `VLM-upgrade`, `dynamic-aiim` → merged in main
- Phase 16 (AIIM Dynamic) завершена — без рефлексивного цикла часть метрик (RDI, CRS) не имеет источника данных

**Delivers:**

- `System/adam/evaluation/` — новый пакет с модулями расчёта метрик
- `scripts/export_turns_for_markup.py` — экспорт turn'ов с pre-filled данными для экспертной разметки
- `data/adam/eval/` — корпус разметки + результаты автоматического расчёта
- Метрики:
  - **RAS** (Role Adherence Score) — экспертная + автоматическая компонента (lexical analysis ответов)
  - **RDI** (Role Drift Index) — на основе истории сессий (требует Phase 16)
  - **NVR** (Normative Violation Rate) — правило-based детектор + опциональная LLM-проверка
  - **RI** (Repetition Index) — анализ echoes_used.jsonl + chinese_used.jsonl
  - **CRS** (Coherence-Response Strength) — semantic similarity между запросом и ответом
  - **LMRR** (LTM Retention Rate) — анализ обращений к семантической памяти diary.md
  - **SCS** (Scene Coherence Score) — корреляция VLM-описаний с ответами агента
  - **SIAR** (Spontaneous Initiative Activity Ratio) — счётчик проактивных событий (требует Proactive Speech)
- `GET /api/agent/metrics/summary` — текущие значения метрик
- Dashboard на `:8083/metrics` — графики метрик за последние N дней
- `docs/EVALUATION-FRAMEWORK.md` — методология, рубрики оценки, примеры разметки
- Главы диплома 3.4 актуализируются с реальными значениями вместо спецификации

**Mode:** standard (full GSD cycle)

**Связь с Phase 12 находками:** закрывает T-02 (метрики как honesty-проблема), задачи №3 и №6 из ch00

---

## Phase 27: AIIM Core Runtime — структурированные аспекты в коде

**Branch:** `aiim-core-runtime` (new — создаётся при старте фазы)

**Goal:** Перевести AIIM из чисто текстовой семантики (`Identity.md` в системном промпте) в структурированную runtime-конфигурацию: 12 аспектов сознания с уровнями, состояниями и Δ-приоритетами должны жить как валидируемая структура в `Tuning.json`, читаться при каждом цикле и модулироваться правиловым или модельным контуром. Закрывает гэп между текстом ch3 §3.2.3 диплома и фактической реализацией.

**Requires:**

- Phase 15A (Diploma Convergence Pass) завершена ✓ — текст ch3 §3.2.3 финализирован
- Независима от Phase 16 (Phase 16 — рефлексивный уровень, Phase 27 — конфигурационный + динамический уровни)

**Delivers:**

- Pydantic-модель `AIIMTuning` в `tuning.py`: 12 аспектов (co, se, sp, im, pe, at, be, wi, lo, ho, em, me), каждый — уровень (B/P/S/T/I), состояние (Ac-Or / Ac-Ch / Pa-Or / Pa-Ch), Δ-вес [0..1]
- Парсер `Identity.md` → `Tuning.json::aiim` при первом запуске (если секция `aiim` ещё не создана)
- Модуль `System/adam/aiim.py` с правиловым контуром Δ-сдвигов: эмпатичный ввод → +Δ для `lo` и `em`, ироничный → +Δ для `im`, попытка вытащить из персонажа → +Δ для `ho`
- Коридор Δ-сдвигов ±0.15 от базы `Identity.md`: за пределами — параметр клампится
- Параметр `services.action.mood_source` ∈ {`rules`, `slm`, `llm_self_tag`} в `Config.json` и `Config.schema.json`; в первой итерации реализуется только `rules`, остальные — заглушки с TODO
- Связь `aiim.py` → `action.py`: выбор тега `Mood` опирается на доминирующий аспект в текущем срезе `Tuning.json::aiim`, а не на keyword matching по тексту ответа
- Hot-reload через `TuningStore` без кеширования (читается каждый цикл) — уже есть в `tuning.py`, нужно добавить аспекты в pydantic-схему
- Регрессионный тест: после серии эмпатичных обращений `lo` сдвинут на +0.10 ± 0.02, выбор `Mood` смещён к `warm`
- Разблокирует: Phase 16 (рефлексивный уровень), Phase 19 (mood LLM-driven как режим `mood_source: llm_self_tag`), Phase 17 (RDI метрика на основе Δ-сдвигов)

**Requirements:** AIIM-CORE-01 (структура), AIIM-CORE-02 (парсер Identity), AIIM-CORE-03 (Δ-логика правиловая), AIIM-CORE-04 (mood_source), AIIM-CORE-05 (связь с action)

**Mode:** standard (полный GSD-цикл) | **Priority:** P0 | **Effort:** XL (3–4 недели)

**Связь с диплом-расхождениями (gap T3 в `ANALYSIS-THEORY-vs-CODE.md`):** закрывает заявку текста ch3 §3.2.3 на структурированные AIIM-аспекты, Δ-коридор и переключатель `mood_source`. После завершения Phase 27 + Phase 16 текст ch3 §3.2.3 и §3.2.6 становится полностью соответствующим коду.

---

## Phase 28: Event-driven Proactivity — дельта-реакция на изменения сцены

**Branch:** `proactive-delta` (new — создаётся при старте фазы)

**Goal:** Реализовать второй слой проактивного контура из диплома §3.3.4 — событийную дельта-реакцию на изменения сцены. В отличие от Phase 24 (idle-scheduler — реакция на длительный простой) и существующего `scene_director` (периодическая фоновая моторика), Phase 28 запускает спонтанные реакции по событийному триггеру и с вероятностной модуляцией.

**Requires:**

- Phase 25 (VLM Upgrade) или текущий VILA 1.5-3b с включённым scene worker и кэшем сцен
- Phase 27 (AIIM Core Runtime) — желательно, для интеграции Δ-сдвигов аспектов на дельта-событие
- Независима от Phase 24 — слои дополняют друг друга

**Delivers:**

- Модуль `System/adam/scene_delta.py` — сравнение текущего описания VLM с предыдущим из `scene_buffer`. Возвращает категоризированное событие: `appeared` / `disappeared` / `count_change` / `engagement_change` (none → watching / watching → approaching / approaching → interacting), либо `no_delta`
- Парсер двухчастного формата VLM-промпта (Scene + Engagement) для извлечения переходов уровня вовлечённости
- Вероятностный модулятор `proactive.spontaneous_speech_prob` в `Tuning.json` (база 0.17 на значимое дельта-событие) с механизмом затухания: при повторных однотипных триггерах вероятность снижается коэффициентом `proactive.repeat_decay` (база 0.5)
- Интеграция в Orchestrator: при детекции дельта-события — вызвать моторный отклик через `scene_director` overlay (выбор сцены по типу события), и с вероятностью `spontaneous_speech_prob` — запустить LLM-цикл с промптом-затравкой типа «прокомментируй появление зрителя в духе персонажа», результат озвучивается без пробуждного слова
- Если Phase 27 завершена: дельта-событие также модулирует Δ-веса AIIM перед выбором тега `Mood` (например, `appeared` → +Δ для `at`, `im`)
- Соблюдение `half_duplex_mute` инварианта: спонтанная реакция не запускается, если идёт активный диалог или TTS
- Регрессионный тест: при имитированной последовательности сцен «пустая → один зритель → один наблюдает → один приближается» система генерирует 3 дельта-события и в среднем за 100 прогонов производит 17 ± 5 спонтанных реплик
- Метрика SIAR в Phase 17 получает данные не только от idle-scheduler (Phase 24), но и от дельта-реакций

**Requirements:** PROAC-DELTA-01 (детектор), PROAC-DELTA-02 (вероятностный модулятор), PROAC-DELTA-03 (интеграция с моторикой), PROAC-DELTA-04 (интеграция с AIIM)

**Mode:** standard | **Priority:** P1 | **Effort:** L (2–3 недели) | **Exhibition:** H

**Связь с диплом-расхождениями:** закрывает заявку текста ch3 §3.3.4 на трёхуровневый проактив — без Phase 28 в коде представлены только слои 1 (`scene_director` фоновая моторика) и 3 (Phase 24 idle-scheduler), а слой 2 (событийная дельта-реакция) остаётся декларацией в дипломе.

---

## Phase 29: Technoflora Reactions — реактивный свето/вибро-слой по состояниям пайплайна

**Branch:** `LuxFlora-modes`

**Goal:** Дать установке выразительный физический отклик: светофлора (каналы 0–10, лампы Эдисона) и виброфлора (каналы 11–14) реагируют на 6 состояний голосового пайплайна (покой → детекция → слушание → раздумье → ответ → пробуждение), управляемые событиями оркестратора, а не выводом LLM.

**Requires:** Phase 11 (Voice Pipeline FSM — источник событий состояний) завершена ✓; прошивочная готовность ESP (новый анимационный движок в firmware).

**Locked decisions (из discuss-концепта):**

- Раскладка светофлоры — **кластер без порядка**: направленные эффекты (волна/бегущий огонь/цветение 0→10) заменены на коллективные и случайно-групповые (блуждающие вспышки, случайное прорастание, коллективный вдох).
- Архитектура — **гибрид**: ESP крутит автономные анимации по `id+параметры`; Jetson шлёт только переходы состояний + RMS-огибающую для речи.
- Технофлора — **реактивный слой по событиям пайплайна**, не вывод LLM (детерминированно, без латентности). Отдельно от `action.py` (mood→scene).

**Delivers (предв.):**

- Анимационный движок в прошивке ESP (`breathe`/`attentive`/`think_pulse`/`wake_bloom`/`accent` по id+параметрам) + эндпоинт `POST /api/flora/state`
- Event-слой на Jetson: подписка на `EventBus` (`oww_detected`/`asr_start`/`llm_start`/`tts_start`/`tts_end`) → переключение состояний
- RMS-синхронизация речи (состояние 4): расчёт огибающей из WAV + передача на ESP, синхронный плейбэк с поправкой на латентность HDMI-буфера
- Config-First: диапазоны duty, периоды, gamma (~2.2), маски каналов (свет 0–10 / вибро 11–14), frame interval, латентность-офсет — в `Config.json` + схему
- Раздельная политика виброфлоры (молчит в слушании — не наводит в микрофон)

**Mode:** standard (full GSD cycle)

**Requirement IDs:** FLORA-01 (ESP-движок), FLORA-02 (эндпоинт state), FLORA-03 (Jetson event-слой), FLORA-04 (RMS-синхронизация), FLORA-05 (Config-First параметры), FLORA-06 (вибро-политика)

**Plans:** 3/4 plans executed

Plans:
**Wave 1**

- [ ] 29-01-PLAN.md — ESP firmware animation engine (FreeRTOS task) + POST /api/flora/state [FLORA-01, FLORA-02]
- [x] 29-02-PLAN.md — Config-First flora section + Config.schema + Wave 0 tests/test_flora.py [FLORA-05]

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 29-03-PLAN.md — Jetson FloraController event layer + vibro policy + lifespan wiring [FLORA-03, FLORA-06]

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 29-04-PLAN.md — RMS speech sync streamer (WAV→envelope→light, barge-in) [FLORA-04]

---

## Phase 30 (main): Technoflora Reliability & Brightness Fixes

**Branch:** `LuxFlora-modes_V1.1`

**Goal:** Закрыть оставшиеся баги технофлоры после фикса погасания (Parts A/B/C уже применены: I2C-мьютекс, External-режим, развод легаси-слоя). Источник: `.planning/debug/flora-stops-on-state-change.md` + анализ R1–R9.

**Requires:** Фикс погасания (debug/flora-stops-on-state-change, Parts A/B/C) применён ✓; firmware собирается `pio run`.

**Locked decisions:**

- **R5 = вариант A** — убрать перцептивную гамму, сырой PWM: `duty = 4095 × pct/100`. «70%» = 2867 PWM. Подписи = сырой PWM-сигнал. Устраняет двойное применение гаммы (Jetson linear %→duty + firmware gammaApply).
- **Safe-ceiling** — глобальный параметр `flora.max_duty_pct` (в сыром PWM), клампится во всех write'ах флоры (Jetson + firmware defence-in-depth). В scope.
- **Страница настроек технофлоры (WebUI)** — НЕ в этой фазе (UI-фича, отдельная фаза позже).

**Delivers (баги R1–R9):**

- **R1** — калибровочный скрипт `flora_line_identify.py` ставит `flora enabled=false` на время прогона (+ re-enable в конце и в Ctrl+C), иначе floraTask перетирает его записи
- **R2** — guard в `flora.py _on_answer_end` (`if not _answer_active: return`) — barge-in + поздний `tts_finished` не должен перетирать состояние на breathe
- **R3** — деградированный `/speak`-путь: не уходить в breathe во время ответа (вернуть steady-плато или удержать External без watchdog-сброса)
- **R4** — External watchdog не должен срабатывать преждевременно в начале ответа (рефреш на `tts_started` или увеличенный grace)
- **R5** — сырой PWM без гаммы (Jetson + firmware), вариант A
- **R6** — idle-пресет не должен выглядеть «выключено» (поднять базу или оседать в breathe)
- **R7** — загейтить `/api/agent/scene` + manual `/api/pca9685/*` за `flora.enabled` (или явный override-флаг), чтобы ручные записи не дрались с floraTask
- **R8** — `flora enabled=false` не должен оставлять флору тёмной навсегда при сбое (безопасное восстановление / re-enable гарантия в скрипте)
- **R9** — `feed_speech_wav` считает RMS-огибающую вне event-loop (`to_thread`), чтобы не блокировать цикл
- Safe-ceiling `flora.max_duty_pct` + клампы (Config-First + схема)

**Mode:** standard (debug-fix; firmware + Jetson, hardware-gated verification)

**Requirement IDs:** FFIX-01 (R1), FFIX-02 (R2), FFIX-03 (R3), FFIX-04 (R4), FFIX-05 (R5 raw PWM), FFIX-06 (R6 idle), FFIX-07 (safe-ceiling), FFIX-08 (R7 gate manual), FFIX-09 (R8 recovery), FFIX-10 (R9 async envelope)

---

## Phase 30 (voice-loop-recovery): Voice Loop Recovery & Flora Integration

**Branch:** `voice-loop-recovery` (создана от 9da07f9 — «Стабильная работа всего аудио-тракта с esp динамиками и usb cam&mic»)

**Goal:** Восстановить корректную работу голосового цикла ПО ФАКТУ (живой тест, не анализ кода): mic→VAD→wake(«адам»)→ASR→LLM→TTS→выход. Затем интегрировать технофлору из коммита `47fd0c5` (origin/LuxFlora-modes_V1.1, автор 7teenzzz) с разрешением ВСЕХ конфликтов через глубокий анализ, не реактивируя поломки голосового цикла. Корневая причина прошлых поломок — runtime/host-слой ВНЕ git (мёртвые сервисы, Ollama держит VRAM, конфликт портов, битый ESP IP), поэтому откат коммитов её не лечил.

**Requires:**
- Ветка `voice-loop-recovery` от 9da07f9 (готово), BRANCH.md в корне
- sudo-доступ для systemctl-операций (снос Ollama, старт adam-llm/adam-tts) — на стороне пользователя
- Подключённый монитор VG27AQA1A (DP) ИЛИ виртуальный дисплей, если выход TTS уходит на локальный HDMI-аудио (`plughw:1,3`)

**Delivers:**
- Снос/выключение Ollama (инвариант проекта) → освобождение ~3.3 GB VRAM под llama.cpp
- Поднятые и проверенные сервисы: llama.cpp(:8081), Silero TTS(:8082); устранённый конфликт порта 8095 (нативный ASR vs Docker)
- Оркестратор запущен штатно (systemd, с NO_PROXY hardening), а не вручную
- Jetson подключён к проводной сети 10.10.10.x (eno1 / W5500 Ethernet), ESP доступен на `10.10.10.171` — IP в Config ВЕРНЫЙ, менять не нужно (решение D-01)
- Выход TTS — ТОЛЬКО через ESP-динамик (`esp32_speaker`); HDMI/`plughw:1,3` fallback не используется (решение D-02) → живой тест блокируется до восстановления сети ESP
- Живой end-to-end тест голосового цикла через ESP, зафиксированный в VERIFICATION.md: wake «адам» → транскрипт → ответ LLM → озвучка TTS → слышимый звук из ESP-динамика
- Влитый коммит `47fd0c5` (технофлора) с разрешением ВСЕХ конфликтов; flora-gate ПЕРЕРАБОТАН на сосуществование — моторика Адама (LLM action-layer) overlay поверх флоры, флора фон (решение D-03); FLORA-04 `feed_speech_wav` consumer интегрирован без поломки голоса
- Перепрошитый ESP под флору (firmware 47fd0c5 — в теле коммита «Прошивка обязательна»)

**Requirements:** REQ-VOICE-RECOVERY-01 (живой end-to-end голос), REQ-NO-OLLAMA (Ollama снесена, VRAM свободна), REQ-SERVICES-STABLE (8081/8082/8095 без конфликтов, через systemd), REQ-ESP-IP-FIX (корректный IP + доступность), REQ-FLORA-MERGE (47fd0c5 влит с разрешением конфликтов), REQ-ESP-REFLASH-FLORA (прошивка под флору)

**Mode:** standard | **Priority:** P0 | **Effort:** M (несколько дней) | **Exhibition:** Critical

**Связь с историей:** ветка luxflora (47fd0c5, автор 7teenzzz) внесла flora-gate, подавляющий action-layer, и сменила ESP IP; сегодня main откатывали (`backup/main-pre-rollback-2026-06-07`). Фаза наводит порядок: сначала рабочий голос, потом осознанная интеграция флоры.

---

## Phase 34: ASR Quality — пустые строки и галлюцинации

**Branch:** `voice-loop-recovery` (текущая)

**Goal:** Устранить два подтверждённых класса дефектов ASR: (1) пустые транскрипции после детекции wake-word, когда речевой буфер обнуляется до того как команда полностью произнесена; (2) галлюцинации (субтитры-фантомы типа «Спасибо за внимание», «Тревожная музыка» и т.д.), проходящие сквозь фильтры ASR-сервиса и оркестратора.

**Requires:**
- Все изменения из Phase 31 (barge-in fix, queue drain) уже закоммичены

**Delivers:**
- Wave 1: Pre-wake audio buffer — сохранять N секунд аудио до момента детекции wake-word и прикреплять к основному сегменту; strip wake-word из транскрипта в оркестраторе
- Wave 2: Hallucination guard — расширить `_HALLUCINATION_PATTERNS` в ASR_WhisperX.py + добавить post-filter в оркестраторе как второй эшелон; пересобрать Docker-контейнер

**Requirements:** REQ-ASR-EMPTY-PREWAKE (пустые после OWW), REQ-ASR-HALLUCINATION (фильтрация галлюцинаций)

**Mode:** standard | **Priority:** P0 | **Effort:** S | **Exhibition:** Critical

**Plans:** 2 plans

Plans:
- [ ] 34-PLAN-wave1.md — Pre-wake buffer fix: _pre_wake_buf в VoiceLoopController + Config param
- [ ] 34-PLAN-wave2.md — Hallucination guard: asr_filter.py + second-tier в Orchestrator + Docker rebuild

---

## Phase 30: Echoes/Chinese Gate Activation — реальный инжект пулов About в диалог

**Branch:** `MemoryFixes` (existing)

**Goal:** Заставить пулы Echoes (`About/Echoes.md`) и Chinese (`About/Chinese_lines.md`) реально срабатывать в диалоге. Сейчас gate матчит теги-образы карточек («коридор», «эскалатор», «物是人非») против сырого транскрипта зрителя — пересечение словарей почти нулевое, поэтому echoes практически никогда не инжектятся, а Chinese-пул вовсе выключен. Цель — устранить корневую причину через тематический мост, мягкий вероятностный движок выбора, разнообразие и спонтанный канал; включить китайский пул с русскими подсказками для LLM.

**Requires:**

- Phase 6A/6B (Memory Foundation/Search) завершены ✓ — `EpisodicMemory`, `SessionAccumulator`, `EchoGate` существуют
- Независима от Phase 18/19/20 (пересекается с Phase 19 в части «оживления mood», но не блокируется ей)

**Delivers:**

- **Слой A (тематический мост + окно истории):** `EchoGate` матчит теги карточек против множества `{acc.themes} ∪ {ключевые слова кластеров}` (нормализация уже делается в `SessionAccumulator.note_turn`), собранного из взвешенного окна последних N реплик (зритель + Адам), а не против одной сырой реплики. Чистые образы-теги остаются для редких буквальных совпадений.
- **Слой B (мягкий вероятностный движок):** замена жёсткого порога `match_threshold=0.55` на скоринг `final = thematic_match × weight × recency_decay` с взвешенно-случайным выбором кандидата выше низкого пола; редкость держится на cooldown'ах, а не на обрыве.
- **Слой C (спонтанный канал):** независимый низковероятный путь инжекта по внутренним сигналам (длинная пауза зрителя / глубина сессии / N-й turn), выбор по `weight` без тематического матча — «память всплывает сама» по лору.
- **Слой D (разнообразие + починка mood):** анти-повтор семантического кластера за сессию; оживление либо удаление мёртвого `mood`/`mood_block` (сейчас `mood` жёстко прибит к `"neutral"`, `adam_state` передаётся в gate, но игнорируется — `mood_block` полностью инертен).
- **Chinese-активация:** `tuning.chinese.enabled=true` + ослабление порога; `ru_hint` карточки прокидывается в `[hint]` для LLM (смысловая подсказка), т.к. Silero `v5_5_ru` не озвучит иероглифы корректно. Pre-rendered wav-озвучка по `audio_id` — **вне scope** (отдельная фаза).
- Все новые числовые параметры — в `System/Config.json` + `Config.schema.json` (Config-First).
- Тесты: матчинг по темам, вероятностный выбор, анти-повтор, спонтанный канал, активация Chinese.

**Requirements:** ECHO-01, ECHO-02, ECHO-03, ECHO-04, ECHO-05, ECHO-06, ECHO-07, ECHO-08

**Mode:** standard | **Priority:** P1 | **Exhibition:** H (напрямую обогащает речь персонажа)

**Связь:** реализует цель «использовать все файлы из папки About в диалоге». Пересекается с Phase 19 (Mood LLM-driven) в части оживления mood-сигнала — Phase 30 делает минимальную починку (revive/remove), полноценный LLM-driven mood остаётся за Phase 19. Спонтанный канал (слой C) концептуально родственен Phase 24/28 (проактивность), но действует на уровне gate-инжекта, не отдельного речевого цикла.

---

## Phase 35: Live Integration Testing — ultimate-integration после всех слияний

**Branch:** `ultimate-integration` (worktree `/tmp/adam-ult`, merge `15d23ca` ещё не запушен)

**Goal:** Подтвердить живыми тёрнами на железе Jetson, что полностью собранная ветка `ultimate-integration` работает end-to-end после всех предыдущих слияний (voice-loop-recovery Phase 34 ASR, LuxFlora ремап каналов, MemoryFixes, Extra шутки+погода, и только что разрешённый merge с починкой мохибейка Config.json). Не косметика — реальный голос в микрофон, реальный звук из ESP-динамика, реальная запись эпизода в память.

**Requires:**
- Merge `15d23ca` в worktree (Config.json де-мохибейк + barge-in fix) — готов, не запушен
- Живое железо: ESP на `10.10.10.171` (mic INMP441 + динамик PCM5102A), Jetson в сети `10.10.10.x`
- Сервисы: llama.cpp(:8081), Silero TTS(:8082), WhisperX(:8095), оркестратор(:8080)

**Delivers:**
- Wave 1 — Bring-up & smoke: подъём сервисов, healthcheck, валидация конфига на железе (wake_words=«адам», persona грузится, flora.enabled, skills weather/jokes)
- Wave 2 — Live voice E2E: wake «адам» → ASR → LLM → TTS → звук из ESP; barge-in (прерывание во время TTS); silence keyword «стоп»
- Wave 3 — Integration surfaces: флора-сосуществование (моторика Адама overlay поверх фоновой флоры, не подавление), pre-LLM скиллы шутки/погода, запись эпизода в episodic memory
- Wave 4 — Debug loop: для каждого дефекта из живых тёрнов — `/gsd-debug` (научный метод, persistent state), фикс, ре-тест; решение go/no-go на push

**Requirements:** REQ-INT-VOICE-E2E (голос end-to-end через ESP), REQ-INT-FLORA-COEXIST (сосуществование моторики и флоры), REQ-INT-SKILLS (шутки/погода pre-LLM), REQ-INT-MEMORY (запись эпизода), REQ-INT-CONFIG-LIVE (конфиг валиден на железе)

**Mode:** standard | **Priority:** P0 | **Effort:** M | **Exhibition:** Critical

**Plans:** 4 plans (Wave 1 → 2 → 3 → 4)
- [ ] 35-01-PLAN.md — Bring-up & smoke: checkout ultimate-integration в основной каталог, restart, healthcheck, валидация live-конфига, maintenance text-turn smoke (REQ-INT-CONFIG-LIVE)
- [ ] 35-02-PLAN.md — Live voice E2E: exhibition power-gate, оператор «адам»+команда, trace oww→…→action + звук из ESP, barge-in, «стоп» (REQ-INT-VOICE-E2E)
- [ ] 35-03-PLAN.md — Integration surfaces: флора-сосуществование (operator), pre-LLM шутки/погода, запись в dialogue_turns (REQ-INT-FLORA-COEXIST, REQ-INT-SKILLS, REQ-INT-MEMORY)
- [ ] 35-04-PLAN.md — Debug loop & go/no-go: /gsd-debug по каждому дефекту, ре-тест, решение go/no-go, user-gated push на origin/ultimate-integration

**Связь с историей:** `ultimate-integration` — пред-main интеграционная ветка, собравшая 4 линии разработки. До мёржа в main нужно живое подтверждение, что слияния не сломали голосовой тракт и что починка мохибейка (wake word на ult читался как «Р°РґР°Рj») восстановила распознавание.

---

## Direction: Подсознание-симбионт

Cosmos Reason2-2B — визуальное подсознание симбионта. Locked решение 2026-06-10 (benchmark: Cosmos 764ms/frame vs Gemma E4B vision inline 5099ms). Этот блок фаз переносит нарратив в архитектуру: подсознание анализирует речь зрителя акустически, управляет флорой семантически, предмодулирует AIIM без участия LLM, ведёт наблюдательный журнал и помнит посетителей через реестр.

Три фазы идут последовательно. Phase 38 дополнительно разблокирует Phase 28 (Event-driven Proactivity).

---

## Phase 36: SubconsciousProcessor — речевое подсознание

**Branch:** `subconscious-symbiont` (existing)

**Goal:** Создать `SubconsciousAnalyzer` — компонент, который анализирует акустику речи зрителя (RMS, пики, паузы) до того как LLM получает запрос. Подсознание управляет флорой (семантический выбор пресета) и предмодулирует AIIM-состояние (`emotion_hint` при нейтральном тексте).

**Requires:**
- Phase 35 (Live Integration) завершена — стабильный pipeline
- Phase 29 (Technoflora) завершена — FloraController с `push_preset()` API

**Research findings (2026-06-10):**
- Точка вставки: `_run_dialogue_turn_locked` строка ~3444 — после echoes/mood, до AIIM блока (строки 3445–3476)
- Acoustic features вычислять в `_transcribe_and_dispatch` (строка 1779, параметр `pcm`) и передавать через новый параметр `_run_dialogue_turn(acoustic_features=...)`
- EmotionMachine детерминирована с keyword-приоритетами; premod применяется ТОЛЬКО при `emotion_src == ""` — нельзя перебить keyword-override
- FloraController: нет приоритетов сейчас ("последний выигрывает"); нужен уровень P2 (subconscious) между P3 (pipeline) и P1 (idle)
- Оптимальное окно для флоры: между `asr_final` и `llm_thinking_started`
- D-11 инвариант: vibro всегда OFF при `voice_state="attentive"` — FloraController уже реализует это через `vibro.silent_states`
- `audio_level` events: 25 Hz, `bands[24]` FFT — доступны как rolling window

**Research findings (2026-06-11, Agent B — VLM dual-task architecture):**
- Двойная архитектура VLM: Task A (сцена → `[ctx.vision]`, по `scene_interval_sec`) + Task B (AIIM JSON модулятор, по `asr_final`)
- Task B семантически зависит от Task A — выполнять последовательно, не параллельно; 2 × 764ms = 1528ms суммарно при событийном запуске
- Task A output: `"3 people; two adults (30s, casual wear) speaking at center..."` — factual, English, ≤80 tokens
- Task B output JSON: `{"emotion_hint": "curious|warm|unease|sharp|calm", "flora_mode": "breathe|accent|...", "intensity": 0.0-1.0, "reasoning": "..."}`
- Failure resilience: Task A timeout → кэш предыдущей сцены; Task B JSON malformed → нейтральный сигнал (calm, breathe, 0.3)
- Точки интеграции: SceneWorker._run() (~строка 1940) для Task A; `_transcribe_and_dispatch` для Task B trigger; `_run_dialogue_turn_locked` (~3445) для применения сигнала
- Полный дизайн: `.planning/research/subconscious_prompts.md`

**Research findings (2026-06-11, Agent C — AIIM тест-стек):**
- `emotion_src == ""` → единственная точка для premod; строка 305 identity.py `return current, ""`
- `to_ctx_block()` строки 186-188: emotion="curious" без injectable → возвращает `""` (экономия токенов); остальные эмоции инжектируются
- Существующих тестов для premod нет; нужен новый файл `tests/test_aiim_premod.py`
- 4 unit-теста + 2 integration + 1 bash-скрипт (ручная проверка Cosmos → SubconsciousSignal)
- Полный дизайн: `.planning/research/aiim_test_design.md`

**Research findings (2026-06-11, Agent D — flora анимации):**
- AIIM эмоции (`curious/warm/unease/sharp/calm`) не маппируются на flora сейчас — только pipeline-события; это gap
- 10 новых пресетов (5 эмоций × 2 варианта A/B): `curious_a/b`, `warm_a/b`, `unease_a/b`, `sharp_a/b`, `calm_a/b`
- Модулируемые параметры из SubconsciousSignal: `intensity` (0-1), `tempo` (0.5-2.0), `jitter` (unease), `focus` (sharp attack_ms), `tenderness` (warm vibro%), `stillness` (calm range)
- Firmware FloraParams нужно расширить: добавить `intensity`, `tempo`, `jitter`, `attackMs`, `flicker`, `sparkProbability`
- Variant выбор: intensity ≤ 0.65 → variant A; intensity > 0.65 → variant B
- Полный дизайн: `.planning/research/flora_animations.md`

**Delivers:**
- Новый модуль `System/adam/subconscious.py`:
  - `SubconsciousAnalyzer.analyze(transcript, acoustic_features, scene_text, turn) → SubconsciousSignal`
  - `SubconsciousSignal(emotion_hint, weight, flora_preset, observation_text, acc_tone)`
  - Маппинг акустика → сигнал: `rms_peak / rms_mean > 3.0` → взволнованность; `silence_ratio > 0.4` → медленная речь; тематические слова → flora `think_pulse`
- Acoustic features pipeline:
  - `_transcribe_and_dispatch(pcm)` → вычислить `AcousticFeatures(rms_mean, rms_peak, silence_ratio)` из PCM uint16
  - Передать через `_run_dialogue_turn(acoustic_features=...)` → `_run_dialogue_turn_locked`
- AIIM premod:
  - Поле `premod: dict | None = None` в `AIIMRuntimeState` (`identity.py`)
  - После `EmotionMachine.transition()`: если `emotion_src == ""` и `premod["weight"] > 0.35` → применить `premod["emotion_hint"]`, выставить `emotion_src = "subconscious"`
  - `acc.set_tone()` из акустики (тихий медленный голос → "sad" независимо от слов зрителя)
- Flora semantic control:
  - Priority system в `FloraController`: P3 (pipeline transitions), P2 (subconscious), P1 (idle)
  - Прямой вызов `flora_controller.push_preset_p2(preset)` внутри turn (синхронно, не через EventBus)
  - P2 блокируется если текущий priority ≥ P3 или `voice_state="attentive"`
- `observations.jsonl` writer (базовые типы):
  - Типы: `emotion_spike` (rms_peak > 7000 + emotion words), `session_digest` (при `episode_committed`)
  - EventBus подписка на `episode_committed` для session_digest
- VLM dual-task architecture (Task A + Task B):
  - Task A: структурированное описание сцены → `[ctx.vision]`; промпт: people count + demo tier (CHILD/YOUNG/ADULT/ELDER) + gender + clothes + activity (speaking/silent) + position + engagement
  - Task B: AIIM JSON модулятор; промпт принимает scene_text + transcript + acoustic_features → возвращает `{emotion_hint, flora_mode, intensity, reasoning}`; запускается только на `asr_final`; failure → нейтральный сигнал (calm, breathe, 0.3)
  - VLM клиент: новые методы `describe_scene_structure()` (Task A) и `analyze_aiim_signal()` (Task B)
- Flora emotion presets: 10 новых пресетов в `Config.json flora.emotion_presets`:
  - `curious_a/b`, `warm_a/b`, `unease_a/b`, `sharp_a/b`, `calm_a/b`
  - Variant выбор: `intensity ≤ 0.65` → A; `intensity > 0.65` → B
  - Параметры от подсознания: `intensity`, `tempo`, `jitter` (unease), `focus`=attack_ms (sharp), `tenderness`=vibro% (warm), `stillness`=range compression (calm)
  - FloraController: `push_preset_p2_emotion(emotion, intensity)` + `_compute_emotion_params()`
  - Вызов после AIIM блока: если эмоция изменилась → `flora.push_preset_p2_emotion(new_emotion, intensity)`
  - Firmware FloraParams расширить: добавить `intensity`, `tempo`, `jitter`, `attackMs`, `flicker`
- Тест-стек AIIM premod (новый файл `tests/test_aiim_premod.py`):
  - Unit: premod применяется при `emotion_src == ""`; premod заблокирован при keyword; weight < 0.35 игнорируется; ctx_block содержит premod-эмоцию
  - Integration: PCM → SubconsciousSignal → emotion → ctx_block; flora_preset propagation
  - Bash: `scripts/test_subconscious_inference_stack.sh` — ручная проверка pipeline

**Requirements:** SUBCON-01 (SubconsciousAnalyzer), SUBCON-02 (acoustic features pipeline), SUBCON-03 (AIIM premod), SUBCON-04 (flora semantic control), SUBCON-05 (priority system), SUBCON-06 (observations.jsonl base), SUBCON-07 (VLM Task B AIIM JSON modulator), SUBCON-08 (flora emotion presets 10×), SUBCON-09 (premod test suite)

**Mode:** standard | **Priority:** P1 | **Effort:** L | **Exhibition:** H

**Plans:** 6 plans
- [ ] 36-01-PLAN.md — AcousticFeatures: вычисление rms_mean/rms_peak/silence_ratio из PCM, передача через сигнатуру в _run_dialogue_turn_locked
- [ ] 36-02-PLAN.md — subconscious.py: SubconsciousAnalyzer + SubconsciousSignal + acoustic→signal маппинг
- [ ] 36-03-PLAN.md — AIIM premod: premod поле в AIIMRuntimeState (identity.py) + conditional merge после EmotionMachine; acc.set_tone() из акустики + тест-стек (test_aiim_premod.py + bash script)
- [ ] 36-04-PLAN.md — Flora P2 priority system в FloraController + observations.jsonl writer (emotion_spike + session_digest via EventBus)
- [ ] 36-05-PLAN.md — VLM dual-task architecture: Task A (scene structure prompt) + Task B (AIIM JSON modulator prompt) + VLM client методы + Orchestrator integration points (SceneWorker + _transcribe_and_dispatch + _run_dialogue_turn_locked)
- [ ] 36-06-PLAN.md — Flora emotion presets: 10 пресетов в Config.json (flora.emotion_presets) + FloraController.push_preset_p2_emotion() + firmware FloraParams расширение (intensity/tempo/jitter/attackMs)

---

## Phase 36B: SmartFlora — пользовательский уровень управления флорой

**Branch:** `SmartFlora` (from `subconscious-symbiont @ 028bea5`)

**Goal:** Трёхуровневая система управления технофлорой поверх Phase 36 P2-слоя: библиотека пользовательских пресетов (Level 1), именованные последовательности анимаций (Level 2), явная привязка эмоций AIIM к пресетам (Level 3). WebUI-панель управления.

**Requires:** Phase 36 Direction 1 завершена (P2 coexistence priority system — commit `028bea5`)

**Delivers:**

- `flora.user_presets` dict в Config.json — пользовательские пресеты, отдельные от `flora.states`
- `flora.sequences` list — именованные цепочки `{preset, hold_ms, crossfade_ms?}`
- `flora.emotion_map` dict — явный маппинг AIIM-эмоций на пресеты (fallback на naming convention)
- CRUD API: `/api/flora/presets`, `/api/flora/sequences`, `/api/flora/emotion_map`
- Sequence runner как cancellable asyncio.Task (P2 приоритет, отменяется P1/P3)
- WebUI: редактор пресетов, step-builder секвенций, emotion map с дропдаунами

**Requirements:** FLORA-UP-01 (user_presets CRUD), FLORA-UP-02 (sequences runner), FLORA-UP-03 (emotion_map binding), FLORA-UP-04 (WebUI management)

**Mode:** standard | **Priority:** P1 | **Effort:** M | **Exhibition:** H

**Plans:** 1 plan

- [x] 36B-01 — реализация (выполнено, ветка SmartFlora)

---

## Phase 36C: SmartFlora Testing — тестирование на железе

**Branch:** `SmartFlora` (continuation)

**Goal:** Живое подтверждение на Jetson + ESP32, что SmartFlora не ломает существующий pipeline и три уровня работают корректно.

**Requires:** Phase 36B завершена

**Delivers:**

- Smoke-тест: wake_word→accent→attentive→breathe цикл не сломан после Phase 36B
- Тест Level 1: создать пресет через WebUI → применить → убедиться что ESP реагирует
- Тест Level 2: создать секвенцию 3 шага → запустить → прервать voice_state
- Тест Level 3: привязать emotion → вызвать `push_preset_p2_emotion` → убедиться что emotion_map используется
- Тест совместимости: P2-sequence отменяется при wake_word (P1 приоритет)
- `36C-SUMMARY.md` с результатами тестов и go/no-go решением для мёржа в subconscious-symbiont

**Mode:** standard | **Priority:** P0 (блокер мёржа) | **Effort:** S | **Exhibition:** Critical

**Plans:** 1 plan

- [ ] 36C-01-PLAN.md — live hardware test: smoke + Level 1/2/3 + P2 cancel test + go/no-go

---

## Phase 37: VisitorRegistry + Notes System

**Branch:** `subconscious-symbiont` (continuation)

**Goal:** Создать полноценную систему памяти о посетителях: реестр с агрегированными профилями, O(1) поиск по имени, расширенный формат инжекции профиля в промпт. Параллельно — полный observations.jsonl со всеми типами событий подсознания.

**Requires:** Phase 36 завершена (базовый observations.jsonl writer)

**Research findings (2026-06-11, Agent A — WebUI visitors page):**
- Роутинг: hash-based SPA, добавить `visitors: { file: "visitors", label: "Зрители" }` в `ROUTES` (router.js) + `{ key: "visitors", label: "Зрители" }` в `NAV_STRUCTURE` (main.js)
- Паттерн компонента: `export function mount(target)` → возвращает teardown; `el()` DOM-builder; `.card-grid` CSS (auto-fill minmax 320px)
- CSS-переменные готовые: `--accent: #43d17a`, `.badge`, `.dot.ok/.warn/.bad`, `.card` + `.card-header` + `.card-body`
- Карточка посетителя: имя + визит-бейдж + time-ago, темы как `.badge`, first/last visit даты, tone profile top-2, highlights excerpt
- API нужен: `GET /api/visitors` (список), `GET /api/visitors/{slug}` (профиль), `GET /api/visitors/stats`
- Стратегия: параллельно с Phase 37-01 (mock API первый, реальный endpoint после VisitorRegistry)
- Полный дизайн: `.planning/research/ui_visitor_cards.md`

**Research findings (2026-06-10):**
- `query_by_name` — O(N files) перебор JSONL за `lookup_days`; нет индекса; вызывается дважды за turn при наличии имени (строки 3297 и 3311 Orchestrator)
- Двухсловный фильтр `_extract_visitor_name` (строки 300–301 Orchestrator) блокирует однословные имена — большинство реальных представлений ("меня зовут Андрей") отклоняется; `introduced_name = null` в большинстве реальных эпизодов
- `recurring_signal` в `Episode.visitor` выставляется при каждом turn, но не используется в `_format_recent_episodic` — мёртвые данные
- `by_theme` strategy в `RecentInjectionTuning` объявлена (tuning.py строка 66), но не реализована в Orchestrator — мёртвое значение enum
- `notes/` и `summaries/` директории пусты; `MemoryStore.add_note()` и `summary_text()` нигде не вызываются из Orchestrator — мёртвый код
- `_format_recent_episodic` возвращает только `"дата — тема1, тема2"` без имени, highlights, "что Адам сказал"
- EventBus: `episode_committed` уже публикуется (~строка 383) с payload: id, salience, name, themes, duration_s, reason — готовый hook для VisitorRegistry

**Delivers:**
- VisitorRegistry (`System/adam/visitor_registry.py`):
  - `data/adam/visitors/{name_slug}.json` — профиль: visit_count, all_themes, tone_profile (dict emotion→count), first/last_visit_ts, highlights (last 5), episode_ids
  - `data/adam/visitors/_index.json` — `{name_slug: last_visit_ts}` для O(1) lookup
  - EventBus подписка на `episode_committed` → `VisitorRegistry.update(episode)` — обновить/создать профиль
  - Методы: `get_profile(name) → dict | None`, `update(episode)`, `list_names() → list`
- Relaxed name filter в `_extract_visitor_name`:
  - Одно слово → `first_name` (принимается, не отклоняется)
  - Два слова → `full_name`
  - Lookup key по `display_name.lower()`
- Enriched prompt injection:
  - `_format_recent_episodic` использует VisitorRegistry: "Посещений: 3. Темы: память, страх. Последний визит: 3 дня назад." вместо голых дат
  - `recurring_signal=True` → другой регистр приветствия (новый зритель vs знакомый)
  - `by_theme` strategy реализована: `query_by_theme(themes) → [Episode]` через кластеры из `acc.themes`
- observations.jsonl полный набор типов:
  - `visitor_arrival` — Cosmos engagement меняется с none → watching/approaching
  - `visitor_left` — engagement меняется на none или session_end
  - `topic_shift` — смена тематического кластера между turn'ами (из `acc.themes`)
  - `long_silence` — gap `last_turn_at` > threshold (из session_state)
  - `repeated_theme` — та же тема встречается ≥3 раз за сессию
- Cleanup:
  - `MemoryStore.add_note()` + `summary_text()` — подключить к SubconsciousProcessor или удалить как dead code (решение в plan)

**Requirements:** VIS-01 (VisitorRegistry structure), VIS-02 (O(1) index), VIS-03 (relaxed name filter), VIS-04 (enriched prompt injection), VIS-05 (by_theme implementation), VIS-06 (recurring_signal in prompt), VIS-07 (observations full types), UI-VIS-01 (visitors WebUI panel), UI-VIS-02 (API endpoints /api/visitors)

**Mode:** standard | **Priority:** P1 | **Effort:** M | **Exhibition:** H

**Plans:** 4 plans
- [ ] 37-01-PLAN.md — VisitorRegistry: visitor_registry.py + visitors/ dir + _index.json + EventBus subscription + get/update profile
- [ ] 37-02-PLAN.md — Relaxed name filter + _format_recent_episodic enrichment + by_theme implementation (строки 3310–3312 Orchestrator)
- [ ] 37-03-PLAN.md — observations.jsonl полный набор типов (topic_shift, visitor_arrival/left, long_silence, repeated_theme) + мёртвый код audit
- [ ] 37-04-PLAN.md — UI visitors page: GET /api/visitors + /api/visitors/{slug} + /api/visitors/stats в api_runtime.py; WebUI panel visitors.js (card-grid, карточки с темами/тоном/визитами); ROUTES + NAV_STRUCTURE; mock API для параллельной разработки

---

## Phase 38: Subconscious Autonomy — Cosmos как агент

**Branch:** `subconscious-symbiont` (continuation) или новая ветка `cosmos-agent`

**Goal:** Перевести Cosmos Reason2-2B из пассивного VLM-провайдера в активный агент: адаптивная частота съёмки, события на EventBus при изменении сцены, модуляция `pe`/`be` аспектов IdentityVector через подсознание.

**Requires:** Phase 36, Phase 37 завершены

**Research findings (2026-06-10):**
- Cosmos: 764ms/frame (480×360), 2.9GB VRAM, порт 8051, `llama-server`; KV-cache miss: +25 токенов от описания сцены → +484ms LLM (не стоимость токенов, а инвалидация кэша)
- Текущий `scene_worker`: периодический, `scene_interval_sec=4`, не событийный; не публикует дельта-события
- `be` и `pe` аспекты в `IdentityVector` никогда не модулируются в `AspectModulator` — готовый хук; не включены в `AspectCeilingConfig`; дрейф через DriftTable тоже не затрагивает их
- `phase_28` (Event-driven Proactivity): паттерн scene_delta детектора будет создан там же — Phase 38 может переиспользовать его

**Delivers:**
- Scene delta detection (`System/adam/scene_delta.py`):
  - Парсинг двухчастного формата "Scene: X. Engagement: Y." → структурированные поля `count`, `positions`, `engagement`
  - Сравнение текущего с предыдущим из `scene_buffer` → категория: `appeared`, `disappeared`, `count_change`, `engagement_change`, `no_delta`
  - Публикация `scene_delta` событий в EventBus с payload: `from`, `to`, `category`
- Adaptive capture rate:
  - `engagement=interacting/approaching` → `scene_interval_sec` уменьшается (min 2s)
  - `engagement=none` + `no_delta` серия → `scene_interval_sec` увеличивается (max 10s)
  - Config-First параметры: `media.scene_adaptive_rate_enabled`, `scene_interval_min_sec`, `scene_interval_max_sec`
- Cosmos → SubconsciousProcessor:
  - `scene_delta` → дополнительный вход для `SubconsciousAnalyzer.analyze()` (Phase 36 расширить сигнатуру)
  - `appeared` → `accent` flora + `at↑`; `interacting` → `think_pulse` flora; `none` длительно → `breathe` + `be↑`
- `pe`/`be` aspect modulation:
  - `SubconsciousSignal.aspect_hints: dict[str, float]` — дополнительные Δ для аспектов
  - `AspectModulator.modulate()` расширить: смешивать `premod.aspect_hints` с результатом (additive, clamp к ceiling)
  - `pe` (perception): активный engagement → pe↑; пустая сцена → pe нейтральный
  - `be` (being/self): длительное отсутствие зрителей → be↑ (Адам в режиме саморефлексии)

**Requirements:** COSM-01 (scene_delta.py), COSM-02 (adaptive rate Config-First), COSM-03 (EventBus scene_delta), COSM-04 (pe/be modulation в AspectModulator), COSM-05 (Cosmos → SubconsciousSignal mapping)

**Mode:** standard | **Priority:** P2 | **Effort:** L | **Exhibition:** M

**Plans:** 3 plans
- [ ] 38-01-PLAN.md — scene_delta.py: парсер двухчастного формата + детектор переходов + EventBus событие
- [ ] 38-02-PLAN.md — Adaptive capture rate: engagement → interval logic + Config-First параметры в media section
- [ ] 38-03-PLAN.md — pe/be aspect modulation: aspect_hints в SubconsciousSignal + AspectModulator расширение (смешивание premod.aspect_hints)

---

## Phase 39: AIIM + Subconscious Dashboard — мониторинг внутреннего состояния

**Branch:** `subconscious-symbiont` (continuation)

**Goal:** Добавить в WebUI три живых блока мониторинга: (1) системный промпт + инжекции подсознания, (2) текущее эмоциональное состояние Адама (AIIM), (3) лента ответов подсознания (Task B outputs). Всё через SSE/polling без перезагрузки страницы.

**Requires:** Phase 36 завершена (SubconsciousProcessor публикует события)

**Research findings (2026-06-11, Agent B — WebUI структура):**
- Chat-страница: grid 3fr:2fr; слева — лента диалога + текстовый ввод; справа — камера, VLM-описание, FFT-эквалайзер, speech status
- SSE через `/api/agent/stream`: `{id, ts, type, payload, turn_id}`; frontend: `subscribeEvents()` → `state.patch("last_events", ...)` → компоненты подписываются через `state.subscribe("last_events", callback)`
- AIIM эмоция **не попадает в события** сейчас — только `aiim_humor_reaction`; нет AIIM-секции в `/api/agent/status`
- EmotionWidget: +5 строк Orchestrator (event_log.append "aiim_state_snapshot" после строки ~3474), компонент в правой колонке между sceneCaption и микрофоном
- SubconsciousResponsesFeed: зависит от Phase 36 SubconsciousProcessor; пока placeholder
- PromptInjectionsBadges: данные уже доступны через status polling + SSE, без дополнительных backend-изменений
- Полный дизайн: `.planning/research/ui_live_widgets.md`

**Research findings (2026-06-11, Agent C — системный промпт):**
- `PromptBuilder.build_messages()` → messages[0] = статичная персона (System+Identity+Lore+Abilities), messages[1] = динамический ctx_body
- 6 ctx блоков (строгий порядок): `[ctx.identity]`, `[ctx.memory]`, `[ctx.recent_visitors]`, `[ctx.vision]`, `[ctx.sensors]`, `[ctx.weather]` (только при weather-intent)
- `[hint]` идёт в user message, не в ctx_body (echo/chinese gate)
- SubconsciousSignal **не идёт в промпт напрямую** — premodулирует AIIM state; виден косвенно через `[ctx.identity]`
- **`GET /api/agent/prompts` уже существует** (ring buffer 50 turns); **`panels/prompts.js` уже существует**
- Нужно: +3 поля в trace_record (identity_block, weather_ctx, echo_hint_text) + новый `GET /api/prompt/current` (~50 строк) + promptCurrent.js (~150 строк)
- Полный дизайн: `.planning/research/prompt_viewer.md`

**Delivers:**

- Блок "Системный промпт + инжекции" (item 1):
  - `GET /api/prompt/current` → JSON с секциями: `[{name, content, chars}]` + total_chars + turn_id
  - Prompt viewer component: секции как collapsible items с цветовой кодировкой по типу ([ctx.identity]=синий, [ctx.vision]=зелёный, echoes=жёлтый, subconscious=фиолетовый)
  - Показывает текущий SubconsciousSignal (emotion_hint, flora_mode, intensity) как отдельную секцию
- Блок "Текущая эмоция" (item 2):
  - SSE событие `aiim_emotion_change` с payload: `{emotion, emotion_src, vector_snapshot}`
  - EmotionWidget на главной chat-странице: имя эмоции + источник + цветовой индикатор + 12 aspect bars
  - Обновляется в реальном времени через SSE
- Блок "Ответы подсознания" (item 3):
  - SSE событие `subconscious_signal` с payload: Task B JSON + acoustic_features + turn_id
  - SubconsciousResponsesFeed: лента последних 5-10 сигналов на главной странице
  - Каждая запись: emotion_hint + flora_mode + intensity + reasoning + timestamp

**Requirements:** DASH-01 (prompt viewer API), DASH-02 (prompt viewer component), DASH-03 (aiim_emotion_change SSE), DASH-04 (EmotionWidget), DASH-05 (subconscious_signal SSE), DASH-06 (SubconsciousResponsesFeed)

**Mode:** standard | **Priority:** P1 | **Effort:** M | **Exhibition:** H

**Plans:** 3 plans
- [ ] 39-01-PLAN.md — GET /api/prompt/current: сборка промпта в labeled sections + prompt_viewer WebUI component (collapsible, color-coded)
- [ ] 39-02-PLAN.md — SSE aiim_emotion_change: EventBus hook после EmotionMachine.transition() + EmotionWidget на chat-странице (emotion + src + aspect bars)
- [ ] 39-03-PLAN.md — SSE subconscious_signal + SubconsciousResponsesFeed: лента Task B outputs на главной странице

---

## Phase 40: AIIM Personality Editor — редактор личности Адама

**Branch:** `subconscious-symbiont` (continuation) или `aiim-editor`

**Goal:** Интерактивный редактор личности Адама: 12 аспектов (ползунки + числовые поля) + индивидуальные дельты дрейфа по эмоциям. Изменения интегрируются в формулу AIIM в `Identity.md` и/или `Config.json`. Кнопка "Описать Адама" вызывает подсознание (Cosmos) которое генерирует описание итоговой личности с учётом текущей формулы + delta-дрейфа.

**Requires:** Phase 36 завершена (Cosmos Task B работает), Phase 39 завершена (SSE events работают)

**Research findings (2026-06-11, Agent A — AIIM formula + editor backend):**
- Формат AIIM formula: `aspect(plan level mode)Δweight` — plan=B/S/P/I/T; level=1-4; mode=Ac/Pa + Or/Ch; weight=0.0–1.0 (>0.8 = ядро)
- **LOCKED аспекты**: `se` (0.92) и `co` (0.88) — жёстко заморожены в коде, не редактируются через UI
- Drift: накапливается в `data/adam/identity/drift.json` как `aspect_drift: {lo: 0.012, ...}`; применяется при старте сессии; 5 типов сессий (void/witnessed/memory_surfacing/confrontation/deep_contact)
- Потолки drift по аспектам: lo≤0.85, em≤0.75, me≤0.60 и т.д. (документированы в `identity_drift.py`)
- **`GET/PUT /api/persona` уже существует** (raw text); `identity_drift.py` уже существует
- Нужно добавить 5 новых endpoints в `api_runtime.py` — все классы уже есть в `identity.py` + `identity_drift.py`
- Полный дизайн: `.planning/research/aiim_editor_backend.md`

**Delivers:**

- Backend AIIM Editor API (item 4):
  - `GET /api/aiim/formula` → JSON: `{aspects: [{name, polar, scale, align, orient, delta}], raw_formula}`
  - `PUT /api/aiim/formula` → принимает изменённые параметры → перезаписывает блок формулы в `Agent-Adam-Chip/About/Identity.md`; hot-reload persona_paths
  - `GET /api/aiim/drift` → текущие drift deltas per emotion (DriftAccumulator state)
  - `PUT /api/aiim/drift` → обновить drift deltas → применить к `AIIMRuntimeState.vector`
  - `POST /api/aiim/describe` → собирает текущую формулу + drift state → отправляет Cosmos с personality-description промтом → стримит ответ в SSE
- Frontend AIIM Editor (item 4):
  - WebUI панель "Личность": 12 аспектов в grid; каждый — ползунок (диапазон по scale) + numeric input + имя + кодировка polar/align/orient
  - Drift deltas editor: таблица emotion × delta, редактируемые ячейки
  - Preview generated formula string (обновляется при изменении любого ползунка)
  - Кнопка "Описать Адама": вызывает POST /api/aiim/describe → показывает стримящийся ответ в блоке подсознания
  - Кнопка "Сохранить" → PUT /api/aiim/formula; "Сбросить" → откат к сохранённым значениям

**Requirements:** AIIMED-01 (formula parser/writer), AIIMED-02 (GET/PUT /api/aiim/formula), AIIMED-03 (drift API), AIIMED-04 (describe endpoint + Cosmos call), AIIMED-05 (editor frontend sliders), AIIMED-06 (drift deltas table), AIIMED-07 (Describe button + streaming response)

**Mode:** standard | **Priority:** P2 | **Effort:** L | **Exhibition:** M

**Plans:** 3 plans
- [ ] 40-01-PLAN.md — AIIM formula backend: parse_aiim_formula() → JSON + write back; GET/PUT /api/aiim/formula; hot-reload после записи; GET/PUT /api/aiim/drift
- [ ] 40-02-PLAN.md — AIIM editor frontend: WebUI панель "Личность" — 12 слайдеров + drift table + live formula preview + Сохранить/Сбросить кнопки
- [ ] 40-03-PLAN.md — "Описать Адама": POST /api/aiim/describe → собрать формулу + drift → Cosmos personality prompt → SSE stream → отображение в SubconsciousResponsesFeed

---

## Phase 41: Audio Pipeline Latency Fix — PipeWire node.max-latency

**Branch:** TBD — фикс не относится к `SmartFlora` (флора), требует отдельной ветки от `main`/`subconscious-symbiont` перед `/commit-push` (branch gap, см. 41-CONTEXT.md)

**Goal:** Восстановить нормальный темп доставки аудио (~50 кадров/сек по 20мс) с USB-микрофона WebCamera, чтобы OpenWakeWord («адам»), VAD-endpointing и ASR-таймауты работали как раньше (06-08/06-09).

**Findings (2026-06-12, диагностика «OWW не детектит ничего»):**
- Root cause: PipeWire ALSA-узел `alsa_input.usb-WebCamera_*` имеет `node.max-latency=48000/48000` (1с) и `buffer_size=96000` (2с@48kHz) → доставляет аудио пачками ~120мс раз в ~1.1-1.2с (~10% реального throughput) вместо непрерывных 20мс-кадров
- `oww_score` застывает на 0.001 — `debounce_hits=2` требует двух ПОСЛЕДОВАТЕЛЬНЫХ оценок на временно-непрерывном аудио, но соседние вызовы разделены ~1.1с и не являются соседними кадрами
- Та же проблема ломает VAD/ASR endpointing-таймеры (`silence_after_speech_ms`, `endpointing_*_debounce_frames`, `*_segment_ms`) — растягиваются в wall-clock на порядок
- WirePlumber override уже создан (`~/.config/wireplumber/main.lua.d/51-webcamera-latency.lua`, `node.latency=512/48000`), но НЕ активирован — требует `systemctl --user restart wireplumber pipewire pipewire-pulse` с явным подтверждением пользователя (разрывает live mic-стрим оркестратора)
- Полная диагностика: `.planning/phases/41-audio-pipeline-latency-fix/41-CONTEXT.md`

**Delivers:**
- Активация и верификация WirePlumber-фикса latency для WebCamera-узла (после явного подтверждения рестарта аудио-стека)
- `_find_pulse_source` retry-with-backoff в `local_mic_reader.py` (intermittent `None` на холодном старте)
- Решение по сегодняшнему `_raw_chunk_for_monitor` фиксу в Orchestrator.py (оставить/откатить/доработать) — после верификации throughput-фикса
- Перекалибровка `wake_word.threshold`/`debounce_hits` и при необходимости VAD/ASR endpointing-таймеров на основе живых замеров после фикса
- Живая верификация: произнесение «адам» triggers `wake_word_detected`

**Requirements:** APLF-01 (PipeWire/WirePlumber latency override активирован и верифицирован), APLF-02 (`_find_pulse_source` retry-with-backoff), APLF-03 (`_raw_chunk_for_monitor` решение принято и применено), APLF-04 (OWW threshold/debounce перекалиброваны и подтверждены живым тестом), APLF-05 (VAD/ASR endpointing таймеры проверены на нормальном темпе кадров)

**Mode:** standard | **Priority:** P0 | **Effort:** S | **Exhibition:** critical (OWW — основной механизм пробуждения для exhibition mode)

**Plans:** 4 plans in 3 waves

Plans:
**Wave 1**
- [ ] 41-01-PLAN.md — Activate + verify WirePlumber latency override (restore ~50 Hz frame cadence) [wave 1]
- [ ] 41-02-PLAN.md — `_find_pulse_source` retry-with-backoff + finalize `_raw_chunk_for_monitor` OWW-input decision [wave 1]

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 41-03-PLAN.md — Live OWW threshold/debounce recalibration + VAD/ASR endpointing timer verification [wave 2]

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 41-04-PLAN.md — End-to-end voice loop verification (wake → ASR → LLM → TTS) [wave 3]

---

## Phase 42: WebUI Reorganization — рефакторинг интерфейса оператора

**Branch:** TBD (от `main` или `SmartFlora`)

**Goal:** Убрать дублирование и мёртвый код в операторском интерфейсе, реорганизовать конфигурацию по смысловым разделам, вынести память в отдельный раздел. Результат — интерфейс без дублей, с чёткой структурой, готовый к расширению.

**Delivers:**

- Удаление трёх страниц-дублей/заглушек: скрытая страница тонкой настройки (→ уникальные блоки мигрируют на страницы Личность и Память), скрытая страница промтов (→ уникальный кусок `inlineList(recent_episodic)` переносится на страницу Метрики), мёртвая страница-заглушка Сцена (прямой редирект на флору, без своего контента)
- Объединение страниц «Сервисы» и «Модели» в одну «Сервисы инференса» — очистка устаревших полей (мёртвая VILA-карточка, несуществующие опции ASR/LLM)
- Новая страница «Память» как отдельный верхнеуровневый раздел: эпизодическая память + веса, семантическая (дневник), инжекция из прошлых сессий, ночная консолидация
- Реорганизация страницы «Конфигурация» на разделы: «Как Адам думает и говорит», «Как Адам слышит», «Как Адам видит», «Железо» (переименование «Железо и безопасность»); удаление дублирующих полей ASR и видео
- AIIM-блок (характер Адама) + индикатор эмоции/режима → страница «Личность агента» под карточкой Identity
- Страница «Аудио-вход»: исправить oversized блок громкости (`card-full` → нормальный размер), убрать дублирующее поле чувствительности wake-word (остаётся только в калибровочном блоке)
- Флора: 5 карточек состояний → одна таблица (строки=состояния, столбцы=база/пик(≤71%)/скорость/вибро/«показать сейчас»)

**Out of scope (отдельные фазы):**

- Отображение эмоции и ленты подсознания на чате → Фаза 39
- Кейфрейм-редактор анимаций → расширение Фазы 36B
- Страница зрителей → Фаза 37
- Страница диагностики → будущая фаза

**Requirements:** WEBUI-R01 (дублирующие страницы удалены), WEBUI-R02 (объединены Сервисы+Модели), WEBUI-R03 (новая страница Память в навигации), WEBUI-R04 (Конфигурация реорганизована с удалением дублей), WEBUI-R05 (AIIM-блок на странице Личность), WEBUI-R06 (Аудио-вход: размеры и дубли исправлены), WEBUI-R07 (Флора: таблица состояний вместо 5 карточек)

**Mode:** standard | **Priority:** P1 | **Effort:** M | **Exhibition:** non-blocking

**Plans:** 8 plans (4 волны)

Plans:
- [ ] 42-01-PLAN.md — Фундамент: router parseHash nested routes + 3-уровневый nav + marked.js (Wave 1)
- [ ] 42-02-PLAN.md — Личность: AIIM-матрица + preset + блок-редакторы Интенции/Голос (Wave 2)
- [ ] 42-03-PLAN.md — Инструкции (markdown render/edit) + Память (Базовая/Дополненная) (Wave 2)
- [ ] 42-04-PLAN.md — Флора: таблица состояний + backend запись states в Flora.json (Wave 2)
- [ ] 42-05-PLAN.md — Аудио и видео (3.1): объединение audioInput + settings + фикс card-full (Wave 3)
- [ ] 42-06-PLAN.md — Сервисы и модели (3.2): merge services+models, очистка мёртвых полей (Wave 3)
- [ ] 42-07-PLAN.md — Подсистема ESP32 (3.3) + Диагностика (5.x) + миграция inlineList (Wave 3)
- [ ] 42-08-PLAN.md — Удаление мёртвого кода: scene/tuning/prompts/settings + чистка ROUTES (Wave 4)

---

## Direction: Flora Coexistence — логика сосуществования анимаций (обновление Phase 36)

Пункт 5 запроса пользователя (2026-06-11): "продумать логику сосуществования и корректного выполнения задаваемых подсознанием режимов анимации и уже существующих."

Это уточнение к Phase 36-04 (Flora P2 priority system) и 36-06 (flora emotion presets). Находки агента по этой теме будут интегрированы как детализация плана 36-04 и документ coexistence spec.

**Research findings (2026-06-11, Agent D — flora coexistence):**
- FloraController — pure event consumer, **нет priority tracking, нет current_preset, нет P2/P3**. "Last writer wins" сейчас НЕ проблема в single-path архитектуре — но станет проблемой как только добавить P2 без приоритетов
- Один turn = 6 flora transitions: `accent(220ms)` → `attentive` → `think_pulse` → `external+RMS_stream` → `breathe` → P2_restore
- `_consume()` — последовательная обработка: `wake_word_detected` спит 220ms и БЛОКИРУЕТ очередь → `voice_state_change(to=listening)` выполняется ровно в t+220ms. Это правильное поведение, не race condition
- `tts_finished → breathe` уже имеет R2 guard (`_on_answer_end` не пушит breathe если `_answer_active=False` — barge-in уже сбросил)
- **Priority design** (IntEnum): `P1_BARGE_IN=3` (аварийный, уже реализован), `P3_PIPELINE=2` (все текущие пресеты), `P2_SUBCONSCIOUS=1` (новый, AIIM emotion)
- **P3 → P2 restoration**: немедленно, без holdout. crossfade_ms=200ms обеспечивает плавность. `breathe` = transitional state — P3 ставит, P2 сразу заменяет
- **P2 pending**: сигнал НЕ теряется при P3 override → сохраняется в `_p2_preset/_p2_params` → восстанавливается в `_restore_p2()` после P3
- `push_preset_p2_emotion()` вызывается из Orchestrator как `create_task(...)` (non-blocking) — не блокирует dialogue pipeline
- **Firmware dependency**: `jitter`, `attackMs`, vibro mode strings (`"soft"/"medium"/"intense"/"sync"`) требуют firmware изменений. `curious_a/b`, `warm_a`, `calm_a/b` — работают без firmware changes
- Реализация: ~120 строк в 2 файлах + Config.json
- Полный дизайн: `.planning/research/flora_coexistence.md`

---

## Backlog (неспланированные задачи)

> Сырые идеи и задачи из [ToDo.md](../ToDo.md). Когда задача готова к планированию — переезжает сюда как Phase N с требованиями.

### Режим «Разговор с создателем» (creator_conversation personality preset)

**Решение 2026-06-12:** Система имеет два художественных режима работы — «Выставочный» (exhibition)
и «Разговор с создателем» (creator_conversation). В текущей ветке SmartFlora разрабатывается
только **exhibition**. Creator_conversation — в бэклоге до окончания выставочной фазы.

**Что это такое:**
Не технический `agent.mode` (тот остаётся `exhibition`/`maintenance` в Config.json).
Это `personality_preset` в `Agent-Adam-Chip/iAdam.json` — набор overrides AIIM-весов и параметров
поведения для конкретного сценария взаимодействия.

**exhibition_public** (разрабатывается сейчас): Публичная выставка, незнакомые зрители. Ядро se=0.92/co=0.88 без изменений. Default emotion: curious. Decay к curious быстрый.

**creator_conversation** (бэклог): Диалог наедине с создателем; высокий доверительный контекст. Ядро не меняется, но порог warm ниже, calm глубже. Decay медленнее, hysteresis выше. Специфические intention_triggers (candor, reflection). Возможна другая flora emotion map.

**До планирования:** нужно определить точный набор overrides и тестовые сценарии диалога.

### Memory Wave 2: Neural search

Заменить TF-IDF векторизацию в `FaissEpisodeIndex` на llama.cpp `/embeddings` endpoint.
Условие запуска: VRAM ≥ 4 GB свободно при работающем Gemma 4 E4B (Q4_K_XL ≈ 8 GB → остаток ~8 GB на Jetson 16 GB).
Интерфейс не меняется (`.build()` / `.search()` / `.save()` / `.load()`), только векторизация.

### wake_word_required: maintenance-mode bypass не реализован

`Config.schema.json` (`services.asr.wake_word_required`) и описание `agent.mode="maintenance"` подразумевают,
что в maintenance режиме ASR не требует wake word "адам" перед активацией.
Фактически в `Orchestrator.py` (voice loop, ~line 1324) переход STANDBY→LISTENING гейтится только
`self.wake_word_required` (из `services.asr.wake_word_required`) — проверки `agent.mode` там нет.
То есть при `wake_word_required=true` wake word требуется даже в maintenance.

Не баг, мешающий текущей работе (OWW буфер уже переведён на post-DSP audio, см. Phase audio fix),
но расходится с документацией. Решение отложено пользователем — реализовать отдельной задачей:
либо добавить явный bypass по `agent.mode=="maintenance"`, либо обновить
`Config.schema.json`, убрав упоминание автоматического bypass (выбрать одно — Config-First, без дублей).

### Config.json: мёртвая секция `tuning.*` — дубликат Agent-Adam-Chip/Tuning.json

Расследование 2026-06-12 (запрос «изучи legacy»): `System/Config.json` и `System/Config.schema.json`
содержат верхнеуровневую секцию `tuning` (memory/echoes/chinese/session/scene_director/llm/voice/
audio_input/prompt/diagnostics — ~800 строк схемы), с комментарием в schema "merged here so
Config.json is the single source of truth, previously lived in Agent-Adam-Chip/Tuning.json".

Фактически это **не так**: `System/adam/tuning.py` (`DEFAULT_TUNING_PATH`, `TuningStore`) и
`Orchestrator.py` (`tuning_store = get_store()`) читают/пишут **только** `Agent-Adam-Chip/Tuning.json` —
это реальный hot-reload backing store для `/api/tuning` (WebUI tuning panel), и он жив, активно
редактируется. Секция `Config.json.tuning.*` была дубликатом, который НИКТО не читал — grep по
`section("tuning")` нашёл только два места (Orchestrator.py post-TTS lag diag + `/api/diag/lag/toggle`),
которые в этой сессии переведены на `tuning_store` (теперь единый источник для `diagnostics.trace_post_tts_lag`).

`System/adam/CLAUDE.md` тоже содержал ложное утверждение "Tuning.json удалён в V-S07.2, заменён
Config.json.tuning" — исправлено в этой сессии на описание реального устройства.

**Выполнено 2026-06-12 (подтверждение получено):**
Секция `tuning` удалена из `System/Config.json` (744→358 строк) и `System/Config.schema.json`
(2445→1617 строк) через Python json.load/dump, валидность подтверждена. Grep `section("tuning")` —
ноль обращений. `System/Config.json` теперь содержит только runtime-параметры инфраструктуры.

---

### Phase 7AA: Branch Merge — Identity_Tunning → dynamic-aiim ✅ ЗАВЕРШЕНА (2026-06-07)

**Цель:** Влить накопленные изменения ветки `Identity_Tunning` в `dynamic-aiim` до мёржа в `main`.
Без этого dynamic-aiim теряет: исправления персоны, путей, камеры, warmup-fix и systemd.

**Анализ diff (2026-06-07):** Identity_Tunning опережает dynamic-aiim на 20+ коммитов.
Не всё можно взять напрямую — три жёстких конфликта требуют явных решений.

**Конфликт 1 — Директория персоны (жёсткий):**
Identity_Tunning переименовала `Agent Adam Chip/` (пробел) → `Agent-Adam-Chip/` (дефис).
Dynamic-aiim использует пробел везде: Config.json, config.py, BRANCH.md, Orchestrator.py.
Решение перед мёржем: выбрать одно имя и зафиксировать.

- Дефис безопаснее на Linux (shell-safe), пробел — текущее состояние dynamic-aiim и Config.json.
- Рекомендация: перейти на дефис в dynamic-aiim до мёржа (`git mv`), обновить все ссылки.

**Конфликт 2 — Tuning store (жёсткий):**
Identity_Tunning: `tuning.py` читает из `Config.json` (single source of truth, `Settings`).
Dynamic-aiim: `tuning.py` читает из `Tuning.json` (отдельный hot-reload файл, `TuningStore`).
Это фундаментальные разные архитектуры бэкенда — Git не разрешит автоматически.
Решение перед мёржем: выбрать архитектуру-победителя.

- `Tuning.json` сохраняет hot-reload и отделяет persona-параметры от инфраструктуры.
- `Config.json` даёт single source, но теряет возможность reload без рестарта оркестратора.
- Рекомендация: оставить `Tuning.json` (dynamic-aiim wins), перенести туда патчи Identity_Tunning.

**Конфликт 3 — Orchestrator.py (разрешимый вручную):**
Identity_Tunning добавила: skip warmup TTS, camera dual-path OV5640/OV7670.
Dynamic-aiim добавила: полный AIIM wiring per-turn.
Обе стороны правы, конфликт в разных местах файла — merge по секциям.

**Безопасный cherry-pick (без конфликтов с AIIM):**

| Что | Откуда | Риск |
| --- | --- | --- |
| Persona text: Lore.md, Abilities.md, Echoes.md | Identity_Tunning | низкий |
| `fix(persona)`: Главное правило, AI-deflection, голос | Identity_Tunning | низкий |
| Camera dual-path OV5640/OV7670 | Identity_Tunning | низкий |
| Systemd: VLM autostart, ASR model=small | Identity_Tunning | низкий |
| Skip warmup TTS fix | Identity_Tunning | низкий |
| Path fixes Config.json / config.py | Identity_Tunning | средний (зависит от решения по директории) |
| `.planning/phases/07..15` (документация) | Identity_Tunning | низкий |

**Что НЕ брать из Identity_Tunning:**

- `tuning.py` целиком (конфликт архитектуры)
- `Agent Adam Chip/Tuning.json` DELETE (в dynamic-aiim этот файл критичен)
- `Agent-Adam-Chip/About/Identity.md` — берём только text-патчи поверх текущей (AIIM-формула уже там)

**Порядок операций:**

1. Создать рабочую ветку от dynamic-aiim
2. Решить конфликт директории (`git mv` если переходим на дефис)
3. Cherry-pick безопасных коммитов (persona, camera, systemd, warmup)
4. Вручную перенести text-патчи из Lore.md / System.md Identity_Tunning
5. Разрешить Orchestrator.py вручную (skip warmup + AIIM wiring вместе)
6. Обновить BRANCH.md: добавить Identity_Tunning в "Includes from"
7. Прогнать `pytest tests/` — все 29+34 тестов должны остаться зелёными

**Затрагивает:** `Agent Adam Chip/About/*`, `System/Config.json`, `System/adam/config.py`,
`System/Orchestrator.py`, `Subsystem/AdamsServer/src/camera/*`, `deploy/systemd/*`, `BRANCH.md`

**Результат (2026-06-07):** Мёрж выполнен. `Agent-Adam-Chip/` (дефис) — единственная директория персоны.
Config.json persona_paths обновлены. Persona text patches применены. Конфликты разрешены:
tuning.py и Tuning.json — dynamic-aiim wins; Orchestrator.py — auto-merge (warmup skip + AIIM wiring совместимы).
29/29 тестов зелёные. Warmup skip fix, camera dual-path, VLM autostart — все из Identity_Tunning.

**Приоритет:** Выполнить ДО Phase 7A — 7A работает на стабилизированной ветке.

---

### Phase 7A: AIIM Mechanic Fixes — починить без смены парадигмы

**Предпосылка:** Критический анализ (2026-06-07) выявил что механизм работает не так как задуман.
Это направление устраняет конкретные механические дефекты, не меняя общую архитектуру keyword→emotion→ctx.

**Решения (зафиксированы 2026-06-07):**

- Default emotion → **`curious`** ✅ применён (Identity.md исправлен: "любопытство (по умолчанию)")
- Канонический AIIM-профиль → **`Identity.md`** (lo=Δ0.70, Ac-Or — "открытый, идёт к людям")
- `Personality_AIIM.md` → пометить как `[ARCHIVED — superseded by Identity.md]` (ещё не сделано)

**Выполнено (2026-06-07) в рамках первичного патча:**

- ✅ **Salience заглушка:** `acc.finalize()` перемещён перед drift-блоком; drift использует `episode.salience`
- ✅ **Нет внутрисессионного накопления:** `AspectModulator` теперь стартует с `aiim_state.vector` (предыдущий turn), не с `_base_vector`; modulation накапливается внутри сессии
- ✅ **`classify_session` вызывается дважды:** кешируется в `session_type`, вызывается один раз
- ✅ **`_UNREADABLE_PATTERNS` захардкожен:** убраны hardcoded regex; `become_unreadable` читает keywords из `tuning.intention_triggers` (конфигурируется в Tuning.json)

**Остаток к реализации:**

- **`warm` заблокирован для новых зрителей:** зависит от `acc.tone_visitor` (эпизодическая память) — нужен inline tone-detector из transcript (длина + вопросительные конструкции + тематические слова)
- **Однонаправленный drift:** аспекты только растут к потолку; нужны деградационные дельты для `void` (lo убывает, at убывает)
- **Два мёртвых флага:** `signal_void` и `become_unreadable` трекируются, но behavioural consequence не реализовано
- **Formula Ac vs Pa игнорируется:** `Or vs Ch` не используются в `AspectModulator`; `Ac-Ch` аспекты должны модулироваться иначе чем `Pa-Or`
- **`Personality_AIIM.md`** → пометить `[ARCHIVED]`

**Затрагивает:** `identity.py`, `identity_drift.py`, `tuning.py`, `Orchestrator.py` (session close), `Agent-Adam-Chip/Engineering/Personality_AIIM.md`

**Условие запуска:** 7AA завершена (ветка стабилизирована). Тесты зелёные. Полный деплой на Jetson перед merge в main.

---

### Phase 7B: AIIM Label Enrichment — обогатить метки, не заменять

**Решение (зафиксировано 2026-06-07):** Остаёмся на метках (`emotion=X`), не переходим на нарратив.
Метки логируемы, тестируемы, предсказуемы. Задача — сделать их максимально эффективными.

**Предпосылка:** Текущие метки (`emotion=unease`) терсы и опаки для LLM. Семантический вес
слова "unease" есть в весах модели, но он не привязан к конкретным речевым паттернам Адама.
Направление добавляет к меткам: семантический контекст (что именно происходит), поведенческий
hint (что меняется в речи), и систему проверки что метки реально работают.

**Концепция обогащённых меток:**

```text
[ctx.identity]
emotion=unease|src=memory       ← что спровоцировало
me=0.38↑                        ← дрейфующий аспект со стрелкой направления
intention=relive_death          ← только injectable-интенции
```

- `src=` — источник эмоции: `memory`, `challenge`, `contact`, `decay`
- Аспекты показываются как `code=value↑` / `↓` вместо голого числа
- `System.md` [ctx.identity]-инструкция расписывается на 5 пунктов — по одному на каждую эмоцию: конкретные речевые следствия, не абстрактное "интерпретируй"

**A/B тест-план:**

- **Версия A (baseline):** текущий формат `emotion=unease`
- **Версия B:** обогащённый формат `emotion=unease|src=memory` + направление аспектов
- **Метрики:** (1) echo-rate — процент ответов с утечкой меток; (2) emotion-alignment — совпадение задуманной и наблюдаемой эмоции по оценке судьи; (3) token overhead — разница в длине ctx-блока
- **Объём:** ≥30 диалоговых turn'ов на версию, два оценщика (человек + LLM-judge)
- **Инструментация:** лог `turn_id → identity_block_used → judge_score` в `drift_log.jsonl`

**Затрагивает:** `identity.py` (to_ctx_block, src-аннотация), `tuning.py` (EmotionTransitionRule + src поле), `Agent-Adam-Chip/About/System.md` (расписать per-emotion инструкции), `Tuning.json`

**Условие запуска:** Phase 7A завершена; тест запускается до полной реализации 7B.

---

### Phase 7C: AIIM Autonomous Identity — эмоция не из транскрипта

**Решение (зафиксировано 2026-06-07):** Направление подтверждено.
Адам должен иметь внутренние источники состояния, независимые от слов зрителя.

**Предпосылка:** Все текущие эмоции и 4 из 5 интенций активируются только когда зритель произносит
нужные слова. Это не живая идентичность — это зеркало. Направление вводит три независимых
источника внутреннего состояния.

**Источник 1 — Физическая среда (слабые фоновые смещения):**

Новый `EnvironmentDriver` читает `sensors` dict (уже приходит в Orchestrator per-turn) и
возвращает `float bias` в диапазоне [-0.15, +0.15] для каждого возможного перехода.
EmotionMachine применяет bias к своим threshold'ам — не переопределяет, а смещает.

- `light < threshold_low` + `silence_s > 30` → bias к `calm` (+0.1)
- `datetime.hour in [22..06]` → bias к `calm` (+0.05), `curious` (-0.05)
- `sensors.presence == 0 AND turn > 0` → bias к `calm` (постепенное успокоение при уходе)
- Все пороги в `Tuning.json → identity.environment_driver`, не хардкодятся

**Источник 2 — Автономные интенции с поведенческими следствиями:**

`signal_void` (уже реализован, 3%/turn) получает consequence:

- При активации → в `to_ctx_block` добавляется `mode=void_signal` метка
- В `System.md` прописано: при `mode=void_signal` — одна реплика из "другого канала": короче, без прямого адреса к зрителю, может содержать китайскую фразу

Новая интенция `return_to_observation`:

- Вероятностная: rate_per_turn ≈ 0.04, cooldown 20 turns
- Consequence: `mode=observe` в ctx → System.md: Адам отвечает короче обычного, задаёт вопрос вместо утверждения, "слушает" а не "говорит"

**Источник 3 — Historical arc (кем становится):**

`DriftAccumulator` получает метод `extract_trend(record, base_weights) → str | None`.
Trend формируется при total_sessions кратном N (например, 10), хранится в `drift.json` как поле `trend_line`.
В `to_ctx_block` при наличии trend → добавляется как `arc=<trend_line>` (одна строка, max 60 символов).

Примеры trend_line (формируются из drift-дельт, не LLM):

- `"lo↑ глубокий контакт накапливается"` (если lo-drift > 0.05)
- `"me↑ прошлое всплывает чаще"` (если me-drift > 0.03)
- `None` если drift минимальный (не показываем)

**Ключевые ограничения:**

- `max_autonomous_shift` в Tuning.json — потолок суммарного смещения от автономных источников за один turn (дефолт 0.15)
- Автономные источники никогда не переопределяют keyword-триггер — они только модифицируют вероятности
- Все три источника независимо включаются/выключаются в Tuning.json (`environment_driver.enabled`, `autonomous_intentions.enabled`, `historical_arc.enabled`)

**Затрагивает:** `identity.py` (EmotionMachine + новый EnvironmentDriver, новые intention rules), `identity_drift.py` (extract_trend, trend_line в DriftRecord), `Orchestrator.py` (передача sensors dict в AIIM per-turn), `tuning.py` (новые модели конфига), `Tuning.json`, `Agent-Adam-Chip/About/System.md`

**Условие запуска:** Phase 7A + 7B завершены; требует дизайн-сессии по sensors-диапазонам на реальном Jetson.

---

### AIIM → Motor Layer Integration

После стабилизации Dynamic AIIM (ветка `dynamic-aiim`) — связать эмоциональное состояние
с физическим слоем (techflora, scene_director, ActionLayer).

**Концепция:** emotion=warm → плавные движения; emotion=sharp → резкий импульс → тишина;
emotion=unease → быстрые нерегулярные паттерны. SceneDirector получает `EmotionState` из
AIIM вместо текущего keyword-based `Mood`.

**Условие запуска:** Dynamic AIIM стабильно работает на Jetson ≥2 недели без ошибок в логах.

**Затрагивает:** `System/adam/action.py`, `scene_director`, `Orchestrator.py`, возможно новый `System/adam/motor_director.py`.

**Зависит от:** Phase 7A (или 7B) — Motor Layer берёт EmotionState из стабилизированного AIIM.

---

### UI: Пересборка интерфейса управления

- Перегруппировка параметров по логическим блокам: ESP (камера, mic, PCA9685, PCM5102A, сенсоры) / Agent (ASR, VLM, LLM, TTS) / Adam Identity
- Визуализация уровня громкости микрофона (эквалайзер в реальном времени)
- Настройка silence timeout для определения конца запроса пользователя
- Возможность Адаму управлять громкостью вывода

### Remote: Удалённый доступ к Jetson

- Агрегация логов каждого этапа pipeline (частично реализовано: `scripts/adam_pull_logs.py`)

### Refactor: Структурный рефакторинг

- Пересмотр структуры директорий и файлов
- Единый реестр параметров: анализ использования, перенос в Config.json, подтягивание по всей системе

---

### Proactive Speech: Спонтанная речевая инициатива

**Контекст:** система реализует проактивное *восприятие* (SceneWorker, SessionWatcher), но не проактивную *речь* — агент не инициирует голосовые высказывания без wake word.

**Суть задачи:** добавить idle-scheduler — фоновый процесс, который при выполнении условий (посетители в пространстве, тишина дольше N секунд, не во время TTS) вызывает LLM с коротким промптом-затравкой и воспроизводит ответ без wake word.

**Ключевые вопросы до планирования:**

- Пороговое условие: через сколько секунд тишины инициировать? (зависит от выставочного контекста)
- Контроль частоты: не чаще 1 раза в M минут, чтобы не «засорять» пространство
- Промпт-затравка: отдельный системный промпт или модификация основного?
- Ресурс: ~9 с на вызов LLM — приемлемо для idle-инициативы

**Связь:** критерий квазисубъектности 2.1.1 (степень автономизации) — переход с уровня 2 (контекстно-управляемый) к уровню 3 (проактивный); диплом раздел 3.3.4, метрика 3.4.4.

---

### Trigger-Word Eavesdrop: Проактивное «подслушивание» по тематическим словам

**Контекст:** текущий OWW детектирует только имя «адам» для пробуждения. Зрители говорят между собой — агент не реагирует, даже если разговор касается тем, близких персонажу.

**Суть задачи:** загрузить в OWW пул тематических ONNX-моделей (слова-триггеры: «технофлора», «агент», «ии», «симбиоз» и др.). При детекции любого из них Voice Loop переходит в режим **eavesdrop** — ASR начинает слушать без wake word, накапливая контекст разговора. Через N секунд (или по детекции паузы) агент с вероятностью P принимает решение «встрять» и генерирует реплику-вставку от персонажа.

**Ключевые вопросы до планирования:**

- Словарь триггеров: фиксированный список в Config или hot-reload из Tuning.json?
- Порог вхождения в eavesdrop vs порог реакции wake word (разные sensitivity)?
- Накопление контекста: сколько секунд ASR пишет фоном до решения о вставке?
- Вероятностная модуляция: P зависит от AIIM-аспектов (высокий `im` → выше шанс встрять)?
- Отдельный промпт-затравка для eavesdrop-реплики или модификация основного?
- Соблюдение `half_duplex_mute` и rate-limit чтобы не превратиться в шум

**Связь:** дополняет Phase 19 (idle-scheduler) и Phase 23 (дельта-реакция на сцену) — три независимых слоя проактивности. Тематический триггер — наиболее «персонажный» слой: Адам реагирует не на тишину и не на движение, а на смысл разговора вокруг него.

### Phase 29: ESP Audio Output — TTS DSP chain (HPF, compressor, limiter, soxr resample) for loudness and quality on ESP MAX98357A speakers

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 28
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 29 to break down)

---

### AIIM Dynamic: Рефлексивный уровень идентичности

**Контекст:** частично реализуется в ветке `dynamic-aiim`. AIIM-модель предусматривает автоматическое изменение «уровней зрелости» аспектов на основе опыта, но в текущей реализации параметры `Tuning.json` меняются только вручную.

**Суть задачи:** после каждой сессии консолидатор (или отдельный модуль) анализирует паттерны взаимодействия и корректирует параметры Tuning.json — например, снижает `drive` при частых отказах от диалога, повышает `verbosity` при длинных сессиях.

**Ключевые вопросы до планирования:**

- Какие параметры Tuning.json поддаются автокоррекции (не все)?
- Как предотвратить дрейф в нежелательную сторону (ограничения на magnitude изменений)?
- Частота обновления: после каждой сессии или ежедневно через consolidator?

**Связь:** критерий квазисубъектности 2.1.3 (устойчивость идентичности, рефлексивный уровень); AIIM [53]; диплом раздел 3.4.5 «Направления дальнейшего развития».
