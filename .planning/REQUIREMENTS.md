# Requirements

## Phase 1 — Doc Refactor: Концепция C + A ✓ COMPLETE

Все выполнены. Итог: [phases/01-doc-refactor-c-a/](phases/01-doc-refactor-c-a/)

| ID | Requirement |
|----|-------------|
| DOC-01 | Исправить ASR model в CONTEXT.md и README.md: "medium" → "small" |
| DOC-02 | Исправить wake word threshold в CONTEXT.md: 0.35 → 0.20 |
| DOC-03 | Исправить wake word debounce_hits в CONTEXT.md: 3 → 2 |
| DOC-04 | Удалить/переписать устаревшие Ollama-defaults из docs/RUNBOOK_JETSON_EXHIBITION.md; исправить audio input device hw:0,0 → pulse |
| DOC-05 | Создать System/Config.schema.json с JSON Schema описаниями всех параметров Config.json |
| DOC-06 | Синхронизировать DEFAULT_CONFIG в System/adam/config.py с реальными значениями System/Config.json |
| DOC-07 | Удалить CONTEXT.md или свести к указателю; убрать числовые параметры из README.md и CLAUDE.md, которые дублируют Config.json |

## Phase 2 — Progressive Disclosure: навигация для нового агента

| ID | Requirement |
|----|-------------|
| NAV-01 | Обновить `.planning/STATE.md`: Phase 1 помечена ✓ COMPLETE с кратким итогом реализованных изменений |
| NAV-02 | Обновить `.planning/ROADMAP.md`: Phase 1 помечена ✓ done с датой завершения; Phase 2 добавлена |
| NAV-03 | Создать `.planning/phases/01-doc-refactor-c-a/01-SUMMARY.md` — одностраничный итог Phase 1: что изменено, принятые решения, принципы (Config-First, Lean Docs) |
| NAV-04 | Добавить секцию "Reading Order" в `CLAUDE.md`: иерархия файлов Level 0–4 с ссылками, указание с чего начать новому агенту |
| NAV-05 | Добавить секцию "Текущее состояние" в `README.md` с ссылкой на `.planning/STATE.md` и кратким статусом |
| NAV-06 | Проверить и добавить перекрёстные ссылки между Level 0–4 документами (CLAUDE.md ↔ README.md ↔ STATE.md ↔ ROADMAP.md ↔ phase SUMMARY) |

## Phase 3 — Branch Coordination: контекст для мульти-агентной работы

| ID | Requirement |
| --- | ----------- |
| BR-01 | Создать `docs/BRANCH-template.md` — шаблон BRANCH.md + конвенция (когда создавать, как заполнять, удалять после мёржа без архива; имя ветки = идентификатор, нет поля Owner) |
| BR-02 | Создать `.planning/ACTIVE.md` — таблица активных веток: ветка / статус / modified areas / merge blocker. Обновляется при создании и закрытии ветки, не в середине работы |
| BR-03 | Обновить `CLAUDE.md` Reading Order: добавить строку «если не на main — прочитай `BRANCH.md` первым» |
| BR-04 | Обновить `.planning/STATE.md`: добавить ссылку на `.planning/ACTIVE.md` в раздел Active Phase |

## Phase 4 — Context Automation: per-directory CLAUDE.md и git hooks

| ID | Requirement |
| --- | ----------- |
| CTX-01 | Создать `Subsystem/AdamsServer/CLAUDE.md` — ESP32 tech context: PlatformIO build system, запрещённые файлы (`PrivateConfig.h`, `credentials.h`), flash tools, static IP `192.168.0.171`, порты 80/81 |
| CTX-02 | Создать `System/adam/CLAUDE.md` — карта всех 23 модулей (одна строка на модуль), `Settings.load()` как единственный config entrypoint, service adapter pattern (только через `inference.py`), EventBus convention |
| CTX-03 | Создать `Agent Adam Chip/CLAUDE.md` — порядок загрузки персоны (System.md → Identity.md → Lore.md → Abilities.md), запрет на JSON/code blocks, зависимость порядка от `Config.json agent.persona_paths` |
| CTX-04 | Создать `.githooks/post-checkout` (POSIX sh) — scaffold BRANCH.md при переключении на новую не-main ветку если `docs/BRANCH-template.md` существует |
| CTX-05 | Создать `.githooks/pre-commit` (POSIX sh) — warning (не блок) если коммит на не-main ветке и BRANCH.md отсутствует |
| CTX-06 | Обновить root `CLAUDE.md` Quick start: добавить команду `git config core.hooksPath .githooks && chmod +x .githooks/*` |

## Phase 5 — Agent Protocol: поведение агента-разработчика

| ID | Requirement |
| --- | ----------- |
| AGT-01 | Создать `docs/AGENT-PROTOCOL.md` секция "Режимы работы": таблица Advisor / Planner / Implementer / Debugger с триггерами переключения |
| AGT-02 | Добавить в `docs/AGENT-PROTOCOL.md` секция "Триггеры уточнения": конкретный список условий (Config.json изменение, shared infrastructure, размытый глагол, >3 модулей, global vs experiment) |
| AGT-03 | Добавить в `docs/AGENT-PROTOCOL.md` секция "Гэпы контекста": классификация Branch gap / Phase gap / Config gap / Invariant gap / Stale gap + поведение агента для каждого |
| AGT-04 | Добавить в `docs/AGENT-PROTOCOL.md` секция "Протокол планирования": GSD-first (проверить ROADMAP.md → использовать `/gsd-plan-phase` → inline GSD-формат для малых задач) |
| AGT-05 | Обновить `CLAUDE.md`: добавить `@docs/AGENT-PROTOCOL.md` в строку с `@`-референсами и однострочную подпись |

## Phase 8 — Reply-Echo-Hang debug: устранить заморозку voice_loop после reply window

| ID | Requirement |
| --- | ----------- |
| REQ-NO-HANG-AFTER-REPLY | После перехода `reply → standby` (по любой причине: silence timeout, max_segment_ms, успешный submit) voice_loop в `System/Orchestrator.py` продолжает эмитить события (`voice_loop_heartbeat` минимум раз в N секунд, плюс reaction на wake word). Заморозка > 60 сек = регрессия. |
| REQ-NO-SELF-ECHO-VAD | Защитный буфер `_REPLY_GUARD_SEC = 0.6` сохранён в `_vad_loop` reply-блоке и не убран (defence-in-depth для будущих сценариев акустического контура speaker↔mic, даже если сейчас эхо не root cause). `half_duplex_mute=true` остаётся инвариантом. |
| REQ-REPLY-MATCHES-LISTENING | Логика accumulation/endpointing в `_vad_loop` для reply идентична listening (один общий блок кода, без дубликата). Единственное отличие reply от listening — таймер silence 4.0 сек → standby (если `speech_ms == 0`). Защита от бесконечной диктовки — общий `max_segment_ms`. Поле `services.asr.reply_absolute_deadline_sec` удалено из `System/Config.json` и `System/Config.schema.json`. |
| REQ-DIAGNOSTIC-LOGS-VOICE-STATE | `_vad_loop` эмитит событие `voice_state_changed` (поля: from, to, reason, timestamp) при каждом `_set_voice_state` и `voice_loop_heartbeat` периодически (например раз в 5 сек), чтобы при повторении hang можно было точно установить место заморозки по `events.jsonl`. SIGUSR1 → asyncio task stack dump deferred to follow-up phase (см. CONTEXT §Deferred). |

## Phase 9 — VAD debounce + UI smoothness + chat panel cleanup

| ID | Requirement |
| --- | ----------- |
| REQ-VAD-DEBOUNCE | `_vad_loop` НЕ эмитит `endpointing_started` чаще чем раз в N silence-кадров подряд (default 5 ≈ 100 ms). Параметр в Config (`services.asr.endpointing_debounce_frames`). На длинной речевой фразе одна реплика даёт ≤ 2 emit'а endpointing_started (а не 40, как в Test 2). |
| REQ-AUDIO-LEVEL-CONTINUOUS | `MicReader` имеет отдельную asyncio-task, которая эмитит `audio_level` event каждые ≤ 200 ms на основе последних известных значений, даже если drain_loop стал из-за stall/reconnect или I/O задержки. UI VU/equaliser обновляется без длинных gap'ов (> 500 ms) кроме реальных потерь сигнала. |
| REQ-HEARTBEAT-INDEPENDENT | `voice_loop_heartbeat` эмитится из отдельной asyncio-task `_heartbeat_loop` (не из `_vad_loop`), интервал 5 sec ± 200 ms независимо от ASR/TTS блокировок в `_vad_loop`. Hang voice_loop'а немедленно виден как остановка heartbeat. |
| REQ-UI-CHAT-CLEANUP | В chat-панели (System/WebUI/static/js/panels/chat.js, widgets/wakeMeter.js): убраны текстовые подписи (`t=X s=Y max=Z`) с эквалайзера; кнопка «Калибровать» убрана из chat (остаётся в settings.js); `micSourceBadge` перенесён над эквалайзером, выровнен по правому краю (там где была кнопка Калибровать); VU-метр (`vuCanvas`) высота = 96 px (под высоту эквалайзера). |
| REQ-ESP32-AUDIO-REPORT | Создан отчёт о текущей конфигурации ESP32 INMP441 микрофона: sample rate, bit depth, slot bits, формат. Сравнение с рекомендуемой частотой 44.1/48 kHz и 16-bit. Включён в `09-SUMMARY.md`. |

## Phase 10 — Flush stale audio on safe state transitions (V-S07.1 backport)

| ID | Requirement |
| --- | ----------- |
| REQ-FLUSH-ON-SAFE-TRANSITIONS | `MicReader` имеет публичный метод `flush_queue(discard_window_ms: float = 200.0) -> int`: дренирует все чанки из очереди + ставит `_discard_until_ts = perf_counter() + window/1000` чтобы `_drain_loop` discard'ил всё что приходит из socket в этом окне (drain TCP buffer но не push в queue, W5500 SPI не переполняется). VoiceLoopController вызывает `flush_queue(200.0)` **только в двух безопасных точках**: (1) после возврата `_transcribe_and_dispatch` — V-S07.1 эквивалент `_drain_esp32_backlog`; (2) на `reply_silence_timeout` в reply→standby transition. **НЕ вызывается на `wake_word_detected`** — Phase 10 v1 (commit `36cded5`, реверт `5664121`) показал что это съедает первые ~200ms запроса пользователя (Test 5 regression: success rate 64%→33%, 5 подряд `wake_silence_timeout`). Событие `mic_queue_flushed {frames, ms, trigger, discard_window_ms}` эмитится в events.jsonl при каждом вызове. Логика MicReader-стрима не нарушена — socket reads остаются в `_drain_loop`, drain происходит на queue-уровне. |
