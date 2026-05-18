---
title: Fix: ESP32 audio stream закрывается во время mute → background drain task
date: 2026-05-16
priority: HIGH
context: [voice-pipeline-vs-ui-layering](../../notes/voice-pipeline-vs-ui-layering.md)
---

# Background-drain ESP32 audio stream во время mute

## Проблема — корневой триггер

После `mic_muted` (на момент ASR transcribing) Jetson **прекращает читать** PCM из ESP32 long-poll stream. `_transcribe_and_dispatch()` блокирует на 10–20 секунд (ASR + LLM + TTS).

Цифры:
- 16 kHz × 2 ch × 16 bit = **64 KB/sec** PCM
- 19-секундный mute window = **~1.2 MB** накопится в TCP send buffer
- W5500 SPI Ethernet на ESP32 имеет очень ограниченный буфер (десятки KB)
- ESP32 firmware закрывает TCP соединение (write timeout / watchdog)
- Jetson при попытке drain получает `IncompleteRead(161536 bytes read)` → death-spiral в `_vad_loop`

**Это нормальное поведение ESP32 firmware**, не bug. Bug в архитектуре Jetson-side — нельзя останавливать чтение от ESP32 на ~20 секунд, ESP не дизайнен под это.

Существующий `_drain_esp32_backlog` ([Orchestrator.py:828](../../../System/Orchestrator.py#L828)) **запускается после unmute** — слишком поздно. К этому моменту ESP уже разорвал.

## Fix — background drainer

Запустить фоновую задачу при `mic_muted`, которая **постоянно читает** из ESP stream и **сбрасывает** байты, пока mute активен. Это держит TCP socket alive — ESP не закрывает connection.

### Псевдокод

```python
# В _vad_loop, перед blocking _transcribe_and_dispatch:
mute_start = time.perf_counter()
self.muted_by_tts = True
event_log.append("mic_muted", {"reason": "asr_transcribing"})

drainer_stop = asyncio.Event()
drainer_task = None

if not _using_process:  # ESP32 mode
    drainer_task = asyncio.create_task(
        self._esp32_background_drainer(_reader[0], frame_bytes, drainer_stop),
        name="adam_esp32_drainer",
    )

try:
    spoke = await self._transcribe_and_dispatch(pcm)
finally:
    if drainer_task:
        drainer_stop.set()
        await drainer_task  # ensure clean stop, read pointer не в drained state

# После — обычная логика
event_log.append("mic_unmuted", {"reason": "transcription_complete"})
self.muted_by_tts = False
```

```python
async def _esp32_background_drainer(
    self,
    read_fn: Callable[[int], bytes],
    frame_bytes: int,
    stop_event: asyncio.Event,
) -> None:
    """Drain (discard) ESP32 audio bytes while voice_loop is muted.
    Keeps TCP socket alive — ESP firmware closes connection if Jetson
    stops reading for ~10+ seconds. Without this drainer, every turn
    triggers IncompleteRead after transcribe + LLM + TTS dispatch."""
    while not stop_event.is_set():
        try:
            chunk = await asyncio.to_thread(read_fn, frame_bytes)
            if not chunk:
                await asyncio.sleep(0.05)
        except Exception as exc:
            event_log.append("esp32_mic_drainer_error", {"error": str(exc)})
            return  # let main loop see this on next read
```

### Тонкости

1. `read_fn` это **тот же read** который использует `_vad_loop`. Конкуррентное чтение из одного HTTPResponse — небезопасно. Нужно либо:
   - **Передать ownership reader в drainer** на время mute, и забрать обратно (через mutable list или Lock)
   - **Использовать `asyncio.Lock` на read_fn** — но тогда блокирующий read под локом всё равно эксклюзивный
2. После drainer-stop `_drain_esp32_backlog` уже не нужен (стрим был всё время живой) — убрать вызов или сделать no-op.
3. Если drainer получил exception (`IncompleteRead`) — пробросить через event, в `_run_esp32` retry connection после unmute. С [fix-vad-loop](fix-vad-loop-exception-handling.md) это сработает корректно.

## Альтернатива (хуже)

Послать ESP32 команду `POST /api/audio {"pause": true}` при mute, потом `{"pause": false}` при unmute. Требует расширения firmware. **Не делать** — увеличивает связь Jetson↔ESP firmware.

## Acceptance

После прогрева оркестратора прогнать 5 turns подряд через UI без пауз:
- ✅ Воспроизвести каждый turn без обрыва ESP32 stream
- ✅ В логе **нет** `IncompleteRead` после `tts_finished`
- ✅ В логе видим `esp32_mic_drainer_started` / `esp32_mic_drainer_stopped` события (опционально для observability)
- ✅ `_session_fail_count` остаётся 0 на протяжении 5 turns

## Затронутые файлы

- `System/Orchestrator.py` — добавить `_esp32_background_drainer` method, изменить `_vad_loop` mute handling

## Связано

- Парный фикс с [fix-vad-loop-exception-handling](fix-vad-loop-exception-handling.md). Этот предотвращает trigger, тот делает retry-логику работоспособной если trigger всё же случится.
- Возможно подсасет clip_burst 4776 — см. [investigate-mic-unmuted-clip-burst](investigate-mic-unmuted-clip-burst.md).
