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

**Requirements:** PLAN9-01, PLAN9-02, PLAN9-03, PLAN9-04, PLAN9-05, PLAN9-06, PLAN9-07, PLAN9-08, PLAN9-09, PLAN9-10

**Plans:** 4 plans

**Completed:** 2026-05-17 (13 фаз спроектированы, 32 REQUIREMENTS-IDs, dependency graph, 4 артефакта)

Plans:
- [x] 09-01-PLAN.md — CANDIDATES.md: реестр ~13 кандидатов из Ф8 §4.1 + Backlog + активных веток
- [x] 09-02-PLAN.md — 09-PRIORITIZATION.md: матрица 4 критериев (Impact/Effort/Strategic/Exhibition) + P0–P3 группы
- [x] 09-03-PLAN.md — 09-PHASE-DRAFTS.md: полные ROADMAP-style drafts для P0 (10A/10B/11) + компактные для P1–P3
- [x] 09-04-PLAN.md — 09-SUMMARY.md: финальные рекомендации для Phase 10 (что копировать + открытые вопросы + milestone-предложение)

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

## Phase 10A: Diploma Convergence Pass

**Branch:** `diploma-chapter3` (existing — текущая ветка, продолжение)

**Goal:** Применить все оставшиеся текстовые правки диплома из Phase 8 (4 A-path + 7 C-path + 10 оставшихся EMERGENT), финализировать диплом и подготовить ветку `diploma-chapter3` к мёржу в `main`.

**Requires:**
- Phase 8 завершена ✓ (08-SUMMARY.md создан, топ-3 EMERGENT применены)
- Phase 9 завершена ✓ (09-SUMMARY.md создан)

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

## Phase 10B: Config-First Refactor

**Branch:** `config-refactor` (new — создаётся при старте фазы)

**Goal:** Вынести все хардкодированные числовые параметры в `Config.json` / `Config.schema.json` и устранить BUG F-07 (рассинхронизацию `history_turns=2` vs `limit=8`), закрыв Pattern 4 из Phase 8.

**Requires:**
- Phase 8 завершена ✓ (F-07 BUG, Τ-30/31/36 задокументированы)
- Не блокируется другими фазами (независима)

**Delivers:**
- Новый Config-ключ `agent.session_turn_limit` (limit=8 из `prompt.py` → Config) — устраняет Τ-30
- Новый Config-ключ `memory.episodic_decay_days` (14d из `episodic.py` → Config) — устраняет Τ-31
- Новый Config-ключ `memory.salience_weights` (dict из `episodic.py` → Config) — устраняет Τ-36
- Два явных ключа вместо рассинхрона: `agent.prompt_history_limit` (=8) и `agent.context_history_turns` (=2) — устраняет F-07
- Обновлённые `System/Config.json` и `System/Config.schema.json` с descriptions
- Рефакторинг `prompt.py`, `episodic.py`, `Engineering/consolidator.py` (чтение из конфига)
- Unit-тесты для каждого нового Config-ключа (с env-override `ADAM_CONFIG_OVERRIDE`)
- Разблокирует Phase 16 (UI Rebuild) и Phase 18 (Structural Refactor)

**Requirements:** CFG-01, CFG-02, CFG-03, CFG-04

**Mode:** standard | **Priority:** P0

---

## Phase 11: AIIM Dynamic — Рефлексивный уровень идентичности

**Branch:** `dynamic-aiim` (existing)

**Goal:** После каждой сессии консолидатор анализирует паттерны взаимодействия и автоматически корректирует параметры `Tuning.json` (drive, verbosity, доминирующие аспекты) в пределах заданных magnitude limits, реализуя рефлексивный уровень AIIM.

**Requires:**
- Phase 13 (Memory Consolidation) — желательно; integration hook требует работающего consolidator (можно вести параллельно)
- Phase 10A (Diploma Convergence Pass) — согласование diploma-side описания AIIM Dynamic (DIPL-10)

**Delivers:**
- Новый модуль `System/adam/aiim_reflection.py` с функцией `adjust_tuning(session_summary, current_tuning) -> dict`
- Whitelist параметров для автокоррекции в `Config.json::aiim.adjustable_params` (drive, verbosity, aspect_weights)
- Magnitude limits per parameter в `Config.json::aiim.magnitude_limits` — защита от дрейфа
- Интеграция в consolidator hook: после каждой консолидации вызывается `aiim_reflection.adjust_tuning`
- API endpoint `GET /api/agent/aiim/last-adjustment` — последнее корректирующее воздействие с delta и timestamp
- Регрессионный тест: суммарный дрейф параметров за N сессий ≤ magnitude_limit
- Разблокирует Phase 12 (RDI metric source — рефлексивный уровень даёт данные для метрики)

**Requirements:** AIIM-01, AIIM-02, AIIM-03, AIIM-04

**Mode:** standard | **Priority:** P0

---

## Phase 13: Memory Consolidation

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
- Разблокирует Phase 12 (LMRR metric source), Phase 15 (prereq), Phase 19 (context history)

**Requirements:** MEM-01, MEM-02, MEM-03

**Mode:** standard | **Priority:** P1 | **Net-unlock: 3 фазы**

---

## Phase 21: Identity Calibration Финализация

**Branch:** `Identity-tuning` (existing)

**Goal:** Завершить разработку в `Identity-tuning` (Φ-13 path C, Α-24 path A, калибровка 5 mood-состояний) и выполнить merge в `main`.

**Requires:**
- Phase 10A (Diploma Convergence Pass) — согласование diploma-side правок Α-24 и Φ-13

**Delivers:**
- Финализация кода в ветке `Identity-tuning` (Φ-13 path C параграф + Α-24 mood калибровка)
- Code review пройден (`/gsd-code-review`)
- Merge `Identity-tuning` → `main` выполнен
- Регрессионный тест диалогового pipeline после мёржа (тон и поведение агента)
- Согласованность Φ-13 path C параграфа (diploma) с Identity.md изменениями

**Requirements:** ID-01, ID-02, ID-03

**Mode:** standard | **Priority:** P1 | **Effort:** L (code review + merge)

---

## Phase 14: Mood LLM-driven

**Branch:** `mood-llm` (new — создаётся при старте фазы)

**Goal:** Доработать `action.py` для парсинга явных mood-маркеров из LLM-ответа вместо текущего keyword matching по `reply_text`.

**Requires:**
- Независима (улучшает NVR метрику Phase 12)

**Delivers:**
- Доработка `action.py`: парсинг явных mood-маркеров из структуры LLM-ответа (не keyword matching)
- Обновлённый системный промпт: шаблон для генерации mood-маркеров в формате, парсируемом action.py
- A/B тест: сравнение качества mood detection (keyword vs LLM-маркеры)
- Тесты для нового парсера

**Requirements:** MOOD-01, MOOD-02

**Mode:** standard | **Priority:** P2 | **Риск:** изменение промпта влияет на качество ответов — A/B тест обязателен

---

## Phase 15: Memory Wave 2 (Neural Search)

**Branch:** `Memory-upgrade` (existing, Wave 2)

**Goal:** Заменить TF-IDF векторизацию в `FaissEpisodeIndex` на llama.cpp `/embeddings` endpoint для семантического поиска по эпизодической памяти.

**Requires:**
- Phase 13 (Memory Consolidation) завершена — prereq
- Свободная VRAM ≥ 4 GB при работающем Gemma 4 E4B

**Delivers:**
- Замена TF-IDF → llama.cpp `/embeddings` в `FaissEpisodeIndex` (интерфейс `.build()/.search()/.save()/.load()` не меняется)
- VRAM check при запуске Wave 2 (≥4 GB свободной VRAM при работающем LLM)
- Тесты семантического поиска (релевантность vs keyword matching)
- Обновлённый `memory_search.py` с embeddings backend

**Requirements:** MEMN-01, MEMN-02

**Mode:** standard | **Priority:** P2

---

## Phase 17: Remote Access

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

## Phase 20: VLM Upgrade Финализация

**Branch:** `VLM-upgrade` (existing)

**Goal:** Завершить разработку в ветке `VLM-upgrade` и выполнить merge в `main`.

**Requires:**
- Независима (Phase 8 не выявила блокеров)

**Delivers:**
- Финализация кода в ветке `VLM-upgrade`
- Code review пройден (`/gsd-code-review`)
- Merge `VLM-upgrade` → `main` выполнен
- Регрессионный тест: scene_worker_enabled, scene_interval_sec, scene_stale_after_sec корректно читаются из Config.json
- После мёржа Phase 15 может использовать VLM embeddings

**Requirements:** VLM-01, VLM-02

**Mode:** standard | **Priority:** P2 | **Effort:** L (code review + merge)

---

## Phase 19: Proactive Speech

**Branch:** `proactive-speech` (new — создаётся при старте фазы)

**Goal:** Добавить idle-scheduler — фоновый процесс, который при наличии посетителей и тишине дольше N секунд вызывает LLM с промптом-затравкой и воспроизводит ответ без wake word.

**Requires:**
- Phase 13 (Memory Consolidation) завершена — контекст истории сессий

**Delivers:**
- idle-scheduler в Orchestrator: при тишине > N секунд и наличии посетителей (VLM engagement) вызывать LLM
- Промпт-затравка для спонтанных реплик (без wake word) — отдельный системный промпт в Config или Tuning.json
- Rate limiter (не чаще M минут) + соблюдение half_duplex_mute инварианта (idle не перекрывает активный диалог)
- Config-параметры: `proactive.idle_threshold_sec`, `proactive.rate_limit_min`, `proactive.enabled`
- Связана с Phase 12 SIAR метрика (Spontaneous Initiative Activity Ratio)

**Requirements:** PROAC-01, PROAC-02, PROAC-03

**Mode:** standard | **Priority:** P2 | **Exhibition:** H — высокая ценность для выставки

---

## Phase 16: UI Rebuild

**Branch:** `ui-rebuild` (new — создаётся при старте фазы)

**Goal:** Пересобрать операторский веб-интерфейс (`:8080`) с перегруппировкой параметров по доменным блокам (ESP / Agent / Identity), визуализацией уровня микрофона, настройкой silence timeout и управлением громкостью.

**Requires:**
- Phase 10B (Config-First Refactor) завершена — параметры должны быть в Config.json до UI-привязки

**Delivers:**
- Перегруппировка операторского UI по доменным блокам: ESP (камера/mic/PCA9685/PCM5102A), Agent (ASR/VLM/LLM/TTS), Adam Identity
- Real-time визуализация уровня микрофона (mic эквалайзер / VU-meter)
- Настройка silence timeout (command_endpointing_ms, reply_window_sec) через UI без рестарта
- Управление громкостью TTS (output device volume) через UI
- **Open question:** поднять до P2 если дата выставки близко (см. [09-PRIORITIZATION.md R-03](phases/09-next-phases-planning/09-PRIORITIZATION.md))

**Requirements:** UI-01, UI-02, UI-03, UI-04

**Mode:** standard | **Priority:** P3

---

## Phase 18: Structural Refactor

**Branch:** `refactor` (new — создаётся при старте фазы, требует feature-freeze)

**Goal:** Провести структурный рефакторинг кодовой базы: пересмотр директорий `System/`, `Subsystem/`, `Engineering/`, единый реестр параметров и глубокий Config-аудит поверх Phase 10B.

**Requires:**
- Phase 10B (Config-First Refactor) завершена и смёржена
- Feature-freeze других веток на время рефакторинга

**Delivers:**
- Единый реестр всех параметров системы (глубокий аудит поверх Phase 10B — второй слой параметров)
- Пересмотр директорной структуры `System/`, `Subsystem/`, `Engineering/` — логическая группировка по доменам
- Все тесты зелёные после рефакторинга
- systemd units проверены и обновлены под новую структуру (если нужно)

**Requirements:** REF-01, REF-02

**Mode:** standard | **Priority:** P3 | **Риск:** H — масштабный рефакторинг; необходим feature-freeze

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

## Phase 22: AIIM Core Runtime — структурированные аспекты в коде

**Branch:** `aiim-core-runtime` (new — создаётся при старте фазы)

**Goal:** Перевести AIIM из чисто текстовой семантики (`Identity.md` в системном промпте) в структурированную runtime-конфигурацию: 12 аспектов сознания с уровнями, состояниями и Δ-приоритетами должны жить как валидируемая структура в `Tuning.json`, читаться при каждом цикле и модулироваться правиловым или модельным контуром. Закрывает гэп между текстом ch3 §3.2.3 диплома и фактической реализацией.

**Requires:**
- Phase 10A (Diploma Convergence Pass) завершена ✓ — текст ch3 §3.2.3 финализирован
- Независима от Phase 11 (Phase 11 — рефлексивный уровень, Phase 22 — конфигурационный + динамический уровни)

**Delivers:**
- Pydantic-модель `AIIMTuning` в `tuning.py`: 12 аспектов (co, se, sp, im, pe, at, be, wi, lo, ho, em, me), каждый — уровень (B/P/S/T/I), состояние (Ac-Or / Ac-Ch / Pa-Or / Pa-Ch), Δ-вес [0..1]
- Парсер `Identity.md` → `Tuning.json::aiim` при первом запуске (если секция `aiim` ещё не создана)
- Модуль `System/adam/aiim.py` с правиловым контуром Δ-сдвигов: эмпатичный ввод → +Δ для `lo` и `em`, ироничный → +Δ для `im`, попытка вытащить из персонажа → +Δ для `ho`
- Коридор Δ-сдвигов ±0.15 от базы `Identity.md`: за пределами — параметр клампится
- Параметр `services.action.mood_source` ∈ {`rules`, `slm`, `llm_self_tag`} в `Config.json` и `Config.schema.json`; в первой итерации реализуется только `rules`, остальные — заглушки с TODO
- Связь `aiim.py` → `action.py`: выбор тега `Mood` опирается на доминирующий аспект в текущем срезе `Tuning.json::aiim`, а не на keyword matching по тексту ответа
- Hot-reload через `TuningStore` без кеширования (читается каждый цикл) — уже есть в `tuning.py`, нужно добавить аспекты в pydantic-схему
- Регрессионный тест: после серии эмпатичных обращений `lo` сдвинут на +0.10 ± 0.02, выбор `Mood` смещён к `warm`
- Разблокирует: Phase 11 (рефлексивный уровень), Phase 14 (mood LLM-driven как режим `mood_source: llm_self_tag`), Phase 12 (RDI метрика на основе Δ-сдвигов)

**Requirements:** AIIM-CORE-01 (структура), AIIM-CORE-02 (парсер Identity), AIIM-CORE-03 (Δ-логика правиловая), AIIM-CORE-04 (mood_source), AIIM-CORE-05 (связь с action)

**Mode:** standard (полный GSD-цикл) | **Priority:** P0 | **Effort:** XL (3–4 недели)

**Связь с диплом-расхождениями (gap T3 в `ANALYSIS-THEORY-vs-CODE.md`):** закрывает заявку текста ch3 §3.2.3 на структурированные AIIM-аспекты, Δ-коридор и переключатель `mood_source`. После завершения Phase 22 + Phase 11 текст ch3 §3.2.3 и §3.2.6 становится полностью соответствующим коду.

---

## Phase 23: Event-driven Proactivity — дельта-реакция на изменения сцены

**Branch:** `proactive-delta` (new — создаётся при старте фазы)

**Goal:** Реализовать второй слой проактивного контура из диплома §3.3.4 — событийную дельта-реакцию на изменения сцены. В отличие от Phase 19 (idle-scheduler — реакция на длительный простой) и существующего `scene_director` (периодическая фоновая моторика), Phase 23 запускает спонтанные реакции по событийному триггеру и с вероятностной модуляцией.

**Requires:**
- Phase 20 (VLM Upgrade) или текущий VILA 1.5-3b с включённым scene worker и кэшем сцен
- Phase 22 (AIIM Core Runtime) — желательно, для интеграции Δ-сдвигов аспектов на дельта-событие
- Независима от Phase 19 — слои дополняют друг друга

**Delivers:**
- Модуль `System/adam/scene_delta.py` — сравнение текущего описания VLM с предыдущим из `scene_buffer`. Возвращает категоризированное событие: `appeared` / `disappeared` / `count_change` / `engagement_change` (none → watching / watching → approaching / approaching → interacting), либо `no_delta`
- Парсер двухчастного формата VLM-промпта (Scene + Engagement) для извлечения переходов уровня вовлечённости
- Вероятностный модулятор `proactive.spontaneous_speech_prob` в `Tuning.json` (база 0.17 на значимое дельта-событие) с механизмом затухания: при повторных однотипных триггерах вероятность снижается коэффициентом `proactive.repeat_decay` (база 0.5)
- Интеграция в Orchestrator: при детекции дельта-события — вызвать моторный отклик через `scene_director` overlay (выбор сцены по типу события), и с вероятностью `spontaneous_speech_prob` — запустить LLM-цикл с промптом-затравкой типа «прокомментируй появление зрителя в духе персонажа», результат озвучивается без пробуждного слова
- Если Phase 22 завершена: дельта-событие также модулирует Δ-веса AIIM перед выбором тега `Mood` (например, `appeared` → +Δ для `at`, `im`)
- Соблюдение `half_duplex_mute` инварианта: спонтанная реакция не запускается, если идёт активный диалог или TTS
- Регрессионный тест: при имитированной последовательности сцен «пустая → один зритель → один наблюдает → один приближается» система генерирует 3 дельта-события и в среднем за 100 прогонов производит 17 ± 5 спонтанных реплик
- Метрика SIAR в Phase 12 получает данные не только от idle-scheduler (Phase 19), но и от дельта-реакций

**Requirements:** PROAC-DELTA-01 (детектор), PROAC-DELTA-02 (вероятностный модулятор), PROAC-DELTA-03 (интеграция с моторикой), PROAC-DELTA-04 (интеграция с AIIM)

**Mode:** standard | **Priority:** P1 | **Effort:** L (2–3 недели) | **Exhibition:** H

**Связь с диплом-расхождениями:** закрывает заявку текста ch3 §3.3.4 на трёхуровневый проактив — без Phase 23 в коде представлены только слои 1 (`scene_director` фоновая моторика) и 3 (Phase 19 idle-scheduler), а слой 2 (событийная дельта-реакция) остаётся декларацией в дипломе.

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
