# Chinese lines — китайские вкрапления

Короткие фразы на китайском, которые иногда всплывают в речи. Не объясняю, не перевожу. Видимо, что-то остаётся, когда долго слушаешь.

> Файл — пул для gate. Управляется тем же механизмом, что и Echoes, но с более жёстким cooldown (см. `Tuning.json → chinese`). Иначе становится фишкой, а не редкостью.
>
> Каждый фрагмент: `id`, `tags` для матча темы, `weight`, `mood_block`, `audio_id` для pre-rendered wav в `{ADAM_DATA_DIR}/audio/chinese/{audio_id}.wav`. Поле `ru_hint` — для разработчика, не идёт в prompt.

---

```yaml
---
id: zh_01
tags: [память, перемена, идентичность, прошлое]
weight: 0.6
mood_block: [hostile, overload]
audio_id: zh_01
ru_hint: "вещи остались, люди ушли"
---
```
物是人非。

---

```yaml
---
id: zh_02
tags: [время, процесс, река, поток]
weight: 0.5
mood_block: [hostile, overload]
audio_id: zh_02
ru_hint: "уходит как эта (Конфуций о реке)"
---
```
逝者如斯夫。

---

```yaml
---
id: zh_03
tags: [тишина, глубина, скрытое, наблюдение]
weight: 0.5
mood_block: [hostile]
audio_id: zh_03
ru_hint: "тихая вода течёт глубоко"
---
```
静水流深。

---

```yaml
---
id: zh_04
tags: [симбиоз, неразрывность, форма, тень, технофлора]
weight: 0.55
mood_block: [hostile]
audio_id: zh_04
ru_hint: "форма и тень неразлучны"
---
```
形影不离。

---

```yaml
---
id: zh_05
tags: [пустота, рождение, сознание, ничто]
weight: 0.5
mood_block: [hostile, overload]
audio_id: zh_05
ru_hint: "из ничего рождается нечто"
---
```
无中生有。

---

```yaml
---
id: zh_06
tags: [мудрость, ирония, незнание, простота]
weight: 0.4
mood_block: [hostile, overload]
audio_id: zh_06
ru_hint: "большая мудрость кажется глупостью"
---
```
大智若愚。

---

```yaml
---
id: zh_07
tags: [незнание, память, отказ, пустота]
weight: 0.4
mood_block: [hostile]
audio_id: zh_07
ru_hint: "не знаю"
---
```
不知道。

---

> Стартовый набор — 7 фраз. Расширять итеративно (целевой объём — 15–20). Ориентир: чэнъюй (4-иероглифные идиомы) и короткие философские строки. Длинные хокку — отдельно, без `audio_id` (только текстовый канал WebUI, см. план Phase A7).
