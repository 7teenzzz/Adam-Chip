# Phase 7: ESP32 Mic Pipeline Refactor — MicReader keep-alive - Context

**Gathered:** 2026-05-16
**Status:** Ready for planning
**Branch:** `V-S07.3-ESP32_mic_fix`

<domain>
## Phase Boundary

Извлечь работу с ESP32 audio-stream в долгоживущую producer-задачу `MicReader` по аналогу `CameraReader`. Producer/consumer-разделение между сетевым I/O (MicReader) и VAD/OWW логикой (voice_loop). Поток открывается до warmup TTS, держится keep-alive весь срок жизни Orchestrator, drainer всегда активен, переоткрытие на exception с экспоненциальным backoff. `disable_local_fallback=true` — никогда не падать на local mic.

**В scope:**
- Новый модуль `System/adam/mic_reader.py` с классом `MicReader`.
- Упрощение `Orchestrator._run_esp32` до consumer'а на shared queue.
- Boot ordering: MicReader стартует в `_orchestrated_startup` после `_wait_for_services`, до `_warmup_wakeup`.
- Удаление `_audio_level_monitor` (его роль перенимает MicReader как единый emitter `audio_level`).
- Новый voice_state `"boot_warmup"` — drain-only ветка в `_vad_loop`.
- Config: `disable_local_fallback`, `esp_open_timeout_sec`, `esp_probe_after_fails`, `esp_retry_backoff_sec`.
- UI: «⌛ Инициализация» во время boot_warmup; плашка Mic и эквалайзер тихо стоят до выхода в standby.

**НЕ в scope:**
- Реализация MicReader для local mic (использование fallback на local).
- Изменение `_NO_PROXY_OPENER` и proxy-handling.
- Изменение mute/unmute mechanism внутри `_vad_loop` (он остаётся).
- Изменение `_make_stereo_reader` (используем как есть).
- Изменение `EspAudioHealthMonitor` (он мониторит /api/audio, не stream).

</domain>

<decisions>
## Implementation Decisions

### Queue policy (producer ↔ consumer)
- **D-01:** Один `asyncio.Queue` с `maxsize=50` (~1 секунда аудио при 20 ms frame).
- **D-02:** **drop_oldest** policy: MicReader пишет через `put_nowait`. При `QueueFull` — `get_nowait()` (выкинуть старейший) + `put_nowait(chunk)`. Voice_loop всегда читает «live edge» — это критично для real-time VAD/OWW (otherwise wake-word detection отстаёт на 1 сек).
- **D-03:** Single-producer (MicReader._run) → single-consumer (voice_loop._vad_loop). Никакого fan-out: события `audio_level` MicReader эмитит **до** put в queue, не через consumer.

### MicReader startup timing
- **D-04:** MicReader стартует в `_orchestrated_startup` **после `_wait_for_services`** (LLM/TTS/ASR/VLM healthy), **до `_warmup_wakeup`**. Гарантировано: ESP /api/audio отвечает (services_ok прошёл), значит control plane :80 жив. Stream open на :81 имеет шанс с первой попытки.
- **D-05:** ESP-boot-wait (legacy `_wait_for_esp_ready` 90 sec polling) переезжает внутрь MicReader как часть его retry-loop. MicReader сам решает когда ESP «готов» — через `/api/status` probe перед каждым новым open.
- **D-06:** При старте MicReader voice_loop ещё не запущен. После того как stream active → MicReader эмитит `mic_reader_active` event → `_orchestrated_startup` вызывает `voice_loop.start()` с уже-готовым потоком.

### Mute API (voice_loop ↔ MicReader)
- **D-07:** Прямая coupling через `voice_loop.muted_by_tts` (атрибут). MicReader в цикле читает `read_fn` всегда (drain ESP buffer); если `voice_loop.muted_by_tts is True` — **не делает put_nowait** (бросает chunks). Иначе — кладёт в queue.
- **D-08:** Это убирает текущий `_esp32_drain_during_mute` task: drainer теперь не отдельная задача, а просто `if muted: continue` ветка в MicReader-loop. Меньше движущихся частей.
- **D-09:** Mute не означает «закрыть stream» — соединение остаётся открытым весь mute window. `mic_muted` event эмитится из voice_loop как раньше (UI-сигнал, не команда MicReader-у).

### audio_level emission
- **D-10:** **MicReader — единый источник `audio_level` events.** Эмитит каждый ~100 ms (5 фреймов × 20 ms). `_audio_level_monitor` (фоновая задача в lifespan) **удалена**.
- **D-11:** Payload `state` берётся из `voice_loop._voice_state` (если voice_loop запущен) или `"boot_warmup"` (если MicReader готов, но voice_loop ещё не зашёл в `start()`).
- **D-12:** Payload `source` — MicReader сам знает: `esp32_stereo` / `esp32_mono` / `"connecting"` (до получения WAV header) / `"failed"` (на retry-backoff).

### voice_state `"boot_warmup"`
- **D-13:** Новое значение `voice_state` (рядом со standby/listening/reply). voice_loop в boot_warmup:
  - читает chunks из queue (чтобы queue не переполнялась drop_oldest'ом)
  - **не** сканирует OWW (Adam не должен реагировать на собственный warmup TTS)
  - **не** делает endpointing
- **D-14:** Переходы:
  - `voice_loop.start()` → начальный state `"boot_warmup"`
  - После завершения `_warmup_wakeup` → `_orchestrated_startup` зовёт `voice_loop._set_voice_state("standby", "warmup_done")`
- **D-15:** Frontend: HEARING_LABELS["boot_warmup"] = «⌛ Инициализация». Эквалайзер и VU-meter в placeholder пока voice_state не в {standby, listening, reply}.

### Disabling local fallback
- **D-16:** Новый config-ключ `services.asr.disable_local_fallback` (default `true`). Когда true — voice_loop никогда не вызывает `_run_local`. Если MicReader не может открыть stream — продолжает retry бесконечно с backoff.
- **D-17:** Legacy `_esp_mic_fallback` flag оставлен (для `disable_local_fallback=false`), но в production-path не активируется.

### Retry / backoff
- **D-18:** `esp_open_timeout_sec` (default 8 sec) вместо hardcode 30 sec.
- **D-19:** `esp_probe_after_fails` (default 2) — после N consecutive fails MicReader сначала пробует `/api/status` на :80; если probe fail — backoff и не пытается :81 (экономим 8s × N).
- **D-20:** `esp_retry_backoff_sec: [2, 4, 8, 15]` — последовательность пауз между retry. Последнее значение reuse'ится.

### Claude's Discretion
- Точный layout `MicReader` class (private methods, naming) — за исполнителем.
- Lifecycle hooks для `Orchestrator.lifespan()` (start/stop вызовы) — исполнитель решает по аналогии с `camera_reader`.
- Внутреннее именование событий (`mic_reader_started`, `mic_reader_active`, `mic_reader_error`, и т.д.).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & invariants
- `CLAUDE.md` — non-obvious invariants, особенно: `_NO_PROXY_OPENER`, half_duplex_mute, ESP32 socket gotchas
- `README.md` — inference stack, network topology (Jetson 10.10.10.1, ESP32 10.10.10.171)
- `docs/AGENT-PROTOCOL.md` — поведение агента-разработчика

### Code references (must-read for implementation)
- `System/Orchestrator.py` §`class CameraReader` — паттерн для MicReader
- `System/Orchestrator.py` §`_run_esp32` (line ~746) — текущая stream-open логика
- `System/Orchestrator.py` §`_esp32_drain_during_mute` (line ~841) — текущий drainer
- `System/Orchestrator.py` §`_audio_level_monitor` (line ~1687) — удаляемая задача
- `System/Orchestrator.py` §`_active_audio_source_label` (line ~468) — source label rules
- `System/Orchestrator.py` §`_vad_loop` (line ~904) — consumer-side читает chunks
- `System/adam/device.py` — McuClient.mic_stream_url(), _NO_PROXY_OPENER usage
- `System/Config.schema.json` — новые ключи добавить здесь, документация на 100%

### Phase predecessors (context for callbacks)
- `.planning/phases/asr-wakeword-fixes/` — last touch на voice pipeline (если есть)
- ROADMAP.md §Phase 7 — high-level deliverables

### UI surface
- `System/WebUI/static/js/panels/chat.js` — HEARING_LABELS, drawVuMeter, audio_level handler
- `System/WebUI/static/js/widgets/wakeMeter.js` — pipelineReady gate

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CameraReader` class в `Orchestrator.py` — паттерн для долгоживущей задачи (start/stop, retry loop, event log).
- `_NO_PROXY_OPENER` (top of Orchestrator.py) — must-use для urlopen к ESP32:81.
- `_make_stereo_reader` ([Orchestrator.py:885](System/Orchestrator.py#L885)) — wrapper для downmix stereo→mono с per-channel RMS. Использовать as-is.
- `_active_audio_source_label` ([Orchestrator.py:468](System/Orchestrator.py#L468)) — логика выбора лейбла. Переезжает в MicReader.

### Established Patterns
- `EventLog.append(event_type, payload)` — все события через единую шину.
- `asyncio.create_task(name="…")` + cancel-on-shutdown — стандартный pattern lifespan tasks.
- `settings.section("services").get("asr", {})` — чтение config с graceful defaults.

### Integration Points
- **Orchestrator.lifespan** — добавить `mic_reader.start()` после `camera_reader.start()`; `mic_reader.stop()` на shutdown.
- **`_orchestrated_startup`** — порядок: `_wait_for_services` → `mic_reader.start()` → `_warmup_wakeup` → `voice_loop.start()` (входит в boot_warmup) → after warmup `_set_voice_state("standby")`.
- **`_vad_loop`** — заменить chunk-read source: вместо `read_fn(frame_bytes)` (raw socket) → `mic_reader.get_chunk()` (async queue get). Добавить ветку `if voice_state == "boot_warmup": continue`.
- **`_run_esp32`** — удалить (логика переехала в MicReader). `voice_loop._run()` теперь всегда зовёт упрощённый consumer `_run_via_mic_reader(frame_bytes)`.
- **`rebuild_clients`** — при PATCH `services.asr` MicReader получает новые timeout/backoff/probe значения (через `mic_reader.apply_config()` или restart).

</code_context>

<specifics>
## Specific Ideas

- **Drop_oldest должен быть **видим** для диагностики**: счётчик `dropped_frames` в MicReader, event `mic_reader_overflow` каждые N drops (rate-limited).
- **Single source of truth для audio_level**: после удаления `_audio_level_monitor` тест на регрессию — `_audio_level_monitor` references в коде/импортах не должны остаться.
- **`voice_loop_started` сейчас флипает `pipelineReady=true` в wakeMeter** — надо снять (boot_warmup ещё не ready). pipelineReady должен flip на первом audio_level со state ∈ {standby, listening, reply} или на `voice_state_change to=standby` event.

</specifics>

<deferred>
## Deferred Ideas

- Адаптивный backoff (увеличивать paused interval при многих consecutive fails) — пока фиксированная последовательность [2,4,8,15].
- Метрики stream uptime/recovery в `/api/agent/status` — пока только в events.jsonl.
- Hot-reload изменений MicReader через `apply_config` (без restart task) — пока на каждый PATCH рестартует MicReader через `rebuild_clients`.
- Реализация MicReader для local mic source (для maintenance-режима без ESP) — текущая фаза только ESP32.

</deferred>

---

*Phase: 7-ESP32 Mic Pipeline Refactor — MicReader keep-alive*
*Context gathered: 2026-05-16*
