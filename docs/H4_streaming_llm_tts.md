# H4 — Streaming LLM → TTS: принципы и анализ

> **TL;DR:** оптимизация **уже реализована** в [System/Orchestrator.py](../System/Orchestrator.py#L2261) — функция `_stream_llm_and_speak()` запускает producer (LLM-стрим → разделение по предложениям) и consumer (синтез N+1 во время playback N) как параллельные asyncio-таски. TTS стартует на первом готовом предложении, не дожидаясь финала LLM. Этот документ описывает текущий статус, оставшиеся возможности оптимизации и риски при попытках пойти глубже.

---

## Цель оптимизации H4

Сократить **TTFV (Time To First Voice)** — задержку между концом речи зрителя и первым звуком ответа Адама из динамика — за счёт параллельного выполнения LLM-генерации и TTS-озвучивания.

Без streaming'а:
```
ASR_final ─[LLM full generation ~3s]─[TTS full synthesis+play ~5s]─→ end
                                    ↑ зритель слышит первый звук
                                    TTFV = 3s + ~200ms TTS-prep ≈ 3.2s
```

Со streaming'ом (целевое поведение):
```
ASR_final ─[LLM token stream  ─[1st sentence ~600ms]──[continue LLM ~2.4s]─→ end
                                  └──[TTS synth+play 1st chunk]──[chunk 2]→
                                  ↑ TTFV ≈ 700-900ms
```

---

## Что уже реализовано (актуальный код)

### 1. SSE-стриминг от LLM
`System/adam/inference.py:41` → метод `generate_streaming()` — async-генератор, yield'ит токены **по мере поступления** из llama.cpp OpenAI-compat SSE-endpoint (`/v1/chat/completions?stream=true`).

### 2. Producer task: разделение по предложениям
`System/Orchestrator.py:2286–2329` → `_producer()`:
- Аккумулирует токены в `buf`
- На каждом токене ищет `_SENTENCE_BOUNDARY_RE = (?<=[.!?。！？—])\s+`
- При нахождении границы → cleaned-предложение кладётся в `asyncio.Queue` (maxsize=4)
- Параллельно пишется событие `llm_partial` в event log (для отладки через UI)

### 3. Consumer task: pipelined synth + play
`System/Orchestrator.py:2390–2452` → `_consumer()`:
- Читает из queue
- Синтезирует chunk N+1 (через `tts._get_wav_bytes_sync` → Silero `/wav`) **в потоке**, параллельно с playback chunk N
- При первом успешном synth → событие `tts_started`, switch UI «Думаю» → «Говорю»
- Wav-байты проигрываются через ALSA `aplay`
- Fallback: если `/wav` упал → переход на `/speak` (synth+play one-shot)

### 4. Filler-mask для cold first sentence
`System/Orchestrator.py:2344–2388` → `_filler_task()`:
- Если первое предложение задерживается > `filler_delay_ms` (800ms) — играется кешированный «Хм...» (предварительно синтезирован в boot — N6)
- Когда реальный TTS стартует → filler аккуратно завершается, реальный звук идёт следом

### 5. Sentence-level granularity
Граница предложений включает русский em-dash «—», точки, восклицания, вопросы — натуральная просодия сохраняется. Минимальная единица для TTS = одно предложение (Silero v5_5_ru стабильно работает на коротких предложениях, на subsentence уровне начинает выдавать клипы).

---

## Где сейчас система = ожидаемое поведение H4

| Требование H4 | Реализация |
|---|---|
| TTS начинает проговаривать ответ по мере генерации LLM | ✅ Реализовано (sentence-level pipelining через `_producer`/`_consumer`) |
| LLM передаёт partial-результаты в TTS | ✅ `generate_streaming` yield'ит токены, producer группирует в предложения |
| TTS не ждёт финала LLM | ✅ Первый chunk играет сразу после первого `.!?—` |
| Partial-токен на знаке препинания → отдельное предложение | ✅ `_SENTENCE_BOUNDARY_RE` ловит границы |
| TTS запускает проговаривание на первом готовом предложении | ✅ `_consumer.first` ставит `tts_started` |
| Каждые ~500ms partial-апдейты | ⚠️ Не точно 500ms — события привязаны к sentence boundaries, не к таймеру. Эффективно: один partial ≈ каждые 600-2000ms (зависит от длины предложения) |

**Замер на E2B+ngram-mod (warm 5 turns):** TTFV avg = **656ms**. Это уже близко к теоретическому минимуму (LLM time-to-first-sentence ≈ 400-500ms + 150-200ms на Silero synth + ALSA boot).

---

## Что ещё можно оптимизировать

Дальнейшие шаги дают **диминишинговый выигрыш** (десятки ms) при значительных рисках просодии/качества.

### Опция A: Sub-sentence streaming (по запятым/паузам)
**Идея:** дополнительно к `.!?` ловить `, и `, ` но `, ` — `, ` поэтому ` и стримить более короткие куски.

**Ожидаемый выигрыш:** TTFV −100-200ms (первое «Слышу,» вместо «Слышу. Голос твой проникает…»).

**Риски (высокие):**
- Silero TTS на коротких фрагментах <3 слов выдаёт urgentную/обрезанную просодию — звучит «спотыкающимся»
- Пунктуация на запятой не всегда совпадает с натуральной паузой → unstable rhythm
- LLM может ещё дописать продолжение фразы, которое не вяжется с уже произнесённым началом

**Решение:** оставить sentence-level (текущий) **как оптимальный компромисс**.

### Опция B: Уменьшить TTS startup latency
**Идея:** Silero сейчас грузится в свой процесс, /wav endpoint работает через HTTP — есть overhead на сериализацию (~30-50ms на chunk).

**Возможные шаги:**
1. **In-process Silero:** загружать Silero в orchestrator-процессе напрямую, через PyTorch API. Экономия HTTP roundtrip ~30ms на первом chunk. Минус: дублирование VRAM (TTS уже занимает ~600MB), сложность жизненного цикла.
2. **Pre-warm sentence templates:** кэшировать synth-результат для часто встречающихся открытий предложений Адама («Я …», «Это …», «Тишина…»). Top-N начал предложений в Echoes.md → preload.

**Ожидаемый выигрыш:** TTFV −50-150ms. Стоимость: 1-2 дня работы.

### Опция C: GPU contention reduction
**Проблема:** ASR (WhisperX) + LLM (Gemma) + TTS (Silero, если используется в onnx/PT режиме) + VLM (VILA) — все идут на одну CUDA. Сейчас VLM последовательно с LLM (scene cache prefetch перед turn).

**Решение:** explicit GPU prioritization через `CUDA_VISIBLE_DEVICES` или CUDA streams. Не наш приоритет — на Jetson Orin NX единственная GPU.

### Опция D: TTS playback pre-emption
**Идея:** если зритель начал говорить НА середине ответа Адама — обрывать playback мгновенно (сейчас это делается через `runtime_state["interrupt_tts"]`).

**Статус:** уже реализовано через `interrupt_tts` flag (см. строки 2403, 2440 — взлом цикла consumer'а).

---

## Ожидаемое влияние на голосовой пайплайн (если всё сделано идеально)

| Метрика | T8 (E4B) | После H1+H2 (фактическое) | Теор. предел H4-optimized |
|---|---:|---:|---:|
| LLM avg warm | 4082 ms | 1548 ms | 1300-1500 ms |
| **TTFV avg warm** | **2864 ms** | **656 ms** | **400-500 ms** |
| TTS avg (play) | 5922 ms | 4500-5000 ms | не меняется |
| Total avg | 9103 ms | ~6700 ms | ~6500 ms |
| Throughput | 3.02 turn/min | ~4.0-4.5 turn/min | ~4.5-5.0 turn/min |

**Главный вывод:** после H1 (E2B) + H2 (ngram-mod) система **уже близка к теоретическому пределу** для sentence-level streaming. Дальнейшая оптимизация даёт меньше 200ms TTFV.

---

## Анализ рисков

### Риск 1: Просодия и интонация Silero (СРЕДНИЙ)
Sentence-level streaming уже **на грани** — короткие предложения Адама («Тишина.», «Скучно.», «Слышу.») часто звучат урывисто. Если двигаться к sub-sentence — риск растёт быстро.

**Митигация:** оставить sentence-level. Не дробить меньше.

### Риск 2: LLM генерация с длинными первыми токенами (НИЗКИЙ)
Если Gemma начинает с «Хм..., давай подумаю...» — первое предложение длинное, TTFV растёт. Текущий filler-кэш («Хм...» из N6) маскирует это.

**Митигация:** filler уже работает; promt-инструкции в `About/Identity.md` сокращают «думающие» вступления.

### Риск 3: Race conditions producer/consumer (НИЗКИЙ)
При неаккуратной cancel-семантике (например, при wake-word interrupt в середине LLM) producer мог бы остаться висеть. В текущем коде есть `asyncio.wait(... ALL_COMPLETED)` + try/finally с `queue.put(None)` сентинелом → решено.

**Митигация:** уже решено.

### Риск 4: TTS queue overflow (НИЗКИЙ)
Queue maxsize=4. Если LLM генерирует быстрее чем TTS играет — producer блокируется. Но Silero playback (~150 words/min) обычно медленнее, чем Gemma generation (300+ wpm) → backpressure естественный.

**Митигация:** queue size = 4 даёт защиту от runaway.

### Риск 5: GPU contention при concurrent ASR+LLM+TTS (СРЕДНИЙ)
Когда зритель уже договорил и WhisperX делает finalize в момент когда llama-server обрабатывает прошлый turn → можно получить spike в latency. Сейчас на Jetson это последовательно (sync pipeline → mic muted во время TTS, ASR ждёт unmute).

**Митигация:** `half_duplex_mute=true` (см. CLAUDE.md инвариант 5) гарантирует не пересекаться. Pre-emption через interrupt_tts работает.

### Риск 6: Sub-sentence regression при будущих изменениях (НИЗКИЙ)
Если кто-то поменяет `_SENTENCE_BOUNDARY_RE` на более агрессивную (добавит запятые) — UX упадёт, но безопасно, можно откатить.

**Митигация:** Comment в коде [System/Orchestrator.py:122-124](../System/Orchestrator.py#L122-L124) описывает принципы регекса.

---

## Решение по H4

**Не нужно дополнительной работы.** Sentence-level streaming уже реализован, измеренные TTFV (656ms warm) близки к теоретическому пределу. Любые дальнейшие оптимизации либо несут существенные UX-риски (Опция A — sub-sentence), либо дают маржинальный выигрыш не стоящий сложности (Опция B — in-process Silero).

**Рекомендация:** документировать текущее состояние как «H4 done» в RESULTS.md и сосредоточиться на нерешённых проблемах (e.g., reduce TTS playback duration через response shortening — N7 из исходного плана).

---

## Файлы (для будущих изменений)

- [System/Orchestrator.py:2261-2520](../System/Orchestrator.py#L2261-L2520) — `_stream_llm_and_speak()`
- [System/Orchestrator.py:124](../System/Orchestrator.py#L124) — `_SENTENCE_BOUNDARY_RE`
- [System/adam/inference.py:41](../System/adam/inference.py#L41) — `generate_streaming()`
- [System/Speech/TTS.py:112](../System/Speech/TTS.py#L112) — Silero `synthesize()`
