# Phase 34: ASR Quality — пустые строки и галлюцинации — Context

**Gathered:** 2026-06-09
**Status:** Ready for planning
**Source:** Debug session — events.jsonl analysis + code review

<domain>
## Phase Boundary

Две конкретные, подтверждённые проблемы распознавания речи (ASR), не связанные между собой.
Ни LLM, ни TTS, ни VAD, ни barge-in механизм не затрагиваются.

Изменения в:
- `System/Orchestrator.py` — pre-wake audio buffer + orchestrator-side hallucination guard
- `System/Speech/ASR_WhisperX.py` — расширение `_HALLUCINATION_PATTERNS`
- `System/Dockerfile.asr` + `compose.yaml` — пересборка Docker-контейнера для подхватывания кода

</domain>

<decisions>
## Implementation Decisions

### Bug 1: Пустые транскрипции после OWW (REQ-ASR-EMPTY-PREWAKE)

**Подтверждённая корневая причина:**  
`speech_frames.clear()` в `_vad_loop` (строка 1171 `System/Orchestrator.py`) при детекции wake-word обнуляет буфер речи. Пользователь говорит «адам скажи что-нибудь» единой фразой. OWW подтверждает детекцию через `debounce_hits=2` × 80 ms = 160 ms → к этому моменту «адам» уже произнесён и часть команды тоже. После очистки буфера ASR получает только хвост команды — 1–1.4 секунды тихой речи → `asr_result.empty=True`.

**Доказательство из events.jsonl (00:29:56):**
```
00:29:50  wake_word_detected  score=0.419
00:29:51  asr_partial  speech_started
00:29:53  asr_request  pcm_ms=1400          ← всего 1.4 сек аудио
00:29:56  asr_result   empty=True, raw=''
```

**Решение (D-01): Pre-wake rolling buffer**
- Добавить `_pre_wake_buf: deque[bytes]` с ограничением по времени (параметр Config.json `asr.pre_wake_buffer_ms`, default 1500 ms)
- В `_vad_loop` каждый кадр сначала попадает в `_pre_wake_buf` (обрезается по max размеру)
- При детекции wake-word: **НЕ очищать `speech_frames`**, вместо этого `speech_frames = list(_pre_wake_buf) + speech_frames`
- Очищать `_pre_wake_buf` ПОСЛЕ переноса в `speech_frames`
- Параметр `pre_wake_buffer_ms` добавить в `Config.json` + `Config.schema.json`

**Решение (D-02): Strip wake-word из ASR результата**
- После получения непустой транскрипции стриппить wake-word «адам» в начале строки (уже частично реализовано в `_transcribe_and_dispatch` — нужно проверить и убедиться что strip работает с pre-wake audio)
- Wake-words берутся из `settings.section("asr")["wake_words"]` — не хардкодить

### Bug 2: Галлюцинации ASR (REQ-ASR-HALLUCINATION)

**Подтверждённые галлюцинации из events.jsonl:**
- `raw='Спасибо за внимание.'` (23:42:25) — есть в `_HALLUCINATION_PATTERNS`, но прошла
- `raw='Компиция.'` (23:25:52) — возможно реальная речь, но похоже на галлюцинацию Whisper

**Корневая причина A (подтверждена): устаревший Docker-контейнер**  
`_HALLUCINATION_PATTERNS` добавлены в `System/Speech/ASR_WhisperX.py`, но Docker-образ не пересобирался после этого изменения. Контейнер гоняет старый код без фильтра.

**Корневая причина B: одна линия защиты**  
Фильтр только в ASR-сервисе — если сервис запущен со старым кодом или упадёт, галлюцинации попадают в оркестратор без проверки.

**Решение (D-03): Расширить `_HALLUCINATION_PATTERNS` в ASR_WhisperX.py**
- Добавить паттерны характерные для Whisper-small на русском (YouTube-субтитры, аудиомаркеры)
- Паттерн-матчинг должен быть регистронезависимым и нечувствительным к пунктуации (уже реализовано)

**Решение (D-04): Второй эшелон — orchestrator-side hallucination guard**
- В `_transcribe_and_dispatch` после получения транскрипции из ASR-сервиса добавить проверку против того же набора паттернов
- Паттерны вынести в `System/adam/asr_filter.py` (новый модуль), чтобы оба места использовали единый источник
- Возвращать пустую строку и логировать событие `asr_hallucination_filtered` если совпадение найдено

**Решение (D-05): Пересборка Docker-образа ASR**  
После исправления `ASR_WhisperX.py` пересобрать образ: `docker compose build adam-asr-whisperx && docker compose up -d adam-asr-whisperx`

### Структура волн

**Wave 1** (независимо): Pre-wake buffer fix → пустые строки  
**Wave 2** (независимо): Hallucination guard → галлюцинации  

Волны независимы — можно выполнять параллельно или последовательно.

### Config-First (инвариант проекта)

D-01 вводит новый числовой параметр → обязательно в Config.json + Config.schema.json:
```json
"asr": {
  "pre_wake_buffer_ms": 1500
}
```

### Claude's Discretion

- Точный размер `_pre_wake_buf` в фреймах (рассчитать из `pre_wake_buffer_ms / frame_ms`)
- Тип контейнера для pre-wake buf: `collections.deque(maxlen=N)` — оптимально
- Имена новых событий event_log для диагностики
- Полный список паттернов галлюцинаций для расширения

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Кодовая база — файлы с изменениями
- `System/Orchestrator.py` строки 1155–1195 — OWW trigger path + speech_frames.clear() (MUST READ перед правкой)
- `System/Orchestrator.py` строки 985–1450 — _vad_loop полностью (контекст для pre-wake buffer)
- `System/Orchestrator.py` функция `_transcribe_and_dispatch` — wake-word strip + event log
- `System/Speech/ASR_WhisperX.py` строки 44–57 — `_HALLUCINATION_PATTERNS` (MUST READ)
- `System/Speech/ASR_WhisperX.py` строки 183–200 — `_transcribe_audio` с фильтрацией

### Config
- `System/Config.json` секция `services.asr` — runtime параметры ASR (добавить `pre_wake_buffer_ms`)
- `System/Config.schema.json` секция `services.asr` — документация параметров

### Docker / деплой
- `System/Dockerfile.asr` — образ WhisperX ASR сервиса
- `compose.yaml` — секция `adam-asr-whisperx` с env vars

### Правила проекта
- `CLAUDE.md` секция "Config-First Principle" — числовые параметры только в Config.json
- `CLAUDE.md` секция "Gotchas" — порядок установки PyTorch при пересборке образа

</canonical_refs>

<specifics>
## Specific Ideas

### Pre-wake buffer (D-01) — точный механизм

```python
# В __init__ VoiceLoopController:
_pre_wake_frames = int(pre_wake_buffer_ms / frame_ms)  # e.g. 1500/20 = 75 frames
self._pre_wake_buf: deque[bytes] = deque(maxlen=_pre_wake_frames)

# В _vad_loop перед OWW processing:
self._pre_wake_buf.append(chunk)

# При triggered (OWW):
speech_frames = list(self._pre_wake_buf) + speech_frames  # prepend pre-wake
self._pre_wake_buf.clear()
# НЕ делать speech_frames.clear() здесь
```

### Hallucination patterns расширение (D-03)

Дополнить `_HALLUCINATION_PATTERNS` в ASR_WhisperX.py:
```python
# Дополнительные YouTube/учебный контент
"лайк и подписка", "колокольчик уведомлений", "смотрите также", "следующее видео",
"конец видео", "до следующего раза", "пока пока",
# Пустые/шумовые артефакты Whisper-small
"компиция", "цыц", "ля ля ля",  # типичные для тихой речи
# Технические артефакты
"[музыка]", "[аплодисменты]", "[смех]",
```

### Orchestrator-side filter (D-04)

Минимальная реализация в `_transcribe_and_dispatch`:
```python
# После получения transcript от ASR:
from adam.asr_filter import is_hallucination
if is_hallucination(transcript):
    event_log.append("asr_hallucination_filtered", {"raw": transcript})
    transcript = ""
```

</specifics>

<deferred>
## Deferred Ideas

- Confidence score threshold из Whisper — хорошая идея, но требует парсинга `avg_logprob` на стороне оркестратора через отдельный ASR API endpoint; отложить в Phase N+
- Языковая детекция (отклонять non-ru транскрипции) — сложнее, риск ложных срабатываний
- pre_wake_buffer_ms = 0 как способ отключить (пусть останется минимум 400ms)

</deferred>

---

*Phase: 34-asr-quality-fixes*
*Context gathered: 2026-06-09 via debug session (events.jsonl + code review)*
