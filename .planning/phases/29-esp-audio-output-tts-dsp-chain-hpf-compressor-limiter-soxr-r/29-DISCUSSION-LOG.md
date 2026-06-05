# Phase 29: ESP Audio Output — TTS DSP chain - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 29-esp-audio-output-tts-dsp-chain
**Areas discussed:** Этапность внедрения, Характер громкости, Стабильность уровня, Presence-EQ

---

## Этапность внедрения

| Option | Description | Selected |
|--------|-------------|----------|
| 2 плана, слушать между | Этап A (HPF + soxr + лимитер + норм.) → послушать → Этап B (компрессор + makeup + presence). Два коммита. | ✓ |
| Один план, компрессор off | Вся цепочка в одном плане, агрессивные части off-by-default | |
| Всё сразу | Вся цепочка enabled, тюнинг hot-reload потом | |

**User's choice:** 2 плана, слушать между.
**Notes:** Этап A — enabled по умолчанию при лендинге (второй вопрос): безопасные части (HPF + soxr + лимитер + makeup) только улучшают, гарантия нуля клиппинга.

---

## Характер громкости

| Option | Description | Selected |
|--------|-------------|----------|
| Мягко/естественно | Лёгкая компрессия ratio ~2:1, soft knee, сохранить живость | ✓ |
| Агрессивно/broadcast | ratio ~4:1+, плотный звук, макс громкость, больше окраски | |

**User's choice:** Мягко/естественно.
**Notes:** Можно поднять hot-reload'ом, если на 3.3 В не хватит громкости.

---

## Стабильность уровня

| Option | Description | Selected |
|--------|-------------|----------|
| Фикс-порог/gain | Фиксированный порог + makeup, без пофразной нормализации. Сохраняет динамику, без накачки. | ✓ |
| Нормализация каждой фразы | Каждая фраза к целевому пику отдельно. Риск пыхтения между фразами. | |

**User's choice:** Фикс-порог/gain.
**Notes:** Следствие — в Этапе A пик-нормализация заменена на фикс makeup + лимитер.

---

## Presence-EQ

| Option | Description | Selected |
|--------|-------------|----------|
| Включить в Этап B | Лёгкий +2–3 дБ ~3 кГц, разборчивость на мелких динамиках, toggle | ✓ |
| Отложить (deferred) | Держать цепочку минимальной | |

**User's choice:** Включить в Этап B.

---

## Claude's Discretion

- Точные дефолтные значения всех DSP-параметров (HPF ~180 Гц, порог/attack/release компрессора, makeup дБ, лимитер ~−1 dBFS, presence-EQ freq/Q/gain) — консервативно, далее на слух. Всё в Config.json.
- Структура ключей в Config.json и реализация soxr-замены `audioop.ratecv`.

## Deferred Ideas

- Миграция питания усилителей на 5 В (реальный потолок громкости — железо).
- Firmware speaker → 48 кГц (чистый ×2 апсемпл из 24k).
- Агрессивная компрессия как hot-reload тюнинг, если мягкой мало.
- Reviewed todo (не folded): `fix-esp32-stream-drain-during-mute.md` — про mic-mute drain, вне scope.
