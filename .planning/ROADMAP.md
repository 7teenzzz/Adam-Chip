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

## Backlog (неспланированные задачи)

> Сырые идеи и задачи из [ToDo.md](../ToDo.md). Когда задача готова к планированию — переезжает сюда как Phase N с требованиями.

### Memory Wave 2: Neural search

Заменить TF-IDF векторизацию в `FaissEpisodeIndex` на llama.cpp `/embeddings` endpoint.
Условие запуска: VRAM ≥ 4 GB свободно при работающем Gemma 4 E4B (Q4_K_XL ≈ 8 GB → остаток ~8 GB на Jetson 16 GB).
Интерфейс не меняется (`.build()` / `.search()` / `.save()` / `.load()`), только векторизация.

---

### Phase 7AA: Branch Merge — Identity_Tunning → dynamic-aiim

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

**Условие завершения:** `git diff Identity_Tunning..dynamic-aiim` показывает только
AIIM-специфичные файлы (`identity.py`, `identity_drift.py`, `tests/test_identity.py`) и
нет конфликтующих версий persona-файлов. Все тесты зелёные.

**Приоритет:** Выполнить ДО Phase 7A — 7A работает на стабилизированной ветке.

---

### Phase 7A: AIIM Mechanic Fixes — починить без смены парадигмы

**Предпосылка:** Критический анализ (2026-06-07) выявил что механизм работает не так как задуман.
Это направление устраняет конкретные механические дефекты, не меняя общую архитектуру keyword→emotion→ctx.

**Решения (зафиксированы 2026-06-07):**

- Default emotion → **`curious`** (подтверждён; Identity.md будет поправлен: "любопытство (по умолчанию)")
- Канонический AIIM-профиль → **`Identity.md`** (lo=Δ0.70, Ac-Or — "открытый, идёт к людям")
- `Personality_AIIM.md` → пометить как `[ARCHIVED — superseded by Identity.md]`

**Дефекты к устранению:**

- **Salience заглушка:** drift всегда применяется с 0.5 — нужна реальная salience из `acc.finalize()`; требует перестройки session-close: сначала `acc.finalize()`, потом `apply_session()`
- **Нет внутрисессионного накопления:** `AspectModulator` каждый turn стартует с `_base_vector`, не с предыдущего модулированного — 20 "warm" turn'ов = 1 "warm" turn; нужен rolling vector внутри сессии
- **`warm` заблокирован для новых зрителей:** зависит от `acc.tone_visitor` (эпизодическая память) — нужен inline tone-detector из transcript (длина + вопросительные конструкции + тематические слова)
- **Однонаправленный drift:** аспекты только растут к потолку; нужны деградационные дельты для `void` (lo убывает, at убывает)
- **Два мёртвых флага:** `signal_void` и `become_unreadable` трекируются, но нигде не используются — нужно behavioural consequence (см. обсуждение)
- **Формула AIIM парсится но план/уровень/состояние выбрасываются:** `Ac vs Pa` и `Or vs Ch` не используются в `AspectModulator`; `Ac-Ch` аспекты должны модулироваться иначе чем `Pa-Or`
- **`classify_session` вызывается дважды:** дублирующий вызов в session-close блоке

**Затрагивает:** `identity.py`, `identity_drift.py`, `tuning.py`, `Orchestrator.py` (session close), `Identity.md` (текст дефолта), `Personality_AIIM.md` (архивирование)

**Условие запуска:** `dynamic-aiim` смёрджена в `main`; Jetson стабилен ≥1 неделя.

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

**Затрагивает:** `identity.py` (to_ctx_block, src-аннотация), `tuning.py` (EmotionTransitionRule + src поле), `Agent Adam Chip/About/System.md` (расписать per-emotion инструкции), `Tuning.json`

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

**Затрагивает:** `identity.py` (EmotionMachine + новый EnvironmentDriver, новые intention rules), `identity_drift.py` (extract_trend, trend_line в DriftRecord), `Orchestrator.py` (передача sensors dict в AIIM per-turn), `tuning.py` (новые модели конфига), `Tuning.json`, `Agent Adam Chip/About/System.md`

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
