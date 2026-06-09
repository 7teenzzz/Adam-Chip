# Phase 35: Live Integration Testing — ultimate-integration после всех слияний — Context

**Gathered:** 2026-06-09
**Status:** Ready for planning
**Source:** Discussion после ручного merge voice-loop-recovery → ultimate-integration (`15d23ca`, worktree `/tmp/adam-ult`)

<domain>
## Phase Boundary

Подтвердить **живыми тёрнами на железе Jetson**, что собранная ветка `ultimate-integration`
работает end-to-end после всех предыдущих слияний (voice-loop-recovery Phase 34 ASR,
LuxFlora ремап каналов, MemoryFixes, Extra шутки+погода, + только что разрешённый merge
с де-мохибейком Config.json). Это **фаза верификации**, не разработки: новых фич не добавляем,
проверяем интегрированную систему и роутим каждый отказ в `/gsd-debug`.

**В scope:**
- Подъём/проверка сервисов на интегрированной ветке, валидация конфига на железе
- Живой голос: wake «адам» → ASR → LLM → TTS → звук из ESP-динамика; barge-in; silence keyword «стоп»
- Флора-сосуществование (моторика overlay поверх фоновой флоры); pre-LLM скиллы шутки/погода; запись эпизода в память
- Debug-луп по дефектам из живых тёрнов; решение go/no-go на push в `origin/ultimate-integration` и далее merge в `main`

**Вне scope (НЕ трогаем):**
- Доработка самих фич (флора-механизм, ASR-фильтры, скиллы) — кроме фиксов конкретных дефектов, найденных тестом
- Reflash ESP под флору — отдельный обязательный шаг ПОСЛЕ зелёного push (см. BRANCH условие 4), но не предмет этой фазы
- Изменение архитектуры, рефактор, новые параметры Config

</domain>

<decisions>
## Implementation Decisions

### Режим тестирования (Test mode)
- **D-01:** Двухэтапный прогон **maintenance → exhibition**.
  - Сначала `maintenance`: быстрый smoke без power-gate (wake-гейт обойдён), проверяем что
    интегрированный код вообще поднимается, конфиг валиден, текстовый `/api/agent/turn` отвечает,
    флора/скиллы/память живут.
  - Затем `exhibition`: полный живой тест с реальным wake-гейтом («адам» обязателен). Требует
    power-gate (MAXN + jetson_clocks) — он проверяется автоматически при старте (инвариант проекта).
  - Причина порядка: послойно развязать дефекты — отделить «код не поднялся / конфиг битый» от
    «wake word не ловится / звук не идёт».

### Загрузка интегрированной версии в живые сервисы (Service source)
- **D-02:** **Checkout `ultimate-integration` в основной каталог** `/home/i17jet/Agents/Adam-Chip`,
  затем restart `adam-orchestrator.service` (+ при необходимости TTS/ASR). systemd-юниты смотрят
  только на основной каталог, поэтому интегрированный код+конфиг должен лежать именно там.
  - Worktree `/tmp/adam-ult` после checkout убрать (`git worktree remove`) — иначе ветка
    `ultimate-integration` занята в двух местах и checkout в основной каталог невозможен.
  - Незакоммиченной работы в основном каталоге нет (всё в `7f7cfe2`), потерь не будет.
  - Перед checkout вернуть основной каталог в чистое состояние и зафиксировать текущую ветку,
    чтобы вернуться (`voice-loop-recovery`) после фазы.
  - **Почему НЕ «копировать только Config.json»:** интегрированная функциональность — это не только
    конфиг, а код (`Orchestrator.py` merge, `flora.py`, модули скиллов). Копии конфига недостаточно.

### Evidence на каждый живой тёрн (Evidence)
- **D-03:** На каждый тёрн фиксируем **turn_id-трейс + запись в память**:
  - `events.jsonl` trace по `turn_id` (oww→vad→asr→llm→tts→action) через `scripts/adam_pull_logs.py`
  - проверка появления соответствующего ряда/эпизода в `data/adam/memory.sqlite3`
  - Звук из ESP-динамика — **устное подтверждение пользователя** (ok/нет), без авто-записи аудио.
  - Это канонично для проекта (каждый тёрн уже получает `turn_id`), автоматизируемо, без доп-железа.

### Debug-луп и условие push/мёржа (Debug + gate)
- **D-04:** **Fix-в-worktree/основном-каталоге ДО push, полный green.**
  - Каждый дефект из живого тёрна → `/gsd-debug` **поочерёдно** (научный метод, persistent state),
    фикс, ре-тест того же тёрна.
  - **Push в `origin/ultimate-integration`** — ТОЛЬКО после зелёных Wave 1–3 (bring-up+smoke,
    live voice E2E, integration surfaces).
  - **Merge в `main`** (merge target из BRANCH.md) — после полного green + обязательного reflash ESP
    под флору (BRANCH условие 4). Push — необратимый шаг в общую ветку, требует подтверждения пользователя.

### Разделение авто / ручное (Auto vs manual)
- **D-05:** Чёткое разделение по физике:
  - **Агент автоматизирует:** checkout+restart, healthcheck (`adam_healthcheck.sh`,
    `adam_service_status.sh`), валидацию конфига на железе, текстовый `/api/agent/turn`,
    проверку флоры/скиллов через API, сбор трейсов (`adam_pull_logs.py`), чтение `memory.sqlite3`,
    смену режима maintenance↔exhibition.
  - **Пользователь делает физически (только он):** произносит wake «адам» и команды в микрофон,
    слушает звук из ESP-динамика, делает barge-in (говорит во время ответа Адама), произносит «стоп».
  - Агент готовит структурированный чек-лист живых проверок; пользователь идёт по нему и отмечает ok/fail;
    на каждый fail агент тянет трейс и запускает debug-луп.

### Carried forward (Phase 30 D-01..D-05) — НЕ переспрашивать
- ESP IP = `10.10.10.171`, Jetson в проводной сети `10.10.10.x` (eno1/W5500). **Подтверждено живьём:**
  eno1 UP (`10.10.10.1/24`), ESP пингуется, `:80/api/status` OK.
- Выход TTS — только `esp32_speaker`, без HDMI-fallback.
- Флора = сосуществование (D-03 Phase 30): на время ответа Адама firmware уходит в `external`
  (анимация подавлена), RMS его речи (`flora.feed_speech_wav`) гонит каналы; между ответами — фон.
- Ollama выпилена (подтверждено живьём: `which ollama` пусто); сервисы — через systemd.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Ветка и merge
- `BRANCH.md` — цель ветки voice-loop-recovery, merge conditions 1–5 (условие 4 = reflash ESP)
- `.planning/phases/30-voice-loop-recovery-flora-integration/30-CONTEXT.md` — решения D-01..D-05 (флора, TTS routing, ESP IP, Ollama, порядок)
- `.planning/phases/34-asr-quality-fixes/34-CONTEXT.md` — pre-wake buffer + hallucination guard (что именно влито из voice-loop-recovery)

### Код под тестом
- `System/Orchestrator.py` — `_vad_loop` (OWW feed, pre-wake buffer), `_consumer` (FLORA-04 врезка), barge-in (`_local_barge_in_feed`, `_read_exact_bi`), `_execute_action`/`/api/agent/scene`/`/api/agent/stop` (flora-сосуществование), TTS `output_target`
- `System/adam/flora.py` — `_on_answer_start`/`_on_answer_end` (external-режим), `feed_speech_wav`, `_rms_envelope`, `_envelope_to_duties` (механизм сосуществования)
- `System/Config.json` — после де-мохибейка: `wake_words=«адам»`, блоки `flora`, `skills.weather`/`skills.jokes`, `tuning.voice.volume=0.45`, `silence_rms_threshold=2100`

### Тест-инструментарий (готовый)
- `scripts/adam_pull_logs.py` — turn_id-трейсы (oww/vad/asr/llm/tts/action), `--follow`, `--last N`
- `scripts/adam_healthcheck.sh`, `scripts/adam_service_status.sh` — статус сервисов
- `scripts/adam_media_probe.sh` — камеры/аудиоустройства
- `scripts/adam_tts_smoke.sh`, `scripts/adam_tts_doctor.sh` — TTS smoke
- `scripts/test_wake_word.py`, `scripts/test_esp32_stream.py` — wake-word и ESP-стрим
- API: `/api/agent/status`, `/api/agent/turn`, `/api/agent/turns?limit=N`, `/api/agent/events?turn_id=…`, `/api/config`
- `data/adam/memory.sqlite3` — проверка записи эпизодов; `data/adam/events.jsonl` — поток событий

### Запуск/режимы
- `scripts/adam_set_mode.sh maintenance|exhibition` — переключение режима
- `deploy/systemd/` — adam-orchestrator / adam-llm / adam-tts-silero / adam-asr-whisperx
- `README.md` §«Логи Pipeline», §«Production Boot»; `docs/RUNBOOK_JETSON_EXHIBITION.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/adam_pull_logs.py`: канонический сборщик turn_id-трейсов — основа evidence (D-03). Без внешних зависимостей.
- `adam_healthcheck.sh` / `adam_service_status.sh`: готовая проверка живости сервисов для Wave 1.
- `/api/agent/turn`: текстовый ввод тёрна (обходит ASR/mic) — позволяет агенту прогнать LLM→TTS→action→память без физического голоса в maintenance-smoke.
- `flora.feed_speech_wav` + `_on_answer_start/_end`: механизм сосуществования уже в коде — тест проверяет поведение, не реализует.

### Established Patterns
- Каждый тёрн получает короткий `turn_id`, связывающий ASR→LLM→TTS→Action — основа верификации.
- `_NO_PROXY_OPENER` / `curl --noproxy '*'`: все локальные и ESP-запросы в обход v2ray (инвариант проекта).
- half_duplex_mute=true: mic заглушается во время TTS — влияет на тест barge-in (barge-in идёт через параллельный OWW-feed, не через основной mic-тракт).

### Integration Points
- systemd ↔ основной каталог: оркестратор грузит код+Config ТОЛЬКО из `/home/i17jet/Agents/Adam-Chip` → D-02 (checkout в основной каталог).
- Текущий живой оркестратор (на момент discuss) на `voice-loop-recovery`: `flora: False, skills: False` — подтверждает необходимость D-02 перед тестом интеграции.
- exhibition mode ↔ power-gate (MAXN+jetson_clocks): авто-проверка при старте → влияет на Wave-порядок (D-01).

</code_context>

<specifics>
## Specific Ideas

- Живое состояние на момент discuss (2026-06-09): сеть 10.10.10.x UP, ESP `:80` OK, llama:8081 / TTS:8082(health ok) / ASR:8095(health ok) / орк:8080 / logviewer:8083 — все живы; Ollama отсутствует. Bring-up-блокера нет — Wave 1 это валидация+переключение ветки, не восстановление с нуля.
- Wake-word idle-пол OWW `oww_score≈0.001` в standby — НОРМА (прецедент ESP-Mic-Fix: 0/1247 ложных). Не считать дефектом; проверять wake живым голосом.
- Merge `15d23ca` починил мохибейк: на ult wake word читался как «Р°РґР°Рj» (распознавание было сломано) → один из ключевых пунктов проверки exhibition-теста.

</specifics>

<deferred>
## Deferred Ideas

- **Reflash ESP под флору** (вибро 0-3 / свет 4-14, vibro cap ~95%) — обязателен ПОСЛЕ зелёного push (BRANCH условие 4), но это отдельный hardware-шаг, не предмет этой тест-фазы.
- **Запись аудио ESP как артефакт** — рассмотрена в evidence, отклонена в пользу turn_id-трейсов (D-03); вернуться, если устного подтверждения звука окажется недостаточно для go/no-go.
- **Авто-тест физического голоса** (проигрывание эталонного wake-WAV в mic-тракт) — за рамками; живой голос подтверждает пользователь.

</deferred>

---

*Phase: 35-live-integration-testing-ultimate-integration*
*Context gathered: 2026-06-09*
