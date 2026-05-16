# CROSS-GRAPH-FINDINGS.md — Перекрёстные находки 3 графов

**Дата:** 2026-05-17 | **Фаза:** 08 Wave 2 synthesis
**Графы:** `Knowledge-graphs/code/`, `Knowledge-graphs/persona/`, `Knowledge-graphs/esp32/`
**Метод:** cross-graph queries — поиск концептов, существующих одновременно в нескольких графах, и обнаружение асимметрий (концепт есть в одном графе, отсутствует в другом).

---

## Persona ↔ Code (AIIM в runtime)

**Главное открытие:** AIIM не «висит» в персоне как декларативный документ — он действительно достигает runtime через 4 точки интеграции.

- **AIIM как god-node в persona** (20 edges) — это пересекается с TuningStore + PromptBuilder + ActionLayer в code-графе. Самый связный узел персоны имеет прямые соответствия в коде.
- **12 аспектов сознания** в Identity.md (Persona Community 3, 5, 6, 7) → **5 mood в action.py** (code-граф): зафиксировано **упрощение 12→5** на границе персоны и runtime. Это не bug, а архитектурное решение (аспекты — статика конфига, mood — динамика реакции).
- **Δ-приоритеты в Tuning.json** → читаются `tuning.py::TuningStore` каждый turn (hot-reload). Persona-граф содержит концепт «приоритет», code-граф — механизм его чтения. Совпадение полное.
- **Persona conditioning механизм:** `PromptBuilder._load_persona()` инжектирует AIIM-формулу в system prompt при каждом запросе. Это runtime-связка между статической persona и динамическим LLM-вызовом.

**Severity:** MEDIUM (упрощение 12→5 нужно документировать); CRITICAL=0.
**Связано с:** Α-17, Α-22, Α-23, Α-25 (см. THEORY-CODE-MATRIX.md).

---

## ESP32 ↔ Code (технофлора в runtime)

**Главное открытие:** ESP32-граф содержит physical-layer концепты, code-граф содержит logical-layer клиентов. Граница между ними — REST API, не HAL.

- **PCA9685** в esp32-графе (Community 14, «PCA9685 PWM Control») → `MCUClient` в `device.py` делает REST API calls (`/scene`, `/pwm`). Концепт «PWM-контроллер моторов» полностью представлен на обоих уровнях.
- **PCM5102A/PAM8403** на уровне HAL (audio out стек) — **не появляются в логическом графе esp32-firmware**, потому что инициализируются на уровне Device Tree / Arduino HAL. Jetson обращается к ним только через `POST :81/speaker` endpoint. Это **осознанная асимметрия Jetson↔ESP32** (Χ-45 PARTIAL/C-path).
- **Health monitoring** (silence_threshold, clip_burst_threshold) в прошивке ESP32 → конфиг `media.audio.esp_health` в `Config.json` определяет thresholds, но Jetson **не использует эти метрики напрямую** в принятии решений. Это **EMERGENT #10** — самонаблюдение тела агента, не связанное с runtime-логикой Jetson.

**Severity:** MEDIUM (асимметрия требует ремарки в ch03.3.1.2); CRITICAL=0.
**Связано с:** Χ-45, EMERGENT #10.

---

## Triangulation: AIIM ↔ Code ↔ ESP32

**Главное открытие:** существует полный путь от персоны до физической реакции — 4 узла, 3 графа.

- **AIIM эмоциональные теги** (persona) → `action.py::Mood` (code) → `device.py::set_scene()` (code) → ESP32 PCA9685 patterns (esp32-firmware).
- Это полный путь от персоны до физической реакции (4 узла, 3 разных графа).
- Подтверждает: **AIIM не «висит» в персоне, а действительно достигает железа**. Это сильное доказательство для тезиса диплома о воплощённости агента (Φ-15).

**Триангуляция доказывает:**
1. Персона (Identity.md AIIM-формула) задаёт направление эмоциональной реакции.
2. Runtime (action.py) дискретизирует это направление в 5 mood-состояний.
3. Действие (device.py → ESP32 REST) преобразует mood в motor scene.
4. Прошивка (PCA9685) выводит PWM в физические моторы технофлоры.

**Severity:** — (positive finding); CRITICAL=0.
**Связано с:** Φ-2 Квазисубъектность, Φ-11 Распределённая агентность, Φ-15 Воплощённость, Χ-44 Инсталляция, Χ-45 Технофлора.

---

## Architectural insights

- **Persona-граф имеет god-node (AIIM), code-граф имеет несколько god-nodes** (VoiceLoopController, EpisodicMemory, MCUClient — см. CONTEXT D-02). Это значит, что персона **более центрирована** концептуально, чем код архитектурно. Код — это сеть равноправных подсистем; персона — формула с одним ядром. Эта асимметрия — концептуально интересная.
- **esp32-граф самый маленький** (Community 13–14 значимые), но содержит **физические узлы**, которые в code-графе представлены только как HTTP-клиенты. Это правильное разделение ответственности: Jetson не должен знать о Device Tree деталях.
- **Memory-слой** (memory.py, episodic.py, memory_search.py) образует собственный кластер в code-графе и **слабо связан с persona-графом** напрямую — это значит, что AIIM пока **не использует историческую память для адаптации Δ-весов** (это домен Phase 11 AIIM Dynamic).
- **Action-слой** (action.py) — единственный мост между AIIM (persona) и ESP32 (firmware). Если этот мост ломается, вся триангуляция рушится. Это указывает на critical path: `action.py` нужно тестировать как integration point, не как unit.
- **EMERGENT #1** (AIIM god-node) и **EMERGENT #13** (AIIM мост Брайдотти↔Латур↔код) — это два самых ценных cross-graph открытия. Оба требуют документирования в ch01–ch03 как ключевая концептуальная ось диплома.

---

## Сводка по cross-graph severity

| Finding | Severity | Path | Артефакт |
|---------|----------|------|----------|
| Упрощение 12→5 (persona ↔ code) | MEDIUM | C (документировать) | CONTRADICTIONS.md / Φ-5 |
| Асимметрия Jetson↔ESP32 (esp32 ↔ code) | MEDIUM | C (документировать) | CONTRADICTIONS.md / Χ-45 |
| Health monitoring изолирован (esp32 ↔ code) | MEDIUM | A (упомянуть в дипломе) | EMERGENT-FEATURES.md / #10 |
| AIIM god-node не визуализирован (persona) | HIGH (для диплома) | A (добавить мини-диаграмму) | EMERGENT-FEATURES.md / #1 |
| Полная триангуляция AIIM→Mood→Device→ESP32 | — (positive) | A (явный мост в ch03) | EMERGENT-FEATURES.md / #13 |

**CRITICAL: 0** — cross-graph анализ не выявил никаких принципиальных конфликтов между тремя слоями. Все находки документируемы или закрываются тривиальными правками.

---

**Анализ:** Phase 8 Wave 2 synthesis, 2026-05-17
