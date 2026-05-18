# Phase 9 — Candidates for Next Phases

**Date:** 2026-05-17
**Sources:** Phase 8 §4.1 + ROADMAP Backlog + Active branches (STATE.md)
**Total candidates:** 13
**Consumed by:** Wave 2 (09-02 PRIORITIZATION) → Wave 3 (09-03 PHASE-DRAFTS)

---

## Already in ROADMAP (NOT re-drafted in Phase 9)

- **Phase 10**: Roadmap Global Update — следующая после Ф9, уже внесена в ROADMAP.md
- **Phase 12**: Metrics & Evaluation Framework — DEFERRED, ждёт стабилизации веток (`Memory-upgrade`, `Identity-tuning`, `VLM-upgrade`, `dynamic-aiim` → merged in main) + завершения Phase 11 (AIIM Dynamic) как условия существования данных для RDI/CRS

---

## Candidates

### Phase 10A: Diploma Convergence Pass

- **Source:** `phase8-summary §4.1`
- **Branch:** `diploma-chapter3` (текущая ветка)
- **Goal (1 sentence):** Применить все оставшиеся текстовые правки диплома из Ф8 (4A + 7C paths + 5 оставшихся HIGH-EMERGENT фичей) и закрыть незакрытые CRITICAL-находки из Ф7.
- **Trigger artifact:** `08-SUMMARY.md §4.1 row "Phase 10A: Diploma Convergence Pass"` | `07-SUMMARY.md §2.1–2.10 (T-01 AIIM-вакуум, T-02 метрики, T-03 симбионт, T-05 противоречие ch02, T-06 дрейф агент/персонаж, T-07 технофлора)`
- **Dependencies:** `requires: [Phase 8 ✓]`; топ-3 EMERGENT уже применены (commit `b48ccb8`); фаза не блокирует другие, но является предпосылкой для мёржа `diploma-chapter3` → `main`
- **Raw effort estimate:** M (дни — преимущественно текстовые правки диплома)
- **Linked findings (Ф7/Ф8):** T-01, T-02, T-03, T-05, T-06, T-07 (Ф7); F-04 EMERGENT #13 (AIIM мост), F-05 EMERGENT #2 (TuningStore), F-06 EMERGENT #9 (Voice Loop FSM) — применены; EMERGENT #1 (AIIM god-node), #3 (5 mood), #6 (SceneWorker), #7 (Salience scoring), #8 (Mood FSM) — остались
- **Notes:** После завершения Ф10A диплом готов к мёржу `diploma-chapter3` → `main`. Совмещённые работы из Ф8 §4.3 обрабатываются в рамках этой фазы (EMERGENT #3 + #8 + path A Α-24 = одна редактура ch03.3.2.6; EMERGENT #6 + path A Χ-46 = одна правка ch03.3.2.2).

---

### Phase 10B: Config-First Refactor

- **Source:** `phase8-summary §4.1`
- **Branch:** `new: config-refactor`
- **Goal (1 sentence):** Вынести все хардкодированные числовые параметры в `Config.json` / `Config.schema.json` и устранить BUG F-07 (рассинхронизацию `history_turns=2` vs `limit=8`).
- **Trigger artifact:** `08-SUMMARY.md §4.1 row "Phase 10B: Config-First Refactor"` | `CONTRADICTIONS.md §"Сессионная память — 8 turn buffer (Τ-30)"`, `"Эпизодическая память — decay 14d (Τ-31)"`, `"Салиентность (Τ-36)"`, `"F-07 BUG"`
- **Dependencies:** `requires: []` (независима, но логически следует за Phase 10A)
- **Raw effort estimate:** M (дни — рефакторинг кода + обновление Config.json, Config.schema.json, тесты)
- **Linked findings (Ф7/Ф8):** F-07 (BUG); CONTRADICTIONS.md paths B: Τ-30, Τ-31, Τ-36; Паттерн 4 Ф8 «Параметры размазаны между Config.json и кодом»
- **Notes:** Затрагивает `System/adam/prompt.py` (limit=8), `System/adam/episodic.py` (decay 14d, salience_weights), `System/Config.json`, `System/Config.schema.json`. После этой фазы Phase 18 (Structural Refactor) можно начинать — Ф10B является её логическим предшественником.

---

### Phase 11: AIIM Dynamic

- **Source:** `phase8-summary §4.1` + `active-branch`
- **Branch:** `dynamic-aiim` (existing)
- **Goal (1 sentence):** Реализовать рефлексивный уровень AIIM: после каждой сессии консолидатор анализирует паттерны взаимодействия и корректирует параметры `Tuning.json` автоматически.
- **Trigger artifact:** `08-SUMMARY.md §4.1 row "Phase 11: AIIM Dynamic"` | `EMERGENT-FEATURES.md #2 "TuningStore hot-reload"`, `#4 "Доминирующие состояния"` | `STATE.md ACTIVE branches: dynamic-aiim` | `ROADMAP.md Backlog "AIIM Dynamic: Рефлексивный уровень"` (merged with Backlog item)
- **Dependencies:** `requires: [Phase 13 Memory Consolidation (consolidator должен быть интегрирован), Phase 10A (AIIM мост в дипломе)]`
- **Raw effort estimate:** L (недели — новый рефлексивный модуль, интеграция с consolidator, ограничения на drift magnitude)
- **Linked findings (Ф7/Ф8):** F-05 EMERGENT #2 (TuningStore hot-reload как фундамент); EMERGENT #4 (доминирующие состояния как контекст); Ф7 Паттерн 4 (self-reflection loop, internal motivation); 07-SUMMARY §5 кандидат Phase 10F
- **Notes:** Ветка `dynamic-aiim` уже ведётся. Ключевые вопросы до планирования: какие параметры `Tuning.json` поддаются автокоррекции (не все); ограничения на magnitude изменений; частота (после сессии или ежедневно). Backlog-item «AIIM Dynamic» из ROADMAP объединён с Ф8-кандидатом Phase 11 — merged source.

---

### Phase 13: Memory Consolidation

- **Source:** `phase8-summary §4.1`
- **Branch:** `new: memory-consolidation` (или объединить с `Memory-upgrade` — открытый вопрос)
- **Goal (1 sentence):** Интегрировать `Engineering/consolidator.py` в Orchestrator runtime с daily cron или post-session trigger, реализовав работающий механизм консолидации эпизодической памяти.
- **Trigger artifact:** `08-SUMMARY.md §2.2 "F-02 HIGH-1 — Τ-35 Консолидация памяти"` | `CONTRADICTIONS.md §"Термин: Консолидация памяти (Τ-35)"` | `08-SUMMARY.md §4.1 row "Phase XX: Memory Consolidation"`
- **Dependencies:** `requires: []`; является **блокером** для Phase 12 (Metrics & Evaluation) — без консолидации метрика LMRR не имеет источника данных
- **Raw effort estimate:** L (недели — реальная разработка модуля, не текстовая правка; единственный B-path с полноценной разработкой в Ф8)
- **Linked findings (Ф7/Ф8):** F-02 HIGH-1; CONTRADICTIONS §Τ-35 (Path B — единственный B-кейс с реальной разработкой); связь с Phase 12 LMRR (предпосылка)
- **Notes:** `Engineering/consolidator.py` существует и уже использует llama.cpp API (Phase 6A, commit `f6b2c5a`), но не интегрирован в Orchestrator runtime. Вопрос: создать отдельную ветку `memory-consolidation` или работать в `Memory-upgrade`?

---

### Phase 14: Mood LLM-driven

- **Source:** `phase8-summary §4.1`
- **Branch:** `new: mood-llm`
- **Goal (1 sentence):** Доработать `action.py` для парсинга явных mood-маркеров из LLM-ответа вместо текущего heuristic keyword matching по `reply_text`.
- **Trigger artifact:** `08-SUMMARY.md §4.1 row "Phase XX: Mood LLM-driven"` | `CONTRADICTIONS.md §"Термин: Агентность (Φ-3)"` (Path B — явные маркеры из LLM)
- **Dependencies:** `requires: []` (независима, но логически связана с Phase 11)
- **Raw effort estimate:** M (дни — изменение action.py + системного промпта + тесты)
- **Linked findings (Ф7/Ф8):** Φ-3 Агентность B-path; CONTRADICTIONS §"Φ-3 Агентность — LLM не выдаёт явные маркеры действия"; EMERGENT #8 (Mood FSM — текущая реализация)
- **Notes:** Риск: изменение поведения LLM-промпта может повлиять на качество ответов — нужны A/B тесты. Связь с Phase 12: метрика NVR (Normative Violation Rate) будет точнее при явных маркерах.

---

### Phase 15: Memory Wave 2 (Neural Search)

- **Source:** `roadmap-backlog` + `active-branch`
- **Branch:** `Memory-upgrade` (existing)
- **Goal (1 sentence):** Заменить TF-IDF векторизацию в `FaissEpisodeIndex` на llama.cpp `/embeddings` endpoint для семантического поиска по эпизодической памяти.
- **Trigger artifact:** `ROADMAP.md Backlog "Memory Wave 2: Neural search"` | `08-SUMMARY.md §4.2 "Memory-upgrade: Wave 2 (Neural search) ждёт VRAM"`
- **Dependencies:** `requires: [Phase 13 Memory Consolidation]`; условие запуска: свободная VRAM ≥ 4 GB при работающем Gemma 4 E4B (Q4_K_XL ≈ 8 GB → остаток ~8 GB на Jetson 16 GB)
- **Raw effort estimate:** M (дни — замена векторизации в memory_search.py, интерфейс `.build()/.search()/.save()/.load()` не меняется)
- **Linked findings (Ф7/Ф8):** CONTRADICTIONS §Τ-33 (BM25+FAISS Wave 1 ✓ готова, Wave 2 ждёт VRAM); Phase 6B B2 `FaissEpisodeIndex` уже сделан с TF-IDF placeholder
- **Notes:** Wave 1 (BM25 + FAISS CPU + TF-IDF) завершена в Phase 6B. Ветка `Memory-upgrade` готова к мёржу после code-review — Phase 15 может быть либо продолжением этой ветки, либо новой ветвью от мёржа.

---

### Phase 16: UI Rebuild

- **Source:** `roadmap-backlog`
- **Branch:** `new: ui-rebuild`
- **Goal (1 sentence):** Пересобрать операторский веб-интерфейс (`:8080`) с перегруппировкой параметров по доменным блокам, визуализацией уровня микрофона, настройкой silence timeout и управлением громкостью.
- **Trigger artifact:** `ROADMAP.md Backlog "UI: Пересборка интерфейса управления"`
- **Dependencies:** `requires: [Phase 10B Config-First Refactor]` (параметры должны быть в Config.json до UI-привязки)
- **Raw effort estimate:** L (недели — переработка HostUI/WebUI, новые API эндпоинты, frontend)
- **Linked findings (Ф7/Ф8):** нет прямых находок Ф7/Ф8; косвенно связана с EMERGENT #12 (VAD aggressiveness как параметр восприятия — должен быть в UI)
- **Notes:** Затрагивает `System/adam/ui.py`, `System/HostUI/`, `System/WebUI/`. Перегруппировка: ESP (камера, mic, PCA9685, PCM5102A) / Agent (ASR, VLM, LLM, TTS) / Adam Identity.

---

### Phase 17: Remote Access

- **Source:** `roadmap-backlog`
- **Branch:** `new: remote-access`
- **Goal (1 sentence):** Расширить `scripts/adam_pull_logs.py` и API до полноценного удалённого мониторинга pipeline-этапов с фильтрацией по turn_id / stage / временному диапазону.
- **Trigger artifact:** `ROADMAP.md Backlog "Remote: Удалённый доступ к Jetson"`
- **Dependencies:** `requires: []` (частично реализовано: `adam_pull_logs.py` + `/api/agent/turns` + `/api/agent/events`)
- **Raw effort estimate:** M (дни — расширение существующего API + scripts, без архитектурных изменений)
- **Linked findings (Ф7/Ф8):** нет прямых; косвенно — EMERGENT #9 (Voice Loop FSM) создаёт новые события для отладки
- **Notes:** Основа уже есть: `scripts/adam_pull_logs.py` работает с Windows/macOS без зависимостей. Расширение: агрегация по stage, фильтрация по временному диапазону, опциональный dashboard.

---

### Phase 18: Structural Refactor

- **Source:** `roadmap-backlog`
- **Branch:** `new: refactor`
- **Goal (1 sentence):** Провести структурный рефакторинг: пересмотр директорий, единый реестр всех параметров системы и их перенос в Config.json там, где не покрыто Phase 10B.
- **Trigger artifact:** `ROADMAP.md Backlog "Refactor: Структурный рефакторинг"`
- **Dependencies:** `requires: [Phase 10B Config-First Refactor]` (должна следовать ПОСЛЕ — Ф10B покрывает первый слой параметров, Ф18 — более глубокий аудит)
- **Raw effort estimate:** L (недели — полный аудит + пересмотр структуры `System/`, `Subsystem/`, `Engineering/`)
- **Linked findings (Ф7/Ф8):** Паттерн 4 Ф8 (параметры размазаны); CLAUDE.md Rule «File Structure & Organization»
- **Notes:** Риск высокий — масштабный рефактор при работающей системе. Требует feature-freeze других веток. Условие мёржа: все существующие тесты зелёные, systemd units проверены.

---

### Phase 19: Proactive Speech

- **Source:** `roadmap-backlog`
- **Branch:** `new: proactive-speech`
- **Goal (1 sentence):** Добавить idle-scheduler — фоновый процесс, который при наличии посетителей и тишине дольше N секунд вызывает LLM с промптом-затравкой и воспроизводит ответ без wake word.
- **Trigger artifact:** `ROADMAP.md Backlog "Proactive Speech: Спонтанная речевая инициатива"` | `07-SUMMARY.md §5 Паттерн 4 (internal motivation не раскрыто в ch03)`
- **Dependencies:** `requires: [Phase 13 Memory Consolidation]` (для контекста истории сессий); связана с Phase 12 SIAR метрика
- **Raw effort estimate:** M (дни — новый idle-scheduler модуль, интеграция в Orchestrator без нарушения half_duplex_mute инварианта)
- **Linked findings (Ф7/Ф8):** Ф7 Паттерн 4 (internal motivation — ch02.2.4.3 заявлено, ch03 не раскрыто); 07-SUMMARY §"кандидаты для Phase 9": Phase 10E; диплом §3.3.4, §3.4.4 (SIAR)
- **Notes:** Ключевые инварианты: `half_duplex_mute = true` (mic заглушён во время TTS) — idle-scheduler не должен перекрывать активный диалог. Ключевые вопросы: порог тишины (N сек), контроль частоты (не чаще M минут), отдельный системный промпт.

---

### Phase 20: VLM Upgrade Финализация

- **Source:** `active-branch`
- **Branch:** `VLM-upgrade` (existing)
- **Goal (1 sentence):** Завершить разработку в ветке `VLM-upgrade` и выполнить merge в `main`.
- **Trigger artifact:** `STATE.md ACTIVE branches table "VLM-upgrade: Активная разработка | Нет"` | `08-SUMMARY.md §4.2 "VLM-upgrade: SceneWorker уже параметризован. Никаких блокеров со стороны Ф8"`
- **Dependencies:** `requires: []` (Ф8 не выявила блокеров для этой ветки)
- **Raw effort estimate:** S (часы–дни — code review, тестирование, merge процедура)
- **Linked findings (Ф7/Ф8):** EMERGENT #6 (SceneWorker с параметризацией — уже готов); 07-SUMMARY §5 "Phase 10G: Vision Upgrade"; CONTRADICTIONS §Τ-33 (FAISS Wave 1 ✓ — VLM-ветка не затронута)
- **Notes:** Перед мёржем: `/gsd-code-review`, проверка `scene_worker_enabled`, `scene_interval_sec`, `scene_stale_after_sec` в Config.json. После мёржа: Phase 15 (Memory Wave 2) может использовать VLM embeddings.

---

### Phase 21: Identity Calibration Финализация

- **Source:** `active-branch`
- **Branch:** `Identity-tuning` (existing)
- **Goal (1 sentence):** Завершить разработку в ветке `Identity-tuning` (Φ-13 path C, Α-24 path A, calibration 5 mood-состояний) и выполнить merge в `main`.
- **Trigger artifact:** `STATE.md ACTIVE branches table "Identity-tuning: Активная разработка | Нет"` | `08-SUMMARY.md §4.2 "Identity-tuning: Φ-13 Автономия (C-path), 5 mood (path A)"`
- **Dependencies:** `requires: [Phase 10A Diploma Convergence Pass]` (diploma-side правки для Α-24 и Φ-13 должны быть согласованы с Identity-изменениями)
- **Raw effort estimate:** S (часы–дни — code review, согласование с правками диплома, merge)
- **Linked findings (Ф7/Ф8):** Φ-13 Автономия (C-path) — CONTRADICTIONS §HIGH; 5 mood path A — Α-24; 07-SUMMARY §5 "Phase 10H: Identity Calibration" + §2.8 "Дрейф «идентичность»: 4 модели"; T-06 (дрейф агент/персонаж)
- **Notes:** Ветка затрагивает `Agent Adam Chip/About/Identity.md` + `Tuning.json`. Осторожность: Identity-изменения влияют на тон и поведение агента — тестирование dialogue pipeline после мёржа обязательно.

---

## Cross-source notes

### Совмещения работ из Ф8 §4.3 (Single-edit optimization)

Следующие кажущиеся отдельными задачи реализуются одной правкой:

1. **EMERGENT #3 + #8 + path A Α-24 → одна редактура ch03.3.2.6** (Phase 10A):
   - EMERGENT #3 (5 mood-состояний как код-уровневая типизация)
   - EMERGENT #8 (Mood FSM диаграмма переходов)
   - Path A Α-24 (добавить таблицу и enum в ch03.3.2.6)
   - Всё это = одна секция в одном разделе диплома.

2. **EMERGENT #7 + path B Τ-36 → одна задача** (Phase 10B):
   - EMERGENT #7 (Salience Scoring формула не раскрыта)
   - Path B Τ-36 (вынос `salience_weights` в Config.json + формула в ch03.3.4)
   - Один коммит: правка Config.json + schema + одна секция диплома.

3. **EMERGENT #6 + path A Χ-46 → одна правка ch03.3.2.2** (Phase 10A):
   - EMERGENT #6 (SceneWorker background pattern не описан)
   - Path A Χ-46 (добавить `Mode = Literal["dialogue","idle","dormancy"]` enum + ссылку из ch03.3.1.2)
   - Связано: объяснение проактивности через pull-mode VLM.

### Связь активных веток с candidate-фазами

| Ветка | Candidate-фаза(ы) | Статус |
|-------|-------------------|--------|
| `Memory-upgrade` | Phase 13 (Consolidation — открытый вопрос) + Phase 15 (Neural search) | Ready for merge after code-review; Phase 15 = Wave 2 этой ветки |
| `dynamic-aiim` | Phase 11 (AIIM Dynamic) | Активная разработка; Foundation готов (TuningStore hot-reload) |
| `Identity-tuning` | Phase 21 (Identity Calibration финализация) | Активная разработка; requires Phase 10A для согласования |
| `VLM-upgrade` | Phase 20 (VLM Upgrade финализация) | Активная разработка; нет блокеров из Ф8 |
| `diploma-chapter3` | Phase 10A (Diploma Convergence Pass) | Текущая ветка; stays until diploma merged |

### Открытые вопросы по совмещению

- **Phase 13 vs `Memory-upgrade`:** Консолидация памяти (Τ-35) изначально начата в ветке `Memory-upgrade` (Phase 6A создала `consolidator.py`). Нужно решить: выполнять Phase 13 в этой же ветке (после merge) или завести новую `memory-consolidation`. Рекомендация: решить в Wave 2 (приоритизация).
- **Phase 10B vs Phase 18:** Config-First Refactor (10B) покрывает первый слой параметров (Τ-30, Τ-31, Τ-36, F-07). Structural Refactor (18) — глубокий аудит. Правило: Ф18 начинается только после Ф10B завершена и смёржена.

---

## Verification checklist

- [x] Минимум 13 candidates (итого: 13 записей: Phase 10A, 10B, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21 = 12 numbered + Phase 13 итого 13 уникальных candidate-фаз)
- [x] Каждый candidate имеет все обязательные поля (source, branch, goal, dependencies, effort, trigger artifact, linked findings)
- [x] Phase 12 НЕ передрачена — упомянута только в секции "Already in ROADMAP" выше
- [x] Все 5 Ф8-candidates присутствуют (Phase 10A, 10B, 11, 13, 14)
- [x] Все 6 Backlog items присутствуют (Memory Wave 2 = Phase 15, UI Rebuild = Phase 16, Remote Access = Phase 17, Structural Refactor = Phase 18, Proactive Speech = Phase 19, AIIM Dynamic = Phase 11 merged)
- [x] Все 4 активные ветки упомянуты (Memory-upgrade → Phase 15+13; dynamic-aiim → Phase 11; Identity-tuning → Phase 21; VLM-upgrade → Phase 20)

---

*Документ создан: 2026-05-17 | Phase 9, Wave 1*
*Consumed by: 09-02-PLAN.md (PRIORITIZATION)*
