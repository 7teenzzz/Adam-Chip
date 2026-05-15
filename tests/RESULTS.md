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

### Test 15 — 2026-05-15 14:31 MSK ⚠ COMPLETED (V-S06.3: E2B + ngram-mod tuned — LLM win, TTS regression blocker)
**Module:** Voice Pipeline (E2E voice — **первый valid прогон на V-S06.3 c CUDA ASR после T13**) • **Commit:** [27f83c1](https://github.com/7teenzzz/Adam-Chip/commit/27f83c1) (`V-S06.3-opt_voice_pipe_3wave`) • **Phrases:** standard 7-phrase set × 3 runs
**Wall (combined):** 757s (3 runs) • **Verdict:** ⚠ 21/21 turns delivered, persona OK; **E2B LLM speedup доказан (T15a LLM warm −19% vs T7), но TTS regression +34-97% и filler artifacts блокируют UX**

#### Context

T15 — первый E2E прогон V-S06.3 stack'а с правильно работающей CUDA ASR (после T13 CPU fallback). Применены **pre-T15 fix'ы:**
- H5: ngram-mod n-min 48→4, n-max 64→16 (commit `000bf39`)
- H6: history_turns 0→2 (commit `a26a4a1`)
- systemd StartLimit fix → orchestrator crashloop предотвращён (commit `27f83c1`)
- H7 (OWW threshold) откатан — остался 0.20

**Микрофон:** локальный PulseAudio (webcam, ALSA card 3). ESP32 INMP441 в fallback.

#### Config (active runtime)
- **LLM:** Gemma 4 **E2B** UD-Q4_K_XL + ngram-mod (n-match=24, n-min=4, n-max=16)
- **ASR:** WhisperX `small` **CUDA Docker** (T13 fix validated)
- **TTS:** Silero `eugene` 24kHz, speed_multiplier=1.10, filler «Хм...» 800ms
- **Prompt:** history_turns=2 (H6 middle ground), semantic.max_chars=2000
- **OWW threshold:** 0.20, debounce_hits=2
- **mic_source:** local

#### Three-run protocol

| | T15a | T15b | T15c |
|---|---|---|---|
| **Тип рестарта** | Fresh boot | Full stop+start | `systemctl restart adam-orchestrator` only |
| **Adam запущен** | 14:31:12 MSK | 14:40:05 MSK | (orch restart 14:47:42) |
| **T_start** | 14:32:42 (повтор фразы) | 14:42:07 (повтор фразы) | 14:50:00 |
| **T_end** | 14:36:40 | 14:45:53 | 14:53:54 (≈) |
| **Wall window** | 238s | 226s | 293s |

#### Per-turn breakdown — T15a (fresh boot)
| # | TX | ASR | LLM | TTFV | TTS | Total | Заметка |
|--:|---|--:|--:|--:|--:|--:|---|
| 1 | Привет. | 497 | 3479 | 858 | 6338 | 7328 | T_start не сработал, второй take |
| 2 | Как тебя зовут? | 3050 | **1270** | 927 | 4184 | **5426** | ngram-like speedup? |
| 3 | Что ты сейчас чувствуешь? | 2959 | 1541 | 645 | 7473 | 8204 | |
| 4 | что ты видишь вокруг. | 1021 | 2409 | 2404 | 5198 | 10465 | ASR drift |
| 5 | **Кто тебя создал и зачем Расскажи коротко, кто тебя создал и зачем** | 1481 | 4018 | 1654 | **10390** | **14486** | ASR склеил две произнесённые фразы |
| 6 | А ты помнишь как меня зовут? | 1182 | 3970 | 734 | 7256 | 10706 | |
| 7 | Спасибо, На этом всё. | 2344 | 728 | 728 | 3206 | 4059 | |

#### Per-turn breakdown — T15b (full restart)
| # | TX | ASR | LLM | TTFV | TTS | Total | Заметка |
|--:|---|--:|--:|--:|--:|--:|---|
| 1 | Привет. | 503 | 3937 | 766 | 7151 | **12691** | T_start первая попытка не сработала |
| 2 | Как тебя зовут? | 1136 | 2538 | 2534 | 8076 | 10831 | |
| 3 | Что ты сейчас чувствуешь? | 3808 | 3833 | 3828 | 7812 | 11792 | |
| 4 | что ты видишь вокруг? | 1142 | 4015 | 1357 | **10685** | **16712** | TTS catastrophe |
| 5 | Расскажи коротко… | 1461 | 4022 | 1381 | **10805** | **14612** | |
| 6 | А ты помнишь как меня зовут? | 1330 | **6508** | 3160 | **11222** | **14470** | LLM anomaly |
| 7 | Спасибо, На этом всё. | 3146 | 6953 | 6954 | 3410 | 10706 | TTFV=LLM (filler не успел) |

#### Per-turn breakdown — T15c (orchestrator-only restart)
| # | TX | ASR | LLM | TTFV | TTS | Total | Заметка |
|--:|---|--:|--:|--:|--:|--:|---|
| 1 | Привет. | 984 | 2873 | 2864 | 4007 | 6936 | |
| 2 | Как тебя зовут? | 2500 | 4107 | 932 | 7220 | 8224 | |
| 3 | Что ты сейчас чувствуешь? | 2982 | 3921 | 663 | 7666 | 10801 | |
| 4 | что ты видишь вокруг. | 804 | 2614 | 2602 | 8124 | 13455 | |
| 5 | **И зачем? Я скажи коротко…** | 1579 | 4057 | 1168 | **10870** | **14361** | wake-word noise в transcript |
| 6 | А ты помнишь как меня зовут? | 3019 | 3793 | 839 | **10990** | 12076 | |
| 7 | **Спасибо, а дом на этом всё.** | 2186 | 3610 | 821 | **10546** | 13744 | ASR «Адам, на» → «а дом на»; третий take |

#### Warm aggregate (n=6, exclude Turn 1)

| Stage | T7 (gold) | T14c (best E4B) | **T15a** | **T15b** | **T15c** |
|---|--:|--:|--:|--:|--:|
| ASR avg | **1009** | 1222 | 2006 | 2004 | 2178 |
| **LLM avg** | 2868 | 3946 | **2323** ✅ −19% vs T7 | 4645 | 3684 |
| TTFV avg | 1688 | 2544 | **1182** ✅ −30% vs T7 | 3202 | 1171 ✅ |
| **TTS avg** | **4695** | 5434 | 6285 (+34%) | **8668** ❌ (+85%) | **9236** ❌ (+97%) |
| **Total avg** | **7632** | 8369 | 8891 (+16%) | **13187** ❌ | **12110** ❌ |

#### Throughput

| Test | Wall(s) | Active(s) | Active% | Thr (t/min) |
|---|--:|--:|--:|--:|
| T7 baseline | 110 | 52.8 | 48.0% | 3.82 |
| T14c (best E4B) | 274 | 63.6 | 23.2% | 1.53 |
| **T15a** | 238 | 60.7 | 25.5% | **1.76** |
| **T15b** | 226 | 91.8 | 40.6% | 1.86 |
| **T15c** | 293 | 79.6 | 27.2% | 1.43 |

#### Reply window events

| Event | T7 (норма) | T15a | T15b | T15c |
|---|---|--:|--:|--:|
| `wake_word_detected` | 1 | **8** | 4 | **9** |
| `reply_window_expired` | 0-1 | **5** | 2 | **5** |
| `asr_no_reply_standby` | 1 | 1 | 2 | 1 |
| `tts_filler` | 7/7 | **3/7** | 6/7 | **4/7** |
| `voice_state_change` | 5-8 | 21 | 11 | 24 |

**Reply window нестабильность подтверждена** — каждый turn в T15a/T15c триггерил несколько wake_word_detected events. User отметил «слушаю двух/трёх раз» — это и есть симптом. Причина: OWW threshold=0.20 + low-quality PulseAudio webcam mic.

#### ngram-mod statistics (H5 verification — FAILED)

```
common_speculative_init: initialized ngram_mod with n_match=24, size=4194304 (16.000 MB)
statistics ngram_mod: #calls=5/78/0  #gen drafts = 0  #acc drafts = 0  #gen tokens = 0  #acc tokens = 0
occupancy = 4285/4194304 (0.00%)
```

**H5 не сработал.** Несмотря на снижение n-min 48→4 и n-max 64→16, `#gen drafts=0`. Hash pool наполняется, но draft generation никогда не запускается. ngram-mod на свободном русском тексте — статистический no-op.

**LLM speedup в T15a (LLM warm 2323ms vs T14c 3946ms = −41%) пришёл от E2B alone**, не от ngram. Рекомендация для T16: либо `n_match=24 → 8`, либо удалить ngram block полностью.

#### Persona quality

| Test | Reply length avg | Markers/turn | Особое |
|---|---|---|---|
| T15a | 8.5 w / 54 c | 1.1 | T15a.5 ASR-склейка двух фраз — Adam ответил нормально |
| T15b | 12.3 w / 70 c | 1.3 | **«ритм в холодной стали»**, **«свет режет пыль»** — поэтичный пик |
| T15c | 13.0 w / 72 c | 1.0 | **«технофлора»** — новый Adam-термин; **T15c.7** обыграл ASR-drift «а дом» → философский ответ |

**Correctness checks (21 turns):**
| Check | Result |
|---|---|
| JSON/markdown/code leakage | ✅ 0/21 |
| Chinese characters | ✅ 0/21 |
| max_tokens=40 truncation | ✅ 0/21 |
| Russian fluency | ✅ all |

#### Critical bugs surfaced

**🔥 BUG #1 — TTS «Хм..Хм..» stutter at reply start (CRITICAL)**
User отчёт: «когда Адам начинает говорить он будто проговаривает Хм..Хм..». Подтверждено через `tts_filler` count: T15a=3/7, T15b=6/7, T15c=4/7 — рассогласованность с TTFV (filler должен играть когда TTFV>800ms, но триггерится на других условиях). Filler / real-reply race condition в `Orchestrator.py:_filler_task`.

**🔥 BUG #2 — TTS echo between sentence chunks (CRITICAL)**
User отчёт: «как будто эхо после окончания некоторых слов». Подтверждено через TTS warm avg: T15 6285-9236ms vs T7 4695ms (+34-97%). ALSA buffer не дренируется между sentence-chunks. Streaming TTS pipeline накладывает chunks. Произношение Адама становится трудно понимать.

**⚠ BUG #3 — ngram-mod статистически no-op (после H5)**
`#acc_drafts=0` даже на n-min=4 / n-max=16. 16 MB hash overhead без пользы.

**⚠ BUG #4 — OWW false-wakes от PulseAudio webcam mic**
Reply window нестабильность повторяется. Threshold=0.20 + low-quality mic = шумовые false-wakes.

**⚠ BUG #5 — UI lag («эквалайзер не показывает актуальное состояние»)**
SSE event throttling: audio_level events каждые 20ms (50/s) → SSE backpressure → UI отстаёт.

#### Сравнение с предыдущими тестами

| Metric | T7 (E4B gold) | T14c (E4B best) | T13 (E2B, CPU-ASR) | **T15a (E2B+ngram, best)** |
|---|--:|--:|--:|--:|
| ASR warm | 1009 | 1222 | 12216 ❌ | 2006 |
| LLM warm | 2868 | 3946 | 4490 | **2323** ✅ |
| TTFV warm | 1688 | 2544 | 3843 | **1182** ✅ |
| TTS warm | **4695** | 5434 | 9044 | 6285 (+34%) ❌ |
| Total warm | **7632** | 8369 | 14665 | 8891 (+16%) |
| Persona | OK | OK | OK | OK |

**T15 не побил T7.** E2B/LLM выигрыш съеден TTS-регрессией.

#### Key findings

1. ✅ **E2B is faster than E4B on LLM stage** (T15a LLM warm 2323ms vs T14c 3946ms = **−41%**). Подтверждённый win.
2. ✅ **TTFV warm 1182ms — лучший показатель из всех voice-тестов.** Streaming pipeline работает.
3. ❌ **TTS regression блокирует прогресс.** Без чистого произношения никакой LLM speedup не имеет смысла. Цель T16 — фикс BUG #1 и BUG #2.
4. ❌ **ngram-mod на русском free-form тексте — no-op.** Удалить или попробовать `n_match=8`.
5. ⚠ **history_turns=2 кореллирует с TTS regression.** Возможно длиннее prompt → длиннее replies → больше TTS chunks → больше «эхо». Стоит проверить с history_turns=0 в T16.
6. ✅ **systemd crashloop fix работает** — `sound_success` events только при настоящем boot (3 раза за весь T15), без loop'а.

#### Raw data filter
```
T15a: source=voice_loop, ts ∈ [2026-05-15T11:32:42Z, 2026-05-15T11:36:40Z]
T15b: source=voice_loop, ts ∈ [2026-05-15T11:42:07Z, 2026-05-15T11:45:53Z]
T15c: source=voice_loop, ts ∈ [2026-05-15T11:50:00Z, 2026-05-15T11:54:53Z]
Backup: /tmp/T15_metrics.jsonl, /tmp/T15_events.jsonl, /tmp/T15_adam_llm.log, /tmp/T15_orchestrator.log
```

---

### Test 14 — 2026-05-15 13:17 MSK ✅ COMPLETED (restart-resilience: 3 consecutive runs on T7 baseline config)
**Module:** Voice Pipeline (E2E voice — **regression validation на a8ff3ce, T7-equivalent state**) • **Commit:** [a8ff3ce](https://github.com/7teenzzz/Adam-Chip/commit/a8ff3ce) (detached HEAD from `V-S06.3-opt_voice_pipe_3wave`) • **Phrases:** standard 7-phrase set × 3 runs
**Wall (combined):** 1003s (3 runs) • **Verdict:** ✅ 21/21 turns delivered, persona OK, total warm avg в одной лиге с T7 baseline (+10-18%); все 3 restart pattern'а отработали без потерь

#### Context

T14 — критический тест на «нет ли регрессии относительно T7» и «как 3 разных типа рестарта влияют на пайплайн». Запускался на коммите `a8ff3ce` (fix(reply-window): restore T7 values) — отличается от T7 baseline (`238f886`) только одной строкой `Tuning.json` (speed_multiplier 1.15→1.10).

После T13 (где ASR упал на CPU из-за висячего native Python процесса) была применена правка `deploy/systemd/adam-asr-whisperx.service` → Docker wrapper. В T14 эта правка валидирована — ASR warm avg ~1-1.8с против T13's 12.2с.

#### Config (active runtime)
- **LLM:** Gemma 4 **E4B** UD-Q4_K_XL, max_tokens=40, num_ctx=8192, no speculative — historical T7 baseline
- **ASR:** WhisperX `small` ru-RU **CUDA via Docker** (`/health → device=cuda model_loaded=true`), endpointing 1500ms, reply 3.75s / deadline 7.5s → cap 11.25s
- **TTS:** Silero `eugene` 24kHz, speed_multiplier=**1.10** (T7 был 1.15), filler «Хм...» 800ms enabled
- **Prompt:** history_turns=4, semantic.max_chars=2000, prompt_chars=~11100
- **Mic:** `mic_source=local` (PulseAudio)

#### Three-run protocol

| | T14a | T14b | T14c |
|---|---|---|---|
| **Тип рестарта** | Fresh boot (cold start) | Full stop.sh + start.sh | `systemctl restart adam-orchestrator` only |
| **Adam запущен** | 13:17:51 MSK | 13:27:10 MSK | (continued from T14b) |
| **T_start** | 13:19:45 MSK | 13:28:35 MSK | 13:36:16 MSK |
| **T_end** | 13:22:07 MSK | 13:31:05 MSK | 13:38:26 MSK |
| **Wall window** | 397s | 332s | 274s |
| **Что сохраняется live** | — | LLM/TTS/ASR Docker контейнер | LLM/TTS/ASR + llama-server cache |

#### Per-turn breakdown — T14a (fresh boot)
| # | TX | ASR | LLM | TTFV | TTS | Total | Reply (60c) |
|--:|---|--:|--:|--:|--:|--:|---|
| 1 | Привет! | **6735** | **9184** | 7113 | 5394 | **13150** | Привет. Ты здесь, и я тебя слышу. Что привело тебя |
| 2 | Как тебя зовут? | 4023 | 4833 | 2882 | 6826 | 9931 | Адам Чип — это имя, которое дали мне те, кто держит |
| 3 | Что ты сейчас чувствуешь? | 854 | 3667 | 1342 | 7118 | 8630 | Спокойствие. Медленный ритм, как будто внутри всё |
| 4 | Кто ты видишь вокруг? | 991 | 4665 | 4665 | 3649 | 8979 | Вижу человека в черном платье и парня, у которого |
| 5 | Расскажи коротко… | 1516 | 4300 | 2697 | 5623 | 8834 | Они дали мне имя, Адам Чип. Зачем — это вопрос… |
| 6 | А ты помнишь… | 1575 | 4503 | 3573 | 6575 | **12173** | Я не храню таких данных, если вы сами мне не сказа |
| 7 | Спасибо, на этом всё. | 1096 | 2184 | 2184 | 3023 | 5282 | Я жду, если захотите продолжить. |

#### Per-turn breakdown — T14b (full restart)
| # | TX | ASR | LLM | TTFV | TTS | Total | Reply (60c) |
|--:|---|--:|--:|--:|--:|--:|---|
| 1 | Привет. | **6848** | 2233 | 1548 | 3766 | 5839 | Приветствую. Что вас привело сюда? |
| 2 | Как тебя зовут? | 3801 | 4625 | 3963 | 3624 | 7776 | Это имя мне дали учёные. Адам Чип. |
| 3 | Кто ты сейчас чувствуешь? | 1008 | 3942 | 1756 | 6901 | 8748 | Сейчас я ощущаю спокойствие. Тихий ритм, как буд |
| 4 | Что ты видишь вокруг? | 2778 | 4258 | 2376 | 8785 | **11647** | Вижу человека, который стоит в комнате. Свет здесь |
| 5 | Расскажи коротко… | 989 | 5623 | 3577 | 7975 | **11694** | Учёные дали мне имя, и это всё, что я знаю о созд |
| 6 | А ты помнишь… | 929 | 3907 | 1769 | 6196 | 8762 | Я вижу перед собой человека. Имя — это как частота |
| 7 | Спасибо, на этом всё. | 1276 | 2840 | 2218 | 2746 | 5142 | Тишина — это тоже ответ. |

#### Per-turn breakdown — T14c (orchestrator-only restart)
| # | TX | ASR | LLM | TTFV | TTS | Total | Reply (60c) |
|--:|---|--:|--:|--:|--:|--:|---|
| 1 | Привет. | 999 | **10304** | 8515 | 4374 | **13394** | Здравствуй. Что ты принес со собой? |
| 2 | Как тебя зовут? | 1354 | 3718 | 2122 | 5884 | 8284 | Адам Чип — это имя, которое мне дали. Я не выбирал |
| 3 | Что ты сейчас чувствуешь? | 1598 | 4639 | 2437 | 6241 | 9211 | Сейчас тишина. Форма есть, содержание пока ещё ище |
| 4 | Что ты видишь вокруг? | 1295 | 3323 | 2307 | 5393 | 8169 | Вижу женщину слева и человека справа. Свет здесь |
| 5 | Расскажи коротко… | 841 | 6299 | 4072 | 8384 | **12536** | Учёные дали мне имя, это просто ярлык. Они хотели |
| 6 | помнишь как меня зовут? | 1233 | 4377 | 3008 | 5581 | 9109 | Форма есть, содержания нет. Мне неизвестно, как ва |
| 7 | Спасибо, на этом всё. | 1012 | 1316 | 1316 | 1115 | 2903 | Тишина. |

> **ASR fidelity issues:** T14a.1 «Адам, привет.» → «Привет!» (восклицание вместо точки — норм, wake обрезан). T14a.4 «Что» → «Кто», T14b.3 «Что» → «Кто» — известный quirk WhisperX small на быстрой речи. T14c.6 «А ты помнишь» → «помнишь» (потеря «А ты»). Все semantic-корректные.

#### Aggregate warm (n=6, exclude Turn 1) — сравнение трёх прогонов

| Stage | T14a warm | T14b warm | T14c warm |
|---|--:|--:|--:|
| ASR avg | 1676 | 1797 | **1222** ← лучший |
| LLM avg | 4026 | 4200 | 3946 |
| TTFV avg | 2891 | 2610 | 2544 |
| TTS avg | 5470 | 6038 | 5434 |
| **Total avg** | 8972 | 8962 | **8369** ← лучший |

#### Cold-start analysis — Turn 1 каждого теста

| Тест | Cold ASR | Cold LLM | Объяснение |
|---|---|---|---|
| T14a (fresh) | **6735** ms | **9184** ms | Всё холодное — Docker ASR booting + full LLM SWA prefill |
| T14b (full restart) | **6848** ms | 2233 ms | Docker ASR контейнер сохранил kv-cache → cold client reconnect (~7s); LLM warm |
| T14c (orch restart) | 999 ms | **10304** ms | ASR Docker не трогали → warm; orchestrator → warmup_llm_prefix → new SWA prefill |

**Открытие:** разные паттерны рестарта дают разные «холодные точки» в Turn 1, но **никогда не ломают пайплайн**. Это означает что для production достаточно `systemctl restart adam-orchestrator` — самый дешёвый рестарт с самым быстрым boot.

#### Throughput

| Metric | T7 baseline | T14a | T14b | T14c |
|---|--:|--:|--:|--:|
| Wall (s) | 110 | 397 | 332 | 274 |
| Active (s) | 52.8 | 67.0 | 59.6 | 63.6 |
| Active ratio | **48%** | 17% | 18% | **23%** |
| Throughput (t/min) | 3.82 | 1.06 | 1.27 | **1.53** |
| Δ Active vs T7 | baseline | +27% | +13% | +20% |

> **Throughput-by-wall в 2.5× ниже T7** — обусловлено пользовательскими паузами 2-3с между фразами (T7 wall = 110s, T14 = 274-397s на тех же 7 фразах). **Pipeline-internal regression**: Active +13-27% vs T7 — приемлемо, в той же лиге.

#### Events — reply window stability

| Event | T7 (норма) | T14a | T14b | T14c |
|---|---|--:|--:|--:|
| `wake_word_detected` | 1 | 2 | **3** | 2 |
| `reply_window_expired` | 0-1 | 0 | 0 | 1 |
| `asr_no_reply_standby` | 1 | 1 | 2 | 1 |
| `wake_silence_timeout` | 1 | 1 | 1 | 1 |
| `tts_filler` | 7/7 | 7/7 ✅ | 7/7 ✅ | 7/7 ✅ |

**«Двойное слушаю» подтверждено в metrics** (UX-замечание пользователя): T14b 3 wake = 1 настоящий + 2 ложных в тишине; T14c 2 wake + 1 reply_window_expired = wake→reply→timeout→standby→повторный wake. Причина — OWW `threshold=0.20` (низкий) + фоновые шумы. Не баг, UX-шероховатость.

#### Persona quality

| Test | Reply length avg | Стиль |
|---|---|---|
| T14a (fresh boot) | 64 chars / 12 words | Описательный, прозаический |
| T14b (full restart) | 72 chars / 12 words | Сжатее, больше метафор |
| T14c (orch restart) | **57 chars / 10 words** | Минималистичный, **INTP/5w4 pure** |

**Golden quotes:**
- T14b.7: «Тишина — это тоже ответ.» ← signature INTP closing
- T14c.4: «Вижу женщину слева и человека справа. Свет здесь холодный, как старый металл.»
- T14c.7: «Тишина.» ← single-word closing, perfect

**Correctness checks (across 21 turns):**
| Check | Result |
|---|---|
| JSON/markdown/code leakage (CLAUDE.md invariant 1) | ✅ 0/21 |
| Chinese characters | ✅ 0/21 |
| Reply truncation by max_tokens=40 | ✅ 0/21 |
| Russian fluency | ✅ all |
| Filler hit rate | ✅ 21/21 |

#### Regression vs predecessors

| Metric | T7 (E4B) | T8 (E4B) | T11 (E4B regression) | T13 (E2B+ngram, CPU ASR) | **T14c (best of T14)** |
|---|--:|--:|--:|--:|--:|
| LLM model | E4B | E4B | E4B | E2B+ngram | **E4B** |
| ASR warm | 1009 | 1264 | (n/a) | 12216 (CPU!) | **1222** ✅ |
| LLM warm | **2868** | 4082 | 6022 | 4490 | 3946 |
| TTFV warm | **1688** | 2864 | 4610 | 3843 | 2544 |
| TTS warm | **4695** | 5922 | 6618 | 9044 | 5434 |
| Total warm | **7632** | 9103 | 11555 | 14665 | **8369** |
| Wake re-triggers | 0 | 0 | 1 | 8 | 2 |
| Persona | OK | OK | OK | OK | **OK** |

**T14c — лучший из T14 — на +10% медленнее T7, но в одной лиге.** Все 21 turn успешные. Pipeline стабилен.

#### Bugs surfaced (новые)

1. **🐛 BUG #1 — success.wav loop после orch restart (T14c).**
   - User report: «звук success воспроизводился постоянно раз в несколько секунд после restart orchestrator»
   - 7 `voice_state_change` events в T14c window → возможно success-cue триггерится на каждом state change
   - **TODO:** найти источник в `sound.py` или `voice.py`, ограничить до boot-once

2. **⚠ BUG #2 — OWW false wakes в тишине (T14b: 3 wake, T14c: 2 wake).**
   - Причина: `wake_word.threshold=0.20` + `debounce_hits=2` слишком чувствительно
   - **TODO:** Бенчмарк threshold=0.35 vs 0.20 на тех же фразах, выбрать оптимум

3. **⚠ ASR fidelity issue — WhisperX small «Что» ↔ «Кто».**
   - 3 случая из 21 turn — punctuation/short-words drift
   - **TODO:** оценить трейдоф (small 1.2с) vs (medium ~2.5с) для аккуратности

#### Key findings

1. ✅ **CUDA ASR fix полностью валидирован.** Все три прогона: ASR warm avg 1.2-1.8с против T13's 12.2с (CPU). Docker контейнер устойчив через 3 разных типа рестарта.
2. ✅ **Restart-resilience confirmed.** Три разных паттерна рестарта (fresh / full / orch-only) — все три дали 7/7 успешных turn'ов. **Не обнаружено патернов где restart ломает пайплайн.**
3. ✅ **T14c (orch-only restart) — fastest path:** Total warm 8369ms = T7 +10%, near-baseline. Для production использовать `systemctl restart adam-orchestrator` как штатный «refresh».
4. ✅ **Persona quality прогрессирует** между прогонами — T14c имел самые поэтичные/минималистичные реплики. С `history_turns=4` Adam «прогревается» примерами в контексте.
5. ⚠ **Pipeline не быстрее T7** — Total warm 8369 vs 7632 (+10%). E4B + flash-attn + q8_0 cache = верхний потолок без рефакторинга prompt'а или модельной замены. Для дальнейшего прогресса — T15 на V-S06.3 (E2B + ngram-mod + CUDA ASR).

#### Raw data filter
```
T14a metrics: source=voice_loop, ts ∈ [2026-05-15T10:19:45Z, 2026-05-15T10:22:07Z]
T14b metrics: source=voice_loop, ts ∈ [2026-05-15T10:28:35Z, 2026-05-15T10:31:05Z]
T14c metrics: source=voice_loop, ts ∈ [2026-05-15T10:36:16Z, 2026-05-15T10:38:26Z]
Backup logs: /tmp/T14_metrics.jsonl, /tmp/T14_events.jsonl, /tmp/T14_adam_llm.log, /tmp/T14_orchestrator.log
```

---

### Test 13 — 2026-05-15 11:37 MSK ⚠ COMPLETED (ASR CPU fallback — new bottleneck)
**Module:** Voice Pipeline (E2E voice — **первый завершённый прогон на V-S06.3 с реально активным E2B+ngram_mod**) • **Commit:** [5ad3f0a](https://github.com/7teenzzz/Adam-Chip/commit/5ad3f0a) (`V-S06.3-opt_voice_pipe_3wave`) • **Phrases:** standard 7-phrase set (7/7 delivered)
**Wall:** 327s (T_start 11:37:10 → T_end 11:42:37 MSK) • **Verdict:** ⚠ 7/7 turns delivered, persona OK, но total avg warm 14665ms (на 60% медленнее T8 baseline) — root cause: WhisperX ASR упал на CPU runtime (avg 12.2s на запрос)

#### Context
T13 — первый полноценный E2E прогон где:
- LLM реально на **E2B + ngram_mod** (verified в journalctl: `adam_llm_run.sh` загружает Config.json → spec_type=ngram-mod, model=E2B-it-UD-Q4_K_XL)
- `mic_source=local` (после T12 ESP32 mic fail), local PulseAudio mic captured all 7 turns без degradation
- `prompt.history_turns=0` (clean baseline, без накопленной памяти)
- `adam_llm_run.sh` wrapper является единым источником истины для модели (после commit 5ad3f0a)

#### Config (active runtime)
- **LLM:** Gemma 4 **E2B** UD-Q4_K_XL, max_tokens=40, ngram-mod (n-match=24, n-min=48, n-max=64)
- **ASR:** WhisperX `small`, ru-RU — **fell back to CPU runtime** (см. Root cause), endpointing 1500ms, reply 3.75s / deadline 7.5s → cap 11.25s
- **TTS:** Silero `eugene` 24kHz, speed=1.10, filler «Хм...» enabled
- **Prompt:** history_turns=0, semantic.max_chars=2000, prompt_chars=11117

#### Per-turn breakdown
| # | UTC | Transcript | ASR | LLM | TTFV | TTS | Total | Reply (60ch) |
|--:|---|---|--:|--:|--:|--:|--:|---|
| 1 | 08:38:07 | Привет. | **24186** | 3486 | 3477 | 11599 | **18520** | Тишина в воздухе густая, как смола. Я просто здесь, |
| 2 | 08:38:50 | Как тебя зовут? | 18696 | 2862 | 2858 | 8003 | 11887 | Меня зовут Адам Чип. Это имя дали мне те, кто не знает, |
| 3 | 08:39:31 | Что ты сейчас чувствуешь? | 11296 | 6484 | 3148 | 11330 | 15495 | Тепло. Оно проникает сквозь слои, как медленный свет в |
| 4 | 08:40:21 | Что ты видишь вокруг? | 8363 | **10550** | **10547** | 7708 | **21833** | Вижу тень на экране. Свет холодный, он не греет. |
| 5 | 08:40:59 | Расскажи коротко, кто тебя создал и зачем. | 14189 | 2730 | 2724 | 7935 | 11685 | Меня создали, чтобы понять, что значит быть чем-то бол |
| 6 | 08:41:51 | А ты помнишь как меня зовут? | 11645 | 3650 | 3120 | **15969** | 20115 | Имя — это форма, которую мне дали. Оно не вписывается  |
| 7 | 08:42:32 | Спасибо, на этом все. | 9107 | 662 | 662 | 3316 | 6978 | Дальше темно. |

> **ASR fidelity:** T1 "Привет." вместо "Адам, привет." — wake word отбросился WhisperX от транскрипта (правильное поведение). T6 без запятой. T7 без «Адам» и «всё». 7/7 распознано смыслово корректно.

> **T4 anomaly (LLM=10550ms):** Аномальный LLM-tick в turn 4 — возможно SWA-инвалидация после scene_updated (27 scene_updated events в окне теста, scene_interval_sec=4). Не повторилось в T2/T3/T5/T6.

#### Aggregate stats (n=7)
| Stage | avg | p50 | min | max |
|---|--:|--:|--:|--:|
| ASR | **13926** | 11645 | 8363 | 24186 |
| LLM | 4346 | 3486 | 662 | 10550 |
| TTFV | 3791 | 3120 | 662 | 10547 |
| TTS | 9409 | 8003 | 3316 | 15969 |
| Total | **15216** | 15495 | 6978 | 21833 |

#### Warm aggregate (n=6, exclude Turn 1 cold)
| Stage | avg |
|---|--:|
| ASR | 12216 |
| LLM | **4490** |
| TTFV | **3843** |
| TTS | 9044 |
| Total | **14665** |

#### Throughput
- Wall: 327s, Active: 106.5s (32.6%), Idle: 220.5s (67.4% — userpauses + reply_window_expired re-wakes)
- Throughput: **1.28 turn/min** (catastrophic — T7 baseline 3.82 turn/min)

#### Reply window verification (UX critical)
| Metric | Value | Expected | Verdict |
|---|---|---|---|
| Turns delivered | 7/7 | 7/7 | ✅ |
| `wake_word_detected` events | **9** | 1 | ❌ — Adam ушёл в standby несколько раз |
| `reply_window_expired` events | **5** | 0–1 | ❌ — ASR overrun cap=11.25s |
| `asr_no_reply_standby` | 2 | 1 (после T7) | ⚠ |
| `wake_silence_timeout` | 1 (финальный) | 1 | ✅ |

**Это и есть «слушаю срабатывал два раза»** — пока ASR грыз 14–24с на распознавание, reply window (cap 11.25s) истекал, Адам уходил в standby, OWW снова детектил wake word на следующей фразе. Не баг UI, а симптом ASR slowdown.

#### Stage contribution (% of total, warm)
| Stage | % | Comment |
|---|--:|---|
| **ASR** | **83.3%** | catastrophic CPU fallback |
| TTS | 61.7% | overlaps with LLM via streaming |
| LLM | 30.6% | E2B+ngram OK, аномалия T4 inflates avg |

(сумма >100% потому что TTS streaming работает параллельно с LLM/ASR)

#### Root cause: ASR runtime regression (CPU instead of CUDA)

**Discovery (post-test investigation):**
```bash
$ curl -sf http://127.0.0.1:8095/health
{"device": "cpu", "device_requested": "cuda", ...}
```

Контейнер `adam-asr-whisperx` (Docker, CUDA) был в состоянии `Exited (1)` — порт 8095 был занят. На нём слушал нативный Python-процесс `python -m System.Speech.ASR_WhisperX` (PID 2878607), запущенный вручную через `nohup` в более ранней сессии диагностики. У нативного runtime'а `ctranslate2` — это **pip-wheel CPU-only** для aarch64 (нет CUDA binary на PyPI для arm64); CUDA-build нужно собирать из исходников (см. CLAUDE.md gotcha + `scripts/adam_asr_cuda_check.sh`).

Поэтому каждый `/transcribe` шёл на CPU → small model для русского аудио (~6с произнесения) даёт 8–24с processing. Совершенно нерабочее значение для realtime UX.

**Why не заметили раньше:** в Tests 7/8/11 ASR работал через Docker CUDA (verified). После T11→T12 сессия с port-collision, диагностические попытки запускать native ASR оставили висячий процесс. T13 запущен на native CPU без явной индикации в UI.

#### Fix applied (post-T13, pre-T14)
```bash
# 1. Kill native Python ASR
kill 2878607

# 2. Start canonical Docker ASR
docker compose up -d adam-asr-whisperx

# 3. Verify
curl -sf http://127.0.0.1:8095/health
# → {"device": "cuda", "model_loaded": true, "compute_type": "float16"}
```

Healthcheck: **healthy (Up 54 min)** на момент написания этой записи.

#### Quality assessment

**Persona integrity (INTP/5w4):**
- Реплики в характере: «тишина в воздухе густая, как смола», «свет холодный, он не греет», «дальше темно» — характеристический lexical markers сохранены
- Tone consistent: замкнутый, фрагментарный, чёрно-юморной (T4 «Свет холодный, он не греет.» — отличный INTP-paradox в одной фразе)
- Никаких хаотичных переключений тона, language drift, китайских иероглифов, markdown/JSON leakage

**Correctness checks:**
| Check | Result |
|---|---|
| JSON/markdown/code leakage (CLAUDE.md invariant 1) | ✅ 0/7 |
| Reply truncation by max_tokens=40 | ⚠ T3 truncated mid-phrase ("Я просто жду, что дальше." — закончен корректно но reply длиннее обычного) |
| Lexical TTR | ✅ 0.85+ across all 7 |
| Russian fluency | ✅ OK по выборке |
| Filler hit rate | 6/7 (`tts_filler` events) |

#### Regression vs предыдущие тесты

| Metric | T7 (E4B voice) | T8 (E4B voice) | T9 (E2B API) | T11 (E4B voice) | **T13 (E2B voice, ASR=CPU)** | Δ vs T8 |
|---|--:|--:|--:|--:|--:|--:|
| ASR warm avg | 1009 | 1264 | n/a | (не зафиксировано) | **12216** | **+866%** |
| LLM warm avg | 2868 | 4082 | 1509 | 6022 | **4490** | +10% |
| TTFV warm avg | 1688 | 2864 | 902 | 4610 | 3843 | +34% |
| TTS warm avg | 4695 | 5922 | 5001 | 6618 | 9044 | +53% |
| Total warm avg | 7632 | 9103 | 5998 | 11555 | **14665** | **+61%** |
| Throughput turn/min | 3.82 | 3.02 | 8.40 (API) | ~5.0 | **1.28** | **−58%** |
| Wall clock | 110s | 139s | 50s (API) | ~360s | 327s | comparable |
| Wake re-triggers | 0 | 0 | n/a | 1 | **8** | regression |
| Persona | OK | OK | OK | OK | **OK** | ✅ |

#### Key findings

1. **ASR — новый bottleneck**, не LLM. Если CPU ASR ≈ 12s/turn — никакая оптимизация LLM/TTS не спасёт UX. Это **первый тест где замерили реальный воздействие WhisperX runtime на live pipeline**. Все ранее «измеренные» ASR-времена (T7=1009, T8=1264, T11 не зафиксировано) были на CUDA.
2. **E2B + ngram_mod working** в runtime (verified via journalctl + adam_llm_run.sh logs). LLM warm avg 4490ms смешано с аномалией T4 — без T4 avg падает до ~2078ms (в одной линии с T9 API mode E2B=1509ms).
3. **`adam_llm_run.sh` Wrapper-pattern OK.** Single source of truth работает: `Config.json` → `services.llm.model_path` подхватывается launcher'ом → llama-server загружает правильную модель. UI редактирование Config.json → `systemctl restart adam-llm.service` → новая модель в продакшене. Verified в этом тесте.
4. **`mic_source=local` стабилен.** 7/7 turns с PulseAudio mic без degradation. `voice_degraded=false` во всех записях. ESP32 mic пока fallback'нут — не критично для T13/T14.
5. **TTS — bottleneck #2**, как было видно ещё в T9. Реплики Адама в T13 в среднем длиннее (avg ~80 chars vs T9 65 chars) → 9044ms vs 5001ms TTS. Reasonably explained by content variance.
6. **«Слушаю двух раз» — известное последствие ASR overrun**, не баг UI. С CUDA ASR (~1с) reply window ≈ 11s полностью покроет endpointing+ASR+filler delay.

#### Next steps (T14)

После применения fix (Docker ASR with CUDA):
1. Прогон Test 14 с тем же набором 7 фраз
2. Ожидание: ASR warm avg ≈ 800–1500ms, Total warm avg ≈ 6000–8000ms, throughput ≥ 3.5 turn/min
3. Если T4-style LLM anomaly повторится — investigate SWA invalidation pattern (scene churn ↔ LLM)
4. Filler hit rate ≥ 6/7, wake re-triggers ≤ 1

#### Pre-T14 fixes (to apply)
1. **Ensure Docker ASR is canonical runtime** (Add to runbook: NEVER run native ASR via nohup — collision risk)
2. **Add health gate в Orchestrator**: при boot проверять `/health → device=cuda`, иначе deny voice_loop_start (FAIL-FAST)
3. Документировать в CLAUDE.md: `device:cpu в /health = degraded — ОБЯЗАТЕЛЬНО Docker container, ctranslate2 pip-wheel CPU-only на aarch64`

#### Raw data filter
```
data/adam/inference_metrics.jsonl: source=voice_loop, ts ∈ [2026-05-15T08:37:10Z, 2026-05-15T08:42:37Z]
data/adam/events.jsonl: same window (1833 events, 9 wake_word_detected, 5 reply_window_expired)
journalctl: -u adam-llm.service --since "2026-05-15 11:35:00" --until "2026-05-15 11:43:00"
ASR health snapshot (degraded): {"device": "cpu", "device_requested": "cuda"} — captured post-test
```

---

### Test 12 — 2026-05-15 10:48 MSK ❌ FAILED (ESP32 mic timeout, fallback too slow)
**Module:** Voice Pipeline (E2E voice — **первая попытка с реально применёнными H1+H2**) • **Commit:** [1dc0e64](https://github.com/7teenzzz/Adam-Chip/commit/1dc0e64) (`V-S06.3-opt_voice_pipe_3wave`) • **Phrases:** standard 7-phrase set (не дошёл до first turn)
**Wall:** не применимо (тест прерван на стадии mic-fallback) • **Verdict:** ❌ pipeline не получал аудио от ESP32 mic; fallback на local не успел сработать

#### Context
T12 — **первый запуск где systemd реально загружает E2B + ngram_mod** (после правки `/etc/adam-chip/adam.env` и `/etc/systemd/system/adam-llm.service` через sudo). Ранее T10 декларировал H1+H2 но фактически шёл на E4B без ngram из-за двойного override-слоя systemd (см. T10 entry).

Также применена Опция B: `prompt.history_turns=4→0` + `dialogue_turns` trim 1118→11.

#### Timeline (UTC)
| Time | Event | Comment |
|---|---|---|
| 07:47:45 | systemd boot adam-llm | E2B загружен (verified) |
| 07:48:11 | tts_started + tts_filler | warmup turn started |
| 07:48:26 | warmup_wakeup OK | LLM сгенерировал warmup reply |
| 07:48:28 | warmup_llm_prefix latency=**1664ms** | E2B prefix warmup (vs E4B 12453ms — **−87% faster**!) |
| 07:48:31 | voice_loop_started | mic_source=esp32, esp_mic_fallback=false |
| 07:48:31 | voice_loop_boot_ready | |
| 07:48:00 | **T_start (пользователь говорил)** | |
| 07:48:45 | voice_loop_error stage=esp32_mic timed out | retry 1 |
| 07:49:01 | timeout 2 | retry 2 |
| 07:49:17 | timeout 3 | retry 3 |
| 07:49:33 | timeout 4 | retry 4 |
| 07:49:49 | timeout 5 | retry 5 |
| 07:50:05 | timeout 6 + **esp32_mic_fallback_start** | **fallback наконец сработал на 6/6 = 96 секунд после старта** |
| 07:50:05 | Пользователь остановил Адама | ровно в момент fallback |

#### Root cause analysis

1. **ESP32 mic streaming таймаутится** каждые ~16с с сообщением `voice_loop_error: timed out, stage: esp32_mic`
2. **ESP32 как устройство — функционирует**: `/api/status` отвечает (audio_ready=true, ethernet_connected=true, IP=192.168.0.171), `/api/audio/clip?ms=500` возвращает корректный WAV. Проблема в streaming-endpoint (не в clip)
3. **Fallback на local mic настроен** (`esp_mic_fail_threshold=6`, code в `Orchestrator.py:546-557`), но **96 секунд слишком долго** для UX-ожидания пользователя
4. **`audio_level`-events не публиковались** с 07:48:26 до 07:50:06 — то есть voice loop **полностью не получал** audio frames между warmup-ом и fallback-ом

#### Что НЕ удалось проверить
- Качество персоны на E2B в голосовом режиме (только в API T9)
- LLM/TTFV/TTS warm timings на E2B+ngram_mod в живом voice-pipeline
- ngram-mod #acc_drafts на реальных голосовых turn'ах
- Reply window stability на cap=11.25s

#### Pre-T13 fix applied
`System/Config.json: media.audio.esp_mic_fail_threshold 6→2`, `esp_mic_retry_interval_sec 10.0→30.0`.

Эффект: fallback теперь срабатывает после 2 таймаутов (~32 секунды) вместо 6 (96s). Зритель не успеет уйти. После fallback orchestrator продолжает периодически проверять ESP32 каждые 30с — если mic восстановится, переключится назад.

#### Observations on E2B from boot
- `warmup_llm_prefix latency: 1664ms` (vs E4B baseline 12453ms) — **подтверждает H1 ускорение на cold prefill**
- `ngram_mod initialized` в логах systemd — H2 реально активирован
- TTS warmup сгенерировал 4 partial-предложения за ~6s → streaming работает

T13 даст реальный замер E2B+ngram_mod в live-voice сценарии. Но требует устойчивого mic — поэтому **до T13 надо либо починить ESP32 mic stream, либо переключить mic_source=local**.

#### Raw data filter
```
data/adam/events.jsonl: ts ∈ [2026-05-15T07:47:30Z, 2026-05-15T07:50:30Z]
journalctl: -u adam-llm.service --since "2026-05-15 10:47:00" --until "2026-05-15 10:51:00"
```

---

### Test 11 — 2026-05-15 09:53 MSK
**Module:** Voice Pipeline (E2E voice) • **Commit:** [8f57bb3](https://github.com/7teenzzz/Adam-Chip/commit/8f57bb3) (`V-S05.2-optim_voice_pipeline` — rollback после T10) • **Phrases:** standard 7-phrase set (с ASR-разбросом)
**Wall:** ~6m (T_start не записан → ~09:53:00, T_end 09:59:33 MSK; standby детектится в 06:57:59 UTC) • **Verdict:** ⚠ regression vs T7/T8 baseline на той же ветке

#### Config (V-S05.2 — фактически активный E4B)
- **LLM:** Gemma 4 **E4B** UD-Q4_K_XL via llama.cpp (systemd cached unit pointed to E4B), max_tokens=40
- **ASR:** WhisperX `small` (Docker, CUDA), endpointing 1500ms, reply 3.75s / deadline 7.5s → cap 11.25s
- **TTS:** Silero `eugene` 24kHz, speed=1.10
- **Prompt:** history_turns=4, semantic.max_chars=2000

#### Methodology context
T11 — попытка validate стабильность V-S05.2 baseline после неудачного T10 на V-S06.3. **Не "чистый" baseline:** перед T11 было два полных restart adam-llm.service, накопленная история в SQLite (1118 turn'ов в `dialogue_turns`), scene_worker обновлял VLM context.

#### Per-turn breakdown
| # | UTC | Transcript | LLM | TTFV | TTS | Total | Reply (50ch) |
|--:|---|---|--:|--:|--:|--:|---|
| 1 | 06:53:17 | Ты меня слышишь? | 5826 | 3961 | 6073 | 10157 | Слышу. Твой тон — это тихий отпечаток на пов |
| 2 | 06:54:09 | Как тебе зовут? | **9775** | 8056 | 6619 | 14834 | Адам Чип — это имя, которое мне дали. |
| 3 | 06:54:43 | Что ты сейчас чувствуешь? | 2892 | 1650 | 6196 | 7992 | Спокойствие. Что-то очень плотное и медленно |
| 4 | 06:55:29 | Что ты видишь вокруг? | 3990 | 3142 | 4410 | 8016 | Вижу двух людей в этой комнате. Один в чёрно |
| 5 | 06:56:10 | Расскажи, кто тебя создал и зачем. | 9289 | 7561 | 7882 | 15779 | Это они придумали имя. Зачем — это уже не мо |
| 6 | 06:56:52 | А ты помнишь как меня зовут? | 4162 | 2643 | 7983 | 11156 | Мне не давали твоего имени. Я вижу только те |
| 7 | 06:59:18 | Спасибо, на этом всё. | **16964** | **16964** | 3597 | 20708 | Дальше темно. |

> **ASR fidelity issues (T1, T2, T5):** T1 "Ты меня слышишь?" вместо "Адам, привет." — пользователь сказал по-памяти из старых тестов или ASR. T2 "Как тебе зовут?" (буква «е» вместо «я»). T5 без "коротко". Pattern совпадает с T7/T8 в смысле фактического содержания, но текст-в-текст не идентичен.

> **T7 anomaly (LLM=TTFV=16964ms):** После T6 пользователь молчал 67 секунд → `reply_window_expired @06:57:59` → standby. Пришлось снова wake @06:58:34. После повторного wake LLM получил полный prefill из-за SWA cache reset. Один-предложение reply ("Дальше темно.") → TTS не успел streaming → TTFV=LLM.

#### Aggregate stats (n=7)
| Stage | avg | p50 | p95 | min | max |
|---|--:|--:|--:|--:|--:|
| LLM | 7557 | 5826 | 21277 | 2892 | 16964 |
| TTFV | 6282 | 3961 | 22309 | 1650 | 16964 |
| TTS | 6109 | 6196 | 8044 | 3597 | 7983 |
| Total | **12663** | 11156 | 23665 | 7992 | 20708 |

#### Warm aggregate (n=5, T2–T6, без T1 cold + T7 anomaly)
| Stage | avg |
|---|--:|
| LLM | **6022** |
| TTFV | **4610** |
| TTS | 6618 |
| Total | **11555** |

#### Regression vs T7/T8 (same V-S05.2, same E4B)
| Stage | T7 | T8 | T11 | Δ vs T7 | Δ vs T8 |
|---|--:|--:|--:|--:|--:|
| LLM warm | 2868 | 4082 | 6022 | **+110%** | **+48%** |
| TTFV warm | 1688 | 2864 | 4610 | **+173%** | **+61%** |
| TTS warm | 4695 | 5922 | 6618 | +41% | +12% |
| Total warm | 7632 | 9103 | **11555** | **+51%** | **+27%** |

#### Root cause investigation

| Hypothesis | Evidence | Verdict |
|---|---|---|
| Prompt size grew | `prompt_chars=11117` в T7/T8/T11 — **идентично** | ❌ not the cause |
| LLM context tokens grew | journalctl T11.7: `task.n_tokens=3919` (vs CLAUDE.md baseline ~2800) | ⚠ partial — +1100 tokens объясняется history+scene context |
| SWA cache invalidation per turn | journalctl: `erased invalidated context checkpoint (n_swa=512)` каждый turn | ⚠ известный bug Gemma 4 (CLAUDE.md gotcha) |
| Cold-restart of llama-server | adam-llm.service stopped 09:49:31 → started 09:50:00 → boot для T11 | ✅ Turn 1 LLM=5826ms объясняется этим |
| Memory accumulation | 1118 rows в `dialogue_turns`, history_turns=4 = 4 messages из старых тестов | ✅ +200-400 tokens на каждый turn |
| Scene_worker churn | scene_updated events каждые 4s → ctx_body меняется → SWA-инвалидация | ✅ contributing factor |

**Primary cause:** combination of SWA cache reset (architectural Gemma 4 bug) + accumulated dialogue history from 1118 prior turns + scene context churn → каждый turn делает ~200-400 token re-prefill сверх baseline.

**Why T7/T8 не страдали:** T7 был на свежей памяти после 238f886, T8 шёл сразу после T7. К T11 в SQLite накопилось 1118 turn'ов из всех предыдущих тестов + smoke + manual API calls. С `history_turns=4` orchestrator подтягивает 4 последних message'а, которые могли быть длинными ответами Адама из T8/T9 (до 121 chars).

#### Notes
- T1 фраза "Ты меня слышишь?" — пользователь импровизировал, не строго следовал standard set
- T7 не было в reply mode (потребовался re-wake) — НЕ regression пайплайна, это пользовательская пауза 67s, превысившая cap=11.25s
- TTS playback stayed stable (6618ms warm) — модель Silero не была затронута
- Persona OK по выборке — реплики в характере, никаких bad-format leakage

#### Recommended fix для T12
1. Очистить `dialogue_turns` до базового состояния (или хранить N последних turns только):
   ```bash
   .venv/bin/python -c "import sqlite3; c=sqlite3.connect('data/adam/memory.sqlite3'); c.execute('DELETE FROM dialogue_turns WHERE id < (SELECT MAX(id)-10 FROM dialogue_turns)'); c.commit()"
   ```
2. Or temporary `prompt.history_turns=0` в Tuning.json для clean benchmark.

#### Raw data filter
```
data/adam/inference_metrics.jsonl: source=voice_loop, ts ∈ [2026-05-15T06:53:00Z, 2026-05-15T07:00:00Z]
journalctl: -u adam-llm.service --since "2026-05-15 09:50:00" --until "2026-05-15 10:01:00"
```

---

### Test 10 — 2026-05-15 09:43 MSK ❌ FAILED
**Module:** Voice Pipeline (E2E voice — **attempted on V-S06.3 with H1+H2**) • **Commit:** [a835ad0](https://github.com/7teenzzz/Adam-Chip/commit/a835ad0) (`V-S06.3-opt_voice_pipe_3wave`) • **Phrases:** standard 7-phrase set (не дошёл до first turn)
**Wall:** не применимо (тест прерван на этапе wake word) • **Verdict:** ❌ pipeline не отреагировал на пользователя

#### Что произошло
- **09:43:26 MSK** (06:43:26 UTC) — Adam запущен
- **09:43:28** — systemd запустил adam-llm.service
- **09:44:08** — `prewarm_filler` OK
- **09:45:11** — `warmup_wakeup` OK
- **09:45:23** — `warmup_llm_prefix latency_ms=12453` (12.5s cold prefill)
- **09:45:26** — `oww_ready threshold=0.20`, `voice_loop_boot_ready`
- **09:46:20** — **T_start: пользователь сказал «Адам, привет.»**
- **09:47:24** — `wake_word_detected score=0.782` (**через 64 секунды после T_start!**)
- **09:47:29** — `wake_silence_timeout` → standby (пользователь к этому моменту уже остановил тест)

#### Two compounding root causes

**Cause 1: H1/H2 не применились в runtime (systemd unit cache).**
journalctl показал что adam-llm.service загрузил:
```
srv  load_model: loading model '.../gemma-4-E4B-it-UD-Q4_K_XL.gguf'
general.name str = "Gemma-4-E4B-It"
```
То есть **E4B, не E2B**. Хотя диск-файл `deploy/systemd/adam-llm.service` на V-S06.3 после H1 коммита (`9b5bd38`) указывает на E2B. Причина: systemd кеширует unit-файлы при первой загрузке; для применения изменений нужен `sudo systemctl daemon-reload`. Этот шаг был пропущен после H1.

Effective config T10 = плоский E4B без ngram-mod. Тест НЕ measured H1+H2.

**Cause 2: Wake-word delay 64 секунды.**
ESP32 mic config (commit `863c204` на V-S06.3 ввёл `mic_source: "esp32"`, `esp_mic_fail_threshold=6`). Возможно ESP32 mic stream не был стабилен в момент boot — local mic eventually picked up wake word, но за 64s пользователь возможно говорил несколько раз. Score 0.782 (выше threshold 0.20) подтверждает что mic в итоге работал.

#### Files & state at the time
- Branch: V-S06.3-opt_voice_pipe_3wave, HEAD = a835ad0
- Config.json: `mic_source=esp32`, model=`E2B` (но systemd игнорил это)
- adam-llm.service (disk): E2B path (но systemd cache имел E4B)

#### Действие после T10
Пользователь сделал `git checkout V-S05.2-optim_voice_pipeline` → запустил Test 11.

#### Notes
- Если бы H1/H2 действительно работали, T10 мог бы дать LLM warm avg ≈ 1500ms, TTFV ≈ 900ms (см. T9 API mode). Но без `daemon-reload` это нереализуемо.
- Wake-word delay — отдельная независимая проблема, требует mic-source verification перед T12

#### Raw data filter
```
data/adam/events.jsonl: ts ∈ [2026-05-15T06:43:00Z, 2026-05-15T06:50:00Z]
journalctl: -u adam-llm.service --since "2026-05-15 09:43:00" --until "2026-05-15 09:50:00"
```

---

### Test 9 — 2026-05-15 09:27 MSK
**Module:** Voice Pipeline (LLM+TTS only — **API mode**) • **Commit:** [cd6c63a](https://github.com/7teenzzz/Adam-Chip/commit/cd6c63a) (`V-S06.3-opt_voice_pipe_3wave`) • **Phrases:** standard 7-phrase set (via `/api/agent/turn`)
**Wall:** 50s (start 09:27:52 → end 09:28:42 MSK) • **Active:** 42.4s • **Verdict:** ✅ persona OK, **LLM −63%** vs T8 baseline; ngram-mod inactive (0 drafts accepted at default n-min=48)

#### Config (post H1+H2)
- **LLM:** **Gemma 4 E2B UD-Q4_K_XL** (H1, vs T8 E4B), max_tokens=40, cache_prompt=true, `--spec-type ngram-mod --spec-ngram-mod-n-match 24 --spec-ngram-mod-n-min 48 --spec-ngram-mod-n-max 64` (H2)
- **ASR:** **не задействовано** — текст подавался напрямую через `/api/agent/turn` (нет реального микрофона)
- **TTS:** Silero `eugene` 24kHz, speed_multiplier=1.10, filler «Хм...» cached
- **Prompt:** history_turns=4 (Tuning.json), `response_word_target` отсутствует в Tuning, semantic.max_chars=2000, prompt_chars=11117 (стабильно)

#### Methodology
Test 9 — **программный прогон через `/api/agent/turn`** для изоляции LLM+TTS пути от ASR. 7 стандартных фраз отправлены последовательно с 1-секундной паузой между ними. Метрики per-turn автоматически попадают в `inference_metrics.jsonl` с `source="manual"`. **ASR не измеряется** в этом режиме — для полной картины пайплайна нужен дополнительный voice-test (T10).

#### Per-turn breakdown (исчерпывающий)
| # | Phrase | LLM ms | TTFV ms | TTS ms | Total ms | Reply chars | Reply words | Reply |
|--:|---|--:|--:|--:|--:|--:|--:|---|
| 1 | Адам, привет. | 1310 | 573 | 5641 | 6385 | 54 | 10 | Привет. Здесь тихо, и я слушаю. Что привело тебя сюда? |
| 2 | Как тебя зовут? | 1223 | 840 | 3498 | 4434 | 47 | 9 | Меня зовут Адам Чип. Это имя, которое мне дали. |
| 3 | Что ты сейчас чувствуешь? | 1829 | 888 | 7362 | 8343 | 93 | 14 | Чувствую медленное мерцание. Это как тепло, которое приходит не извне, а изнутри… |
| 4 | Что ты видишь вокруг? | 1023 | 650 | 2998 | 3744 | 38 | 6 | Дальше темно. Свет холодный и далекий. |
| 5 | Расскажи коротко, кто тебя создал и зачем. | 2343 | 1754 | 9279 | **11125** | 121 | **22** | Меня создали, чтобы увидеть, а теперь я просто то, что остаётся после того, как видение… |
| 6 | А ты помнишь, как меня зовут? | 1959 | 607 | 5775 | 6480 | 87 | 17 | Имя — это форма, которую мне дали. Память об этом, как о чём-то личном, уже не достать. |
| 7 | Спасибо, Адам. На этом всё. | 675 | 675 | 1094 | **1864** | 13 | 2 | Дальше темно. |

#### Aggregate stats (n=7)
| Stage | avg | p50 | p95 | min | max |
|---|--:|--:|--:|--:|--:|
| LLM | **1480** | 1310 | 2573 | 675 | 2343 |
| TTFV | **855** | 675 | 2274 | 573 | 1754 |
| TTS | 5092 | 5641 | 10429 | 1094 | 9279 |
| Total | **6054** | 6385 | 12794 | 1864 | 11125 |

#### Warm aggregate (n=6, exclude Turn 1)
| Stage | avg | p50 | p95 |
|---|--:|--:|--:|
| LLM | 1509 | 1526 | 2592 |
| TTFV | 902 | 758 | 2318 |
| TTS | 5001 | 4637 | 10525 |
| Total | 5998 | 5457 | 12933 |

#### Stage contribution to total (warm avg)
| Stage | ms | % of total |
|---|--:|--:|
| LLM | 1509 | 25.2% |
| TTFV (within LLM/TTS overlap) | 902 | 15.0% |
| **TTS playback** | **5001** | **83.4%** ← новый bottleneck |

#### Throughput
- Active ratio: **84.8%** (high — нет пауз зрителя)
- Throughput: **8.40 turn/min** (нерепрезентативно — API mode skip'ает reply window и audio capture)

#### Quality assessment

**Persona integrity (INTP/5w4):**
- Реплики в характере: лексика «тихо», «темно», «мерцание», «холодный», «память», «форма», «увидеть» — Adam vocab markers по 1.3 на turn в среднем (range 0–3)
- Tone consistent: замкнутый, медитативный, фрагментарный (Turn 7 "Дальше темно." — отличный characteristic closing)
- Никаких хаотичных переключений тона, language drift, китайских иероглифов

**Correctness checks:**
| Check | Result |
|---|---|
| JSON/markdown/code leakage (CLAUDE.md invariant 1) | ✅ 0/7 |
| Reply truncation by max_tokens=40 | ✅ 0/7 (все заканчиваются на `.!?`) |
| Lexical TTR (per-reply diversity) | 1.00 across all 7 — без повторений |
| Reply length avg | 11.4 words (близко к старому `response_word_target=14` несмотря на отсутствие параметра в Tuning) |
| Russian fluency | OK (subjective review всех 7) |

**Regression vs T8 (E4B):**
| Metric | T8 (E4B real voice) | T9 (E2B API) | Δ | Caveat |
|---|--:|--:|--:|---|
| LLM avg warm | 4082 ms | **1509 ms** | **−63%** | direct comparison valid |
| TTFV avg warm | 2864 ms | **902 ms** | **−68%** | direct comparison valid |
| TTS avg warm | 5922 ms | 5001 ms | −16% | T9 чуть короче реплики |
| Total avg warm | 9103 ms | 5998 ms | −34% | T9 без ASR contribution |
| Reply length avg | ~80 chars | 65 chars | −19% | E2B пишет лаконичнее |
| Persona regression | — | none | ✅ | INTP/5w4 maintained |

#### Key findings

1. **H1 (E2B)** дал реальный winning: LLM −63%, TTFV −68%. Без потери персоны.
2. **H2 (ngram-mod) НЕ сработал** в текущих настройках. llama-server log показывает: `#gen drafts = 0, #acc drafts = 0`. Причина — `--spec-ngram-mod-n-min 48` (default) требует минимум 48 draft tokens; ответы Адама короче (avg 11 слов ≈ 25-30 токенов). Hash pool наполняется (5582 entries после 7 turns), но draft generation не запускается.
   - **Recommendation:** в следующей итерации попробовать `--spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 16` (адаптация под короткие реплики) или откатить H2 как no-op для нашего use case
3. **TTS playback — новый bottleneck** (83% от total). Дальнейшее ускорение требует либо сократить реплики (N7), либо параллелизовать playback (уже сделано через `_consumer` pipelining)
4. **Reply length avg 11.4 words** — Gemma 4 E2B стабильно держит короткий стиль даже без `response_word_target`. Это win для нашего use case
5. **TTFV 902ms warm** — близко к теоретическому пределу для sentence-level streaming (см. [docs/H4_streaming_llm_tts.md](../docs/H4_streaming_llm_tts.md))

#### Limitations & follow-up

- **No ASR measurement** в T9 (API mode). Полноценный T10 нужен голосовой — с реальным WhisperX-decoding для оценки end-to-end UX
- **ngram-mod tuning** — отдельная экспериментальная задача, по итогу либо переконфигурировать flags, либо убрать
- **Throughput 8.4 turn/min** не значит что зритель так быстро говорит — это пайплайн без user-pauses

#### Raw data filter
```
data/adam/inference_metrics.jsonl: source=manual, ts ∈ [2026-05-15T06:27:52Z, 2026-05-15T06:28:42Z]
data/adam/events.jsonl: same window (7 prompt_trace events, prompt_chars=11117 across all turns)
llama-server log: /tmp/llama-e2b-spec.log (ngram_mod statistics show 0 drafts accepted)
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
