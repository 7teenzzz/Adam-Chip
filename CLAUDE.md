# Adam Chip — Claude Code Instructions

See @README.md for project overview and @System/Config.json + @System/Config.schema.json for runtime parameters. Agent behavior protocol: @docs/AGENT-PROTOCOL.md

**Язык общения с пользователем: русский.** Code comments: English.

## Reading Order — с чего начать новому агенту

Читать в порядке убывания детализации:

| Уровень | Файл | Что даёт |
| ------- | ---- | -------- |
| 0 — Entry point | `CLAUDE.md` (этот файл) | Инварианты, gotchas, quick start |
| 1 — Overview | [README.md](README.md) | Архитектура, inference stack, структура |
| 2 — Status | [.planning/STATE.md](.planning/STATE.md) | Что сейчас активно, текущая фаза |
| 3 — Plan | [ROADMAP.md](.planning/ROADMAP.md) · [REQUIREMENTS.md](.planning/REQUIREMENTS.md) | История фаз, бэклог |
| 4 — Detail | `.planning/phases/NN-*/NN-SUMMARY.md` | Итоги конкретных фаз |
| 4+ — Code graph | [Knowledge-graphs/code/GRAPH_REPORT.md](Knowledge-graphs/code/GRAPH_REPORT.md) | Граф System/adam/ + Orchestrator + Speech (автогенерация) |
| 4+ — Docs graph | [Knowledge-graphs/docs/GRAPH_REPORT.md](Knowledge-graphs/docs/GRAPH_REPORT.md) | Граф внешних документов: Silero, Jetson AI Lab |
| 4+ — Persona graph | [Knowledge-graphs/persona/GRAPH_REPORT.md](Knowledge-graphs/persona/GRAPH_REPORT.md) | Граф персонажа Адам Чип: AIIM, Memory, Identity |

Числовые параметры — только в `System/Config.json` и `System/Config.schema.json`.

**Если вы не на ветке `main`:** первым делом прочитайте `BRANCH.md` в корне репозитория — там цель ветки, затрагиваемые файлы и условия мёржа. Шаблон и конвенция: `docs/BRANCH-template.md`.

## Non-obvious invariants — MUST NOT violate

1. **LLM = чистый русский текст.** Никакого JSON, markdown, code blocks в ответе LLM. Action layer работает отдельно парсингом вне LLM.
2. **Action failure ≠ silence.** Если action layer падает → `no_action`, голос всё равно произносится.
3. **Inference только на Jetson.** ESP32 MJPEG и ESP32 mic — диагностика/резерв, не AI-поток.
4. **Power gate** — exhibition mode требует `nvpmodel -m 0` + `jetson_clocks`. Проверяется автоматически при старте.
5. **half_duplex_mute = true** — mic всегда заглушается во время TTS playback.
6. **Wake word «адам»** — в exhibition mode ASR не реагирует без него.

## Gotchas (non-obvious)

- **Gemma 4 E4B — thinking model.** Без флага `--reasoning off` весь output уходит в `reasoning_content`, поле `content` пустое. Флаг прописан в `deploy/systemd/adam-llm.service` — не убирать.
- **SWA cache (ожидаемо медленно).** Gemma 4 E4B = hybrid attention (global + sliding window 512). KV-кэш сбрасывается между turn'ами → full prefill ~2781 токенов каждый раз → ~9с на turn. Это норма, не баг.
- **curl + v2ray proxy.** v2ray (порт 10808) перехватывает localhost-запросы. При диагностике всегда: `curl --noproxy '*' http://127.0.0.1:…`
- **Python HTTP к ESP32 — только через `_NO_PROXY_OPENER`.** Тот же v2ray перехватывает `urllib.request.urlopen()` через env-переменные `http_proxy`/`HTTP_PROXY` и **leak'ит сокеты** к ESP32:81 (4 слота firmware быстро исчерпываются → mic stream висит). Любой `urlopen`/`Request` к ESP32 в Python должен использовать локальный `_NO_PROXY_OPENER = build_opener(ProxyHandler({}))`. Уже сделано в [System/adam/device.py](System/adam/device.py), [System/adam/inference.py](System/adam/inference.py) (`_play_wav_bytes_to_esp32_sync`), [System/Orchestrator.py](System/Orchestrator.py) (`_run_esp32`). systemd-юнит `adam-orchestrator.service` дополнительно ставит `NO_PROXY=192.168.0.0/24,127.0.0.1,localhost` как defence-in-depth. Для `httpx` использовать `httpx.Client(..., trust_env=False)`.
- **Silero + Jetson PyTorch.** Порядок обязателен: сначала Jetson-compatible wheel PyTorch, потом `pip install --no-deps "silero>=0.5.0"`. Dependency resolver ломает Jetson PyTorch.
- **WhisperX + Jetson CUDA.** `ctranslate2` для aarch64 нужно собирать из исходников с флагом CUDA — pip-пакет CPU-only. Скрипт диагностики: `scripts/adam_asr_cuda_check.sh`. Аналогично Silero: сначала Jetson-compatible PyTorch, затем `pip install --no-deps "whisperx"`. VAD в пайплайне — WebRTC VAD (`webrtc_vad.py`, CPU-only, без PyTorch), не Silero.
- **LLM model ID mismatch.** llama-server отдаёт имя модели с `.gguf` суффиксом, в Config.json без суффикса — это нормально, сервер игнорирует поле `model` в запросах.
- **Аудио устройства.** TTS output = `plughw:1,3` (HDMI, card 1 HDA NVIDIA). Mic input = `pulse` (PulseAudio → WebCamera card 3). hw:1,0 (Jetson APE I2S) физически не работает — не отдаёт PCM данные. hw:0,0 для input — неправильно.
- **ESP32 IP.** Статический IP = `192.168.0.171`.

## Agent Behavior Rules — для всех агентов

### File Structure & Organization

**Rule:** Файлы организуются **логически по доменам и назначению**, не по типам. Папки создаются при необходимости.

**Why:** Проект охватывает multiple domains (inference, speech, hardware, UI, testing, docs). Flat structure становится неуправляемой.

**How to apply:**

- Перед добавлением/редактированием файла: «Какой primary purpose? Есть ли логическая группировка для этого?»
- Создавать директории, когда:
  - 3+ файлов одной тематики (напр. speech-related → `Speech/`)
  - Конфиги подсистемы (напр. ESP32 → `Subsystem/AdamsServer/config/`)
  - Тесты модуля (напр. inference tests → `tests/inference/`)
  - Утилиты для конкретной цели (напр. диагностика → `scripts/diagnostics/`)

**Существующая структура:**

- `System/adam/` — core inference pipeline (config, inference, prompt, action, device, memory)
- `System/Speech/` — TTS/ASR adapters
- `Subsystem/AdamsServer/` — ESP32 firmware
- `scripts/` — deployment, diagnostics, management
- `docs/` — protocols, runbooks, branch templates
- `data/` — runtime state (memory.sqlite3, events.jsonl, sounds)
- `Engineering/` — consolidation & analysis tools
- `Agent Adam Chip/` — persona (Identity, Lore, Abilities, Tuning)
- `tests/` — automated test suites
- `.planning/` — GSD artifacts (ROADMAP.md, STATE.md, phases/*)

### Config-First Principle

**Rule:** Все числовые параметры и флаги должны быть в `System/Config.json` и `System/Config.schema.json`. Никогда не хардкодить числовые значения в коде.

**Why:** Hot-reload, единая точка управления, изменения без пересборки/рестарта кода.

**How to apply:**

- Если код содержит числовое значение (timeout, threshold, delay, count) → вынести в Config.json
- Обновить Config.schema.json с описанием параметра
- Тесты могут переопределять через env-переменные: `ADAM_CONFIG_OVERRIDE={...}`

### Language & Communication Style

**Rule:** Общение с пользователем — **русский язык, простые объяснения, без жаргона без предварительного контекста.** Code comments: English.

**Why:** Пользователь hardware engineer/artist, проект на русском. Простота = доступность.

**How to apply:**

- Используй русские термины вместо английских где возможно (напр. "инференция" не "inference", "микрофон" не "mic")
- Объясняй через аналогии, избегай абстракций первого упоминания
- Технические детали приветствуются, если контекст это поддерживает
- Если нужен код — объясни на русском, код остаётся на английском

### Excluded Technologies

**Ollama — запрещена.** Только:

- `llama.cpp` (port 8081, OpenAI-compatible API)
- Rule-based fallback для offline scenarios
- Причина: Ollama добавляет лишний layer, в проекте используется llama.cpp напрямую

**Note on PyTorch installation:** см. раздел "Gotchas" для деталей порядка установки Jetson-compatible PyTorch перед Silero/WhisperX. Неправильный порядок ломает CUDA/inference стек.

### Repository Cleanliness

**Никогда не коммитить:**

- `.env` файлы и `PrivateConfig.h`
- `*.gguf` модели (слишком большие)
- `data/` директория (runtime state)
- Temporary/debug файлы

**Коммит после каждой завершённой фазы:**

- Использовать `/commit-push phase-N topic` (Haiku sub-agent для git)
- Atomic commits с ясными сообщениями (почему, не что)

---

## GSD-пайплайн — правила агента

Полный протокол: @docs/AGENT-PROTOCOL.md → раздел «Пайплайн фазы».

### Обязательный scaffold (единственное жёсткое правило)

При создании **любой** фазы — сразу создать `.planning/phases/NN-name/NN-CONTEXT.md`.
Без этого история фазы теряется (прецедент: Фазы 6A–6B выполнены без артефактов → ретробэкфилл 2026-05-16).

### Стандартный порядок для крупной задачи (>2 файлов)

```text
/gsd-discuss-phase N  →  /gsd-plan-phase N  →  /gsd-execute-phase N
  → /commit-push phase-N topic  →  /gsd-extract-learnings N
```

### Автономный режим (bypass / несколько фаз без участия пользователя)

После каждой завершённой фазы → вызвать `/commit-push <phase-N topic>`.

- `/commit-push` спавнит Haiku sub-agent для git операций (add → commit → push)
- Sonnet не делает git-команды напрямую — только делегирует
- Push включён по умолчанию; `--no-push` если фаза помечена WIP в PLAN.md

**Что коммитить:** см. раздел "Repository Cleanliness" в Agent Behavior Rules

### Ситуационные скиллы

| Когда | Скилл |
| ----- | ----- |
| Старт сессии после перерыва | `/gsd-resume-work` |
| Что-то сломалось | `/gsd-debug` |
| Перед мёржем в main | `/gsd-code-review` |
| Бэклог → следующая фаза | `/gsd-review-backlog` |

## Quick start

```bash
./scripts/adam_bootstrap_venv.sh
./scripts/adam_power_maxn.sh
PYTHONPATH=System ADAM_MODE=maintenance ./.venv/bin/python System/Orchestrator.py
# Verify:
curl --noproxy '*' -fsS http://127.0.0.1:8080/api/agent/status | python3 -m json.tool
```

### Git hooks setup

```bash
git config core.hooksPath .githooks
# Linux/macOS only:
chmod +x .githooks/*
```

После этого `post-checkout` автоматически создаст `BRANCH.md` при переходе на новую ветку, а `post-commit` будет перестраивать graphy-граф при изменениях в `System/`.

Первый запуск графа (после установки `graphify install`):

```bash
# Linux/macOS — разрешить исполнение новых хуков:
chmod +x .githooks/post-commit
# Затем в Claude Code:
# /graphify System/ --mode deep
```

---

## Maintaining this file — структура и валидация

**Цель:** CLAUDE.md должен быть единственным источником истины для правил проекта. Без дубликатов, без противоречий.

### Structure Map (иерархия обязана быть в этом порядке)

1. **Entry point** — заголовок, метаинформация, Reading Order table
2. **Non-obvious invariants** — неварианты (MUST NOT), жёсткие требования (инварианты системы)
3. **Gotchas** — подводные камни (когда что-то работает не очевидно, но это норма)
4. **Agent Behavior Rules** — добровольные правила поведения (File Structure, Config-First, Language, Excluded Tech, Repository Cleanliness)
5. **GSD-пайплайн** — правила разработки через GSD фазы
6. **Quick start** — инструкции по запуску
7. **Maintaining this file** — этот раздел (meta)

### Duplicate Detection Rules

Для каждого из этих **критических терминов** может быть ровно **ОДНО** объяснение:

| Термин | Разрешённое место | Почему |
| --- | --- | --- |
| LLM output format | Non-obvious invariants (line 28) | Это неварiant, не просто рекомендация |
| PyTorch на Jetson | Gotchas (lines 41-42) | Порядок установки — это подводный камень, не общее правило |
| Config-First | Agent Behavior Rules §Config-First | Все параметры в Config.json |
| Repository Cleanliness | Agent Behavior Rules §Repository | Что коммитить/не коммитить |
| GSD workflow | GSD-пайплайн (lines 131+) | Все про фазы и commits здесь |

**Проверка:** Если нашёл термин в двух местах сразу → это ошибка. Одно место = source of truth, остальные = кросс-ссылки.

### Validation Script (для локального use)

```bash
#!/bin/bash
# Detect duplicates in CLAUDE.md

echo "=== Checking for duplicate rules ==="

# PyTorch mentions (должно быть только в Gotchas)
echo "PyTorch mentions:"
grep -n "PyTorch\|pip install.*silero\|pip install.*whisperx" CLAUDE.md

# Commit rules (должно быть только в Repository Cleanliness)
echo -e "\nCommit rules (должны быть только в Repository Cleanliness):"
grep -n "коммитить\|commit.*\\.env\|commit.*PrivateConfig" CLAUDE.md

# LLM format (должно быть только в Non-obvious invariants)
echo -e "\nLLM format (должно быть только в Invariants):"
grep -n "JSON.*LLM\|code.*LLM\|чистый русский" CLAUDE.md

# Config parameters (должно быть только в Config-First)
echo -e "\nConfig parameters (должно быть только в Config-First):"
grep -n "Config.json\|числовые параметры\|хардкодить" CLAUDE.md

echo -e "\n=== Done ==="
```

### When editing CLAUDE.md

1. **Перед добавлением нового правила:**
   - Прочитай "Structure Map" выше — в какой раздел это идёт?
   - Grep-ни текущий файл: есть ли это правило где-то ещё?
   - Если есть → удали дубль, оставь одно место + кросс-ссылку

2. **После редакта:**
   - Запусти validation script (он выше)
   - Нет ошибок → можно коммитить
   - Есть duplicate warning → разрешить перед коммитом

3. **Cross-references:**
   - Используй стиль: «см. раздел "Section Name" (line NN)»
   - Или просто: «см. Non-obvious invariants §3»

### Contradiction Prevention

Если на тебя давит requirement, которое противоречит существующему правилу:

- **Не добавляй параллельное правило** (создаст дубль)
- Вместо этого:
  1. Напиши issue в `.planning/` с описанием противоречия
  2. Обнови ROADMAP.md — есть ли это в активной фазе?
  3. Обнови одно правило (удалив старое), объяснив в git commit почему

Пример bad: добавить "Иногда коммитить .env" в другом месте файла
Пример good: обновить "Repository Cleanliness" с исключением: "`.env` → EXCEPT when [reason]. See ROADMAP phase N"
