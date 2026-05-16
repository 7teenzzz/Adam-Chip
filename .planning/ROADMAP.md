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
- `Agent Adam Chip/CLAUDE.md` — порядок загрузки персоны, правила редактирования
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

**Requirements:** REQ-NO-HANG-AFTER-REPLY, REQ-NO-SELF-ECHO-VAD, REQ-DIAGNOSTIC-DUMP-ON-DEMAND (TBD при /gsd-discuss-phase 8)

---

## Backlog (неспланированные задачи)

> Сырые идеи и задачи из [ToDo.md](../ToDo.md). Когда задача готова к планированию — переезжает сюда как Phase N с требованиями.

### Memory Wave 2: Neural search

Заменить TF-IDF векторизацию в `FaissEpisodeIndex` на llama.cpp `/embeddings` endpoint.
Условие запуска: VRAM ≥ 4 GB свободно при работающем Gemma 4 E4B (Q4_K_XL ≈ 8 GB → остаток ~8 GB на Jetson 16 GB).
Интерфейс не меняется (`.build()` / `.search()` / `.save()` / `.load()`), только векторизация.

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
