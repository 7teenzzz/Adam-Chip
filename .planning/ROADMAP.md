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

## Phase 7: Comprehensive Diploma Analysis

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

## Phase 8: Theory-Code Verification

**Branch:** `diploma-chapter3` (анализ остаётся в дипломной ветке)

**Goal:** Для каждого теоретического концепта диплома найти runtime-evidence в коде и классифицировать соответствие. Расширить начатый `diploma/ANALYSIS-THEORY-vs-CODE.md` на все 4 главы.

**Requires:** Phase 7 завершена

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

## Phase 9: Next-Phases Planning

**Branch:** `diploma-chapter3`

**Goal:** На основе аудита диплома (Ф7) и матрицы соответствия (Ф8) сформировать конкретные технические фазы для следующих волн разработки. Привязать их к активным веткам.

**Requires:** Phases 7, 8 завершены

**Delivers:**

- `CANDIDATES.md` — длинный список потенциальных фаз из Ф7+Ф8
- `09-PRIORITIZATION.md` — матрица impact × effort × strategic value
- `09-PHASE-DRAFTS.md` — phase drafts для топ-5-8 кандидатов в формате (Goal / Delivers / Requires / Mode)
- Интеграция с активными ветками:
  - `Memory-upgrade` → Phase 10C: Memory Wave 2 (Neural search)
  - `dynamic-aiim` → Phase 10F: AIIM Dynamic (рефлексивный уровень)
  - `VLM-upgrade` → Phase 10G: Vision Upgrade
  - `Identity-tuning` → Phase 10H: Identity Calibration
- `09-SUMMARY.md` — итог: 5-8 рекомендуемых фаз для добавления в Roadmap

**Mode:** standard

---

## Phase 10: Roadmap Global Update

**Branch:** `diploma-chapter3` (изменения в `.planning/` остаются в дипломной ветке до мёржа)

**Goal:** Обновить ROADMAP.md и REQUIREMENTS.md с глобальной картой будущих фаз; добавить milestone-структуру; привязать активные ветки к фазам.

**Requires:** Phase 9 завершена

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

## Phase 12: Metrics & Evaluation Framework

**Branch:** новая (`metrics-framework`) — создаётся после стабилизации основных веток

**Goal:** Реализовать автоматический сбор и расчёт метрик качества работы агента, заявленных в дипломе (3.4): RAS, RDI, NVR, RI, CRS, LMRR, SCS, SIAR. Закрывает диплом-задачи №3 (формализация критериев устойчивости роли) и №6 (демонстрация в реальном времени + оценка).

**Requires:**
- Стабилизация активных веток: `Memory-upgrade`, `Identity-tuning`, `VLM-upgrade`, `dynamic-aiim` → merged in main
- Phase 11 (AIIM Dynamic) завершена — без рефлексивного цикла часть метрик (RDI, CRS) не имеет источника данных

**Delivers:**

- `System/adam/evaluation/` — новый пакет с модулями расчёта метрик
- `scripts/export_turns_for_markup.py` — экспорт turn'ов с pre-filled данными для экспертной разметки
- `data/adam/eval/` — корпус разметки + результаты автоматического расчёта
- Метрики:
  - **RAS** (Role Adherence Score) — экспертная + автоматическая компонента (lexical analysis ответов)
  - **RDI** (Role Drift Index) — на основе истории сессий (требует Phase 11)
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

**Связь с Phase 7 находками:** закрывает T-02 (метрики как honesty-проблема), задачи №3 и №6 из ch00

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

### AIIM Dynamic: Рефлексивный уровень идентичности

**Контекст:** частично реализуется в ветке `dynamic-aiim`. AIIM-модель предусматривает автоматическое изменение «уровней зрелости» аспектов на основе опыта, но в текущей реализации параметры `Tuning.json` меняются только вручную.

**Суть задачи:** после каждой сессии консолидатор (или отдельный модуль) анализирует паттерны взаимодействия и корректирует параметры Tuning.json — например, снижает `drive` при частых отказах от диалога, повышает `verbosity` при длинных сессиях.

**Ключевые вопросы до планирования:**
- Какие параметры Tuning.json поддаются автокоррекции (не все)?
- Как предотвратить дрейф в нежелательную сторону (ограничения на magnitude изменений)?
- Частота обновления: после каждой сессии или ежедневно через consolidator?

**Связь:** критерий квазисубъектности 2.1.3 (устойчивость идентичности, рефлексивный уровень); AIIM [53]; диплом раздел 3.4.5 «Направления дальнейшего развития».
