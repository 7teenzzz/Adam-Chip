---
title: Pipeline ↔ UI разделение слоёв и death-spiral voice_loop
date: 2026-05-16
context: Диагностика по результатам сессии 11:55–11:58 (events.jsonl). Адам глохнет после первого turn, UI показывает «Инициализация».
---

# Pipeline ↔ UI разделение слоёв и death-spiral voice_loop

## TL;DR

**Архитектурно backend pipeline уже независим от UI** — `VoiceLoopController` это asyncio task, который стартует с оркестратором, не зависит от HTTP-клиентов. UI **наблюдатель** через `/api/agent/status` (snapshot) + `/api/agent/stream` (SSE).

**Все три симптома пользователя** — следствие **одного бага** в `_vad_loop` (Orchestrator.py:1113-1124), а не проблем разделения слоёв:

1. «Mic переключился на local» — на самом деле voice_loop полностью мёртв, `_audio_level_monitor` (idle equaliser) занял ALSA и эмитит `audio_level` с `source="local"`. UI badge правильно отражает то что видит — но это не fallback, это труп.
2. «Status → инициализация после первого turn» — `voice_loop_stopped` event действительно прозвучал, pipeline стоит.
3. «Status → инициализация после навигации» — UI правильно зеркалит мёртвый pipeline.

UI всё-таки имеет один косметический недостаток: после mount показывает дефолт `hearingState="loading"` / `micSource="local"` до прихода первого snapshot/SSE-события. После фикса backend это будет видно только в первые ~100 мс — мелочь, чинится отдельно.

## Точная цепочка смерти voice_loop

Из реального лога `events.jsonl` 11:57:23:

```
11:57:23.238 tts_finished                      (TTS финиш, ESP32 mic не читается уже 19 сек)
11:57:23.844 voice_loop_error                  error=IncompleteRead(161536 bytes read)
11:57:23.845 voice_loop_stopped                (через 1 мс! retry не было)
```

После этого — никаких событий voice_loop. VLM-цикл продолжает работать (он отдельный task), Адам глухой.

### Почему IncompleteRead

Источник — ESP32 long-poll стрим на `http://10.10.10.171:81/audio`. ESP32 разорвал TCP-соединение.

**Почему ESP закрыл стрим:**

1. На `mic_muted` ([Orchestrator.py:1071](../../System/Orchestrator.py#L1071)) Jetson останавливает чтение из ESP32 stream
2. `_transcribe_and_dispatch()` блокирует loop на ASR (8.1с) + LLM (3с) + TTS (7с) ≈ **19 секунд**
3. ESP32 продолжает генерировать PCM @ 16kHz stereo 16-bit = **64KB/sec** → нужно буферизовать ~1.2MB
4. ESP32 TCP send buffer на W5500 (~64KB) переполняется
5. Прошивка закрывает connection (watchdog или TCP-write-timeout)
6. После TTS Jetson зовёт `_drain_esp32_backlog()` → `read()` → **`IncompleteRead`**

Существующий `_drain_esp32_backlog` ([Orchestrator.py:828](../../System/Orchestrator.py#L828)) уже умеет осушать накопленные кадры, но запускается **после** unmute — когда ESP уже закрыл сокет.

**Правильный фикс:** drain `_during_ mute` в фоновом task. Jetson должен **постоянно читать** сокет (и сбрасывать байты) пока voice_loop муто́ен, чтобы TCP-window не переполнилось. Тогда ESP не успеет закрыть connection.

### Почему IncompleteRead killнул весь voice_loop

[Orchestrator.py:1113-1124](../../System/Orchestrator.py#L1113):

```python
try:
    while self.running:
        chunk = await asyncio.to_thread(_reader[0], frame_bytes)
        ...  # VAD/endpointing/ASR dispatch
except asyncio.CancelledError:
    raise
except Exception as exc:
    self.running = False                                          # ← KILL self
    self.vad_state = "error"
    self.last_asr_error = str(exc)
    runtime_state["last_error"] = f"voice_loop:{exc}"
    event_log.append("voice_loop_error", {"error": str(exc)})
    event_log.append("voice_loop_stopped", self.status())         # ← FAKE stop event
finally:
    self._stop_process()
    self.running = False
```

**Проблемы:**

1. `self.running = False` внутри `_vad_loop` принимает решение о жизни pipeline — **это не его уровень ответственности**. retry/fallback живут в `_run_esp32` / `_run_local`, но они **никогда не получают exception** потому что `_vad_loop` его проглатывает.
2. `voice_loop_stopped` — **ложное событие**. Это не stop, это error. UI/dashboard должны их различать.
3. Нет `raise` после log → `_run_esp32` думает что `_vad_loop` нормально вернулся (self.running уже False) → выходит из своего while → конец.

**Корректное поведение:**

`_vad_loop` должен **пробросить** exception в `_run_esp32`/`_run_local`, которые имеют:
- `_session_fail_count` с порогом fallback (esp_mic_fail_threshold=3)
- 2-секундный backoff между попытками
- переход на `_run_local` при превышении порога
- background ESP retry task

## UI слой — реальная архитектурная картина

### Что уже правильно

- `VoiceLoopController` стартует при инициализации оркестратора, не ждёт HTTP-клиента
- `event_bus` — broadcast pattern: подписчики (SSE) получают копии, pipeline их не ждёт
- `/api/agent/status` отдаёт исчерпывающий snapshot (voice_loop.status() поля: running, mic_source, mic_active_source, mic_stream_state, voice_state, esp_mic_fallback, esp_boot_wait_state, esp_bg_retry_active)
- Адам корректно работает БЕЗ открытого браузера — `curl /api/agent/turn` доказывает

### Что не идеально (UI-слой)

- `chat.js` хранит локальные дублирующие переменные: `hearingState`, `micSource` ([chat.js:195](../../System/WebUI/static/js/panels/chat.js#L195), [:107](../../System/WebUI/static/js/panels/chat.js#L107))
- Дефолты лгут: `"loading"` / `"local"` показываются до прихода snapshot/SSE — но snapshot **уже** загружен глобально в `state["status"]` через `main.js:refreshStatus()` (период 4сек). Просто не используется как primary source.
- При remount панели локальные переменные пересоздаются → UI забывает живой state, ждёт следующее SSE-событие (`voice_loop_started` уже отзвучал на boot — не повторится)

### Минимальный UI-фикс

В `chat.js` (mount):

```js
// 1. Не лгать дефолтами — null до первого источника правды
let micSource = null;
const initialStatus = state.get("status");
let hearingState = initialStatus?.voice_loop?.running ? "standby" : null;
// state == null → отдельный label "ожидаем данных"

// 2. Использовать voice_loop.mic_active_source как первичный источник
//    audio_level.source — вторичный, только живой level
const vlMic = initialStatus?.voice_loop?.mic_active_source;
if (vlMic) micSource = vlMic;
```

После фикса backend (см. ниже) — этого практически достаточно.

## Связанные находки

### Зашкаливающий clip_count: 4776 в момент TTS finished

```
11:57:24.172 esp32_audio_health  clip_count_total=4776 clip_delta=4776 ...
```

ESP32 mic клиппинговал во время TTS playback. Гипотеза: эхо TTS через HDMI-динамик → INMP441 микрофон. `half_duplex_mute=true` должен был замьютить — но в логе **нет события `mic_unmuted`** после `tts_finished`. Возможно `set_muted(True)` сработал, а `set_muted(False)` пропущен где-то в TTS flow.

`muted_by_tts` отдельно от `mic_muted(reason="asr_transcribing")` — две разных причины мута. Нужно проверить ([Orchestrator.py:1071-1096](../../System/Orchestrator.py#L1071)) — `muted_by_tts` выставляется в True при ASR transcribing, в False после drain. Где TTS его выставляет/сбрасывает — отдельный вопрос.

## Решения

| # | Что | Где | Сложность |
|---|-----|-----|-----------|
| 1 | Убрать `self.running=False` + `voice_loop_stopped` из `_vad_loop`; пробросить exception наверх | Orchestrator.py:1113-1124 | 5 мин |
| 2 | Фоновый ESP32 stream drainер во время mute — чтоб ESP не разрывал connection | новый task в `_run_esp32` | 30 мин |
| 3 | UI: убрать локальные дефолты, читать `mic_active_source` из snapshot на mount | chat.js | 15 мин |
| 4 | Найти где `muted_by_tts` не сбрасывается → починить + clip_burst подспаст | TTS path | 30 мин |

После #1 и #2 — Адам перестанет умирать после первого turn. После #3 — UI перестанет лгать при навигации.
