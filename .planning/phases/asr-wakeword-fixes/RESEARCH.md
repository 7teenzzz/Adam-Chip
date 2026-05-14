# Phase: asr-wakeword-fixes — Research

**Researched:** 2026-05-11
**Domain:** Python asyncio voice loop, OpenWakeWord, VAD endpointing, smart speaker state machine
**Confidence:** HIGH (все выводы основаны на прямом анализе кода и конфигурации проекта)

---

## Summary

Проект Adam Chip реализует голосовой цикл через `VoiceLoopController` в `System/Orchestrator.py`.
Три подтверждённых бага: (1) voice_loop стартует **параллельно** с warmup-монологом, что при
ложном срабатывании OWW на ALSA-шум в первую секунду приводит к самодиалогу; (2) `vad_state`
выставляется в `"listening"` внутри ветки `standby`, что показывает неверный статус в API;
(3) `command_endpointing_ms = 2500ms` — завышено, пользователь хочет 1500ms.

Дополнительно: в ветке `reply` нет абсолютного таймаута — если VAD детектирует непрерывную
речь, система никогда не вернётся в standby. Это BUG-4.

**Первичная рекомендация:** задержать старт `voice_loop` до завершения `_warmup_wakeup()`;
увеличить `_STANDBY_GUARD_SEC` до 3.0s (стартовый шум ALSA); исправить `vad_state` в
ветке standby; снизить `command_endpointing_ms` до 1500ms; добавить абсолютный таймаут
для ветки `reply`.

---

## Project Constraints (from CLAUDE.md)

- `half_duplex_mute = true` — mic ВСЕГДА глушится во время TTS playback. Инвариант нельзя нарушать.
- Wake word «адам» обязателен в exhibition mode.
- LLM = чистый русский текст, никакого JSON в ответе LLM.
- Action failure ≠ silence: если action layer падает, голос всё равно произносится.
- Inference только на Jetson; ESP32 mic = диагностика/резерв.
- Аудио вход: `pulse` (PulseAudio → WebCamera card 3). `hw:1,0` физически не отдаёт PCM.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Wake word detection | Orchestrator (CPU, OWW) | — | OWW работает на CPU внутри VoiceLoopController._run() |
| VAD + endpointing | Orchestrator (audioop.rms) | — | Пороговый RMS в frame-loop |
| ASR transcription | speaches HTTP service | ASR_Whisper.py (резерв) | WhisperASRClient.transcribe_pcm() |
| TTS playback | Silero HTTP + ALSA plughw:1,3 | — | TTSClient.speak() |
| State machine | VoiceLoopController._voice_state | — | standby / listening / reply |
| Startup monologue | _warmup_wakeup() coroutine | — | Запускается из lifespan как asyncio.create_task |
| Mic muting during TTS | _stop_process() / _start_arecord() | muted_by_tts flag | arecord subprocess прекращается на время transcription+TTS |

---

## Verified Code Analysis

### Текущая последовательность запуска (BUGGY)

```
lifespan() →
  voice_loop.start()           # t=0 — mic ВКЛЮЧЁН, OWW активен
  asyncio.create_task(_warmup_wakeup())   # t≈0 — монолог запускается параллельно
  asyncio.create_task(_warmup_asr())
```

`_warmup_wakeup()` внутри делает `await asyncio.sleep(1.0)` перед запросом к LLM (строка 1757).
За эту 1 секунду ALSA открывает audio device — характерный init-шум.
`_STANDBY_GUARD_SEC = 0.3` (строка 249) — недостаточно, чтобы перекрыть ALSA init.

**Результат:** OWW детектирует «wake word» на ALSA init noise в t+1s. voice_loop переходит
в `"listening"`. Следующие ~20 секунд (время монолога) аккумулирует TTS-аудио как речь
зрителя. Whisper транскрибирует галлюцинацию. Adam отвечает сам себе.

[VERIFIED: прямой анализ Orchestrator.py строки 714-719, 1757]

### BUG-2: Неверный vad_state в standby (строка 342)

```python
if self._voice_state == "standby":
    if self._wake_engine is not None:
        # ... OWW processing ...
    self.vad_state = "listening"  # <<< ВСЕГДА "listening" даже в standby
    continue
```

`vad_state` влияет на API endpoint `/api/agent/status` → поле `vad_state`. Пользователь
видит «listening» когда система на самом деле в standby (ждёт wake word).

[VERIFIED: прямой анализ строки 342, VoiceLoopController.status() строки 251-267]

### BUG-3: command_endpointing_ms = 2500ms

Config.json строка 75: `"command_endpointing_ms": 2500`
VoiceLoopController.__init__ строка 218: `self._command_endpointing_ms = int(asr_cfg.get("command_endpointing_ms", 2500))`

Пользователь хочет 1500ms. [VERIFIED: Config.json]

### BUG-4: Нет абсолютного таймаута для reply state

Строки 346-359: reply-window expires только если `not speech_frames`.
Если пользователь говорит непрерывно (или VAD видит шум как речь) — истечения нет никогда.
Система застревает в reply навсегда.

[VERIFIED: прямой анализ строки 346-359]

---

## Правильная State Machine (Smart Speaker Pattern)

Паттерн Yandex Alice / Amazon Alexa: [ASSUMED] основан на общеизвестном поведении устройств,
не на официальной документации (они закрыты).

```
                      ┌─────────────────────────────────────┐
                      │           BOOT_MUTED                │
                      │  voice_loop НЕ запущен              │
                      │  _warmup_wakeup() играет монолог    │
                      └──────────────┬──────────────────────┘
                                     │ warmup завершён (или failed)
                                     ▼
    ┌───────────── STANDBY ─────────────────────────────────┐
    │  mic ON, OWW сканирует                                │
    │  vad_state = "standby"                                │
    │  STANDBY_GUARD активен 3s после входа                 │
    └──────────────┬────────────────────────────────────────┘
                   │ OWW: wake word detected
                   │ (только после GUARD истёк)
                   ▼
    ┌───────────── LISTENING ───────────────────────────────┐
    │  mic ON, VAD накапливает speech_frames                │
    │  vad_state = "speech" / "endpointing" / "silence"    │
    │  timeout: max_segment_ms (15s) — hard cap             │
    └──────────────┬────────────────────────────────────────┘
                   │ silence >= 1500ms  OR  speech >= 15s
                   ▼
    ┌───────────── TRANSCRIBING ────────────────────────────┐
    │  mic OFF (_stop_process)                              │
    │  muted_by_tts = True                                  │
    │  ASR → LLM → TTS (всё синхронно в одном await)       │
    └──────────────┬────────────────────────────────────────┘
                   │ TTS finished
                   ▼
    ┌───────────── REPLY ───────────────────────────────────┐
    │  mic ON (_start_arecord)                              │
    │  4s окно без wake word                                │
    │  ABSOLUTE DEADLINE: 4s + max_reply_extension_sec      │
    │  (даже если VAD видит speech — hard cutoff 12s)       │
    └──────┬────────────────────┬───────────────────────────┘
           │ новая команда      │ окно истекло
           │ (VAD → endpoint)   │ (4s без команды ИЛИ 12s абс)
           ▼                    ▼
    TRANSCRIBING            STANDBY
    (новый turn)            (вернулись к OWW)
```

**Ключевые тайминги:**

| Параметр | Текущее значение | Рекомендуемое | Обоснование |
|----------|-----------------|---------------|-------------|
| `_STANDBY_GUARD_SEC` | 0.3s | **3.0s** | ALSA init noise длится 1-2s; OWW debounce 3×80ms = 240ms — не спасает от шума |
| `command_endpointing_ms` | 2500ms | **1500ms** | Требование пользователя; типично для умных колонок |
| `reply_window_sec` | 4.0s | **4.0s (оставить)** | Оптимально |
| Reply absolute deadline | отсутствует | **12.0s** | reply_window + 2× max extension; защита от залипания |
| Boot mute guard | отсутствует | **до конца _warmup_wakeup()** | voice_loop стартует ПОСЛЕ warmup |

---

## State Machine: Startup Sequence Fix (детали реализации)

### Вариант A: voice_loop стартует ПОСЛЕ warmup (РЕКОМЕНДУЕТСЯ)

Изменение в `lifespan()`:

```python
# БЫЛО (buggy):
for _retry in range(5):
    _vl_result = await voice_loop.start()
    if _vl_result.get("ok"):
        break
    await asyncio.sleep(2.0)
asyncio.create_task(_warmup_wakeup(), name="warmup_wakeup")

# СТАЛО (correct):
asyncio.create_task(_warmup_then_start_voice_loop(), name="warmup_sequence")
```

Новая корутина:

```python
async def _warmup_then_start_voice_loop() -> None:
    """Run warmup monologue first, then activate voice loop."""
    await _warmup_wakeup()   # ждём завершения — mic НЕ активен во время монолога
    # Небольшой буфер после окончания TTS-монолога
    await asyncio.sleep(0.5)
    for _retry in range(5):
        result = await voice_loop.start()
        if result.get("ok"):
            event_log.append("voice_loop_started_post_warmup", result)
            break
        await asyncio.sleep(2.0)
```

**Плюсы:** mic физически выключен во время монолога. Нет race condition.
**Минусы:** если warmup зависнет (120s timeout) — voice loop не стартует 120s.
**Митигация:** warmup уже имеет 120s deadline (строка 1747), так что это не новый риск.

### Вариант B: флаг `_warmup_active` в VoiceLoopController (запасной)

```python
# В VoiceLoopController._run(), в начале ветки standby:
if self._warmup_active:
    self.vad_state = "boot_muted"
    continue
```

Флаг сбрасывается внешним вызовом после `_warmup_wakeup()`.

**Минус:** сложнее, mic физически ON, только OWW блокируется программно. Шум всё равно
попадает в буфер при ошибке флага. **Вариант A предпочтительнее.**

---

## Fix для каждого бага

### FIX-1: BUG-1 (КРИТИЧЕСКИЙ) — самодиалог при старте

**Файл:** `System/Orchestrator.py`

Изменения в `lifespan()`:
1. Убрать блок `for _retry in range(5): await voice_loop.start()` из основного тела lifespan
2. Заменить `asyncio.create_task(_warmup_wakeup())` на `asyncio.create_task(_warmup_then_start_voice_loop())`
3. Добавить новую корутину `_warmup_then_start_voice_loop()` выше lifespan

Изменения в `VoiceLoopController.__init__()`:
- `_STANDBY_GUARD_SEC` поднять с 0.3 до 3.0 (дополнительная защита для всех последующих
  standby-входов после reply — ALSA drain тоже шумит)

```python
self._STANDBY_GUARD_SEC: float = 3.0  # was 0.3
```

### FIX-2: BUG-2 — неверный vad_state в standby

**Файл:** `System/Orchestrator.py`, метод `VoiceLoopController._run()`

Строка 342: изменить `"listening"` на `"standby"`:

```python
# БЫЛО:
self.vad_state = "listening"
continue

# СТАЛО:
self.vad_state = "standby"
continue
```

Также исправить ветку `standby_guard` — там уже правильно (`"standby_guard"`), не трогать.

### FIX-3: BUG-3 — endpointing 2500ms → 1500ms

**Файл:** `System/Config.json`

```json
"command_endpointing_ms": 1500
```

Дополнительно проверить: `endpointing_ms: 400` (строка 74 Config.json) используется в
ином контексте (speaches server-side VAD) — не менять.

### FIX-4: BUG-4 — абсолютный таймаут reply state

**Файл:** `System/Orchestrator.py`, метод `VoiceLoopController._run()`

Добавить второй check в reply-ветке:

```python
if self._voice_state == "reply":
    elapsed = time.perf_counter() - self._reply_start
    # Expire if window passed with no speech, OR absolute deadline exceeded
    absolute_deadline = self._reply_window_sec + float(
        asr_cfg.get("reply_absolute_deadline_sec", 12.0)
    )
    if (elapsed >= self._reply_window_sec and not speech_frames) or elapsed >= absolute_deadline:
        event_log.append("reply_window_expired", {
            "action": "standby",
            "elapsed_sec": round(elapsed, 1),
            "reason": "absolute_deadline" if elapsed >= absolute_deadline else "no_speech",
        })
        self._voice_state = "standby"
        self._standby_entry_time = time.perf_counter()
        speech_ms = 0
        silence_ms = 0
        self._ww_buf.clear()
        continue
```

Добавить в `VoiceLoopController.__init__()`:
```python
self._reply_absolute_deadline_sec = float(asr_cfg.get("reply_absolute_deadline_sec", 12.0))
```

Добавить в `Config.json`:
```json
"reply_absolute_deadline_sec": 12.0
```

---

## Files to Modify

| Файл | Что менять | Приоритет |
|------|-----------|-----------|
| `System/Orchestrator.py` | lifespan(): выделить _warmup_then_start_voice_loop() | CRITICAL |
| `System/Orchestrator.py` | VoiceLoopController._run() строка 342: vad_state fix | MEDIUM |
| `System/Orchestrator.py` | VoiceLoopController._run(): reply absolute deadline | MEDIUM |
| `System/Orchestrator.py` | VoiceLoopController.__init__(): _STANDBY_GUARD_SEC 0.3 → 3.0 | HIGH |
| `System/Config.json` | command_endpointing_ms: 2500 → 1500 | MEDIUM |
| `System/Config.json` | reply_absolute_deadline_sec: 12.0 (добавить) | LOW |

---

## Don't Hand-Roll

| Проблема | Не строить | Использовать | Почему |
|----------|-----------|-------------|--------|
| TTS-echo подавление | свой эхо-фильтр DSP | half_duplex_mute (mic off во время TTS) | Уже реализовано и работает — mic физически выключается через _stop_process() |
| Wake word debounce | ручной счётчик фреймов | OpenWakeWordEngine._DEBOUNCE_HITS = 3 | Уже реализовано в wake_word.py строка 25 |
| Startup sound timing | sleep(N) эвристика | await _warmup_wakeup() как explicit barrier | Coroutine уже имеет правильный deadline и health-check |

---

## Common Pitfalls

### Pitfall 1: asyncio.create_task не блокирует

**Что идёт не так:** `asyncio.create_task(_warmup_wakeup())` — это огонь и забыть.
voice_loop уже запущен в тот момент, когда warmup только начинается.

**Почему:** `create_task` планирует корутину в event loop, но возвращает управление немедленно.
lifespan продолжается без ожидания.

**Как избежать:** вызвать `await _warmup_wakeup()` (напрямую) или через `await asyncio.gather()`
до `await voice_loop.start()`. Либо вынести всё в `_warmup_then_start_voice_loop()`.

**Признаки проблемы:** в events.jsonl `wake_word_detected` появляется в первые 2s после `orchestrator_started`.

### Pitfall 2: ALSA init noise vs. OWW guard window

**Что идёт не так:** ALSA device открывается через arecord subprocess — первые ~1-2s содержат
спайки от инициализации карты. `_STANDBY_GUARD_SEC = 0.3` перекрывает только 300ms — недостаточно.

**Почему:** OWW работает на 80ms фреймах. За 300ms — 3-4 фрейма. Если шум длится 1s — guard
истекает и OWW видит шум уже без защиты.

**Как избежать:** поднять `_STANDBY_GUARD_SEC` до 3.0s. Это коррелирует с практикой умных
колонок: Alexa добавляет 2-3s blanking period после boot перед активацией hot-word engine.
[ASSUMED — конкретные значения Alexa не задокументированы публично]

**Признаки проблемы:** `wake_word_detected` в первые 3s после `voice_loop_started` без реального произнесения wake word.

### Pitfall 3: vad_state ≠ voice_state — разные переменные

**Что идёт не так:** разработчик путает `self.vad_state` (строковый label для API/UI,
обновляется в каждом кадре) и `self._voice_state` (state machine: standby/listening/reply).

**Почему:** `vad_state` показывает детальное состояние VAD внутри текущего voice_state.
В standby правильное значение — `"standby"` (или `"standby_guard"`). Текущий код ставит
`"listening"` что вводит в заблуждение.

**Как избежать:** правило — `vad_state` должен быть подсостоянием или копией `_voice_state`,
никогда не противоречить ему.

### Pitfall 4: reply absolute deadline при плохом mic входе

**Что идёт не так:** дешёвый микрофон или шумная выставочная среда → VAD постоянно видит
`voiced = True` → `speech_frames` никогда не пуст → reply window никогда не истекает.

**Почему:** guard condition `if elapsed >= self._reply_window_sec and not speech_frames` —
второе условие никогда не выполняется при постоянном шуме.

**Как избежать:** добавить второй OR с абсолютным дедлайном (12s = 4s reply + 8s буфер).

### Pitfall 5: _warmup_wakeup использует turn_lock

**Важно:** `_warmup_wakeup()` захватывает `turn_lock` (строка 1785). Это значит: пока
warmup работает, обычные turn'ы от voice_loop заблокированы. Это **дополнительная страховка**,
но не основная защита — если voice_loop уже запущен, он будет накапливать audio buffer
пока turn_lock занят, и отправит transcript сразу как lock освободится.

Вывод: один лишь turn_lock недостаточен для защиты от BUG-1. Нужно именно не запускать
voice_loop до окончания warmup.

---

## Event Logging Recommendations

Добавить события для наблюдаемости state machine:

| Событие | Когда | Payload |
|---------|-------|---------|
| `voice_loop_boot_muted` | voice_loop задержан на время warmup | `{"reason": "warmup_in_progress"}` |
| `voice_loop_boot_ready` | voice_loop запущен после warmup | `{"delay_sec": N}` |
| `reply_window_expired` | уже есть, но добавить `reason` | `{"reason": "no_speech" / "absolute_deadline"}` |
| `vad_state_change` | (опционально) при смене _voice_state | `{"from": X, "to": Y}` |

---

## Testing Approach

### Ручные тесты (все можно проверить через events.jsonl)

1. **Boot smoke test:** перезапустить orchestrator → в events.jsonl НЕ должно быть
   `wake_word_detected` раньше `warmup_wakeup` event. Порядок: `orchestrator_started` →
   `warmup_wakeup` → `voice_loop_started_post_warmup`.

2. **False positive guard test:** запустить систему, молчать 10s → в events.jsonl нет
   `viewer_transcript`. Счётчик `wake_word_detected` = 0 за первые 3s.

3. **vad_state standby test:** после boot, в standby: `GET /api/agent/status` →
   `vad_state` должен быть `"standby"` (не `"listening"`).

4. **Endpointing test:** произнести «Адам, тест» → дождаться паузы → asr_final должен
   появиться через ~1.5s тишины, не 2.5s.

5. **Reply window test:** после TTS ответа — говорить непрерывно > 12s → система должна
   вернуться в standby (reply_window_expired с reason=absolute_deadline).

6. **Warmup artistic integrity test:** при старте монолог Адама проигрывается полностью
   без перебивания голосовым turn'ом.

### Команды для проверки

```bash
# Проверить порядок событий после перезапуска
tail -50 /home/i17jet/Agents/Adam-Chip/data/adam/events.jsonl | python3 -m json.tool

# Проверить статус API
curl --noproxy '*' -fsS http://127.0.0.1:8080/api/agent/status | python3 -m json.tool

# Тестовый диалоговый turn
curl --noproxy '*' -fsS http://127.0.0.1:8080/api/agent/turn \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"как дела?"}' | python3 -m json.tool
```

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ALSA init noise длится 1-2s для данной конфигурации | FIX-1, Pitfall 2 | Guard 3.0s может быть избыточным (но безопасным) или недостаточным |
| A2 | Alexa/Alice используют 2-3s blanking period при boot | Pitfall 2 | Конкретные значения закрыты; наш выбор 3.0s разумен но не сверен с документацией |
| A3 | 12.0s абсолютный дедлайн reply достаточен для всех сценариев | FIX-4 | В шумной среде (выставка) может потребоваться регулировка — сделали конфигурируемым |

---

## Open Questions

1. **_warmup_asr и voice_loop порядок**
   - Что знаем: `_warmup_asr` отправляет silence в ASR для прогрева cold-start
   - Что неясно: нужно ли запускать _warmup_asr ДО или ПОСЛЕ _warmup_wakeup?
   - Рекомендация: _warmup_asr можно запустить параллельно с _warmup_wakeup (они не конкурируют за mic). Оставить как есть — `asyncio.create_task(_warmup_asr())`.

2. **ALSA pulse vs hw: для OWW**
   - Что знаем: input_device = "pulse" в Config.json; OWW работает на 16kHz S16LE
   - Что неясно: есть ли дополнительная задержка PulseAudio при открытии в arecord?
   - Рекомендация: если после фикса BUG-1 ложные срабатывания продолжатся — проверить
     временной профиль шума через `arecord -D pulse -f S16_LE -r 16000 -c 1 -t raw | audiometer`.

3. **OWW threshold = 0.85 (Config.json) vs. __init__ default 0.7 (wake_word.py)**
   - Что знаем: Config.json строка 106 `"threshold": 0.85`; wake_word.py строка 99 `threshold=float(config.get("threshold", 0.7))`
   - Что неясно: создаётся ли OpenWakeWordEngine с 0.85 или 0.7?
   - Рекомендация: проверить `_create_wake_engine(ww_cfg)` — ww_cfg берётся из `settings.section("wake_word")` строка 243. Значение 0.85 должно передаваться. Вероятно, корректно. Но при фиксации BUG-1 стоит залогировать threshold при старте OWW.

---

## Validation Architecture

Тест-инфраструктура: UAT.md уже ведётся вручную. Автоматизированных тестов нет.

| Req ID | Поведение | Тип теста | Команда | Файл |
|--------|-----------|-----------|---------|------|
| BUG-1 | voice_loop не стартует до warmup | ручной (events.jsonl) | `tail -30 data/adam/events.jsonl` | — |
| BUG-2 | vad_state = "standby" в standby | ручной (API) | `curl /api/agent/status` | — |
| BUG-3 | endpointing ~1.5s | ручной (субъективно) | произнести команду | — |
| BUG-4 | reply expires при непрерывном шуме | ручной (events.jsonl) | шум > 12s → reply_window_expired | — |

Wave 0: тестовая инфраструктура отсутствует — UAT ручной по events.jsonl.

---

## Sources

### Primary (HIGH confidence)
- `System/Orchestrator.py` — прямой анализ строк 206-488, 697-732, 1741-1814
- `System/adam/wake_word.py` — прямой анализ OpenWakeWordEngine
- `System/Config.json` — актуальные значения конфигурации
- `.planning/phases/asr-wakeword-fixes/UAT.md` — текущий статус тестирования

### Tertiary (LOW confidence — ASSUMED)
- Поведение Alexa/Alice при boot (blanking period) — закрытая документация

---

## Metadata

**Confidence breakdown:**
- Анализ багов: HIGH — прямой анализ кода с номерами строк
- Fix-рекомендации: HIGH — основаны на конкретных строках кода
- Тайминги (_STANDBY_GUARD_SEC 3.0s): MEDIUM — логически обоснованы, не измерены
- Smart speaker patterns: LOW — ASSUMED, закрытые системы

**Research date:** 2026-05-11
**Valid until:** не ограничено (код не меняется без коммита)

---

## RESEARCH COMPLETE
