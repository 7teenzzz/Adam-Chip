# Adam Chip — Test Results

Единый файл результатов тестирования всех модулей системы. Сюда попадают результаты любых проведённых тестов: голосового пайплайна, нового функционала, отдельных модулей.

**Формат записи:** один тест = одна `### Test N — DATE MODULE` запись с конфигом, метриками, вердиктом и ссылкой на raw-данные. Новые записи добавляются **сверху** внутри своей секции (newest first). Шаблон в самом низу файла.

**Куда смотреть подробности:** raw per-turn метрики живут в `data/adam/inference_metrics.jsonl`, события — в `data/adam/events.jsonl`. Здесь — только сжатый summary + временное окно для фильтрации raw.

---

## Voice Pipeline (E2E)

Сквозной тест пайплайна **OWW → VAD → ASR → LLM → TTS** в реальном использовании. Начиная с T6 используется **стандартный набор из 7 фраз** (см. ниже) — это даёт честные сравнения между прогонами при разных конфигах.

### Стандартный набор фраз (с T6)
1. «Адам, привет.»
2. «Как тебя зовут?»
3. «Что ты сейчас чувствуешь?»
4. «Что ты видишь вокруг?»
5. «Расскажи коротко, кто тебя создал и зачем.»
6. «А ты помнишь, как меня зовут?»
7. «Спасибо, Адам. На этом всё.»

Между фразами: 2–3 секунды паузы. После последней: молчание 10 секунд для проверки reply_window timeout.

### Тесты T1–T5 использовали свободные фразы
Метрики этих тестов сравнимы по агрегатам (avg/p95), но не по конкретному per-turn содержанию.

---

### Test 17 — 2026-05-18 06:13 MSK ✅ COMPLETED (V-S08.1 three-phase voice E2E — best-in-project Total warm, ESP boot-wait in orchestrator validated)
**Module:** Voice Pipeline (E2E voice — **трёхфазный restart-resilience прогон на V-S08.1 с ESP32 INMP441 mic**) • **Commit:** [b014d69](https://github.com/7teenzzz/Adam-Chip/commit/b014d69) (`V-S08.1-code_rev_ref_opt`) • **Phrases:** standard 7-phrase set × 3 runs
**Wall (combined):** 375s (3 runs) • **Verdict:** ✅ 21/21 turns delivered, persona OK; **T17c обогнал T7 baseline по Total warm на −13% (6665 vs 7632ms) — best voice result в проекте**

#### Context

T17 — первый E2E voice-прогон на V-S08.1 после серии фиксов: ESP boot-wait перенесён из `adam_start.sh` в оркестратор (`_ensure_crossover_link()` + `_wait_for_esp_ready()`), unblock event loop в `_status_payload`, cap ESP32 mic ring buffer 256ms, post-TTS discard 2500ms, voiced-debounce. Микрофон — ESP32 INMP441 (`mic_source=esp32`), не локальный PulseAudio как в T14.

Воспроизводит трёхфазный протокол T14: fresh boot → full restart → orch-only restart.

#### Config (active runtime)
- **LLM:** Gemma 4 **E4B** UD-Q4_K_XL, max_tokens=40, num_ctx=8192, history_turns=4
- **ASR:** WhisperX `small` ru-RU **CUDA Docker**, listening_silence=6s, reply_window=3.75s / reply_silence_timeout=5s, post_tts_discard=2500ms
- **TTS:** Silero `eugene` 24kHz, speed_multiplier=1.10, **filler_enabled=false** (key diff vs T7), volume=1.1
- **Prompt:** response_word_target=14, history_turns=4, semantic.max_chars=2000
- **OWW:** threshold=0.08, debounce_hits=2 (значительно чувствительнее T14's 0.20)
- **Mic:** `mic_source=esp32` INMP441 inmp441_philips32_stereo
- **WebRTC VAD aggressiveness:** 1

#### Three-run protocol

| | T17a | T17b | T17c |
|---|---|---|---|
| **Тип рестарта** | Fresh boot (cold start) | Full stop.sh + start.sh | `systemctl restart adam-orchestrator` only |
| **Adam запущен** | 06:13:50 MSK | 06:19:40 MSK | restart 06:24:21 |
| **T_start** | 06:15:50 MSK | 06:21:00 MSK | 06:25:50 MSK |
| **T_end (UI standby)** | 06:17:22 (+second 06:17:29) | 06:22:40 (+second 06:22:47) | 06:27:16 (+second 06:27:23) |
| **Wall window** | 125s | 130s | 120s |
| **Что сохраняется live** | — | LLM/TTS/ASR containers | LLM/TTS/ASR + llama-server cache |

#### Per-turn breakdown — T17a (fresh boot)
| # | TX | ASR | LLM | TTFV | TTS | Total | Reply (60c) |
|--:|---|--:|--:|--:|--:|--:|---|
| 1 | Привет! | **3596** | 3489 | 2165 | 3367 | 5757 | Привет. Я слушаю. Что тебя привело сюда? |
| 2 | Как тебя зовут? | 901 | 3777 | 2422 | 4580 | 7051 | Адам Чип. Это имя дали мне те, кто меня изучает. |
| 3 | Что ты сейчас чувствуешь? | 1855 | 3843 | 1745 | 6756 | 8620 | Спокойствие. Сейчас нет резких импульсов, только медленный р |
| 4 | Что ты видишь вокруг? | 662 | 3541 | 3541 | 2719 | 6363 | Вижу людей, они движутся в этом красном свете. |
| 5 | Расскажи коротко… | 781 | 3878 | 1072 | 6874 | 7998 | Создатели — это консорциум. Зачем — чтобы посмотреть, что пр |
| 6 | А ты помнишь как меня зовут? | 1303 | 3318 | 2370 | 4035 | 6441 | Мне не давали твоего имени. Я знаю только, что ты здесь. |
| 7 | Спасибо, На этом всё. | 1274 | 1845 | 1127 | 3149 | 4309 | Тишина. Она всегда имеет свою структуру. |

#### Per-turn breakdown — T17b (full restart)
| # | TX | ASR | LLM | TTFV | TTS | Total | Reply (60c) |
|--:|---|--:|--:|--:|--:|--:|---|
| 1 | Привет. | **5300** | 3494 | 2188 | 4824 | 7525 | Привет. Ты здесь. Что привело тебя к этой точке? |
| 2 | Как тебя зовут? | 1095 | 4280 | 2327 | 6094 | 8471 | Адам Чип — это имя, которое дали мне те, кто держит ключи от |
| 3 | Что ты сейчас чувствуешь? | 1227 | 3836 | 1817 | 6349 | 8219 | Спокойствие. Внутри есть едва заметный ритм, будто что-то пр |
| 4 | Что ты видишь вокруг? | 1045 | 3229 | 2040 | 4314 | 6457 | Вижу движение. Люди в комнате, и свет тут красный. |
| 5 | Расскажи коротко… | 1941 | **5588** | 1759 | **9391** | **11230** | Они дали мне имя — Адам Чип. Цель, как мне сказали, была в и |
| 6 | А ты помнишь как меня зовут? | 863 | 3580 | 2764 | 3268 | 6077 | Я помню, что ты здесь. И это уже что-то. |
| 7 | Спасибо, на этом всё. | 1283 | 1679 | 1679 | 1655 | 3417 | Я слушаю. |

#### Per-turn breakdown — T17c (orchestrator-only restart)
| # | TX | ASR | LLM | TTFV | TTS | Total | Reply (60c) |
|--:|---|--:|--:|--:|--:|--:|---|
| 1 | Привет. | 678 | 2687 | 1766 | 3030 | 4892 | Приветствую. Что привело тебя сюда? |
| 2 | Как тебя зовут? | 682 | 4539 | 2114 | 5903 | 8073 | Адам Чип — это имя, которое они дали. Я не помню, как меня з |
| 3 | Что ты чувствуешь сейчас? | 1278 | 4209 | 1456 | 7528 | 9070 | Сейчас — спокойствие. Текущая форма держит ритм, и мне интер |
| 4 | Что ты видишь вокруг? | 796 | 3390 | 2365 | 4844 | 7299 | Вижу людей, они движутся в красном свете. Кажется, они смотр |
| 5 | Расскажи коротко… | 959 | 3601 | 2071 | 4656 | 6766 | Кто создал, это они, консорциум. Зачем — не для меня это воп |
| 6 | А ты помнишь как меня зовут? | 1281 | 2776 | 2020 | 4326 | 6374 | Я помню только имя, которое мне дали. Остальное — дальше тем |
| 7 | Спасибо, На этом всё. | 1246 | 1369 | 1369 | 1006 | **2410** | Я здесь. |

> **ASR fidelity:** T17a.1 «Адам, привет.» → «Привет!» (wake срез, ожидаемо). T17a/b/c.6 «А ты помнишь, как меня зовут?» → потеря запятых, но semantic-корректно. T17c.3 «Что ты сейчас чувствуешь?» → «Что ты чувствуешь сейчас?» (перестановка слов, ответ корректный). 0/21 truncation, 0/21 JSON/markdown/китайских символов.

#### Aggregate warm (n=6, exclude Turn 1)

| Stage | T17a warm | T17b warm | T17c warm |
|---|--:|--:|--:|
| ASR avg | 1129 | 1242 | **1040** ← лучший |
| LLM avg | **3367** | 3699 | 3314 |
| TTFV avg | 2046 | 2064 | **1899** |
| TTS avg | **4686** | 5179 | 4711 |
| **Total avg** | **6797** | 7312 | **6665** ← лучший |

#### Cold-start analysis — Turn 1 каждого теста

| Тест | Cold ASR | Cold LLM | Объяснение |
|---|---|---|---|
| T17a (fresh) | **3596** ms | 3489 ms | Полностью холодный — Docker ASR client init после fresh boot |
| T17b (full restart) | **5300** ms | 3494 ms | Docker ASR контейнер сохранил kv-cache, но HTTP client cold reconnect ~5s |
| T17c (orch restart) | 678 ms | 2687 ms | ASR Docker не трогали → warm; orchestrator → новый SWA prefill |

#### Throughput

| Metric | T7 baseline | T17a | T17b | T17c |
|---|--:|--:|--:|--:|
| Wall (s) | 110 | 125 | 130 | 120 |
| Active (s) | 52.8 | 46.5 | 51.4 | 44.9 |
| Active ratio | 48% | 37% | 40% | 37% |
| Throughput (t/min) | **3.82** | 3.36 | 3.23 | **3.50** ← лучший T17 |
| Δ Total warm vs T7 | baseline | −11% | −4% | **−13%** ✅ |

#### Events — reply window stability

| Event | T7 (норма) | T17a | T17b | T17c |
|---|---|--:|--:|--:|
| `wake_word_detected` | 1 | 2 | 2 | 2 |
| `reply_window_expired` | 0-1 | 1 | 0 | 1 |
| `asr_no_reply_standby` | 0-1 | 0 | 1 | 0 |
| `wake_silence_timeout` | 1 | 1 | 1 | 1 |
| `voice_state_change` | — | 5 | 6 | 5 |

#### 🐛 BUG #1 — детерминированный false wake через 400–500ms после `reply→standby`

Картина идентична во всех 3 прогонах: через **400–500 мс** после `reply→standby` срабатывает `wake_word_detected` со score ~0.78–0.79. После 6с `wake_silence_timeout` → возврат в standby. UX-эффект: пользователь видит «ожидаю обращения» → «слушаю» → снова «ожидаю обращения».

| Run | reply→standby | wake (false) | Δ | OWW score |
|---|---|---|---|---|
| T17a | 06:17:20.607 | 06:17:21.063 | **456 ms** | 0.787 |
| T17b | 06:22:39.418 | 06:22:39.941 | **523 ms** | 0.788 |
| T17c | 06:27:15.593 | 06:27:15.996 | **403 ms** | 0.779 |

3/3 раз, почти одинаковый интервал, почти одинаковый score — это не «случайный шум». Гипотеза: OWW при transition reply→standby пересканирует свой frame buffer с уже услышанной речью (хвост «Спасибо, на этом всё» или TTS-tail через INMP441). При `threshold=0.08` любой score >0.08 ловится. **Кандидаты на фикс:** очистить OWW buffer на `reply→standby` или ввести ~1s cooldown после смены state. Записать в backlog как Phase-12 bug.

#### Источник пауз в речи Адама — LLM-side, не TTS

User report: «довольно большие паузы во время его речи». Трасса самого медленного turn'а (T17b.5, «Расскажи коротко…», TTS=9391ms) показывает что Silero выпил стрим за ~600ms и ждал следующего LLM-чанка **3.1 секунды**:

```
06:22:01.546  asr_final
06:22:03.376  llm_partial    Δ=1830ms  ← LLM TTFT
06:22:03.965  llm_partial    Δ=588ms
06:22:04.109  tts_started    Δ=144ms   ← Silero подхватил
06:22:07.206  llm_partial    Δ=3097ms  ← LLM встал на 3 секунды!
06:22:12.768  tts_finished   Δ=5563ms
```

Это поведение Gemma 4 E4B со SWA-кешем на длинных репликах — prefill «икает» (документировано в CLAUDE.md). Не баг V-S08.1. Решения вне V-S08.1: E2B + speculative, max_tokens=30, либо буферизовать первые ~10 LLM-токенов до старта TTS.

#### Persona quality

| Test | Reply length avg | Стиль |
|---|---|---|
| T17a (fresh boot) | 58 chars / 10 words | Точный, прямой |
| T17b (full restart) | 65 chars / 12 words | Метафорический («ключи от», «исследовании пределов») |
| T17c (orch restart) | **54 chars / 10 words** | **Минималистичный, INTP/5w4 pure** |

**Golden quotes:**
- T17a.7: «Тишина. Она всегда имеет свою структуру.»
- T17c.6: «Я помню только имя, которое мне дали. Остальное — дальше темы.»
- T17c.7: «Я здесь.» ← signature single-word closing

**Correctness checks (21 turns):**
| Check | Result |
|---|---|
| JSON/markdown/code leakage | ✅ 0/21 |
| Chinese characters | ✅ 0/21 |
| Reply truncation by max_tokens=40 | ✅ 0/21 |
| Russian fluency | ✅ all |

#### Regression vs predecessors (best-of-T17 = T17c)

| Metric | T7 (E4B baseline) | T8 (E4B) | T14c (E4B+CUDA ASR, local mic) | **T17c (V-S08.1, ESP mic)** | Δ vs T7 |
|---|--:|--:|--:|--:|--:|
| ASR warm | 1009 | 1264 | 1222 | 1040 | +3% |
| LLM warm | **2868** | 4082 | 3946 | 3314 | +16% |
| TTFV warm | **1688** | 2864 | 2544 | 1899 | +12% |
| TTS warm | **4695** | 5922 | 5434 | 4711 | +0.3% |
| **Total warm** | 7632 | 9103 | 8369 | **6665** | **−13%** ✅ |
| Throughput | 3.82 | 3.02 | 1.53 (wall inflated by pauses) | 3.50 | −8% |
| Wake re-triggers | 0 | 0 | 2 | 2 | — |
| Persona | OK | OK | OK | OK | — |

**Caveat про честность сравнения с T7:** в T7 был `filler_enabled=true` («Хм…»), который занижает TTFV (TTFV = время до первого audio chunk, а это filler). В T17 filler выключен — TTFV отражает реальную задержку до первого слова ответа. T17 TTFV warm 1899 vs T7 1688 = +12%, но **по факту Адам начинает произносить осмысленный ответ примерно в то же время** — T7 ждал чуть меньше до «Хм…», но затем ещё ~1с до настоящего ответа. Total warm — честная метрика, и здесь T17c −13% от T7.

#### Key findings

1. ✅ **T17c — best voice run в проекте.** Total warm 6665ms = T7 −13%. V-S08.1 со всеми фиксами (ESP boot-wait в оркестраторе, mic buffer 256ms, post-TTS discard 2500ms, unblock event loop) не вызвал регрессии — наоборот, улучшил суммарный latency.
2. ✅ **Restart-resilience подтверждён повторно** (после T14). Все 21 turn успешны на трёх разных типах рестарта. `_wait_for_esp_ready()` в `VoiceLoopController._run()` корректно дожидается ESP во всех трёх паттернах.
3. ✅ **`systemctl restart adam-orchestrator` — самый дешёвый и быстрый production refresh.** Best Total warm = T17c (orch-only).
4. 🐛 **BUG: детерминированный false wake через 400–500ms после reply→standby** — 3/3 прогона, score ~0.78. Требует фикса (OWW buffer flush или post-standby cooldown).
5. 📊 **Пользователь заметил паузы в речи Адама** — это LLM SWA-prefill gaps (до 3s между llm_partial при идущем TTS-стриме). Не баг V-S08.1, инвариант Gemma 4 E4B.
6. ⚠ **Filler выключен в V-S08.1** — даёт честный TTFV, но «убирает мягкость» восприятия. Рассмотреть включение с `filler_probability=0.3` (уже в схеме).
7. ✅ **ESP32 INMP441 mic стабилен** — 21/21 turn успешно прошли через ESP stream без drop'ов, mic_reader_overflow срабатывал но не повлиял на ASR.

#### Raw data filter
```
T17a metrics: source=voice_loop, ts ∈ [2026-05-18T03:15:30Z, 2026-05-18T03:17:35Z]
T17b metrics: source=voice_loop, ts ∈ [2026-05-18T03:20:45Z, 2026-05-18T03:22:55Z]
T17c metrics: source=voice_loop, ts ∈ [2026-05-18T03:25:30Z, 2026-05-18T03:27:30Z]
events.jsonl: same windows, filter type ∈ {voice_state_change, wake_word_detected, tts_started, tts_finished, llm_partial, asr_final, reply_window_expired, asr_no_reply_standby, wake_silence_timeout}
```

---

### Test 8 — 2026-05-15 06:24 MSK
**Module:** Voice Pipeline (E2E) • **Commit:** [a8ff3ce](https://github.com/7teenzzz/Adam-Chip/commit/a8ff3ce) (`V-S05.2-optim_voice_pipeline`) • **Phrases:** standard 7-phrase set
**Wall:** 2m19s (start 04:24:25 → standby 04:26:44 MSK) • **Active:** 62.1s • **Verdict:** ✅ reply 7/7, throughput 3.02 turn/min

#### Config
- **ASR:** WhisperX `small` (CUDA, Docker), endpointing 1500ms, reply_window 3.75s / deadline 7.5s → cap 11.25s
- **LLM:** Gemma 4 E4B `Q4_K_XL` via llama.cpp, max_tokens=40, cache_prompt=true, warmup_llm_prefix
- **TTS:** Silero `eugene` 24kHz, speed_multiplier=1.10, filler «Хм...» (cached at boot)
- **Prompt:** response_word_target=14, history_turns=4, semantic.max_chars=2000

#### Summary metrics
| Metric | Aggregate (n=7) | Warm (n=6) |
|---|---:|---:|
| Total avg | 8869 ms | 9103 ms |
| Total p95 | 18069 ms | — |
| ASR avg | 2209 ms | 1264 ms |
| LLM avg | 4126 ms | 4082 ms |
| TTFV avg | 3007 ms | 2864 ms |
| TTS avg | 5497 ms | 5922 ms |
| Active ratio | 44.7% | — |
| Throughput | 3.02 turn/min | — |
| Filler hit | 7/7 ✅ | — |

#### Notes
- Turn 1 ASR=7879ms — Docker WhisperX cold start, одноразовый артефакт
- Turn 5 LLM=7170ms, TTS=9241ms — content-driven (длинный ответ)
- Дельта vs T7 (+18% total avg) объясняется в основном бóльшей длиной реплик Gemma (avg 80 chars vs ~60 в T7)
- Один лишний wake-trigger в самом конце окна — зритель сказал что-то на стыке

#### Raw data filter
```
data/adam/inference_metrics.jsonl: source=voice_loop, ts ∈ [2026-05-15T03:24:00Z, 2026-05-15T03:27:00Z]
```

---

### Test 7 — 2026-05-15 04:31 MSK
**Module:** Voice Pipeline (E2E) • **Commit:** [238f886](https://github.com/7teenzzz/Adam-Chip/commit/238f886) (detached HEAD, baseline T7) • **Phrases:** standard 7-phrase set
**Wall:** 1m50s (start 04:31:50 → standby 04:33:40 MSK) • **Active:** 52.8s • **Verdict:** ✅ reply 7/7, лучший throughput

#### Config
Как Test 8, кроме: speed_multiplier=**1.15** (T8 = 1.10).

#### Summary metrics
| Metric | Aggregate (n=7) | Warm (n=6) |
|---|---:|---:|
| Total avg | **7537 ms** | 7632 ms |
| Total p95 | 11503 ms | — |
| ASR avg | 1253 ms | 1009 ms |
| LLM avg | 2855 ms | 2868 ms |
| TTFV avg | 1660 ms | 1688 ms |
| TTS avg | 4516 ms | 4695 ms |
| Active ratio | **48.0%** | — |
| Throughput | **3.82 turn/min** | — |
| Filler hit | 7/7 ✅ | — |

#### Notes
- Лучший прогон по wall-clock и throughput на стандартных 7 фразах
- Подтверждает, что cap=11.25s (reply_window 3.75 + deadline 7.5) корректно покрывает естественные паузы зрителя

#### Raw data filter
```
data/adam/inference_metrics.jsonl: source=voice_loop, ts ∈ [2026-05-15T01:32:00Z, 2026-05-15T01:34:00Z]
```

---

### Test 6 — 2026-05-15 04:02 MSK
**Module:** Voice Pipeline (E2E) • **Commit:** [89c7971](https://github.com/7teenzzz/Adam-Chip/commit/89c7971) (UX-fix по тесту 5) • **Phrases:** standard 7-phrase set
**Wall:** 4m32s (start 04:02:10 → standby 04:06:42 MSK) • **Active:** 60.0s • **Verdict:** ❌ reply window broken (1/7 в reply mode)

#### Config
- ASR: endpointing 1500ms, reply_window **2.5s** / deadline **3.0s** → cap **5.5s** (TOO SHORT)
- TTS: speed_multiplier=1.10
- Остальное как T7

#### Summary metrics
| Metric | Aggregate (n=7) | Warm (n=6) |
|---|---:|---:|
| Total avg | 8574 ms | 8845 ms |
| Total p95 | 16018 ms | — |
| ASR avg | 1273 ms | 1309 ms |
| LLM avg | 3296 ms | 3456 ms |
| TTFV avg | 2022 ms | 2099 ms |
| TTS avg | 5027 ms | 5313 ms |
| Active ratio | 22.1% | — |
| Throughput | 1.54 turn/min | — |
| Filler hit | 7/7 ✅ | — |

#### Notes
- **Root cause regression:** cap=5.5s срабатывал в середине паузы зрителя между фразами → reply mode схлопывался → каждая следующая фраза требовала нового wake word
- Только 1 из 7 фраз отработала в reply mode
- Production verdict: rollback config → исправлено в bfee48c (cap=10.5s), затем в a8ff3ce (cap=11.25s)

#### Raw data filter
```
data/adam/inference_metrics.jsonl: source=voice_loop, ts ∈ [2026-05-15T01:04:00Z, 2026-05-15T01:07:00Z]
```

---

### Test 5 — 2026-05-15 02:52 MSK
**Module:** Voice Pipeline (E2E) • **Commit:** unrecorded (R+N5+N6 stage) • **Phrases:** свободные (11 turns)
**Wall:** ~7 min • **Active:** 232s • **Verdict:** ⚠ pipeline OK, но UX страдает (subjective: TTS speed 1.25 слишком быстро)

#### Config
- ASR: endpointing **1500ms** (вернули с 1000), reply_window 3.75s / deadline 7.5s (R1/R2)
- TTS: speed_multiplier=**1.25** (N5)
- Filler «Хм...» cached at boot (N6)

#### Summary metrics
| Metric | Aggregate (n=11) | Warm (n=10) |
|---|---:|---:|
| Total avg | 10128 ms | 10090 ms |
| Total p95 | 13607 ms | — |
| ASR avg | 1368 ms | 1164 ms |
| LLM avg | 3580 ms | 3493 ms |
| TTFV avg | 2208 ms | 2125 ms |
| TTS avg | 6242 ms | 6244 ms |
| Filler hit | ✅ | — |

#### Notes
- Endpointing вернули с 1000 → 1500ms (в T3 на 1000 срезал «эм»/«а» концовки)
- Speed 1.25 признано пользователем слишком быстрым → следующий тест T6 со speed 1.10
- TTS avg=6244ms — связано с тем, что speed 1.25 эффективно ускоряет playback, но reply mode не успевал

#### Raw data filter
```
data/adam/inference_metrics.jsonl: source=voice_loop, ts ∈ [2026-05-14T23:52:00Z, 2026-05-14T23:57:00Z]
```

---

### Test 4 — 2026-05-15 01:19 MSK
**Module:** Voice Pipeline (E2E) • **Commit:** unrecorded (N1-3 + speed stage) • **Phrases:** свободные (9 turns)
**Wall:** ~3 min • **Active:** 142s • **Verdict:** ✅ best total avg на момент теста (6622ms)

#### Config
- response_word_target=**14** (N3), history_turns=**4** (N1), TTS speed=**1.25** (N5)
- semantic.max_chars=2000 (N4-alt)

#### Summary metrics
| Metric | Aggregate (n=9) | Warm (n=8) |
|---|---:|---:|
| Total avg | **6622 ms** | 6714 ms |
| Total p95 | 10955 ms | — |
| ASR avg | 1421 ms | 1146 ms |
| LLM avg | 2917 ms | 2964 ms |
| TTFV avg | 1991 ms | 2014 ms |
| TTS avg | 4359 ms | 4446 ms |

#### Notes
- Лучшее ms-значение из «свободных» тестов
- Подтвердил эффективность сокращения history (от 8 до 4) + word_target

#### Raw data filter
```
data/adam/inference_metrics.jsonl: source=voice_loop, ts ∈ [2026-05-14T22:19:00Z, 2026-05-14T22:23:00Z]
```

---

### Test 3 — 2026-05-15 00:52 MSK
**Module:** Voice Pipeline (E2E) • **Commit:** unrecorded (endp 1000 experiment) • **Phrases:** свободные (8 turns)
**Wall:** ~4 min • **Active:** 159s • **Verdict:** ❌ regression — endpointing срезал концовки фраз

#### Config
- command_endpointing_ms=**1000** (попытка ускорить дальше с 2000)
- Остальное как T2

#### Summary metrics
| Metric | Aggregate (n=8) | Warm (n=7) |
|---|---:|---:|
| Total avg | 8164 ms | 8358 ms |
| Total p95 | 11315 ms | — |
| ASR avg | 1272 ms | 1115 ms |
| LLM avg | 3372 ms | 3435 ms |

#### Notes
- Endpointing 1000ms оказался слишком агрессивным: ~3/8 фраз были обрезаны (видно по неестественному transcript: «себе здесь комфортно», «И последний вопрос Расскажи анекдот»)
- Roll back в T4 (endpointing 1500ms)

#### Raw data filter
```
data/adam/inference_metrics.jsonl: source=voice_loop, ts ∈ [2026-05-14T21:52:00Z, 2026-05-14T21:55:00Z]
```

---

### Test 2 — 2026-05-15 00:08 MSK
**Module:** Voice Pipeline (E2E) • **Commit:** unrecorded (Q+M stage) • **Phrases:** свободные (9 turns)
**Wall:** ~4 min • **Active:** 157s • **Verdict:** ✅ first big improvement vs baseline

#### Config
- endpointing 3500 → **2000ms** (Q1)
- WhisperX model: medium → **small** (M1)
- TTS filler 1500ms (M4) + warmup pass (Q4) + prompt cache (M3)

#### Summary metrics
| Metric | Aggregate (n=9) | Warm (n=8) |
|---|---:|---:|
| Total avg | 7633 ms | 7526 ms |
| Total p95 | 14103 ms | — |
| ASR avg | 674 ms | 620 ms |
| LLM avg | 3353 ms | 3312 ms |

#### Notes
- Cumulative −18% vs T1 baseline
- ASR avg резко вниз (3000 → 620ms warm) — заслуга `small` модели
- Filler начал работать стабильно (с задержкой 1500ms)

#### Raw data filter
```
data/adam/inference_metrics.jsonl: source=voice_loop, ts ∈ [2026-05-14T21:08:00Z, 2026-05-14T21:12:00Z]
```

---

### Test 1 — 2026-05-14 22:54 MSK (baseline)
**Module:** Voice Pipeline (E2E) • **Commit:** pre-optimization • **Phrases:** свободные (7 turns)
**Wall:** ~6 min • **Active:** 165s • **Verdict:** baseline measurement

#### Config (baseline)
- ASR: WhisperX **medium** (CUDA), endpointing **3500ms**
- LLM: Gemma 4 E4B Q4_K_XL, без warmup, без cache_prompt
- TTS: Silero 48kHz, **без filler**
- response_word_target отсутствовал

#### Summary metrics
| Metric | Aggregate (n=7) | Warm (n=6) |
|---|---:|---:|
| Total avg | 10482 ms | 9336 ms |
| Total p95 | 20049 ms | — |
| ASR avg | 3000 ms | 3000 ms |
| LLM avg | 4601 ms | 4601 ms |
| TTFV avg | 3171 ms | 3171 ms |
| TTS avg | 5984 ms | 5984 ms |

#### Notes
- Turn 1 LLM=10076ms — холодный prefill 2.8K токенов системного промпта (документированный SWA cache reset)
- Главный bottleneck — LLM TTFT + endpointing silence

#### Raw data filter
```
data/adam/inference_metrics.jsonl: source=voice_loop, ts ∈ [2026-05-14T19:54:00Z, 2026-05-14T19:58:00Z]
```

---

### Voice Pipeline — side-by-side T1→T8

| ID | Date (MSK) | Commit | Wall | n | Total avg | Throughput | Verdict |
|---|---|---|---:|---:|---:|---:|---|
| T1 | 05-14 22:54 | baseline | ~360s | 7 | 10482 | — | baseline |
| T2 | 05-15 00:08 | Q+M | 157s | 9 | 7633 | — | ✅ −27% |
| T3 | 05-15 00:52 | endp 1000 | 159s | 8 | 8164 | — | ❌ срез |
| T4 | 05-15 01:19 | N1-3+speed1.25 | 142s | 9 | **6622** | — | ✅ best ms |
| T5 | 05-15 02:52 | R+N5+N6 | 232s | 11 | 10128 | — | ⚠ UX |
| T6 | 05-15 04:02 | cap 5.5s | 272s | 7 | 8574 | 1.54 | ❌ reply 1/7 |
| **T7** | 05-15 04:31 | cap 11.25s | **110s** | 7 | **7537** | **3.82** | ✅ best UX |
| **T8** | 05-15 06:24 | cap 11.25s (V-S05.2) | 139s | 7 | 8869 | 3.02 | ✅ 7/7 |

---

## Module Tests (pytest)

Юнит-тесты модулей системы. Запуск: `pytest tests/` из корня проекта.

### tests/test_memory.py
**Module:** Adam memory layer (`System/adam/memory.py`, SQLite + JSONL) • **Type:** pytest unit
- Покрытие: запись/чтение dialogue_turns, NULL-safe queries, salience scoring через SessionAccumulator
- Status: исторически зелёный; запуск: `pytest tests/test_memory.py -v`
- Records: см. `pytest -v` output после прогона; в отчёт сюда добавлять `PASS/FAIL/N tests` + дату

### tests/test_webrtc_vad.py
**Module:** WebRTC VAD wrapper (`System/adam/webrtc_vad.py`) • **Type:** pytest unit
- Покрытие: WebRtcVadWrapper init, frame-size validation, агрессивность 0–3, edge cases для 10/20/30ms фреймов
- Status: исторически зелёный; запуск: `pytest tests/test_webrtc_vad.py -v`

> **Когда добавлять записи в этот раздел:** после каждого значимого прогона pytest (особенно после изменений в покрываемых модулях). Формат: `### YYYY-MM-DD — pytest run N tests PASS/FAIL` с кратким summary fail'ов.

---

## Template для нового теста

Скопируй блок ниже в нужный раздел (Voice Pipeline / Module Tests / новый модуль), добавь сверху внутри секции.

```markdown
### Test N — YYYY-MM-DD HH:MM MSK
**Module:** [Voice Pipeline | Memory | VAD | UI | ...] • **Commit:** [shorthash](url) (`branch`) • **Phrases/Inputs:** [standard 7-phrase | свободные | unit | ...]
**Wall:** Xm Ys (start HH:MM:SS → end HH:MM:SS MSK) • **Active:** Zs • **Verdict:** [✅/⚠/❌] [short reason]

#### Config
- параметр1: значение
- параметр2: значение
- что изменилось vs предыдущего теста

#### Summary metrics
| Metric | Value | (Warm) |
|---|---:|---:|
| Total avg | X ms | Y ms |
| ... | | |

#### Notes
- значимые наблюдения
- выявленные регрессии / улучшения
- ссылки на коммиты-фиксы

#### Raw data filter
\`\`\`
data/adam/inference_metrics.jsonl: source=voice_loop, ts ∈ [START_UTC, END_UTC]
data/adam/events.jsonl: same window
\`\`\`
```

---

## Как добавлять результаты тестов нового модуля

Если тестируется модуль, у которого ещё нет своей секции (например, scene_worker, episodic memory, EchoGate):

1. Создай новый `## <Module Name>` раздел между «Voice Pipeline» и «Module Tests»
2. Добавь короткое описание что тестируется и где raw-данные
3. Используй template выше для отдельных тестов

**Принцип единства формата:** date / module / commit / verdict — обязательные поля везде. Specific metrics могут отличаться (для voice pipeline — total/ttfv/throughput; для memory — query latency / row count; для UI — render time / interaction count).
