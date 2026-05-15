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
