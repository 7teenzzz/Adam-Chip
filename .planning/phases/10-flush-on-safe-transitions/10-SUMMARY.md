# Phase 10 v2 — Flush stale audio on safe state transitions ✓

**Дата:** 2026-05-17
**Цель:** портировать V-S07.1 принципы дренажа stale-аудио в V-S07.3 архитектуру (MicReader-стрим), **только в безопасных точках**.

## Почему v2 (контекст реверта v1)

**Phase 10 v1** (commit `36cded5`) добавил `flush_queue(200ms)` в ТРЁХ точках: post-transcribe, reply_silence_timeout, **и wake_word_detected**. Третий вызов оказался катастрофичным:

- **Test 5 (v1 deployed):** 3 успешных из 9 ASR (33%) vs Test 4 baseline 64%.
- **5 подряд `wake_silence_timeout`** на старте теста — пользователь сразу после wake начинал говорить, но первые ~200ms речи попадали в discard_window MicReader → VAD не детектил начало речи → SILTO 3-4 sec.
- Логи показали `FLUSH frames=0 ms=0 trigger=wake_word` — queue в моменте wake пустая, но discard window всё равно отрезал начало.

V-S07.1 НЕ дренировал на wake. Это **критическое наблюдение** которое v1 упустил.

Реверт: commit `5664121` (git revert 36cded5).

## Что сделано в v2

### `System/adam/mic_reader.py`

**Новое состояние:**
- `self._discard_until_ts: float = 0.0` — wall-clock deadline. Пока `perf_counter() < этого`, drain_loop читает socket но discard'ит chunk вместо push в queue.

**Новый метод:** `MicReader.flush_queue(discard_window_ms: float = 200.0) -> int`:
- Дренирует ВСЕ чанки из queue (loop `get_nowait` пока не пусто).
- Ставит `_discard_until_ts = perf_counter() + window/1000`.
- Docstring явно говорит: **CALL ONLY** в post-transcribe и reply_silence_timeout. **DO NOT CALL** на wake_word_detected — съедает речь пользователя.

**Drain_loop gate:** добавлен после mute-gate в `_drain_loop`:
```python
if self._discard_until_ts > 0.0 and time.perf_counter() < self._discard_until_ts:
    continue
```
Семантика идентична mute-gate: socket читается (kernel TCP buffer дренируется, W5500 SPI safe), chunk не попадает в queue. **MicReader-стрим логика сохранена** — socket reads по-прежнему в `_drain_loop`.

### `System/Orchestrator.py`

Вызовы `self.mic_reader.flush_queue(200.0)` в **двух** точках:

1. **После `_transcribe_and_dispatch`** — V-S07.1 эквивалент `_drain_esp32_backlog`.
   ```python
   event_log.append("mic_queue_flushed", {"trigger": "post_transcribe", ...})
   ```
   Безопасно потому что:
   - Пользователь не говорит когда Адам только что озвучил ответ.
   - `_REPLY_GUARD_SEC=0.6` сразу за этим прикрывает overlap.

2. **На `reply_silence_timeout`** в reply→standby transition:
   ```python
   event_log.append("mic_queue_flushed", {"trigger": "reply_silence_timeout", ...})
   ```
   Безопасно потому что:
   - Пользователь по определению молчал (для этого таймер и сработал).
   - `_STANDBY_GUARD_SEC=0.3` сразу блокирует OWW на 300 мс.
   - Следующий wake fires только когда пользователь решит говорить снова — discard window 200 мс к тому моменту истёк.

**Wake_word_detected — БЕЗ вызова flush.** Комментарий в коде явно объясняет почему.

## Сравнение V-S07.1 vs V-S07.3 (Phase 10 v2)

| Аспект | V-S07.1 | Phase 10 v2 |
|---|---|---|
| Слой drain | Raw socket read (`_drain_esp32_backlog`) внутри `_vad_loop` | MicReader queue + discard window |
| Архитектура mic | _vad_loop читает socket напрямую | MicReader-стрим (отдельная task, queue) |
| Drain после transcribe | ✓ есть | ✓ есть (V-S07.1 эквивалент) |
| Drain на reply EXPIR | ❌ нет | ✓ есть (defensive, безопасно) |
| Drain на wake | ❌ нет | ❌ нет (избегаем Phase 10 v1 регрессии) |
| TCP-буфер ESP32 | дренируется через raw read | дренируется через `_drain_loop` discard window |
| W5500 SPI overflow protection | сохраняется (socket всегда читается) | сохраняется (drain_loop всегда читает) |

## Verify

```
$ python3 -c "import ast; ast.parse(open('System/Orchestrator.py').read())" → AST OK
$ python3 -c "import ast; ast.parse(open('System/adam/mic_reader.py').read())" → AST OK
$ PYTHONPATH=System python3 -c "from adam.mic_reader import MicReader; assert hasattr(MicReader,'flush_queue')" → OK
$ grep -c 'self.mic_reader.flush_queue' System/Orchestrator.py → 2 (только post_transcribe + reply_silence_timeout)
```

## Ожидаемый эффект

| Метрика | Test 4 (без Phase 10) | Test 5 (Phase 10 v1 — eats speech) | Ожидаемо (v2) |
|---|---|---|---|
| Success rate | 64% (7/11) | 33% (3/9) ❌ | ≥ 80% |
| pcm_ms после wake | 3680ms (стале) | ~50ms (truncated) | ~1000-3000ms (живое + 1500ms silence buffer) |
| `mic_queue_flushed` events | 0 | 12 (overkill) | 2-7 за тест (по числу turn-ов) |
| Empty ASR rate | 36% | 67% ❌ | ≤ 15% |

## Manual UAT — pending

```bash
sudo systemctl restart adam-orchestrator.service
# Hard reload UI: Ctrl+Shift+R
# Test 7 phrases обычной громкостью:
python3 scripts/adam_test_reply_hang.py --last-minutes 5
grep -c '"type": "mic_queue_flushed"' data/adam/events.jsonl
grep -c '"empty": true' data/adam/events.jsonl
```

Должно быть: 2-7 flushed events, empty ASR резко меньше, success rate выше 80%.

Если empty ASR всё ещё высок — копать в root cause MicReader stalls (CPU profiling, W5500 SPI contention с MJPEG камерой на :81).
