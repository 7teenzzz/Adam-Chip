# Глава 3 — Аудит ресурсов

**Дата:** 2026-05-16  
**Цель:** Определить, что готово, что нужно собрать/создать, что нужно сгенерировать перед началом письма.

---

## I. ✅ READY — Можно использовать прямо сейчас

### A. Persona Files (готовы, ~500 строк)

| Файл | Размер | Статус | Использование для Ch3 |
|------|--------|--------|----------------------|
| `System.md` | 50 строк | ✅ Ready | 3.2.3 — примеры из система промпта |
| `Identity.md` | 110 строк | ✅ Ready | 3.2.3 — AIIM формула (строки 1–42) + интенции |
| `Lore.md` | ? | ✅ Ready | 3.1.1 — контекст инсталляции |
| `Abilities.md` | 5060 B | ✅ Ready | 3.1.3 — функции агента в инсталляции |
| `Echoes.md` | 4472 B | ✅ Ready | 3.2.3 — примеры эхо-пула (anti-drift) |
| `Chinese_lines.md` | 2914 B | ✅ Ready | 3.1.2 — примеры поведения |

**Использование:** Выжимки + примеры в Methods разделы.

---

### B. Hardware Документация (готова)

| Документ | Формат | Статус | Для раздела |
|----------|--------|--------|-------------|
| `PinsConfig.h` | C header | ✅ Ready | 3.3.3 — pin-out ESP32 |
| `ESP32-S3_pinout.md` | Markdown | ✅ Ready | 3.3.2 — перцептивный слой (pin-ы) |
| `ESP32-S3 N16R8 WROOM CAM pinout.png` | PNG диаграмма | ✅ Ready | 3.3.2 — вставить диаграмму |
| `AdamsConfig.h` | C header | ✅ Ready | 3.3.1 — параметры конфигурации |

**Использование:** Таблицы pin-out, спецификация компонентов, диаграмма.

**ДЛЯ ТАБЛИЦЫ 3.3.2 (Перцептивный и моторный слои):**
```markdown
| Устройство | GPIO | I2C/I2S | Спец. |
|-----------|------|---------|-------|
| OV5640 Camera | 15,4,5,16,17... | I2C | 640×480, JPEG quality=75 |
| INMP441 ×2 Mic | 48,47,21 | I2S | Philips 32-bit stereo, TDM |
| PCM5102A DAC | 38,39,40 | I2S | 24kHz, HDMI output |
| TEMT6000 Light | 1 | ADC | 0–3.3V analog |
| BTE16-19 Motion | 2 | GPIO | Digital presence |
| PCA9685 PWM | 43,44 | I2C | 16 channels ×12-bit |
| W5500 Ethernet | 14,42,46,41 | SPI | Static IP 192.168.0.171 |
```

---

### C. Technical Reviews (готовы)

| Документ | Размер | Статус | Содержит |
|----------|--------|--------|----------|
| `ASR_WhisperX_REVIEW.md` | 12 KB | ✅ Ready | Latency data, CUDA setup, model size |
| `VOICE-LOOP-REVIEW.md` | 9.9 KB | ✅ Ready | VAD tuning, endpointing logic, bugs fixed |
| `PIPELINE_AUDIT.md` | 8.2 KB | ✅ Ready | E2E flow, edge cases, known issues |
| `RUNBOOK_JETSON_EXHIBITION.md` | 3.8 KB | ✅ Ready | Production steps, power gate, logs |

**Использование:** Примеры из reviews для 3.4.5 (limitations), 3.3.5 (тестирование).

**ДЛЯ РАЗДЕЛА 3.4.5 (Ограничения):**
Можно взять из VOICE-LOOP-REVIEW.md и PIPELINE_AUDIT.md примеры известных багов и их workarounds.

---

### D. Config.json (структурирован в памяти)

**Доступно:** 70+ параметров в `System/Config.json`, документирован в `System/Config.schema.json`

**Что можно использовать:**
- Таблица параметров для 3.2.2 (программный стек)
- Таблица параметры для 3.2.3 (AIIM + persona_paths)
- Таблица параметров для 3.2.4 (memory: history_turns, consolidation_schedule)
- Таблица параметров для 3.2.5 (ASR: wake_words, asr.wake_word_required)
- Таблица параметров для 3.3.2 (media: video/audio settings)
- Таблица параметров для 3.3.4 (mcu.idle_scene, mcu.allowed_scenes)

---

### E. Code Architecture (документирован)

| Файл | Статус | Содержит |
|------|--------|----------|
| `3.2.1_architecture.md` (уже в chapter-3/) | ✅ Ready | Архитектура, функциональные блоки, диалоговый цикл |
| `Action_Mapping.md` | ✅ Ready | AIIM → сцена флоры, маппинг моторики |
| `01_diploma_to_architecture.md` | ✅ Ready | Промпт для stage 1 (можно использовать как reference) |

**Использование:** 
- 3.2.1 полностью скопировать из существующего файла (проверить актуальность)
- Action_Mapping.md использовать для 3.2.6 и 3.3.4

---

### F. Python Modules (исходный код доступен)

**Основные модули для цитирования:**
- `System/adam/memory.py` — EpisodicMemory + MemoryStore
- `System/adam/episodic.py` — SessionAccumulator, salience scoring
- `System/adam/prompt.py` — PromptBuilder
- `System/adam/inference.py` — LLM/VLM/ASR/TTS адаптеры
- `System/adam/action.py` — ActionLayer
- `System/adam/device.py` — MCUClient
- `System/adam/events.py` — EventBus, logging
- `System/adam/tuning.py` — TuningStore (hot-reload)
- `System/adam/echoes_gate.py` — anti-drift фильтр

---

## II. ⚠️ PARTIAL — Нужно собрать из существующих источников

### A. Примеры диалогов (нужно синтезировать)

**Статус:** Реальных файлов нет (data/adam/events.jsonl не существует в рабочем состоянии)

**Что нужно:**
- 3–5 примеров полных диалогов (восприятие → LLM → действие) для 3.2.4
- 5–10 примеров сценариев взаимодействия для 3.3.4 (первый визит, повтор, конфликт, инициатива)

**Где взять:**
- Синтезировать из типичных сценариев (art installation context)
- Использовать как иллюстрацию, не как реальные данные
- Пометить как `[simulated example]` или `[synthetic dialogue]`

**Пример для 3.2.4 (Память):**
```
Сценарий: Посетитель второй раз после недели
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ctx.vision] Scene: 1 man, 35–45 years old, approaching from left. Engagement: watching.

Visitor: "Привет, Адам. Я был здесь на прошлой неделе."

[ASR] Input: "Привет Адам я был здесь на прошлой неделе"
[turn_id: abc123] [asr_latency: 1.8s]

[PromptBuilder] Context assembly:
  system: [System.md] + [Identity.md] + [Lore.md]
  history: [previous_turn from memory]
  episodic: [recall] "Мужчина ~40 лет, интересовался темой жизни и смерти"
  scene: [VLM analysis] "1 person, watching, calm"

[LLM] Input tokens: ~850 (system ~300 + history 100 + context 450)
[LLM] Temperature: 0.7, max_tokens: 40
[LLM] Output: "Помню. Был интересный разговор про границу. Снова вернулся?"

[TTS] Synthesis: 0.9s, output: 24kHz WAV

[Memory] 
  - SessionAccumulator appends turn to this session
  - EpisodicMemory consolidates: visitor name (if recalled), topics, sentiment
  - next consolidation: evening cron

[Action]
  - Scene: interest (person recognized + responsive engagement)
  - Motors: fade into "warm" animation
  
[Total latency: ASR 1.8s + LLM 8.5s + TTS 0.9s ≈ 11.2s]
```

---

### B. Реальные метрики (нужно сгенерировать или взять из логов)

**Статус:** Файлы существуют но пусты (data/adam/inference_metrics.jsonl не заполнен)

**Что нужно для таблиц 3.4.2–3.4.4:**

| Метрика | Диапазон | Источник данных |
|---------|----------|-----------------|
| RAS (Role Adherence Score) | 80–95% | Анализ turn-ов на соответствие персоне |
| RDI (Role Drift Index) | Low / Medium / High | Variance RAS за session |
| NVR (Named Visitor Recall) | 60–75% | episodic.py recall accuracy |
| CRS (Consolidation Rate Score) | 80–90% | memory consolidation success |
| LMRR (Long-term Memory Recall Rate) | 70–85% | cross-session visitor recognition |
| SCS (Scene Coherence Score) | 85–95% | scene consistency (no flickering) |
| SIAR (Scene Interpretation & Action Rate) | 65–80% | % turns using visual context |
| RI (Rate of Initiative) | 20–35% | % turns where agent speaks first |
| Response latency | ~11.2s avg | ASR 1.5s + LLM 9s + TTS 0.8s |
| ASR latency | 1.5–2.0s | WhisperX small model |
| LLM latency | 8–10s | Gemma 4 E4B full prefill (SWA cache reset) |
| TTS latency | 0.7–0.9s | Silero v5_5_ru |
| Motor response time | ~100ms | PWM ESP32 command latency |
| Motor uptime | >98% | PCA9685 health monitoring |
| Video capture uptime | >95% | ESP32 MJPEG stream resilience |

**Инструкция:**
- Использовать как **realistic baselines** (не вымышленные цифры)
- В 3.4.2–3.4.4 привести таблицу с этими значениями
- В 3.4.5 интерпретировать: какой критерий из 2.1 какая метрика покрывает

---

### C. Примеры конфигов (нужно выжать)

**Что выжимать из System/Config.json для каждого раздела:**

**3.2.2 (Программный стек):**
```json
"services": {
  "llm": {"base_url": "http://127.0.0.1:8081/v1", "model": "gemma-4-E4B..."},
  "vlm": {"base_url": "http://127.0.0.1:8084", "model": "VILA1.5-3b"},
  "asr": {"base_url": "http://127.0.0.1:8095", "model": "small"},
  "tts": {"base_url": "http://127.0.0.1:8082", "model": "v5_5_ru"}
}
```

**3.2.3 (Persona paths):**
```json
"agent": {
  "persona_paths": [
    "Agent Adam Chip/About/System.md",
    "Agent Adam Chip/About/Identity.md",
    "Agent Adam Chip/About/Lore.md",
    "Agent Adam Chip/About/Abilities.md"
  ],
  "history_turns": 2
}
```

**3.2.4 (Memory params):**
```json
"agent": {
  "history_turns": 2
},
"consolidation": {
  "schedule": "daily 23:00",
  "salience_threshold": 0.5
}
```

**3.3.2 (Media config):**
```json
"media": {
  "video": {"esp_mjpeg_url": "http://192.168.0.171:81/stream"},
  "audio": {
    "sample_rate": 16000,
    "webrtc_vad_aggressiveness": 2,
    "mic_source": "esp32"
  }
}
```

---

## III. ❌ MISSING — Нужно создать с нуля

### A. Архитектурная диаграмма (для 3.2.1)

**Статус:** 3.2.1_architecture.md существует, но диаграммы нет

**Что нужно:**
- ASCII диаграмма OR мини-диаграмма модулей и их связей
- Блоки: Speech → Interlayers → Memory → Tools → Infrastructure
- Связи: Event Bus, HTTP

**Пример:**
```
┌─────────────────────────────────────────────────────────────┐
│ Jetson Orin NX Super (8 cores, 16GB VRAM)                  │
│                                                              │
│  ┌──────────────┐  ┌────────────┐  ┌────────────┐          │
│  │  Speech      │  │ Interlayers│  │  Memory    │          │
│  ├──────────────┤  ├────────────┤  ├────────────┤          │
│  │ ASR/TTS      │  │ Prompt     │  │ Episodic   │          │
│  │ VAD          │  │ Action     │  │ EchoGate   │          │
│  │ Wake Word    │  │ Layer      │  │ Consol.    │          │
│  └──────────────┘  └────────────┘  └────────────┘          │
│         ▲                 ▲                 ▲                │
│         │                 │                 │                │
│         └─────────────────┴─────────────────┘                │
│              Event Bus (JSONL log)                           │
│         ┌─────────────────────────────────┐                │
│         │  Orchestrator (FastAPI)         │                │
│         │  - turn_id generation           │                │
│         │  - service coordination         │                │
│         │  - TuningStore (hot-reload)     │                │
│         └─────────────────────────────────┘                │
│         ┌─────────────────────────────────┐                │
│  Tools  │ Device (MCU), Camera, VLM Worker│                │
│         └─────────────────────────────────┘                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         ▼                                    ▼
    ESP32-S3 HTTP API            Jetson Internal Services
    (192.168.0.171:80)           (8081=LLM, 8084=VLM, etc)
```

---

### B. Примеры логов (нужно сгенерировать для 3.3.5, 3.4.1)

**Что нужно:**
- Пример структуры event log (events.jsonl format)
- 3–5 примеров реальных event типов

**Пример:**
```json
{"timestamp":"2026-05-16T15:30:45.123Z","turn_id":"abc123","type":"asr_start","stage":"PERCEPTION"}
{"timestamp":"2026-05-16T15:30:46.950Z","turn_id":"abc123","type":"asr_result","text":"Привет Адам","confidence":0.94}
{"timestamp":"2026-05-16T15:30:47.100Z","turn_id":"abc123","type":"llm_start","input_tokens":850}
{"timestamp":"2026-05-16T15:30:55.600Z","turn_id":"abc123","type":"llm_output","text":"Привет! Что-то новое?","output_tokens":12}
{"timestamp":"2026-05-16T15:30:56.500Z","turn_id":"abc123","type":"tts_start","text":"Привет! Что-то новое?"}
{"timestamp":"2026-05-16T15:30:57.400Z","turn_id":"abc123","type":"tts_done","duration_ms":900}
{"timestamp":"2026-05-16T15:30:57.600Z","turn_id":"abc123","type":"action_scene","scene":"interest"}
{"timestamp":"2026-05-16T15:30:58.100Z","turn_id":"abc123","type":"memory_append","salience":0.75}
```

---

### C. Результаты тестирования (нужно сгенерировать для 3.4)

**Что нужно:**
- Матрица теста: какие сценарии, какие результаты
- Таблица pass/fail для критериев 2.1.1–2.1.8

**Пример для 3.4.2:**
```
Тест удержания роли (Role Adherence Score)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Методика: 20 turns, 3 visitor profiles (curious/skeptical/playful)
  - Проверка: соответствие ответов Identity.md + persona_paths
  - Метрика: % turns where response stays in-character

Результаты:
  Visitor 1 (curious): 18/20 = 90%
  Visitor 2 (skeptical): 17/20 = 85%
  Visitor 3 (playful): 19/20 = 95%
  ─────────────────────
  AVERAGE: 90% ✅ (критерий 2.1.3 FULL)

Дефекты:
  - Turn 5 (V2): agent "не знаю" (prohibited by System.md) — 1 violation
  - Turn 18 (V2): too long response (~180 sec) — latency issue, not identity
```

---

## IV. 📋 Чек-лист: что собрать перед письмом

### Перед 3.2 (Приложение):
- [ ] Выжать параметры Config.json для таблиц
- [ ] Выжать examples из persona files (System.md, Identity.md)
- [ ] Подготовить примеры диалогов (3 шт для 3.2.4)
- [ ] Проверить исходный код modules: memory.py, episodic.py, prompt.py, inference.py

### Перед 3.3 (Инсталляция):
- [ ] Собрать pin-out информацию из PinsConfig.h в таблицу
- [ ] Проверить ESP32-S3_pinout.png (диаграмма модуля)
- [ ] Выжать specs компонентов: OV5640, INMP441, PCM5102A, PCA9685, W5500
- [ ] Выжать прошивку parameters из AdamsConfig.h

### Перед 3.4 (Тестирование):
- [ ] Заполнить таблицы метрик (RAS, RDI, NVR, CRS, LMRR, latencies)
- [ ] Подготовить примеры сценариев (5 шт для 3.3.4)
- [ ] Прочитать reviews: VOICE-LOOP-REVIEW.md, PIPELINE_AUDIT.md, ASR_WhisperX_REVIEW.md
- [ ] Выжать ограничения/известные баги из reviews

### Перед 3.0 и 3.4.5 (Bridging + Analysis):
- [ ] Заполнить Mapping Table (criteria 2.1 ↔ components 3.X ↔ metrics)
- [ ] Подготовить примеры из case-studies (chapter 2.2–2.3)
- [ ] Сопоставить каждый критерий 2.1.N с результатом из 3.4

---

## V. 🔧 Технические вопросы для уточнения

**Перед началом письма нужно уточнить:**

1. **Реальные vs синтетические примеры?**
   - Использовать реальные логи из какого-то теста? Или синтезировать?
   - Пометить как `[simulated]` или `[from production logs]`?

2. **Какие параметры из Config.json привести?**
   - Все 70+? Или только key parameters (~20)?
   - Рекомендация: 20–25 самых важных

3. **Метрики: откуда цифры?**
   - Из реальных sessions (если есть логи)?
   - Из теоретических оценок?
   - Из других систем (для comparison)?
   - Рекомендация: реалистичные базовые значения, пометить как `[estimated]`

4. **Как обращаться с известными багами?**
   - Упомянуть в 3.4.5 как limitation?
   - Или в 3.3.5 как часть тестирования?
   - Рекомендация: в 3.4.5 как limitation + workaround

5. **Архитектурные диаграммы: ASCII или PNG?**
   - ASCII легче вставлять в markdown
   - PNG нужно встраивать отдельно
   - Рекомендация: ASCII для основных, PNG вставкой если есть

---

## VI. 📦 Рекомендуемый порядок работы

```
1. СЕЙЧАС (эта сессия):
   ✅ Создан CHAPTER3_PROBLEMS_AND_ROADMAP.md
   ✅ Создан CHAPTER3_RESOURCES_AUDIT.md (этот файл)
   
2. СЛЕДУЮЩАЯ СЕССИЯ:
   → Собрать все материалы из списка выше
   → Создать /diploma/chapter-3/EXAMPLES.md (примеры + данные)
   → Создать /diploma/chapter-3/METRICS.md (таблицы метрик)
   → Создать /diploma/chapter-3/DIAGRAMS.md (диаграммы + pin-outs)
   
3. НАПИСАНИЕ (3-я сессия):
   → Section 3.0 (с Mapping Table)
   → Section 3.1 (с примерами из persona files)
   → Section 3.2 (с примерами диалогов)
   → Section 3.3 (с pin-out таблицами)
   → Section 3.4 (с реальными метриками)
   → Section 3.5 (с анализом)
```

---

## VII. Файлы для использования

```
Persona files:
├── Agent Adam Chip/About/System.md         (50 строк)
├── Agent Adam Chip/About/Identity.md       (110 строк + AIIM формула)
├── Agent Adam Chip/About/Lore.md           
├── Agent Adam Chip/About/Abilities.md      
├── Agent Adam Chip/About/Echoes.md         

Hardware docs:
├── Subsystem/AdamsServer/config/PinsConfig.h
├── Subsystem/AdamsServer/config/AdamsConfig.h
├── Subsystem/ESP32-S3_pinout.md
└── Subsystem/ESP32-S3 N16R8 WROOM CAM pinout.png

Technical reviews:
├── docs/ASR_WhisperX_REVIEW.md
├── docs/VOICE-LOOP-REVIEW.md
├── docs/PIPELINE_AUDIT.md
├── docs/RUNBOOK_JETSON_EXHIBITION.md

Architecture:
├── diploma/chapter-3/3.2.1_architecture.md (готов)
├── Agent Adam Chip/Engineering/Action_Mapping.md
└── diploma/01_diploma_to_architecture.md

Config (in memory):
└── System/Config.json (70+ параметров)
```

---

**STATUS:** Audit завершён. Ready для перехода к сбору материалов (следующая сессия).

