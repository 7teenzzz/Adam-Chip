# 08-02 — Reply mode refactor ✓

**Дата:** 2026-05-17
**Plan:** 08-02-PLAN.md

## Что сделано

### `System/Orchestrator.py` — `__init__` (строки ~375-379)

- УДАЛЕНО: `self._reply_absolute_deadline_sec` атрибут.
- ДОБАВЛЕНО: `self._reply_silence_timeout_sec = float(asr_cfg.get("reply_silence_timeout_sec", 4.0))` с комментарием про D-02 (max_segment_ms — общий guard).
- НЕ ТРОНУТО: `self._REPLY_GUARD_SEC = 0.6` (per CONTEXT D-04, REQ-NO-SELF-ECHO-VAD).

### `System/Orchestrator.py` — `_vad_loop` reply-блок (старые строки 898-933)

Заменено условие срабатывания таймера. Раньше:

```python
absolute_deadline = self._reply_window_sec + self._reply_absolute_deadline_sec
no_speech_expired = elapsed >= self._reply_window_sec and speech_ms < self.min_speech_ms
hard_cutoff = elapsed >= absolute_deadline
if no_speech_expired or hard_cutoff:
    reason = "absolute_deadline" if hard_cutoff else "no_speech"
    ...
    self._set_voice_state("standby", "reply_expired")
```

Стало:

```python
if speech_ms == 0 and elapsed >= self._reply_silence_timeout_sec:
    ...
    event_log.append("reply_window_expired", {..., "reason": "reply_silence_timeout"})
    self._set_voice_state("standby", "reply_silence_timeout")
```

`_REPLY_GUARD_SEC` guard (0.6 sec) сохранён verbatim перед таймером.

### `System/Orchestrator.py` — `_vad_loop` accumulation/endpointing (старые строки 950-991)

УДАЛЁН дубликат для reply (`elif effective_voiced` / `elif speech_frames` / `else`). Listening и reply теперь идут через ОДИН блок:

```python
if self._voice_state in ("listening", "reply"):
    if effective_voiced: ...
    elif speech_frames: ...  # emits endpointing_started
    else: vad_state = "silence"
speech_frames.append(chunk)
```

Submission/drain блок (далее) НЕ ТРОНУТ — `max_segment_ms` cutoff работает одинаково для обоих состояний (D-02).

## Verify

```
$ python3 verify.py → Plan 08-02: OK (ast valid, all asserts pass)
$ PYTHONPATH=System python3 -c "import Orchestrator" → module imports OK
```

- `grep -c "_reply_absolute_deadline_sec\|absolute_deadline\|hard_cutoff\|no_speech_expired"` — 0.
- `grep -c 'event_log.append("endpointing_started"'` — ровно 1 (было 2).
- `grep -c 'self._REPLY_GUARD_SEC: float = 0.6'` — ровно 1 (нетронут).
- `_voice_state in ("listening", "reply")` — найдено, объединение работает.

## Инварианты сохранены

- `half_duplex_mute=true` — НЕ тронут (CLAUDE.md §Non-obvious invariants #5, REQ-NO-SELF-ECHO-VAD).
- `_REPLY_GUARD_SEC=0.6` — defence-in-depth для будущих сценариев акустического контура.

## Wave & deps

- Wave 2, depends_on: [08-01].
- Готов для Plan 08-03 (heartbeat) и затем 08-04 (UAT).
