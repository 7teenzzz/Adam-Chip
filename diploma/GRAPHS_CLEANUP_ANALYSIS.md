# Анализ графов на мусорность

**Дата:** 2026-05-16  
**Цель:** выявить ненужный контент в каждом граф для дипломной работы (IMRAD chapter 3)

---

## Сводка по графам

| Граф | Путь | Размер | Nodes | Мусорность | Статус |
|------|------|--------|-------|-----------|--------|
| **System/adam** | `graphify-out/` | 526 KB | 646 | СРЕДНЯЯ | 🟡 Нужна чистка |
| **ESP32 firmware** | `graphify-out-esp32/` | 675 KB | 780 | **ВЫСОКАЯ** | 🔴 Критично! |
| **Persona** | `graphify-out-persona/` | 65 KB | ≤100 | НИЗКАЯ | 🟢 Чистый |
| **Raw docs** | `graphify-out-raw/` | 29 KB | 36 | НИЗКАЯ | 🟢 Чистый |

---

## 1️⃣ graphify-out-esp32 — **КРИТИЧНО ГРЯЗНЫЙ** 🔴

### Что там находится

- **65 файлов кода** (~354K слов) — полная прошивка ESP32-S3
- **780 nodes · 1262 edges · 42 communities**

### Мусор, выявленный

#### ❌ Дублирующиеся тесты и сессии

**Communities 3–10:** `"Video Latency Metrics (session A–G)"`

Каждая имеет по 45 nodes с одинаковыми полями:
```
- counters_delta
- buffer_realloc_count
- copy_frame_miss_count
- frame_skipped_due_stale
- latest_mutex_timeout_count
- no_new_frame_poll_count
- slow_send_strike_strike_count
- duration_sec
[+37 more per session]
```

**Статус:** Это бенч-данные из 7 отдельных тестовых сессий. Для дипломной работы нужны только **агрегированные метрики**, а не per-session логи.

**Рекомендация:** Выбросить communities 3–10, оставить только `summary` метрику.

---

#### ❌ Служебные функции логирования и диагностики

**God nodes (top-4):**
- `bootLogf()` — 32 edges (диагностическое логирование)
- `bootLog()` — 23 edges (то же самое)
- `sendJson()` — 24 edges (протокольная функция)
- `sendError()` — 18 edges (обработка ошибок)

Плюс целая **Community 2** — `"Boot Diagnostics and Init"`  (40 nodes):
- `beginBootDiagnostics()`
- `bootSetStage()`
- `bootSetLastInitError()`
- `bootClearLastInitError()`
- и т.д.

**Статус:** Это всё служебное, никому в диплом не нужно. Диплом должен описывать **what the system does**, а не **how to debug it**.

**Рекомендация:** Выбросить Community 2 целиком. Оставить только архитектурно-значимые части: обработчики запросов, основные компоненты.

---

#### ❌ Документация как часть граф-узлов

**Community 1** — `"Firmware Docs and API Reference"` (52 nodes):
- `AdamsServer Claude Code Context`
- `AdamsServer ESP32-S3 Firmware`
- `AdamsServer Windows COM7 Runbook`
- `GET /api/audio/clip Endpoint`
- и т.д.

**Статус:** Это документационные комментарии из кода, которые попали в граф. Графу не нужны, но это не вредит дипломной работе — просто шум.

**Рекомендация:** Можно выбросить, если нужно сжать граф. Или оставить как справку.

---

#### ❌ Метрики для каждого видеозахвата (микрометрики)

Community 0 (93 nodes) содержит API обработчики вроде:
```
- videoLatencyReset()
- appendCameraJson()
- appendLatencySummaryJson()
- resolveDutyFromUpdate()
```

Многие из этих функций — микро-уровневые метрики для отладки видеопотока. Нужна ли каждая функция в дипломе? Нет.

**Рекомендация:** Агрегировать до уровня **"Camera streaming pipeline"**, а не описывать каждый обработчик.

---

### Что оставить из ESP32

**Значимые компоненты (нужны для дипломной работы):**
1. ✅ **Dual HTTP Server** (port 80 + port 81) — архитектурный выбор
2. ✅ **Camera capture pipeline** (OV5640 → MJPEG stream)
3. ✅ **Mic audio capture** (INMP441 × 2 → I2S → WebRTC VAD)
4. ✅ **Speaker playback** (PCM5102A)
5. ✅ **PCA9685 PWM control** (моторный слой)
6. ✅ **OTA firmware update** (как механизм обновления)
7. ✅ **Network failover** (W5500 Ethernet + Wi-Fi fallback)

**Выбросить:**
- ❌ Все serve-диагностические функции (bootLog*, bootSetStage и т.д.)
- ❌ Все дублирующиеся session-метрики
- ❌ Per-frame метрики для отладки
- ❌ Вспомогательные JSON-сборщики

---

## 2️⃣ graphify-out (System/adam) — **СРЕДНЕ ГРЯЗНЫЙ** 🟡

### Что там находится
- **30 файлов Python** (~0 words в отчёте, но это ошибка, явно больше)
- **646 nodes · 1090 edges · 47 communities**

### Мусор, выявленный

#### ❌ Метрики и логирование (возможно)

Из README проекта видно:
- `System/adam/metrics.py` — собирает timing, tokens, memory metrics
- `System/adam/log_viewer.py` — always-on log HTTP сервис

Нужны ли они в дипломной работе?

**metrics.py:**
- Нужно для главы 3.4 (тестирование и метрики)
- Но сам файл — служебный, детали реализации не нужны
- Можно свернуть до одной строки: "метрики собираются через metrics.py"

**log_viewer.py:**
- Это вспомогательный инструмент для оператора, не часть архитектуры
- **Выбросить из архитектурного описания**

#### ❌ Configuration loading (System/adam/config.py)

Нужен ли в дипломе весь процесс загрузки Config.json? Нет.

**Что нужно:**
- Факт, что есть Config.json
- Какие параметры в нём (это уже в диплом-главе 3.2)

**Что не нужно:**
- Реализация config.py
- Как именно парсятся override через env-переменные

---

#### ❌ Возможные unit tests

Нужно проверить, есть ли в `System/adam/` папка `tests/` или тесты в самих файлах.

Если есть — выбросить из архитектурного графа. Тесты — это верификация, а не архитектура.

---

### Что оставить из System/adam

**God nodes (критичные):**
1. ✅ `VoiceLoopController` — 42 edges (основной контроллер)
2. ✅ `EpisodicMemory` — 29 edges (архитектура памяти)
3. ✅ `MCUClient` — 25 edges (коммуникация с ESP32)
4. ✅ `ActionLayer` — validation and motor commands
5. ✅ `SceneWorker` — VLM scene analysis worker
6. ✅ `SessionWatcher` — session lifecycle
7. ✅ `SessionAccumulator` — dialogue accumulation

**Выбросить или свернуть:**
- ❌ `config.py` — просто факт о наличии конфига
- ❌ `log_viewer.py` — инструмент оператора, не архитектура
- ❌ `metrics.py` — агрегировать в раздел "Metrics collection"
- ❌ `api_runtime.py` — HTTP обёртка, не архитектура
- ❌ Любые тесты

---

## 3️⃣ graphify-out-persona — **ЧИСТЫЙ** 🟢

### Что там находится
- Identity.md, AIIM, Memory параметры персонажа
- **Это ВСЕ нужны для дипломной работы**

**Статус:** 0% мусора. Оставить как есть.

---

## 4️⃣ graphify-out-raw — **ЧИСТЫЙ** 🟢

### Что там находится
- Jetson AI Lab документация
- Технологические стеки (Silero, CUDA, VILA, WhisperX)
- Это reference материалы

**Статус:** 0% мусора. Это справочный материал для дипломной работы (источники). Оставить как есть.

---

## План чистки

### Фаза 1: Анализ зависимостей

Перед удалением нужно проверить:
1. Какие узлы из "мусорных" компонент используются архитектурно значимыми узлами?
2. Какие графы-ссылки между компонентами изменятся после чистки?

**Команда для анализа:**
```bash
/graphify query "what imports metrics.py"
/graphify query "what imports log_viewer.py"
/graphify query "bootLogf dependencies"
```

### Фаза 2: Создание cleaned-графов

После анализа создать:
- `graphify-out-system-clean/graph.json` (без metrics, log_viewer, config.py)
- `graphify-out-esp32-clean/graph.json` (без diagnostic functions, session-метрик)

### Фаза 3: Верификация

Для каждого cleaned-графа убедиться:
- [ ] Все 8 критериев квазисубъектности остаются покрыты (глава 2.1)
- [ ] God nodes изменились ожидаемо
- [ ] Не потеряны критичные архитектурные связи

---

## Для дипломной работы потребуется

**Из graphify-out (System/adam):**
- VoiceLoopController, EpisodicMemory, MCUClient
- Perception & Action layer
- Event bus, Memory consolidation
- Session management

**Из graphify-out-esp32:**
- Dual HTTP server architecture
- Camera pipeline (OV5640 → MJPEG)
- Audio capture (INMP441 → I2S)
- Motor control (PCA9685 PWM)
- Network failover

**Из graphify-out-persona:**
- AIIM structure
- Identity model
- Memory tuning parameters

**Из graphify-out-raw:**
- Tech stack dependencies
- Hardware constraints
- CUDA/PyTorch Jetson compatibility

---

## Дальнейшие действия

1. ✅ Прочитать этот анализ
2. 🔧 Запустить graphify queries для проверки зависимостей
3. 🗑️ Создать cleaned-графы
4. ✔️ Верифицировать на соответствие 8 критериям квазисубъектности
5. 📝 Использовать cleaned-графы для writing главы 3

---

**Следующий шаг:** Запустить анализ зависимостей для System/adam и ESP32 графов?
