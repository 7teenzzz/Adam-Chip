# Phase 8: Theory-Code Verification — CONTEXT

**Date:** 2026-05-17
**Branch:** `diploma-chapter3`
**Status:** Context gathered, ready for `/gsd-plan-phase 8`

---

## Domain

Сверка теоретических концептов диплома с реальным кодом Adam Chip. Каждый термин из `TERMINOLOGY-MATRIX.md` (Phase 7) получает классификацию:

- **FULL** — концепт полностью присутствует в коде, имена согласованы
- **PARTIAL** — концепт частично реализован, есть упрощения
- **MISSING** — концепт описан в дипломе, в коде нет реализации
- **EMERGENT** — концепт есть в коде, в дипломе не описан
- **CONTRADICTED** — диплом утверждает X, код делает Y (расхождение по сути)

Результат: полная карта `теория ↔ код` для последующих фаз (Phase 9 — приоритизация и планирование, Phase 10 — обновление Roadmap).

---

## Carrying forward from prior phases

- **Phase 7 (Diploma Analysis):** 11 артефактов готовы как сырьё:
  - `TERMINOLOGY-MATRIX.md` — 48 терминов (главный вход Ф8)
  - `XREF-AUDIT.md` §3 — 19 ссылок на код, частично проверены
  - `GAPS.md` — 44 концепта без раскрытия (кандидаты на EMERGENT при инверсии)
  - `07-SUMMARY.md` — 83 находки, severity-классифицированы
- **Недавние правки диплома (commit 6c84c71):** имена файлов кода актуализированы (Commander→action.py, Communication→device.py, PromtBuilder→prompt.py, ASR→ASR_WhisperX.py). 7 битых code-refs из XREF-AUDIT уже закрыты — Ф8 не должна их переоткрывать.
- **Phase 1 (Doc Refactor):** Config-First принцип — все числовые параметры в Config.json. Ф8 при сверке должна обращаться к Config.json, не к коду напрямую для параметров.
- **Phase 6A/6B (Memory):** 4-слойная память реализована (`memory.py`, `episodic.py`, `memory_search.py`, `memory_metrics.py`). Это resolved-кейс — соответствие диплома (после fe7f062) и кода полное.

### Baseline для Ф8

- `diploma/ANALYSIS-THEORY-vs-CODE.md` — частичный анализ только гл.3, **использовать как baseline**, но проверить и расширить на гл.0-2.

---

## Decisions

### D-01: Scope verification — все 48 терминов

Полная сверка каждого термина из `TERMINOLOGY-MATRIX.md` (Phase 7). Это:
- 16 философских (Φ)
- 9 AIIM-специфичных (Α)
- 18 технических (Τ)
- 5 художественных (Χ)

Дополнительно: проверка концептов из `GAPS.md` (44 шт.) на инверсию — кандидаты в EMERGENT.

### D-02: Использовать 3 графа (без docs/)

- **`Knowledge-graphs/code/`** — основной Python-код System/ (646 nodes, god-nodes: VoiceLoopController, EpisodicMemory, MCUClient)
- **`Knowledge-graphs/persona/`** — AIIM, Memory schema, Identity, TuningStore (критично для T-01 AIIM-вакуум)
- **`Knowledge-graphs/esp32/`** — прошивка ESP32-S3, PCA9685, PCM5102A (критично для раздела 3.3 и технофлоры)

Графы должны быть актуальны — если устарели, перестроить перед Wave 1.

`docs/` граф (Silero, Jetson AI Lab) — **исключён**: не требуется для verification внутренних концептов.

### D-03: Принятие решений по CONTRADICTED — гибрид

- **CRITICAL CONTRADICTED** → перенести в Phase 9 (Next-Phases Planning) как кандидаты с обоснованием. В Ф9 они получат A/B/C path в общем контексте приоритетов.
- **HIGH / MEDIUM CONTRADICTED** → Ф8 сразу классифицирует path:
  - **A** = поправить диплом (если код корректен и упрощение оправдано)
  - **B** = поправить код (если диплом точнее описывает желаемое поведение)
  - **C** = задокументировать как осознанное упрощение (если ни диплом, ни код не менять)

### D-04: Уровень детализации — гибрид

- **Таблица всех 48 концептов** в `THEORY-CODE-MATRIX.md` (компактно: термин × файл/класс × classification × краткий комментарий)
- **Детальные секции** в отдельных файлах:
  - `CONTRADICTIONS.md` — каждый CONTRADICTED получает: code excerpt (3-5 строк), цитата из диплома, причина расхождения, рекомендация (A/B/C path для HIGH/MEDIUM)
  - `EMERGENT-FEATURES.md` — каждый EMERGENT: где в коде, что делает, почему не в дипломе, нужно ли добавить (для Ф9 — кандидаты на дополнения диплома)

### D-05: Wave structure (по модели Ф7)

**Wave 0 (sequential, blocking)**: перестройка устаревших графов
- Проверить актуальность `Knowledge-graphs/code/`, `persona/`, `esp32/`
- Перестроить устаревшие через `/graphify <path> --mode deep`

**Wave 1 (4 parallel subagents Explore)**: per-category verification
- Plan 08-01: Verify философские (Φ) — 16 терминов
- Plan 08-02: Verify AIIM (Α) — 9 терминов
- Plan 08-03: Verify технические (Τ) — 18 терминов
- Plan 08-04: Verify художественные (Χ) — 5 терминов

Каждый плана выдаёт partial matrix `MATRIX-<category>.md` + список кандидатов на CONTRADICTED/EMERGENT в своей категории.

**Wave 2 (1 synthesis subagent)**: cross-graph синтез
- Plan 08-05: Объединить 4 MATRIX-* в `THEORY-CODE-MATRIX.md`
- Дополнительно проверить EMERGENT candidates через cross-graph queries (persona ↔ code, esp32 ↔ code)
- Произвести `CONTRADICTIONS.md` + `EMERGENT-FEATURES.md` + `CROSS-GRAPH-FINDINGS.md`

**Wave 3 (main agent inline)**: финальный summary
- Plan 08-06: `08-SUMMARY.md` — % coverage, главные находки, готовность для Ф9

### D-06: Не дублировать недавние правки

Commit `6c84c71` (от 2026-05-17) уже закрыл:
- ✅ Commander.py → action.py (verified)
- ✅ Communication.py → device.py (verified)
- ✅ PromtBuilder.py → prompt.py (verified)
- ✅ ASR.py → ASR_WhisperX.py (verified)
- ✅ TF-IDF expanded to BM25 + FAISS + TF-IDF (verified)

Ф8 должна верифицировать соответствие диплома (после правок) и кода. Эти 5 пар отметить как ✅ RESOLVED (не CONTRADICTED).

---

## Canonical refs

### Из Phase 7 (входные артефакты)
- `.planning/phases/07-comprehensive-diploma-analysis/07-SUMMARY.md` — 83 находки
- `.planning/phases/07-comprehensive-diploma-analysis/TERMINOLOGY-MATRIX.md` — 48 терминов (главный вход)
- `.planning/phases/07-comprehensive-diploma-analysis/XREF-AUDIT.md` — §3 для code-refs
- `.planning/phases/07-comprehensive-diploma-analysis/GAPS.md` — 44 концепта (для EMERGENT инверсии)
- `.planning/phases/07-comprehensive-diploma-analysis/STRUCTURE.md` — иерархия для навигации
- `.planning/phases/07-comprehensive-diploma-analysis/DUPLICATIONS.md` — терминологические дрейфы

### Baseline для verification
- `diploma/ANALYSIS-THEORY-vs-CODE.md` — частичный baseline (только гл.3)

### Графы (граф-evidence)
- `Knowledge-graphs/code/GRAPH_REPORT.md` + `graph.json`
- `Knowledge-graphs/persona/GRAPH_REPORT.md` + `graph.json`
- `Knowledge-graphs/esp32/GRAPH_REPORT.md` + `graph.json` (если есть; иначе создать)

### Главы диплома (исходники для текстовых evidence)
- `diploma/chapters/ch00_introduction.md`
- `diploma/chapters/ch01_chapter1.md`
- `diploma/chapters/ch02_chapter2.md`
- `diploma/chapters/ch03_chapter3.md` (включает правки commit 6c84c71)

### Код (для verification)
- `System/adam/*.py` (30+ модулей)
- `System/Speech/*.py` (ASR/TTS/VLM)
- `System/Orchestrator.py`
- `System/Config.json` + `System/Config.schema.json` (для всех параметров)
- `Agent Adam Chip/About/*.md` (Identity, Lore, Abilities, System) + `Tuning.json`
- `Subsystem/AdamsServer/` (ESP32 firmware)

### Project rules
- `CLAUDE.md` (root) — Config-First, инварианты
- `diploma/CLAUDE.md` — forensic researcher mode
- `docs/AGENT-PROTOCOL.md` — debugger mode (graph-first)

---

## Out of scope (Deferred Ideas)

- **Стилистические правки диплома** → Phase 10A (Diploma Convergence Pass) — типографские аномалии (H3 без H2 в 3.1)
- **Реализация метрик 3.4** → Phase 12 (Metrics & Evaluation Framework) — после стабилизации
- **Решения по CRITICAL CONTRADICTED** → Phase 9 (Next-Phases Planning) — в общем контексте приоритетов
- **AIIM Dynamic (рефлексивный уровень)** → Phase 11 — ветка `dynamic-aiim`
- **Memory Wave 2 (Neural search)** → отдельная фаза — ветка `Memory-upgrade`
- **Verification внешних библиотек (Silero, Jetson)** → не требуется (D-02)
- **Library version checks** → не scope (это операционная задача)

---

## Code context (для downstream)

- **Не применимо для code-changes:** Ф8 — аналитическая фаза, без модификаций кода
- **Графы:** `/graphify` queries для cross-evidence (3 графа)
- **Subagent type:** Explore (read-only) для Wave 1, general-purpose для Wave 2 synthesis
- **Output:** только в `.planning/phases/08-theory-code-verification/`

### Specific verification patterns

Для каждого термина subagent должен:
1. Найти упоминания в диплома главах (grep по термину)
2. Найти runtime-evidence через graphify queries (3 графа)
3. Применить decision tree:
   - **FULL** = граф находит точное соответствие + Config.json параметры совпадают
   - **PARTIAL** = граф находит частично, есть упрощения (документировать в комментарии)
   - **MISSING** = граф ничего не находит, концепт только в дипломе
   - **EMERGENT** = граф находит код, но в дипломе термина нет (или есть только в baseline)
   - **CONTRADICTED** = граф находит код, но он реализует другое поведение (требует evidence)
4. Зафиксировать в MATRIX-<category>.md

---

## Success criteria

- [ ] 3 графа (`code/`, `persona/`, `esp32/`) актуальны или перестроены
- [ ] `THEORY-CODE-MATRIX.md` содержит все 48 терминов с классификацией
- [ ] `CONTRADICTIONS.md` содержит каждое CONTRADICTED с evidence (code + диплом цитаты)
- [ ] HIGH/MEDIUM CONTRADICTED имеют path-рекомендации (A/B/C)
- [ ] CRITICAL CONTRADICTED помечены как «defer to Phase 9»
- [ ] `EMERGENT-FEATURES.md` содержит фичи кода, не упомянутые в дипломе (с обоснованием «нужно ли добавлять»)
- [ ] `CROSS-GRAPH-FINDINGS.md` фиксирует находки от cross-graph queries (persona ↔ code, esp32 ↔ code)
- [ ] `08-SUMMARY.md` содержит % coverage по категориям + готовый input для Ф9
- [ ] Недавние правки 6c84c71 НЕ переоткрываются (отметить как ✅ RESOLVED)

---

## Next step

`/gsd-plan-phase 8`
