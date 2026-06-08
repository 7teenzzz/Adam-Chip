# Phase 30: Voice Loop Recovery & Flora Integration - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Восстановить корректную работу голосового цикла Адама ПО ФАКТУ (живой end-to-end тест, не анализ кода): mic → VAD → wake («адам») → ASR(WhisperX:8095) → LLM(llama.cpp:8081) → TTS(Silero:8082) → выход на ESP-динамик. Затем — отдельным финальным шагом — влить технофлору из коммита `47fd0c5` с разрешением ВСЕХ конфликтов через глубокий анализ, не реактивируя поломки голосового цикла, и перепрошить ESP под флору.

Корневая причина прошлых поломок (и почему откат любых коммитов не помогал): runtime/host-слой ВНЕ git — мёртвые сервисы, Ollama держит VRAM, конфликт портов, незаведённая сеть ESP. Эта фаза чинит host-слой и наводит порядок в интеграции.

**Out of scope:** новые фичи флоры; миграция на ESP-микрофон (остаётся local USB); neural memory; UI-перестройка.

</domain>

<decisions>
## Implementation Decisions

### Сеть и доступность ESP
- **D-01:** ESP IP = `10.10.10.171` — КАНОН для выставочной проводной сети (W5500 Ethernet). IP в `System/Config.json` ВЕРНЫЙ, менять НЕ нужно. Чинить надо СЕТЬ Jetson: поднять проводной интерфейс (eno1 / линк к W5500) на подсети 10.10.10.x. Текущее состояние: eno1 DOWN, Jetson только на Wi-Fi 192.168.0.199. «192.168.0.171» из REQUIREMENTS.md (CTX-01) — устаревший dev-IP, в этой фазе НЕ применять.

### Выход TTS
- **D-02:** Выход TTS — ТОЛЬКО `esp32_speaker`. HDMI / `plughw:1,3` fallback НЕ используется (ни ручной, ни авто). Следствие: живой end-to-end тест голоса ЗАБЛОКИРОВАН до восстановления сети 10.10.10.x → ESP. Вопрос виртуального дисплея для headless-HDMI-аудио снят с этой фазы (см. Deferred).

### Flora-gate / интеграция 47fd0c5
- **D-03:** При мёрже `47fd0c5` flora-gate ПЕРЕРАБОТАТЬ на СОСУЩЕСТВОВАНИЕ: моторика Адама (LLM action-layer) — overlay/приоритет поверх флоры, флора — фоновая анимация PCA. НЕ оставлять полное подавление action-layer (`suppressed_flora_owns_channels`), как в исходном 47fd0c5. Это основная конфликт-резолюция мёржа и требует глубокого анализа Orchestrator `_execute_action`, `/api/agent/scene`, `/api/agent/stop` + FLORA-04 `feed_speech_wav` consumer.

### Ollama / запуск сервисов
- **D-04:** Ollama — ПОЛНОЕ удаление (`apt purge` + `/usr/local/bin/ollama` + `~/.ollama` модели + `/etc/systemd/system/ollama.service`), освобождает ~3.3 GB VRAM и ~3 GB диска. Сервисы llama.cpp(:8081), Silero TTS(:8082), оркестратор — поднимать ШТАТНО через systemd (нужен sudo пользователя), не bare-процессами. Инвариант проекта: НИКОГДА не использовать Ollama.

### Порядок восстановления (следствие D-01..D-04)
- **D-05:** Жёсткая последовательность: (1) purge Ollama → свободна VRAM; (2) Jetson входит в сеть 10.10.10.x → ESP пингуется на 10.10.10.171; (3) поднять llama.cpp:8081 + Silero:8082 + оркестратор через systemd, устранить конфликт порта 8095 (нативный ASR vs Docker — выбрать один путь); (4) живой end-to-end тест голоса через ESP-динамик; (5) ТОЛЬКО ПОТОМ мёрж 47fd0c5 с сосуществованием (D-03) + reflash ESP под флору. Причина порядка: 9da07f9 — предок 47fd0c5, мёрж до recovery-коммитов = fast-forward на всю LuxFlora_V1.1.

### Claude's Discretion
- Конфликт порта 8095 (нативный systemd ASR vs Docker ASR): выбрать один канонический путь. README/CLAUDE.md называют Docker канонexpress ASR — но нативный сейчас живой и `whisperx loaded`. Решить при планировании/исполнении по факту стабильности.
- Метод reflash ESP под флору: USB (`arduino-cli`/pio + esptool через /dev/ttyACM0, проверено в этой сессии) либо OTA.
- Конкретный механизм «overlay поверх флоры» (приоритетная очередь каналов / временный захват / mute флоры на время жеста) — определит deep-анализ при мёрже.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Фаза и ветка
- `.planning/ROADMAP.md` §Phase 30 — границы и Delivers фазы
- `BRANCH.md` (корень) — цель ветки, условия мёржа, sequencing-инвариант
- `.planning/REQUIREMENTS.md` — voice-pipeline REQ (Phase 8/9/10), CTX-01 (ESP context), DOC-04 (убрать Ollama-defaults)

### Конфиг и флора (HIGH conflict при мёрже 47fd0c5)
- `System/Config.json`, `System/Config.schema.json` — ESP IP, TTS routing, флора-параметры
- `System/adam/config.py` — DEFAULT_CONFIG (флора-каналы, gamma)
- `System/adam/flora.py` — RMS stream, vibro/light duty
- `Subsystem/AdamsServer/config/AdamsConfig.h`, `Subsystem/AdamsServer/src/io/FloraModule.cpp` — firmware каналы/cap (reflash)

### Голосовой цикл и оркестратор
- `System/Orchestrator.py` — `_vad_loop` (local mic OWW feed), `_consumer` (FLORA-04 врезка), `_execute_action` + `/api/agent/scene` + `/api/agent/stop` (flora-gate), TTS `output_target`
- `System/adam/mic_reader.py` — MicReader (ESP-only) и local-mic путь
- `deploy/systemd/` — adam-llm, adam-tts-silero, adam-asr-whisperx, adam-orchestrator (ExecStart, NO_PROXY hardening)
- `docs/RUNBOOK_JETSON_EXHIBITION.md` — production runbook (DOC-04: убрать Ollama)

### Целевой коммит мёржа
- `47fd0c5` (`origin/LuxFlora-modes_V1.1`, автор 7teenzzz) — технофлора: ремап каналов вибро 0-3/свет 4-14, вибро без светового потолка; «Прошивка обязательна»

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `deploy/systemd/*.service` — ExecStart для llama.cpp(:8081), Silero(:8082), оркестратора уже определены; восстановление = `systemctl start`, не написание заново.
- `scripts/adam_healthcheck.sh`, `scripts/adam_service_status.sh`, `scripts/adam_media_probe.sh` — готовая диагностика для верификации этапов.
- `MicReader._vad_loop` + `_start_arecord` — рабочий local-mic→OWW путь (arecord `plughw:WebCamera,0` → `_wake_engine.process_chunk` → `oww_score`).
- `_NO_PROXY_OPENER` (device.py/inference.py/Orchestrator.py) — обязателен для HTTP к ESP (v2ray leak'ит сокеты).

### Established Patterns
- Config-First: все числа в Config.json + schema, не хардкод.
- Инварианты: LLM=чистый русский; `half_duplex_mute=true`; action failure ≠ silence.
- `oww_score≈0.001` в standby — нормальный idle-пол (прецедент ESP-Mic-Fix: 0/1247 ложных), не баг.

### Integration Points
- `Orchestrator._consumer` — точка врезки FLORA-04 `feed_speech_wav` (приходит с 47fd0c5).
- `Orchestrator._execute_action` — точка flora-gate; здесь решается сосуществование (D-03).
- `services.tts.output_target` — переключатель esp32_speaker / jetson_hdmi (D-02: только esp32_speaker).

</code_context>

<specifics>
## Specific Ideas

- ESP физически на W5500 Ethernet, подсеть 10.10.10.x; статический IP 10.10.10.171.
- Монитор VG27AQA1A подключён по DisplayPort (даёт `plughw:1,3`) — но для выхода НЕ используется (D-02).
- Mic = USB WebCamera (ALSA card 0), `plughw:WebCamera,0`, mic_source=local.
- Залитая прошивка ESP = из 070ab4b (no-flora); firmware-исходник идентичен базе ветки 9da07f9 → рассинхрона нет до мёржа 47fd0c5.

</specifics>

<deferred>
## Deferred Ideas

- Виртуальный дисплей / dummy-EDID для headless HDMI-аудио — не нужен при TTS=esp32_speaker (D-02). Вернуть, если когда-нибудь понадобится локальный звуковой fallback.
- Вариант «флора единолично владеет каналами» (полное подавление action-layer) — отвергнут в пользу сосуществования (D-03).
- Миграция на ESP-микрофон (INMP441) вместо USB — отдельная фаза.
- HDMI авто-fallback при ошибке ESP — отвергнут (D-02), при желании отдельной фазой.

</deferred>

---

*Phase: 30-voice-loop-recovery-flora-integration*
*Context gathered: 2026-06-07*
