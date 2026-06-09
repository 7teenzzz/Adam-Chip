# Phase 35 — Wave 2 Evidence (Voice E2E)

**Run:** 2026-06-09 | **Branch:** ultimate-integration @ b9af258 | **Mode:** exhibition
**Power gate:** MAXN ✓  `clocks_ok=true` ✓  `exhibition_gate.ok=true` ✓
**TTS output:** esp32_speaker (10.10.10.171:82) | **Mic:** local USB (pulse)

---

## Пункт 1 — Пробуждение + простой вопрос ✅

**Фраза:** «Адам, который час?»
**turn_id:** `44a7c67d`  **Время:** 09:56:45 local (06:56:45 UTC)

| Stage | Latency | Событие |
|-------|---------|---------|
| wake_word_detected | 06:56:33 | OWW сработал (→ listening) |
| ASR | 597 ms | transcript: "Адон, который час" (фонетика «Адам»→«Адон» — норма для ASR) |
| LLM | 3434 ms | |
| TTS | 4678 ms | tts_started → tts_finished |
| TOTAL | 7399 ms | |

**Reply:** «Я не отслеживаю время в привычном смысле. Что вас интересует в моменте?»
**ESP sound:** оператор подтвердил ✅
**Memory:** dialogue_turns +2 ✓ (chain: oww→asr→llm→tts→adam_reply)

---

## Пункт 2 — Пробуждение + открытый вопрос ✅

**Фраза:** «Адам, расскажи о себе» (×2 попытки)
**turn_id 1:** `6d5bad63`  09:57:11 local
**turn_id 2:** `6b766cbc`  09:57:25 local

| turn_id | ASR | LLM | TTS | TOTAL |
|---------|-----|-----|-----|-------|
| 6d5bad63 | 553 ms | 11318 ms | 17388 ms | 19915 ms |
| 6b766cbc | 518 ms | 3350 ms | 6038 ms | 8066 ms |

**Reply 6d5bad63:** «Я здесь, и я существую в этой точке...»
**Reply 6b766cbc:** «Я не буду повторяться. Вы хотите знать что-то конкретное...»
**ESP sound:** оператор подтвердил ✅
**Chain:** oww→asr→llm→tts→adam_reply на обоих поворотах ✓

---

## Пункт 3 — Barge-in ❌

**Фраза:** «Адам, расскажи длинную историю»
**turn_id:** `93e51708`  09:57:59 local

| Stage | Результат |
|-------|-----------|
| wake_word_detected | 06:57:35 UTC ✓ |
| ASR | 568 ms, transcript: "расскажи длинную историю." |
| LLM | 9089 ms |
| TTS | **18518 ms** — играл ~18.5с без прерывания |
| barge_in_monitor | Активен: 06:57:42–06:57:59 (весь TTS) |
| barge_in_score | max=0.0010, min=0.0008, mean=0.0009 (threshold=0.01) |
| barge_in_hit | **НЕ ПОЯВИЛСЯ** |

**Оператор:** несколько попыток сказать «Адам» во время TTS → Адам не прервался.

**Root cause:** Акустическая обратная связь. TTS играет через ESP PCM5102A в помещении; USB-микрофон подхватывает звук из динамика (barge_in_audio_rms mean=3591). OWW получает смесь голоса пользователя + реверб TTS → score 0.0009 (в 10 раз ниже порога). AEC (Acoustic Echo Cancellation) между ESP-динамиком и local USB-mic отсутствует.

**Wave-4 defect D-BI-01:** Barge-in не работает при mic_source=local + ESP speaker — требует AEC или альтернативного решения.

---

## Пункт 4 — Silence keyword «стоп» ❌

**Фраза:** «Адам, что ты думаешь о времени?» → «стоп»
**turn_id:** `c889e66b`  10:01:15 local

| Stage | Результат |
|-------|-----------|
| ASR | 570 ms, transcript: "что ты думаешь о времени?" |
| TTS | 9189 ms (tts_finished в 07:01:15 UTC) |
| REPLY окно | 5с → voice_state_change → standby в 07:01:20 UTC |
| silence_keyword triggered | **Нет** |

Следующий поворот `444a142f` ("как тебе дела?") в 10:01:55 — через **40 секунд** после завершения `c889e66b`. Это новый wake+command, не REPLY. Вывод: «стоп» был произнесён после закрытия REPLY-окна (5с) или не был захвачен ASR в это окно.

**Root cause:** REPLY-окно 5с — слишком короткое для ручного теста: после 9с TTS оператор физически не успевает произнести «стоп» в требуемый момент. Плюс «стоп» как wake+command требует работающего OWW после TTS (та же barge-in проблема).

**Wave-4 defect D-SK-01:** silence_keyword «стоп» в REPLY-режиме не проверен (окно закрылось до фразы). Нужен повторный тест с явным «Адам, стоп» (wake + ключевое слово).

---

## Итоговая таблица

| Пункт | Результат | ESP звук | turn_id |
|-------|-----------|----------|---------|
| 1. Который час | ✅ GREEN | ✅ ok | 44a7c67d |
| 2. Расскажи о себе | ✅ GREEN | ✅ ok | 6d5bad63, 6b766cbc |
| 3. Barge-in | ❌ FAIL → Wave 4 | — | 93e51708 |
| 4. Silence «стоп» | ❌ FAIL → Wave 4 | — | c889e66b |

**REQ-INT-VOICE-E2E PARTIAL:** Основной голосовой тракт (wake→ASR→LLM→TTS→ESP speaker) работает на реальном железе. Barge-in и silence keyword требуют отдельного разбора в Wave 4.

---

## Дополнительные повороты после теста

Пайплайн продолжил работу без рестарта:
- `444a142f` — «как тебе дела?» → «Тихо тут сегодня.» (3256ms total)
- `51919760` — «привет, как дела?...» → ответ (6289ms total)
- `de293925` — «Шучу.» → ответ (6842ms total)
