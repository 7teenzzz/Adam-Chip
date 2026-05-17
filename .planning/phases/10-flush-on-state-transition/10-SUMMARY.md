# Phase 10 — Flush stale audio on state transitions ✓

**Дата:** 2026-05-17
**Цель:** восстановить поведение V-S07.1 `_drain_esp32_backlog` в архитектуре V-S07.3 (MicReader + queue) — устранить feeding stale TCP-buffered аудио в WhisperX.

## Контекст: почему стало плохо после Phase 7 рефактора

**V-S07.1 (старая ветка):** _vad_loop читал ESP32 socket напрямую через `read_fn`. После каждого `_transcribe_and_dispatch` явно вызывал `_drain_esp32_backlog(read_fn, frame_bytes, mute_start)` — отбрасывал `mute_duration_ms / frame_ms` байт из raw socket'а. По логам тестового сеанса 15:41 MSK видно `esp32_mic_drained {frames: 1112, ms: 22240}` — до 22 секунд аудио дренировалось разово.

**V-S07.3 (Phase 7 refactor):** этот шаг **удалён**. Причина: MicReader теперь читает socket в отдельной asyncio task `_drain_loop`. Во время mute (transcribe + LLM + TTS) MicReader продолжает читать socket, но не push'ит в queue → теоретически TCP буфер ESP32 всегда чистый.

**На практике (Test 4):** MicReader's `_drain_loop` периодически тормозит на 200-500 мс из-за CPU/W5500-SPI конкуренции с MJPEG-камерой. В эти моменты kernel TCP буфер ESP32 накапливает 1-3 сек аудио. Когда `_drain_loop` оживает, бурстит через очередь к consumer'у. speech_frames заполняется stale-чанками за десятки мс после wake → WhisperX видит TTS self-echo + комнатный шум → возвращает пусто.

Доказательство из Test 4 (events.jsonl 12:14:07.638-731):
- `12:14:07.153 synthetic=true` (Phase 9 watchdog сигналит что MicReader стопится в reply mode)
- `12:14:07.375 → 12:14:07.437`: 24 audio_level event'а за 62 мс = MicReader bursts ~2.4 сек аудио через очередь
- `12:14:07.638 WAKE`, `12:14:07.731 ASR pcm_ms=3680` — за 93 мс wall-clock накоплено 3.68 сек аудио (физически невозможно из реального времени → старое из буфера)

## Изменения в коде

### `System/adam/mic_reader.py`

**Новое состояние:**
- `self._discard_until_ts: float = 0.0` — wall-clock deadline. Пока `perf_counter() < этого`, `_drain_loop` читает socket но discard'ит chunk вместо push в queue.

**Новый метод:**
```python
def flush_queue(self, discard_window_ms: float = 200.0) -> int:
    dropped = 0
    while True:
        try:
            self._queue.get_nowait()
            dropped += 1
        except asyncio.QueueEmpty:
            break
    if discard_window_ms > 0:
        self._discard_until_ts = time.perf_counter() + (discard_window_ms / 1000.0)
    return dropped
```

**Drain_loop gate:** добавлен после mute-gate.
```python
if self._discard_until_ts > 0.0 and time.perf_counter() < self._discard_until_ts:
    continue
```
Семантика идентична mute-gate: socket читается (kernel TCP buffer дренируется), но chunk не попадает в queue.

### `System/Orchestrator.py`

Вызовы `self.mic_reader.flush_queue(200.0)` в 3 точках с events:

1. **На `wake_word_detected`** (в standby branch). Защита на случай если TCP буфер накопил что-то в standby/standby_guard.
   ```python
   event_log.append("mic_queue_flushed", {"trigger": "wake_word", ...})
   ```

2. **После `_transcribe_and_dispatch`** возврата, ПЕРЕД transition в reply/standby — это **V-S07.1 эквивалент**. Это самая важная точка: mute window был самый долгий (16-22 сек), TCP буфер мог накопить больше всего.
   ```python
   event_log.append("mic_queue_flushed", {"trigger": "post_transcribe", ...})
   ```

3. **На `reply_silence_timeout`** в reply→standby transition. Чтобы следующее listening не унаследовало стале-аудио из reply window.
   ```python
   event_log.append("mic_queue_flushed", {"trigger": "reply_silence_timeout", ...})
   ```

## Различие с V-S07.1 решением

| | V-S07.1 | Phase 10 (V-S07.3) |
|---|---|---|
| Слой | Raw socket (`read_fn`) | MicReader queue + discard window |
| Объём drain | Точное byte count = mute_duration / frame_ms + 200ms jitter | All-in-queue + 200ms wall-clock discard |
| Где вызывается | Только после transcribe | После transcribe + на wake + на reply EXPIR |
| Метрика drain | `esp32_mic_drained {frames, ms}` | `mic_queue_flushed {frames, ms, trigger, discard_window_ms}` |
| Drain TCP buffer | Да (raw socket read) | Да (через discard window — drain_loop продолжает читать socket) |

**Phase 10 strictly шире чем V-S07.1:**
- Тот же эффект от post-transcribe drain (V-S07.1 эквивалент).
- Плюс defense на wake и reply EXPIR.
- Discard-window вместо byte-count — не нужно знать заранее сколько накопилось.

## Verify

```
$ python3 -c "import ast; ast.parse(open('System/Orchestrator.py').read())" → AST OK
$ python3 -c "import ast; ast.parse(open('System/adam/mic_reader.py').read())" → AST OK
$ PYTHONPATH=System python3 -c "from adam.mic_reader import MicReader; assert hasattr(MicReader,'flush_queue')" → OK
```

## Ожидаемый эффект на следующем тесте

| Метрика | Test 4 (без Phase 10) | Ожидаемо |
|---|---|---|
| Empty ASR rate | 36% (4 из 11) | ≤ 10% (только реальные wake-без-речи) |
| pcm_ms за 93мс после wake | 3680ms (стале) | ~100ms (только живое) |
| `mic_queue_flushed` events | 0 | 3-10 за сессию (по числу transitions) |
| TTS self-echo в speech_frames | Регулярно | Нет |

## Manual UAT — pending

После рестарта оркестратора + hard reload UI:
```bash
sudo systemctl restart adam-orchestrator.service
```

Тест с 7 фразами обычной громкостью. Запустить:
```bash
python3 scripts/adam_test_reply_hang.py --last-minutes 5
grep -c '"type": "mic_queue_flushed"' data/adam/events.jsonl   # должно быть 3-10 за тест
grep -c '"empty": true' data/adam/events.jsonl                  # должно резко уменьшиться
```

Если empty ASR rate всё ещё высокий — открыть отдельную фазу под root cause MicReader stalls (CPU profiling / W5500 SPI contention с MJPEG камерой на :81).
