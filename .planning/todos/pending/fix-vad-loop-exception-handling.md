---
title: Fix _vad_loop swallowing exceptions → killing voice_loop
date: 2026-05-16
priority: CRITICAL
context: [voice-pipeline-vs-ui-layering](../../notes/voice-pipeline-vs-ui-layering.md)
---

# Fix _vad_loop exception handling

## Проблема

[Orchestrator.py:1113-1124](../../../System/Orchestrator.py#L1113) — `_vad_loop` ловит **любой** Exception, выставляет `self.running=False`, эмитит `voice_loop_stopped`, и **не пробрасывает** наверх. В результате retry/fallback логика в `_run_esp32`/`_run_local` никогда не срабатывает.

Реальный сценарий из лога: `IncompleteRead` от ESP32 stream → voice_loop полностью умирает после первого turn.

## Fix

```python
# Orchestrator.py:1113-1124 — _vad_loop tail
except asyncio.CancelledError:
    raise
# REMOVE:
# except Exception as exc:
#     self.running = False
#     self.vad_state = "error"
#     self.last_asr_error = str(exc)
#     runtime_state["last_error"] = f"voice_loop:{exc}"
#     event_log.append("voice_loop_error", {"error": str(exc)})
#     event_log.append("voice_loop_stopped", self.status())
finally:
    self._stop_process()
    # REMOVE self.running = False — это решение принимает выше
```

Так Exception проброcится в `_run_esp32`'s `except Exception as exc` ([Orchestrator.py:782](../../../System/Orchestrator.py#L782)), где:
- инкрементится `_session_fail_count`
- если `< esp_mic_fail_threshold (3)` → `sleep(2.0)` → retry connection
- иначе → `_esp_mic_fallback=True` → `_run_local` запускается

И в `_run_local`'s retry loop ([Orchestrator.py:706](../../../System/Orchestrator.py#L706)) — там 3 попытки с delays [1.0, 2.0, 4.0] перед окончательным stop.

## Acceptance

После фикса прогнать `Привет` дважды подряд через UI:
- ✅ После первого turn voice_loop живёт, ESP32 stream переподключается
- ✅ В логе после `IncompleteRead` видим `esp32_mic_profile_applied` (retry), а не `voice_loop_stopped`
- ✅ UI показывает «🎧 Ожидаю обращения», а не «🎧 Инициализация»

## Затронутые файлы

- `System/Orchestrator.py` — 6 строк убрать

## Связано

- Без фикса #2 (background drain) `IncompleteRead` будет повторяться каждый turn — retry поможет, но Адам терпит обрыв 2-секунды каждый раз. Эти два фикса парные.
