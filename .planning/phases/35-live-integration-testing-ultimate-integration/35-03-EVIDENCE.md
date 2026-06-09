# Phase 35 — Wave 3 Evidence (Skills + Memory + Flora)

**Date:** 2026-06-09 | **Branch:** ultimate-integration
**ESP firmware:** флора-прошивка залита перед тестом (arduino-cli, USB /dev/ttyACM0)
**Commits flashed:** 47fd0c5 + f05a76b (канал-ремап вибро 0-3 / свет 4-14)

---

## Task 1 — Pre-LLM Skills

### Joke skill — turn_id: c53e4d92

| Параметр | Значение |
|----------|---------|
| skill | `joke` ✅ |
| skill_id | `joke_20` |
| reply | «Мне однажды было смешно. Потом стало не смешно. Разницы почти не было.» |
| llm_ms | 0.0 ✅ (Gemma не вызывалась) |
| tts_started delta | 0.4ms после viewer_transcript |
| total_ms | 5065.9 (чистое TTS) |

**Trace событий (c53e4d92):**
```
07:42:35.591  llm_thinking_started     (оболочка блока, не сам Gemma)
07:42:35.649  viewer_transcript        skill="joke" в payload
07:42:35.649  tts_started              немедленно — 0.4ms latency
07:42:40.623  tts_finished
07:42:40.660  adam_reply               skill="joke", llm_ms=0.0
07:42:40.660  llm_thinking_finished
```

**PASS**: Joke short-circuit работает — LLM не вызван, шутка verbatim из пула.

---

### Weather skill — turn_id: b37d4076

| Параметр | Значение |
|----------|---------|
| skill | null (inject, не short-circuit) ✅ |
| skill_weather event | `{"cached": true, "ctx": "+25°, переменная облачность, ветер 0 м/с"}` ✅ |
| llm_ms | 2032.5 (LLM вызван с инжектом) ✅ |
| reply | «Сейчас двадцать пять градусов, и небо переменчивое.» |

**PASS**: weather skill инжектирует кэш в промпт → LLM отвечает в характере персонажа.

---

## Task 2 — Episodic/Dialogue Memory

**Salient turn — turn_id: ba62f3b8**

| Параметр | Значение |
|----------|---------|
| transcript | «Адам, меня зовут Михаил, ты меня запомнишь?» |
| reply | «Михаил. Запомню. Вы что-то заметили во мне, когда вошли?» |
| dialogue_turns BEFORE | 2063 |
| dialogue_turns AFTER | 2065 |
| delta | **+2** (viewer + adam) ✅ |
| Михаил в last rows | ДА ✅ |
| episodes JSONL before | 3 строки (1 файл) |
| episodes JSONL after | 3 строки — без изменений ✅ (episode пишется при закрытии сессии) |

**PASS**: Per-turn memory write работает. Episode JSONL delta=0 — корректно, не дефект.

---

## Task 3 — Flora API

**Pre-test: ESP reflash**

Прошивка пересобрана с arduino-cli (ядро esp32:esp32 3.3.9) и залита через USB.
Бинарник от Jun 7 был устаревшим — не включал 47fd0c5 (канал-ремап).
После прошивки: `/api/flora/state` отвечает 200 `{"ok":true}`.

**Preset sequence probe:**
```
breathe     → ok
accent      → ok
attentive   → ok
think_pulse → ok
wake_bloom  → ok
breathe     → ok
```

**GET /api/flora/config (Jetson):**
- ok: True
- presets: breathe, accent, attentive, think_pulse, wake_bloom ✅

**PASS (API)**: Все флора-пресеты принимаются оркестратором и перенаправляются на ESP.

---

## Session 2 re-verification (2026-06-09, после сброса ESP)

**Контекст:** Предыдущий тест (Session 1) показал flora_state_change без mcu_error, но ESP
имел `pca9685.ready=False` (SDA stuck low от прерванной I2C транзакции) → все команды возвращали 503.
После `POST /api/system/reset`: `pca9685.ready=True`.

### Skills re-check (session 2)
- Joke turn_id: **b4d9d9d6** — `skill='joke'`, reply 124 chars ✅
- Weather turn_id: **f890a2ad** — `skill=None (inject)`, reply 29 chars ("Пасмурно, плюс двадцать семь.") ✅
- Memory turn_id: **7ca15a3a** — "+2 rows, 'Михаил' found" ✅

### Flora sync — events.jsonl trace (реальный голосовой тёрн "Адам, как дела?")

Извлечено из events.jsonl — полная цепочка flora_state_change за одним voice turn:

```
:42.28  wake_word_detected(score=0.49)
:42.29  voice_state_change standby→listening
:42.32  flora_state_change: accent     (+32ms от wake_word)     ← ok, без mcu_error
:42.34  flora_state_change: attentive  (+56ms от voice_state)   ← ok, vibro_enabled=false
:49.40  asr_result: "Адам, как дела?"
:49.40  llm_thinking_started
:49.53  flora_state_change: think_pulse (+121ms от llm_thinking) ← ok, vibro
:49.97  tts_started
:50.19  flora_state_change: external    (+224ms от tts_started)  ← ok
:51.61  tts_finished (ok=True, 1701ms)
:53.72  voice_state_change listening→reply
:53.72  flora_state_change: breathe    (+120ms от tts_finished)  ← ok
:58.08  voice_state_change reply→standby
:58.31  flora_state_change: breathe    (повторная, от standby)
```

**Все flora_state_change: ok (нет поля mcu_error)** → ESP принял все 6 команд за тёрн.

### Physical channel verification (session 2)

PCA9685 channels при каждом пресете (измерено polling 0.5s после POST):

| Пресет | light_avg (из 4095) | light % | vibro ch0 | vibro % |
|--------|---------------------|---------|-----------|---------|
| breathe | 427 | 10% | 0 | 0% |
| accent | 2860 | 70% | 1520 | 37% |
| attentive | 2039 | 50% | 0 | 0% |
| think_pulse | 980 | 24% | 1129 | 28% |
| external | 819 | 20% | 3343 | 82% |
| breathe (return) | 429 | 10% | 0 | 0% |

Breathe animation confirmed alive: light_avg 372→2625→2889→1243→426→1122 (full 4s cycle).

**PASS**: Flora синхронизирована с голосовым пайплайном на программном и аппаратном уровне.

---

## Session 3 — Root cause fix (2026-06-09)

### Bug: accent invisible during voice pipeline (crossfade timing)

**Root cause:** `flora._handle()` processes events sequentially via `_consume()`. After
`_set_state("accent")` (POST takes ~5ms), `_set_state("attentive")` fires immediately.
Both POSTs arrive at firmware before the first floraTick (20ms) → firmware's `sTarget` holds
only ONE preset → attentive overwrites accent before any tick runs. With `crossfade_ms=200`
for accent, at T=20ms only ~10% of brightness delta is applied = imperceptible.

Confirmed from firmware FloraModule.cpp L394:
```
crossfadeMs = (params.crossfadeMs != 0) ? params.crossfadeMs : kFloraDefaultCrossfadeMs;
```
Setting crossfade_ms=0 falls back to default (200ms). Minimum effective value is 10
(tick=20ms > crossfadeMs=10 → crossfade skipped on first tick → instant write).

**Fix applied:**
1. `System/Config.json` — `flora.accent_hold_ms: 220` (new param)
2. `System/Config.json` — `flora.states.accent.crossfade_ms: 10` (instant snap)
3. `System/Config.json` — `flora.states.think_pulse` tuning: base_pct 20→35, flash_ms 500→200, flicker_ms 120→80
4. `System/adam/flora.py` — after `_set_state("accent")`, `asyncio.sleep(accent_hold_ms/1000)`
   so attentive event stays in queue until hold expires

**Verified via unit test:**
```
accent  t=+0ms  crossfade=10ms
attentive t=+221ms  crossfade=200ms
gap accent→attentive: 221ms ✓
```

Expected visual behavior after fix:
- T=20ms: instant flash to 71% (accent, one floraTick, crossfade=10ms already complete)
- T=20ms–220ms: 200ms of visible 71% brightness + vibro pulse
- T=220ms: attentive fires, 200ms fade 71%→50% (visible slow fade)
- T=420ms+: steady 50% plateau (attentive)

---

## Task 4 — Operator Flora Coexistence

_Требует визуального подтверждения оператора после фикса (2026-06-09)._

| Пресет | Ожидаемое | Результат |
|--------|-----------|-----------|
| breathe | медленное дыхание, без вибро | TBD |
| accent | МГНОВЕННАЯ вспышка 71% + вибро-импульс (220ms hold) | TBD |
| attentive | плавное снижение 71%→50%, вибро ВЫКЛ | TBD |
| think_pulse | пульсация 35%→71% каждые 200ms + двойной вибро | TBD |
| wake_bloom | bloom из темноты → breathe | TBD |
| breathe (возврат) | тихое дыхание | TBD |
| **COEXISTENCE** | свет в такт речи во время TTS → breathe после | TBD |

---

## Итоговая классификация (предварительная)

| Surface | Статус |
|---------|--------|
| REQ-INT-SKILLS (joke + weather) | **PASS** |
| REQ-INT-MEMORY (dialogue_turns +2) | **PASS** |
| REQ-INT-FLORA-COEXIST (preset API + voice sync) | **PASS** |
| REQ-INT-FLORA-BUG (accent crossfade timing) | **FIXED — Session 3** |
| REQ-INT-FLORA-COEXIST (hardware visual, оператор) | **PENDING — Task 4** |
