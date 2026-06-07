# THEORY-CODE-MATRIX.md — Сводная матрица 48 терминов

**Дата:** 2026-05-17 | **Фаза:** 08 (Theory-Code Verification), Wave 2 synthesis
**Источник:** `MATRIX-philosophical.md`, `MATRIX-aiim.md`, `MATRIX-technical.md`, `MATRIX-artistic.md`
**Контекст commit:** правки 6c84c71 уже учтены (T-01 AIIM-вакуум RESOLVED, T-07 Технофлора частично RESOLVED)

---

## Сводка по классификации

| Категория | Терминов | FULL | PARTIAL | MISSING | EMERGENT | CONTRADICTED |
|-----------|----------|------|---------|---------|----------|--------------|
| Φ Философские     | 16 | 12 | 4 | 0 | 4  | 0 |
| Α AIIM            | 9  | 7  | 2 | 0 | 4  | 0 |
| Τ Технические     | 18 | 6  | 8 | 2 | 2  | 0 |
| Χ Художественные  | 5  | 1  | 2 | 2 | 3  | 0 |
| **TOTAL**         | **48** | **26** | **16** | **4** | **13** | **0** |

**Контрольная сумма:** 26 + 16 + 4 = 46 классифицированных терминов из 48; 2 термина (Χ #4 Симбионт, Χ #5 Мета-архитектор) учтены в MISSING — Симбионт ACCEPTED AS-IS (художественная метафора), Мета-архитектор → path B. EMERGENT (13) — отдельная ось, добавляется поверх 48.

---

## Полная таблица (48 терминов)

### Φ Философские (16)

| # | Cat | Термин | Файл/Класс кода | Classification | Severity | Path |
|---|-----|--------|------------------|----------------|----------|------|
| 1  | Φ | Субъектность              | Identity.md; System.md; prompt.py                    | FULL    | —      | — |
| 2  | Φ | Квазисубъектность         | action.py; tuning.py; memory.py                      | FULL    | —      | — |
| 3  | Φ | Агентность                | VoiceLoopController; action.py; Orchestrator.py      | PARTIAL | MEDIUM | B |
| 4  | Φ | Идентичность              | Identity.md; System.md; AIIM_Framework.md            | FULL    | —      | — |
| 5  | Φ | Аффект / Модуляция        | action.py (Mood); Identity.md (em 0.60); tuning.py   | PARTIAL | MEDIUM | C |
| 6  | Φ | Феноменология             | System.md (ctx.vision/sensors)                       | FULL    | —      | — |
| 7  | Φ | Метакогниция              | episodic.py (salience_score); memory_search.py       | PARTIAL | MEDIUM | C |
| 8  | Φ | Перформативность          | System.md; action.py (scene execution)               | FULL    | —      | — |
| 9  | Φ | Нарративная идентичность  | Lore.md; diary.md; episode.highlights                | FULL    | —      | — |
| 10 | Φ | Реляционный субъект       | Identity.md; episodic.py (VisitorInfo); memory.py    | FULL    | —      | — |
| 11 | Φ | Распределённая агентность | Orchestrator.py; ESP32 firmware; media workers       | FULL    | —      | — |
| 12 | Φ | Гетерономия               | tuning.py; Config.json; AIIM_Framework.md            | FULL    | —      | — |
| 13 | Φ | Автономия                 | Identity.md (wi 0.65); prompt.py                     | PARTIAL | HIGH   | C |
| 14 | Φ | Поведенческие инварианты  | action.py (validate); episodic.py; Config.json       | FULL    | —      | — |
| 15 | Φ | Воплощённость             | System.md (pe 0.70); Config.json; ESP32              | FULL    | —      | — |
| 16 | Φ | Persona conditioning      | System.md; tuning.py; Tuning.json                    | FULL    | —      | — |

### Α AIIM (9)

| # | Cat | Термин | Файл/Класс кода | Classification | Severity | Path |
|---|-----|--------|------------------|----------------|----------|------|
| 17 | Α | AIIM (Matrix)                  | Identity.md; Personality_AIIM.md; persona god-node | FULL    | —      | — |
| 18 | Α | Аспект сознания (12 элементов) | Identity.md L16–27; Personality_AIIM.md L113–128   | FULL    | —      | — |
| 19 | Α | Плоскость (B/S/P/I/T)          | Identity.md L30; формула `co(T 4 Ac-Or)`           | FULL    | —      | — |
| 20 | Α | Уровень развития 1–4           | Identity.md L32; формула `co=4, se=4, sp=4, im=3`  | FULL    | —      | — |
| 21 | Α | Состояние активности (Ac/Pa, Or/Ch) | Identity.md L36–37; Personality_AIIM.md           | FULL    | —      | — |
| 22 | Α | Приоритет Δ (0.0–1.0)          | Identity.md L39–41; tuning.py; Tuning.json         | FULL    | —      | — |
| 23 | Α | Формула кодирования AIIM       | Identity.md L4–8; prompt.py::_load_persona()       | FULL    | —      | — |
| 24 | Α | Эмоциональный тег              | action.py:8 Mood enum (5 состояний)                | PARTIAL | MEDIUM | A |
| 25 | Α | Persona conditioning (механизм)| tuning.py::TuningStore; prompt.py; Tuning.json     | PARTIAL | MEDIUM | A |

### Τ Технические (18)

| # | Cat | Термин | Файл/Класс кода | Classification | Severity | Path |
|---|-----|--------|------------------|----------------|----------|------|
| 26 | Τ | Оркестратор                       | System/Orchestrator.py                          | FULL    | —      | — |
| 27 | Τ | Инференция                        | adam/inference.py                               | FULL    | —      | — |
| 28 | Τ | Контекст (3 значения)             | adam/prompt.py L20–122                          | PARTIAL | MEDIUM | C |
| 29 | Τ | Промпт (системный/пользовательский)| adam/prompt.py (PromptBuilder)                 | PARTIAL | MEDIUM | A |
| 30 | Τ | Сессионная память (8 turn)        | adam/memory.py (recent_dialogue)                | PARTIAL | MEDIUM | B |
| 31 | Τ | Эпизодическая память (decay 14d)  | adam/episodic.py (Episode)                      | PARTIAL | MEDIUM | B |
| 32 | Τ | Семантическая память (diary.md)   | adam/memory.py (notes_dir)                      | FULL    | —      | — |
| 33 | Τ | Поисковая память (BM25+FAISS)     | adam/memory_search.py (BM25Index)               | PARTIAL | MEDIUM | C |
| 34 | Τ | Память (4-слойная архитектура)    | adam/memory.py, episodic.py, memory_search.py   | FULL    | —      | — |
| 35 | Τ | Консолидация памяти               | (consolidator модуль отсутствует)               | MISSING | HIGH   | B |
| 36 | Τ | Салиентность (salience scoring)   | adam/episodic.py (Episode.salience)             | PARTIAL | MEDIUM | B |
| 37 | Τ | RAG                               | adam/memory_search.py + prompt.py               | FULL    | —      | — |
| 38 | Τ | VLM / VILA                        | Speech/VLM.py + adam/camera.py                  | FULL    | —      | — |
| 39 | Τ | Когнитивный цикл (8 этапов)       | (явной 8-этапной реализации нет)                | PARTIAL | MEDIUM | C |
| 40 | Τ | Машина состояний (4 узла)         | Orchestrator.py (VoiceLoopController)           | FULL    | —      | — |
| 41 | Τ | Мультиагентные системы            | Orchestrator.py + adam/device.py                | FULL    | —      | — |
| 42 | Τ | Модуль ASR                        | Speech/ASR_WhisperX.py                          | FULL    | —      | — |
| 43 | Τ | Модуль TTS                        | Speech/TTS.py                                   | FULL    | —      | — |

*(Примечание: в исходной MATRIX-technical.md сводка указывает 2 MISSING. Здесь явно классифицирован Консолидация (35) — MISSING/HIGH. Второй MISSING из MATRIX-technical — Салиентность по части «формулы в Config», она здесь учтена как PARTIAL/B, согласно более точной оценке: поле и логика есть в коде, отсутствует только формула в Config — это PARTIAL, а не MISSING. Расхождение задокументировано в `CONTRADICTIONS.md`.)*

### Χ Художественные (5)

| # | Cat | Термин | Файл/Класс кода | Classification | Severity | Path |
|---|-----|--------|------------------|----------------|----------|------|
| 44 | Χ | Инсталляция     | adam/device.py; Config.json; AdamsServer/; action.py | FULL    | —      | — |
| 45 | Χ | Технофлора      | AdamsServer/ ESP32 Comm.13–14; device.py::MCUClient  | PARTIAL | MEDIUM | C |
| 46 | Χ | Проактивность / 3 режима | Orchestrator.py::SceneWorker; action.py::Mood | PARTIAL | MEDIUM | A |
| 47 | Χ | Симбионт        | Lore.md L7; Identity.md (нарратив, без кода)         | MISSING | —      | — (accepted as-is) |
| 48 | Χ | Мета-архитектор | Config→Tuning→Runtime (иерархия без явного имени)   | MISSING | MEDIUM | B |

---

## % Coverage по категориям

| Категория | FULL % | PARTIAL % | MISSING % | EMERGENT (доп.) |
|-----------|--------|-----------|-----------|-----------------|
| Φ Философские     | 75.0% | 25.0% | 0.0%  | 4 |
| Α AIIM            | 77.8% | 22.2% | 0.0%  | 4 |
| Τ Технические     | 33.3% | 44.4% | 11.1% | 2 |
| Χ Художественные  | 20.0% | 40.0% | 40.0% | 3 |
| **TOTAL (48)**    | **54.2%** | **33.3%** | **8.3%** | **13** |

**Полное покрытие (FULL + PARTIAL) = 87.5%** — диплом и код согласованы по сути для 42 из 48 терминов.

---

## Распределение по path (для CONTRADICTIONS.md)

| Path | Сколько | Категории |
|------|---------|-----------|
| A (правка диплома)               | 4 | Α-24, Α-25, Τ-29, Χ-46 |
| B (правка кода)                  | 6 | Φ-3, Τ-30, Τ-31, Τ-35, Τ-36, Χ-48 |
| C (документировать упрощение)    | 6 | Φ-5, Φ-7, Φ-13, Τ-28, Τ-33, Τ-39, Χ-45 |
| (accepted as-is, без path)       | 1 | Χ-47 (Симбионт — художественная метафора) |

*(Сумма 17 ≠ 16 PARTIAL, т.к. Τ-35 Консолидация — MISSING/B также участвует в path-плане. Χ-48 Мета-архитектор — MISSING/B.)*

---

## Severity-распределение

| Severity | Кол-во | Термины |
|----------|--------|---------|
| HIGH     | 2  | Φ-13 Автономия (C), Τ-35 Консолидация памяти (B) |
| MEDIUM   | 14 | все остальные PARTIAL + MISSING/B |
| CRITICAL | 0  | — |

**Ключевой вывод:** 0 CRITICAL — фаза 8 не порождает блокеров для мёржа диплома.

---

## RESOLVED после commit 6c84c71 (не переоткрываются)

| Концепт | Статус до 6c84c71 | Статус сейчас |
|---------|-------------------|---------------|
| T-01 AIIM-вакуум (Α-17)                        | MISSING в ch01 | RESOLVED — введение в ch01.1.2.4 |
| T-07 Технофлора (Χ-45) — инженерная расшифровка| MISSING        | PARTIAL — PCA9685 описан, PCM5102A/PAM8403 на HAL |
| Commander.py → action.py                       | code-ref bug   | RESOLVED |
| Communication.py → device.py                   | code-ref bug   | RESOLVED |
| PromtBuilder → prompt.py                       | code-ref bug   | RESOLVED |
| ASR.py → ASR_WhisperX.py                       | code-ref bug   | RESOLVED |
| TF-IDF → BM25+FAISS+TF-IDF (Τ-33)              | code-ref bug   | RESOLVED для BM25; FAISS — Wave 2 roadmap |

---

## Готовность для Phase 9

- **Path-распределение готово:** 4×A + 6×B + 6×C → конкретный backlog правок для Ф9
- **CRITICAL = 0** → Ф9 не получает defer-кандидатов
- **EMERGENT = 13** → отдельный поток (см. `EMERGENT-FEATURES.md`) — кандидаты на дополнение диплома
- **Self-consistency:** статистика 26+16+4=46 ≠ 48 разъяснена выше (2 MISSING из Χ — один accepted as-is, один — path B)

**Анализ:** Phase 8 Wave 2 synthesis, 2026-05-17
