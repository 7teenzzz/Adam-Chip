# 08-03 — Heartbeat diagnostic ✓

**Дата:** 2026-05-17
**Plan:** 08-03-PLAN.md

## Что сделано

### `System/Orchestrator.py` — `_vad_loop`

ДОБАВЛЕНО (после `_was_endpointing = False`, перед `try:`):

```python
_heartbeat_period_sec = 5.0
_last_heartbeat_ts = 0.0
_loop_iter_count = 0
```

ДОБАВЛЕНО (в начале каждой итерации `while self.running:`):

```python
_loop_iter_count += 1
_now = time.perf_counter()
if _now - _last_heartbeat_ts >= _heartbeat_period_sec:
    event_log.append("voice_loop_heartbeat", {
        "state": self._voice_state,
        "iter": _loop_iter_count,
        "uptime_sec": round(_now, 2),
        "vad_state": self.vad_state,
    })
    _last_heartbeat_ts = _now
```

Heartbeat работает во ВСЕХ voice_state (boot_warmup, standby, listening, reply) — это маркер живости.

### Что НЕ тронуто

- Существующее событие `voice_state_change` (эмитится в `_set_voice_state`) — оставлено как было. Вместе с `voice_loop_heartbeat` это закрывает REQ-DIAGNOSTIC-LOGS-VOICE-STATE (D-09).
- SIGUSR1 → asyncio task stack dump — НЕ добавлен (D-10 deferred в follow-up фазу).
- `_heartbeat_period_sec` — константа в коде, не в Config (diagnostic detail, не tuning).

## Verify

```
$ python3 -c "..." → Plan 08-03: OK
$ PYTHONPATH=System python3 -c "import Orchestrator" → import OK
```

## При hang в продакшене

Когда оркестратор замёрзнет (если повторится):

1. Последний `voice_loop_heartbeat` в `events.jsonl` покажет state, iter, vad_state — точное место где loop умер.
2. Отсутствие новых heartbeat > 5-6 sec = подтверждённый hang.
3. Запустить `scripts/adam_test_reply_hang.py` (создаётся в 08-04) для автоматического анализа.

## Wave & deps

- Wave 2, depends_on: [08-01] (логически — общий файл с 08-02; коммит уже учёл 08-02).
