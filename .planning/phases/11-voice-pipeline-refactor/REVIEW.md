# Phase 11 — Voice Pipeline Refactor: Code Review

**Branch:** `V-S08.1-code_rev_ref_opt`
**Scope:** запуск Адама + голосовой пайплайн (STANDBY → LISTENING → ANSWER → REPLY)
**Read-only audit.** Никаких правок кода — только findings, рекомендации, вопросы.

---

## 1. Сводка по соответствию эталонной логике

### 1.1 Цепочка запуска

| Шаг эталона | Реализация | Файл / строка | Статус |
| --- | --- | --- | --- |
| Hard-clear proxy | `unset http_proxy …; NO_PROXY="*"` | [adam_start.sh:33-36](scripts/adam_start.sh#L33-L36) | ✅ |
| Preflight HW checks | `has_usb_camera / has_esp_camera / has_microphone` | [adam_start.sh:115-145](scripts/adam_start.sh#L115-L145) | ✅ |
| Запуск logviewer + LLM + TTS + ASR + VLM | systemd + docker (порядок последовательный, не параллельный) | [adam_start.sh:186-329](scripts/adam_start.sh#L186-L329) | ✅ |
| Success-звук после готовности сервисов | `_play_success_sound("startup_services_ok")` | [Orchestrator.py:1812-1816](System/Orchestrator.py#L1812-L1816) | ✅ |
| Kill предыдущего Orchestrator | `pgrep + kill -9` | [adam_start.sh:333-343](scripts/adam_start.sh#L333-L343) | ✅ |
| lifespan: camera_reader / scene_worker / session_watcher / esp_audio_health / mic_reader | `asyncio.create_task` | [Orchestrator.py:1867-1875](System/Orchestrator.py#L1867-L1875) | ✅ |
| `_ensure_crossover_link` | nmcli up eno1 | [Orchestrator.py:1744-1793](System/Orchestrator.py#L1744-L1793) | ✅ |
| `_wait_for_services(expected)` (120с, polls 5с) | poll health каждые 5с до 120с | [Orchestrator.py:1730-1741](System/Orchestrator.py#L1730-L1741) | ✅ |
| `mic_reader.wait_active(90с)` | через asyncio.Event | [Orchestrator.py:1829-1834](System/Orchestrator.py#L1829-L1834) | ✅ |
| `_prewarm_filler` | синтез filler заранее | [Orchestrator.py:3271-3298](System/Orchestrator.py#L3271-L3298) | ✅ |
| `_warmup_wakeup` | LLM-монолог 2-3 фразы, max 25 слов | [Orchestrator.py:3157-3216](System/Orchestrator.py#L3157-L3216) | ✅ |
| `_warmup_llm_prefix` | прогрев KV cache | [Orchestrator.py:3219-3261](System/Orchestrator.py#L3219-L3261) | ✅ |
| `await asyncio.sleep(0.5)` decay ALSA | hardcoded | [Orchestrator.py:1849](System/Orchestrator.py#L1849) | ✅ |
| `voice_loop.start()` до 5 retry × 2 сек | for loop | [Orchestrator.py:1850-1860](System/Orchestrator.py#L1850-L1860) | ✅ |
| CUDA для LLM/VLM/ASR/TTS, **CPU для OWW** | OWW = openwakeword, CPU-only по умолчанию | [System/adam/wake_word.py](System/adam/wake_word.py) | ✅ |

**Вывод:** цепочка запуска полностью соответствует эталону. Никаких структурных изменений не требуется. Минимальные мини-багфиксы (см. §3).

### 1.2 Голосовой пайплайн — стадии

| Стадия эталона | Реализация (`_voice_state`) | Поведение |
| --- | --- | --- |
| **STANDBY** — OWW «адам», переход в LISTENING | `standby` + `_wake_engine.process_chunk()` | ✅ работает; `_STANDBY_GUARD_SEC=0.3` блокирует OWW первые 300мс |
| **LISTENING** — VAD-накопление, 6с молчания → STANDBY, 1.5с пауза → ANSWER, max 15с | `listening` + `_vad_loop` + `_wake_silence_timeout_sec` | ⚠️ **`wake_silence_timeout_sec = 3` ≠ эталон (6)** |
| **ANSWER** — ASR → LLM → TTS, статус «Распознаю / Думаю / Говорю» | блок внутри `_vad_loop` lines 1101-1179 + `_transcribe_and_dispatch` + `_run_dialogue_turn` + `_stream_llm_and_speak` | ✅ events корректны, UI mapping в [chat.js:230-239](System/WebUI/static/js/panels/chat.js#L230-L239) |
| **REPLY** — guard 0.6с, 5с молчания → STANDBY, max 10с | `reply` + `_REPLY_GUARD_SEC=0.6` + `_reply_silence_timeout_sec` | ⚠️ **`reply_silence_timeout_sec = 4` ≠ эталон (5)**; ⚠️ **REPLY max = LISTENING max (15с) — нет отдельного knob'а** |

---

## 2. Главные находки (по приоритету для рефакторинга)

### 2.1 ⚠️ HIGH — Legacy ESP-fallback каскад в VoiceLoopController дублирует MicReader

`VoiceLoopController` содержит большой блок кода, который ранее управлял ESP-fallback'ом, но после Phase 7 (MicReader keep-alive) стал избыточен — MicReader сам владеет lifecycle стрима, retry, probe, backoff.

**Мёртвые / избыточные поля в `__init__` ([Orchestrator.py:454-482](System/Orchestrator.py#L454-L482)):**
- `esp_mic_fail_threshold`, `esp_mic_retry_interval_sec` — `audio_cfg`-параметры, читаются, но `_run_via_mic_reader` их не использует
- `_esp_mic_fallback` (bool флаг)
- `_esp_mic_fail_count`, `_esp_mic_last_retry`
- `esp_boot_wait_max_sec`, `esp_boot_wait_poll_sec` — для удалённого `_wait_for_esp_ready`
- `esp_bg_retry_attempts`, `esp_bg_retry_interval_sec`
- `_esp_retry_task`, `_esp_boot_wait_state`
- `_mic_stream_state` — дублирует `mic_reader.status()["stream_state"]`
- `_raw_is_stereo`, `_raw_level_l`, `_raw_level_r` — после Phase 7 MicReader = единственный эмиттер audio_level

**Мёртвые / избыточные методы:**
- `_wait_for_esp_ready` ([Orchestrator.py:702-733](System/Orchestrator.py#L702-L733)) — никем не вызывается (комментарий 835-842 подтверждает)
- `_start_background_esp_retry` ([Orchestrator.py:735-741](System/Orchestrator.py#L735-L741)) — никем не вызывается
- `_background_esp_retry` ([Orchestrator.py:743-775](System/Orchestrator.py#L743-L775)) — никем не вызывается
- `force_esp_retry` ([Orchestrator.py:777-805](System/Orchestrator.py#L777-L805)) — вызывается через `/api/voice/force_esp_retry` ([Orchestrator.py:2047](System/Orchestrator.py#L2047)) и кнопку UI; но фактически весь сценарий «fallback на local + кнопка вернуть ESP» не сценарий эталонной логики

**Избыточные поля в `status()` ([Orchestrator.py:550-587](System/Orchestrator.py#L550-L587)):**
- `esp_mic_fallback`, `esp_boot_wait_state`, `esp_bg_retry_active`, `force_esp_retry_available`, `mic_active_source` (дублирует `mic_reader.active_source`)

**Эндпоинт `/api/voice/force_esp_retry`** ([Orchestrator.py:2047-2050](System/Orchestrator.py#L2047-L2050)) — становится ненужным после удаления local-fallback.

**Эффект рефакторинга:** -~200 LOC, упрощение `status()`, ясность контракта (ESP всегда через MicReader, local-mic только для dev-режима без ESP).

---

### 2.2 ⚠️ HIGH — Числовые параметры голосового пайплайна расходятся с эталоном

| Параметр | Сейчас в Config | Эталон | Где живёт | Где читается |
| --- | --- | --- | --- | --- |
| `wake_word.wake_silence_timeout_sec` | 3 | **6** | `wake_word` секция | [Orchestrator.py:453](System/Orchestrator.py#L453) |
| `services.asr.reply_silence_timeout_sec` | 4.0 | **5** | `services.asr` | [Orchestrator.py:379](System/Orchestrator.py#L379) |
| `media.audio.max_command_segment_ms` | 15000 | 15000 для LISTENING ✓ | `media.audio` | [Orchestrator.py:374](System/Orchestrator.py#L374) |
| **(новый) `media.audio.reply_max_segment_ms`** | — отсутствует | **10000** | нужен новый knob | используется только в reply ветке |

**Хардкоды, которые стоит вынести в Config (после согласования):**
- `_REPLY_GUARD_SEC = 0.6` ([Orchestrator.py:449](System/Orchestrator.py#L449))
- `_STANDBY_GUARD_SEC = 0.3` ([Orchestrator.py:448](System/Orchestrator.py#L448))
- `_ENDPOINTING_EMIT_MIN_INTERVAL_SEC = 0.3` ([Orchestrator.py:896](System/Orchestrator.py#L896)) — диагностический throttle, оставить
- `_heartbeat_loop period_sec = 5.0` ([Orchestrator.py:853](System/Orchestrator.py#L853)) — диагностика, оставить
- voice_loop start retry: 5×2с ([Orchestrator.py:1850-1860](System/Orchestrator.py#L1850-L1860)) — оставить хардкод (эталон совпал)

---

### 2.3 ⚠️ MEDIUM — Дублирование счётчиков дебаунса VAD

В `_vad_loop` ([Orchestrator.py:869-1188](System/Orchestrator.py#L869-L1188)) три параллельных механизма дебаунса:
1. `_silence_run_frames` + `_endpointing_debounce_frames` — silence-side
2. `_voiced_run_frames` + `_endpointing_voiced_debounce_frames` — voiced-side
3. `_last_endpointing_emit_ts` + `_ENDPOINTING_EMIT_MIN_INTERVAL_SEC=0.3` — wall-clock throttle

Каждый покрывает реальный кейс (Phase 9 / 9.1). Все три нужны, но они растворены среди 90 LOC inline-логики с тяжёлыми коммент-блоками. **Дублирования нет, но сложность чтения высокая.**

**Рекомендация:** вынести в helper-класс `_EndpointingEmitter` или просто `dataclass` со state-машиной. -~60 LOC + ясность.

---

### 2.4 ⚠️ MEDIUM — `_command_endpointing_ms` vs `silence_after_speech_ms` — путаница

В коде живут два псевдонима одного и того же значения:
- `self._silence_after_speech_ms` ([Orchestrator.py:367-370](System/Orchestrator.py#L367-L370))
- `self._command_endpointing_ms = self._silence_after_speech_ms` — дублирующее поле для обратной совместимости

При этом в `_vad_loop` используется только `_command_endpointing_ms` ([Orchestrator.py:1102](System/Orchestrator.py#L1102)) и в payload `endpointing_started` ([Orchestrator.py:1093](System/Orchestrator.py#L1093)).

В schema.json `command_endpointing_ms` отмечен **deprecated**, но реально жив через alias. После V-S07.2 миграции — пора удалить алиас целиком.

---

### 2.5 ⚠️ MEDIUM — `mic_active_source` в `voice_loop.status()` дублирует `mic_reader.active_source`

[Orchestrator.py:569](System/Orchestrator.py#L569):
```python
"mic_active_source": "local_fallback" if (self.mic_source == "esp32" and self._esp_mic_fallback) else self.mic_source,
```

`mic_reader.active_source` ([mic_reader.py:333](System/adam/mic_reader.py#L333)) уже даёт каноничное значение. Field в voice_loop status — legacy.

---

### 2.6 ⚠️ LOW — `_run_local` использует хардкоды задержек

[Orchestrator.py:807-832](System/Orchestrator.py#L807-L832):
```python
_delays = [1.0, 2.0, 4.0]
```

Это retry-каскад для arecord (только в maintenance/local-mic режиме). Хардкод приемлем, но стоит унифицировать с `esp_retry_backoff_sec` стилем (config-driven).

---

### 2.7 ⚠️ LOW — Filler-feature: по эталону не нужен

Эталон не упоминает filler. Решено (см. discuss): **оставить код, default = выключено** (`filler_enabled=false` в Config.json).

Затрагиваемые места:
- `_filler_task` ([Orchestrator.py:2826-2890](System/Orchestrator.py#L2826-L2890)) — уже учитывает `filler_enabled=false`, выйдет рано
- `_prewarm_filler` ([Orchestrator.py:3271-3298](System/Orchestrator.py#L3271-L3298)) — уже проверяет `filler_enabled=false`, выйдет рано
- `_FILLER_WAV_CACHE` глобал ([Orchestrator.py:3268](System/Orchestrator.py#L3268)) — останется как есть (пустой)
- UI tuning-панель «Филлер» (`tuning.js`) — оставить, оператор может включить через UI

Рисков нет: код безопасен в выключенном состоянии.

---

### 2.8 ⚠️ INFO — UI status mapping корректен

[chat.js:230-239](System/WebUI/static/js/panels/chat.js#L230-L239) `HEARING_LABELS`:
- `boot_warmup` → «⌛ Инициализация» ✓
- `standby` → «💤 Ожидаю обращения» ✓
- `listening` / `reply` → «🎤 Слушаю» ✓
- `transcribing` → «⏳ Распознаю» ✓
- `thinking` → «💭 Думаю» ✓
- `tts` → «🔊 Говорю» ✓

Event mapping ([chat.js:594-649](System/WebUI/static/js/panels/chat.js#L594-L649)):
- `voice_state_change` (boot_warmup ↔ standby) ✓
- `wake_word_detected` → listening ✓
- `mic_muted` (asr_transcribing) → transcribing ✓
- `llm_thinking_started` → thinking ✓
- `tts_started` → tts ✓
- `tts_finished` → routeToIdle ✓
- `asr_reply_window_open` → reply ✓

**Эквалайзер gating** ([wakeMeter.js](System/WebUI/static/js/widgets/wakeMeter.js)):
- В boot_warmup/loading — placeholder «⌛ Инициализация…» (BRANCH.md V-S07.2 заметки)
- В standby/listening/reply — реальный сигнал из `audio_level` событий ✓

**Эталону соответствует.** Никаких правок UI не нужно (кроме возможной мелочи: `voice_state_change` с from=reply, to=standby сейчас не обрабатывается явно в chat.js — `tts_finished` уже скрыто переводит в idle).

---

### 2.9 ⚠️ INFO — `_wake_silence_timeout_sec` reload bug

[Orchestrator.py:3350](System/Orchestrator.py#L3350):
```python
voice_loop._wake_silence_timeout_sec = float(ww_cfg.get("wake_silence_timeout_sec", 6.0))
```

Hot-reload через `_rebuild_clients` обновляет timeout, но `__init__` line 453 имеет fallback `6.0`. После перехода эталонных значений (`wake_silence_timeout_sec=6`) hot-reload и init будут совпадать.

---

### 2.10 ⚠️ INFO — Heartbeat / level_emit_loop — диагностика, оставить

- `_heartbeat_loop` ([Orchestrator.py:844-867](System/Orchestrator.py#L844-L867)) — каждые 5с event `voice_loop_heartbeat`. Делает loop liveness видимой. Не трогать.
- `_level_emit_loop` ([mic_reader.py:494-540](System/adam/mic_reader.py#L494-L540)) — wall-clock fallback эмиттер `audio_level`. Не трогать.

---

## 3. Мини-баги / cosmetic

1. **Inconsistent default `wake_silence_timeout_sec`:** в `__init__` fallback = 6.0 ([Orchestrator.py:453](System/Orchestrator.py#L453)), но Config.json = 3, и существующий комментарий говорит "3 per reference logic" — комментарий устарел.

2. **`apply_audio_config` молча проглатывает удалённые поля:** при удалении `esp_mic_fail_threshold` нужно ничего не делать — поле в схеме больше нет.

3. **Orphan envs в `adam_start.sh`:** `LIVE_VLM_CONTAINER`, `LIVE_VLM_CAMERA` определены, но используются только в нескольких местах — приемлемо.

4. **`SPEECH_SERVICES` массив** ([adam_start.sh:148-149](scripts/adam_start.sh#L148-L149)) содержит только TTS, ASR живёт отдельно как Docker (line 257-277). Это работает, но именование вводит в заблуждение — переименовать в `SYSTEMD_SPEECH_SERVICES`.

5. **`OWW` инициализация:** [Orchestrator.py:427-443](System/Orchestrator.py#L427-L443) если модель отсутствует, лог. Можно сделать жёстче в exhibition mode (сейчас warn, должно быть raise).

---

## 4. Что выглядит здорово — НЕ трогать

- MicReader архитектура (Phase 7) — чистая producer/consumer model, single emitter audio_level
- ANSWER pipeline (`_stream_llm_and_speak`) — concurrent producer/consumer LLM+TTS, sentence-boundary streaming
- `LeadingNoiseFilter` для удаления prefix-noise (Думаю, Слушаю, и т.п.)
- `_warmup_llm_prefix` — KV cache priming для Gemma SWA
- Event-driven UI status mapping — clear separation top-level state vs phase
- `turn_lock` + `session_lock` — sane concurrency primitives
- `runtime_state.success_sound_played` идемпотентный флаг
- power_gate для exhibition mode

---

## 5. Открытые вопросы для рефакторинга

Зафиксирую перед PLAN.md:

**Q1.** Удалять ли эндпоинт `/api/voice/force_esp_retry` + UI-кнопку «Force ESP retry»? (После удаления legacy fallback кнопка теряет смысл.)

**Q2.** `_run_local` (легитимный путь maintenance-mode без ESP) — оставить как есть с хардкод-ретраями `[1.0, 2.0, 4.0]`? Или унифицировать с MicReader-стилем?

**Q3.** Хардкоды `_REPLY_GUARD_SEC=0.6` и `_STANDBY_GUARD_SEC=0.3` — вынести в Config.json (новые поля `services.asr.reply_guard_sec` / `wake_word.standby_guard_sec`)? Или оставить хардкодом (значения не подкручиваются в exhibition)?

**Q4.** Endpointing helper-класс из §2.3 — извлекать в отдельный модуль `System/adam/endpointing.py` или inline `dataclass` в Orchestrator.py?

**Q5.** Mic OFF до STANDBY — оставить текущую модель (MicReader дренирует сокет всё время + UI скрывает эквалайзер до pipelineReady) или сделать жёсткий backend-gate (MicReader.start() переносится в `_orchestrated_startup` после warmup)? Текущая модель проще и работает; жёсткая модель строже соответствует букве эталона.

**Q6.** `wake_word.wake_silence_timeout_sec` сейчас в секции `wake_word`. Логически это «таймер LISTENING без речи», т.е. часть голосового пайплайна, а не wake-word engine'а. Переименовать/перенести в `services.asr.listening_silence_timeout_sec`? Или оставить?
