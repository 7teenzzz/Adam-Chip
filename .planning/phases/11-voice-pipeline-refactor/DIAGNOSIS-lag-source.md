# Диагностика источника 2.3-секундного лага в post-TTS пайплайне

**Контекст:** после фикса 11-hotfix (`baea061`) выяснилось что между событиями `tts_finished` и моментом, когда из ESP32-стрима приходят чанки с хвостом речи Адама, проходит **стабильно ~2.3 секунды**. Чтобы избавиться от мёртвой зоны в REPLY (сейчас оставлено 500ms discard как компромисс) нужно понять, **где** в пайплайне сидит этот лаг.

## Три гипотезы

| # | Источник | Признак на envelope | Как фиксить |
| --- | --- | --- | --- |
| A | ALSA HDMI playback buffer | RMS высокий 50–300ms после `mic_unmute`, потом резкий cliff | `aplay --buffer-size=N` |
| B | Акустическое эхо в комнате | RMS средний 200–800ms, плавный спад | физически отодвинуть speaker от mic, либо AEC |
| C | ESP32 firmware FIFO (audio task buffer + W5500 TCP) | RMS высокий **1500–2500ms подряд**, потом cliff | правка firmware в `Subsystem/AdamsServer/` |

Скорее всего источник = **C** (по предварительной оценке: 2.3с стабильно по нескольким turn'ам — это слишком долго для ALSA/реверба). Но проверим экспериментально.

## Инструментация

В коде добавлены:

- `MicReader.begin_lag_diag(duration_ms, origin)` — стартует логирование RMS каждого чанка
- Per-chunk событие `mic_lag_diag_chunk` с полями: `t_offset_ms`, `rms`, `muted`, `discarded`, `origin`
- Старт/конец помечается `mic_lag_diag_started` / `mic_lag_diag_finished`
- Запускается автоматически после каждого `mic_unmute` (origin=`post_transcribe`) на **4 секунды**, если `tuning.diagnostics.trace_post_tts_lag = true`

## Как запустить диагностику (правильно)

> Адам должен быть запущен (`./scripts/adam_start.sh`). Все команды — на той же Jetson или с любой машины с доступом к `http://JETSON_IP:8080`.

**Шаг 1.** Включить диагностику одной командой (hot, без рестарта):

```bash
curl --noproxy '*' -X POST http://127.0.0.1:8080/api/diag/lag/toggle \
     -H "Content-Type: application/json" -d '{"enabled": true}'
```

Должен вернуть `{"ok":true,"enabled":true,"previous":false}`.

**Шаг 2.** Сделать **3–5 диалоговых turn'ов** через wake word «Адам».

> **ВАЖНО:** НЕ говорите в окно REPLY — нам нужен envelope **без** речи пользователя, только хвост речи Адама. То есть: скажите «Адам, расскажи о себе» → Адам ответит → **молчите** 5+ секунд → возврат в STANDBY → следующий turn через «Адам, …».

**Шаг 3.** Запустить анализатор:

```bash
PYTHONPATH=System python3 scripts/diag_lag_source.py 5
```

Скрипт выведет per-window RMS envelope (по бакетам 100ms) и для каждого окна найдёт **biggest drop** — момент, когда аудио стало тише всего.

**Шаг 4.** Выключить (диагностика шумит ~200 событий/turn в events.jsonl):

```bash
curl --noproxy '*' -X POST http://127.0.0.1:8080/api/diag/lag/toggle \
     -H "Content-Type: application/json" -d '{"enabled": false}'
```

## Проверка что флаг включился

```bash
# Должно вернуть "trace_post_tts_lag": true
curl --noproxy '*' -s http://127.0.0.1:8080/api/tuning | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('trace_post_tts_lag =', d['diagnostics']['trace_post_tts_lag'])
"
```

## Как читать результат

Скрипт печатает что-то вроде:

```
window #3/5 started=2026-05-18T12:34:56.789 origin=post_transcribe duration=4000 ms chunks=200 max_rms=8421
    +   0-99   ms [D] ██████████████████████████████████████····· rms= 7234
    +  100-199 ms [D] ██████████████████████████████████······· rms= 6890
    +  200-299 ms [Q] █████████████████████████████··········· rms= 5612
    +  300-399 ms [Q] ████████████████████████··············· rms= 4521
    +  400-499 ms [Q] ████████████████··················· rms= 3211
    +  500-599 ms [Q] ████████··························· rms= 1822
    +  600-699 ms [Q] ███································· rms=  421
    +  700-799 ms [Q] ··································· rms=   89
    →  biggest drop: -3400 rms at +700 ms (audio went quiet here)
```

**Расшифровка `[D]`/`[Q]`:**
- `[D]` = discarded (внутри post_tts_discard_window — чанк не дошёл до VAD)
- `[Q]` = queued (чанк дошёл до consumer и пошёл в VAD)
- `[M]` = ещё muted_by_tts (не должно быть после mute_unmute)

**Где cliff (момент тишины):**

| Cliff position | Вывод |
| --- | --- |
| +50–300 ms | **A: ALSA HDMI buffer.** Фикс — `aplay --buffer-size`. |
| +200–800 ms | **B: Акустическое эхо.** Фикс — физика комнаты или AEC. |
| +1500–2500 ms | **C: ESP32 firmware FIFO.** Фикс — изменения в `Subsystem/AdamsServer/`. |
| Нет cliff, плавный спад | Mix of room reverb + AEC needed. |

## Что делать с результатом

После того как известен источник:

- **A или B** → могу починить на Jetson-стороне без правки firmware. `_post_tts_discard_window_ms` уменьшится до фактического значения cliff'a + 100ms запаса. Например, если cliff на +400ms → discard=500ms (текущее значение и так покроет).
- **C** → требует правки ESP32 firmware: уменьшить размер audio FIFO в стрим-сервере. Это отдельная задача в `Subsystem/AdamsServer/`. Discard window на Jetson — это workaround до починки firmware.

## Текущее состояние

- `_post_tts_discard_window_ms = 500` (компромисс по требованию пользователя)
- Это значит: при текущем лаге ~2.3с **первые ~1.8с после Адама эхо МОЖЕТ просочиться** в ASR. Если эхо громкое — Адам опять услышит сам себя.
- Если эхо НЕ просочится (например, лаг был не 2.3с а меньше) — пользователь сможет говорить почти сразу.
- Жертвуем стабильностью ради отзывчивости — нужно подтвердить трейдоф диагностикой.
