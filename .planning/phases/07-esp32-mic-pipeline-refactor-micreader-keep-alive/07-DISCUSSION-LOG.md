# Phase 7: ESP32 Mic Pipeline Refactor — MicReader keep-alive - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-16
**Phase:** 7-ESP32 Mic Pipeline Refactor — MicReader keep-alive
**Areas discussed:** Queue policy, Start timing, Mute API, audio_level owner

---

## Queue policy (producer ↔ consumer)

| Option | Description | Selected |
|--------|-------------|----------|
| drop_oldest, size=50 (≈1 сек) | MicReader пишет в queue. При QueueFull — выкидывает старейший chunk. Voice_loop всегда читает «live edge». Лучший вариант для real-time VAD. | ✓ |
| backpressure, size=50 | MicReader блокируется на .put() пока voice_loop не читает. Но ESP32 буфер переполнится за ~1 сек — возможен IncompleteRead. | |
| drop_oldest, size=10 (~200 мс) | Меньше latency при отставании, но больше dropped frames при GIL pauses (LLM JIT и т.п.). | |

**User's choice:** drop_oldest, size=50
**Notes:** real-time VAD/OWW критичны — отставание queue даёт реактивность wake-word на 1 сек хуже, что неприемлемо. 50 frames = разумный compromise.

---

## MicReader startup timing

| Option | Description | Selected |
|--------|-------------|----------|
| Сразу в lifespan (до _orchestrated_startup) | MicReader пытается открыть stream с самого начала. Даже если ESP не готов — retry-loop работает. | |
| В _orchestrated_startup до warmup | MicReader стартует после _wait_for_services. Гарантированно: ESP ответил /api/audio перед stream open. | ✓ |
| При voice_loop.start() (как сейчас _run_esp32) | Никаких изменений в startup ordering. Stream открывается позже — не решает slow-first-connection. | |

**User's choice:** В _orchestrated_startup до warmup
**Notes:** _wait_for_services даёт гарантию что network up и сервисы здоровы. До warmup — stream open до Adam'a начнёт говорить, drainer уже работает к моменту TTS.

---

## Mute API (voice_loop ↔ MicReader)

| Option | Description | Selected |
|--------|-------------|----------|
| Никак — reader всегда drain, voice_loop игнорирует chunks | MicReader постоянно читает и кладёт в queue. Voice_loop в muted-состоянии выбирает chunks из queue но не проводит VAD/OWW. | |
| voice_loop.mic_muted=True → MicReader продолжает читать но drop'ит в queue | MicReader имеет флаг muted: в muted состоянии drain'ит без put_nowait. Меньше IO через queue, но больше coupling. | ✓ |
| Две очереди: vad_queue (gated) + level_queue (always) | MicReader ведёт две очереди: для VAD и для UI levels. Сложнее, не выигрывает. | |

**User's choice:** voice_loop.mic_muted=True → MicReader продолжает читать но drop'ит в queue
**Notes:** drainer как отдельная задача (`_esp32_drain_during_mute`) упрощается до `if muted: continue` ветки внутри MicReader-loop. Меньше движущихся частей. Прямая coupling через атрибут voice_loop.muted_by_tts.

---

## audio_level emission ownership

| Option | Description | Selected |
|--------|-------------|----------|
| MicReader — всегда и всюду | MicReader эмитит audio_level производя voice_state из voice_loop.voice_state. _audio_level_monitor удалён. Единый source of truth. | ✓ |
| voice_loop (как сейчас) | MicReader только работает с socket'ом. voice_loop в _vad_loop эмитит audio_level как раньше. | |

**User's choice:** MicReader — всегда и всюду
**Notes:** _audio_level_monitor (фоновая задача в lifespan на local mic для idle UI) удаляется полностью. MicReader — единственный источник audio_level. UI получает консистентные события вне зависимости от состояния voice_loop.

---

## Claude's Discretion

- Точный layout `MicReader` class (private methods, naming) — за исполнителем.
- Lifecycle hooks для `Orchestrator.lifespan()` (start/stop вызовы) — исполнитель решает по аналогии с camera_reader.
- Внутреннее именование событий (`mic_reader_started`, `mic_reader_active`, `mic_reader_error`, и т.д.).

## Deferred Ideas

- Адаптивный backoff (увеличивать paused interval при многих consecutive fails) — пока фиксированная последовательность [2,4,8,15].
- Метрики stream uptime/recovery в `/api/agent/status` — пока только в events.jsonl.
- Hot-reload изменений MicReader через `apply_config` (без restart task) — пока на каждый PATCH рестартует MicReader через `rebuild_clients`.
- Реализация MicReader для local mic source (для maintenance-режима без ESP) — текущая фаза только ESP32.
