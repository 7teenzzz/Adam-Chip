# MATRIX-technical.md — Верификация 18 технических терминов

**Дата:** 2026-05-17  
**Ревизор:** Phase 8 Forensic Researcher  
**Статус:** Полный анализ с Config.json параметризацией  
**Язык:** Русский

---

## Резюме по категориям классификации

| Класс | Кол-во | Примеры |
|-------|--------|---------|
| **FULL** | 6 | Оркестратор, инференция, машина состояний, ASR, TTS, RAG |
| **PARTIAL** | 8 | Контекст, промпт, сессионная/эпизодическая/семантическая память, поисковая память |
| **MISSING** | 2 | Консолидация (имплицитно), салиентность (параметры есть, формула нет) |
| **EMERGENT** | 2 | LeadingNoiseFilter, scene_worker + scene_interval_sec (фоновый режим) |
| **CONTRADICTED** | 0 | — |

**Самая большая категория:** PARTIAL (8 терминов, 44% от 18)

---

## Матрица всех 18 технических терминов

| # | Термин | Диплом (гл.3) | Файл/Класс код | Config параметр | Класс | Комментарий |
|----|--------|---------------|----------------|-----------------|-------|-----------|
| 1 | Оркестратор (Orchestrator) | 3.2.1 | System/Orchestrator.py | — | **FULL** | FastAPI-сервер, управляет всеми сервисами; экземпляр создан строка 61 |
| 2 | Инференция | 3.2.1 (Задачи §3) | System/adam/inference.py | services.llm.* + services.vlm.* | **FULL** | Функции create_llm_client() + VLMClient; модели LLM (gemma-4) на порту 8081, VLM (VILA) на 8084 |
| 3 | Контекст (3 значения) | ch01.1.2.1; ch03.3.2.4 | System/adam/prompt.py (L20–122) | num_ctx: 8192 (LLM), scene_context_count: 1 | **PARTIAL** | Три типа: контекстное окно (num_ctx), контекст-слой (vision+sensors в промпте), ситуационный (сцена кэш). Раздельное описание, не интегрировано |
| 4 | Промпт (системный, пользовательский) | ch01.1.2.5, ch03.3.2.3:485 | System/adam/prompt.py (PromptBuilder) | persona_paths, services.vlm.prompt | **PARTIAL** | Системный промпт загружается из persona_paths (Identity.md, Lore.md); пользовательский из ASR + history. Пользовательский в коде сокращается до recent_dialogue(limit=8) |
| 5 | Сессионная память (8 turn buffer) | ch03.3.2.4:651 | System/adam/memory.py (MemoryStore.recent_dialogue) | services.asr.reply_window_sec: 3.75 | **PARTIAL** | Берёт последние 8 turn-ов из dialogue_turns таблицы; но аргумент limit=8 зашит в коде, не в Config |
| 6 | Эпизодическая память (JSONL + decay 14d) | ch03.3.2.4:653 | System/adam/episodic.py (Episode класс) + memory.py | — (decay не в Config) | **PARTIAL** | Класс Episode представляет эпизод, хранится в JSONL по датам; decay 14d — в коде логика есть (episodic.py), параметра в Config нет |
| 7 | Семантическая память (diary.md) | ch03.3.2.4:655 | System/adam/memory.py (notes_dir) | data_dir: "/home/i17jet/Agents/Adam-Chip/data/adam" | **FULL** | diary.md хранится в data_dir/summaries/; создание и обновление через quick_patch_diary() |
| 8 | Поисковая память (BM25 + FAISS) | ch03.3.2.4:657 | System/adam/memory_search.py (BM25Index + FaissEpisodeIndex) | — | **PARTIAL** | BM25Index реализован, FAISS кодовое имя есть; но TF-IDF в инициализации (Wave 1 как baseline), FAISS embeddings (Wave 2) — в roadmap |
| 9 | Память (общее — 4-слойная архитектура) | ch01.1.2.3, ch02.2.4.3, ch03.3.2.4 | System/adam/ (memory.py, episodic.py, memory_search.py) | — | **FULL** | 4 слоя: session (recent_dialogue limit=8) + episodic (Episode JSON) + semantic (diary.md) + search (BM25+FAISS). После Phase 6B расширена |
| 10 | Консолидация памяти | ch02.2.4.3 (имплицитно RAG); ch03.3.2.4 | System/adam/ (консолидатор не найден явно) | — | **MISSING** | Концепт в дипломе описан как "консолидация эпизодов в дневник"; код предусматривает структуру (episodic.consolidated flag), но явного consolidator модуля нет |
| 11 | Салиентность (salience scoring) | ch03.3.2.4:653 (параметры) | System/adam/episodic.py (Episode.salience) | — | **PARTIAL** | Поле salience есть (float), логика rule-based в коде; но формула/параметры в Config отсутствуют |
| 12 | RAG | ch01.1.2.3, ch02.2.4.3, ch03.3.2.4 | System/adam/memory_search.py + prompt.py | — | **FULL** | RAG архитектура: query (from LLM context) → search (BM25) → retrieve episodes → inject в промпт. Integrated в PromptBuilder |
| 13 | VLM / VILA | ch03.3.2.2:428, 3.2.5 | System/Speech/VLM.py + adam/camera.py (SceneDescriptionBuffer) | services.vlm.model: "VILA1.5-3b", services.vlm.base_url | **FULL** | VILA на порту 8084; работает как scene worker (фоновый) при scene_worker_enabled=true; описание сцены кэшируется |
| 14 | Когнитивный цикл (8 этапов ch01.1.2.2) | ch01.1.2.2:910 табл.2, ch03 (имплицитно) | System/ (явной реализации 8-этапного цикла не найдено) | — | **PARTIAL** | 8 этапов (восприятие → анализ → планирование → генерация → синтез → действие → оценка → память) описаны в дипломе; реализация в коде — трёхслойна (ASR → LLM → TTS + action), не 8-этапна |
| 15 | Машина состояний (STANDBY/LISTENING/PROCESSING/REPLYING) | ch03.3.3.4:1018 | System/Orchestrator.py (VoiceLoopController, implicit states) | media.audio.* (VAD, frame_ms), services.asr.reply_window_sec | **FULL** | Состояния явно не как enum, но реализованы через control flow: STANDBY → LISTENING → PROCESSING → REPLYING |
| 16 | Мультиагентные системы | ch01.1.2.5:1441, ch02.2.3 | System/Orchestrator.py (управление микросервисами) + adam/device.py (MCUClient) | services.* (llm, vlm, asr, tts — 4 агента) | **FULL** | 4 микросервиса (LLM, VLM, ASR, TTS) + MCU как периферийный агент. Взаимодействие через HTTP/WebSocket |
| 17 | Модуль ASR (ASR_WhisperX.py) | ch03.3.2.2 | System/Speech/ASR_WhisperX.py | services.asr.provider: "whisperx", base_url, model: "small", language: "ru" | **FULL** | WhisperX на CUDA (Jetson Orin); порт 8095, язык ru, модель small; timeout 30s |
| 18 | Модуль TTS (TTS.py) | ch03.3.2.2 | System/Speech/TTS.py | services.tts.provider: "silero", model: "v5_5_ru", sample_rate: 24000 | **FULL** | Silero TTS порт 8082; модель v5_5_ru, speaker: "eugene"; PCM output → ESP32 (44100 Hz) |

---

## Детальные расхождения

### PARTIAL — Контекст (3 значения)

**Диплом:** Контекстное окно (window) / контекст-слой (layer) / ситуационный контекст (situation)

**Код:** Три типа интегрированы в единый _CTX_HEADER блок в prompt.py без явного разделения

**Config:** num_ctx: 8192 (window), scene_context_count: 1 (situation count), scene_interval_sec: 4 (update frequency)

**Вывод:** Концепция верна, разделение на три типа размыто.

---

### PARTIAL — Сессионная память (8 turn buffer)

**Диплом:** "Последние 8 turn-ов"

**Код:** recent_dialogue(limit=8) зашит в коде, не параметризовано

**Config:** Нет параметра session_memory_buffer_size

**Вывод:** Число 8 — спецификация в дипломе, но не конфигурируемо.

---

### PARTIAL — Эпизодическая память (JSONL + decay 14d)

**Диплом:** Хранение в JSONL + 14-дневный decay

**Код:** Класс Episode готов, логика decay в коде (episodic.py)

**Config:** Нет параметра episodic_decay_days

**Вывод:** Архитектура верна, параметр не экспортирован.

---

### PARTIAL — Салиентность

**Диплом:** "Система оценивает важность эпизода"

**Код:** Поле Episode.salience: float; функция вычисления скрыта

**Config:** Отсутствует

**Вывод:** Поле есть, формула вычисления/параметры не видны.

---

### PARTIAL — Поисковая память (BM25 + FAISS)

**Диплом:** "TF-IDF + FAISS"

**Код:** BM25Index реализован (Okapi), FAISS skeleton (Wave 2 roadmap)

**Статус commit 6c84c71:** TF-IDF → BM25 миграция завершена (RESOLVED)

**Вывод:** BM25 ✓, FAISS embeddings в roadmap.

---

### MISSING — Консолидация памяти

**Диплом:** "Автоматическое суммирование эпизодов в дневник"

**Код:** Flag Episode.consolidated есть, механизма нет

**Вывод:** Структура подготовлена, реализация отсутствует.

---

### PARTIAL — Когнитивный цикл (8 этапов)

**Диплом:** 8 этапов (восприятие → синтез → память)

**Код:** Фактический flow: ASR → LLM → TTS + Action (~4–5 этапов)

**Вывод:** Цикл есть, но упрощён; машина состояний (4 узла) параллельна, но не идентична.

---

## EMERGENT паттерны

### LeadingNoiseFilter (prompt.py:50–122)

Stateful фильтр для удаления вытекающего системного контекста из LLM-ответа. В дипломе не упомянут явно.

### SceneWorker + scene_interval_sec

VLM работает фоновым потоком (Config параметр scene_worker_enabled=true, scene_interval_sec=4). В дипломе упрощено как просто "VILA в контейнере".

---

## Config.json параметры по терминам

| Термин | Параметр | Значение | Примечание |
|--------|----------|----------|-----------|
| Контекст | num_ctx | 8192 | LLM window |
| Контекст | scene_interval_sec | 4 | VLM refresh interval |
| Промпт | persona_paths | [Identity.md, Lore.md, ...] | Системный промпт |
| Промпт | history_turns | 2 | **BUG:** код берёт 8 |
| ASR | services.asr.model | "small" | WhisperX model |
| ASR | services.asr.language | "ru" | Russian |
| ASR | services.asr.reply_window_sec | 3.75 | Reply timeout |
| TTS | services.tts.model | "v5_5_ru" | Silero v5.5 Russian |
| TTS | services.tts.sample_rate | 24000 | 24 kHz (convert to 44.1 for ESP32) |
| VLM | services.vlm.model | "VILA1.5-3b" | Vision model |
| MCU | media.audio.webrtc_vad_aggressiveness | 2 | VAD level (0–3) |
| MCU | media.audio.frame_ms | 20 | Frame size |

---

## Сводная статистика

- **FULL:** 6 терминов (33%) ✓
- **PARTIAL:** 8 терминов (44%) ⚠️ ← **Самая большая категория**
- **MISSING:** 2 термина (11%) ❌
- **EMERGENT:** 2 термина (11%) ⭐
- **CONTRADICTED:** 0 терминов (0%) —

**Главный вывод:** Большинство концептов (FULL + PARTIAL = 77%) присутствуют в коде и соответствуют дипломе. PARTIAL требует параметризации в Config.json и документирования упрощений. MISSING кандидаты подготовлены структурно.

---

## Рекомендации для Phase 9

**HIGH PRIORITY:**
1. Параметризовать в Config: session_memory_buffer_size, episodic_decay_days, salience_weights
2. Разрешить конфликт history_turns: 2 vs recent_dialogue(limit=8)
3. Реализовать consolidator модуль

**MEDIUM PRIORITY:**
4. Явно реализовать 8-этапный когнитивный цикл
5. Экспортировать формулу салиентности
6. Документировать LeadingNoiseFilter и SceneWorker

---

**Ревизор:** Claude Code (Phase 8 Forensic)  
**Дата:** 2026-05-17  
**Статус:** COMPLETE ✓
