# Action Mapping — AIIM-состояние → сцена флоры

> Документ для разработчика action layer, не для агента. Не идёт в prompt.

## Принцип

Action layer выбирает сцену моторики **по текущему AIIM-состоянию**, не по явной инструкции в LLM-ответе. Это соблюдает CLAUDE.md: «LLM отвечает чистым русским текстом», «action layer отдельно от голосового ответа».

LLM **никогда** не пишет «сейчас сцена interest». Сцена включается из оркестратора на основе наблюдаемого профиля.

## Маппинг

| Сцена флоры | AIIM-сигнатура | Внешний триггер | Endpoint MCU |
|--------------|----------------|-----------------|--------------|
| `idle` (спокойствие, дыхание) | `Pa-Or` фон, `em` < 0.4 | базовая линия — никого нет, нейтральный диалог | `POST /api/pca9685/scene name=idle` |
| `interest` (интерес) | `Ac-Or` по `at`+`pe` | новое лицо в кадре, новый вопрос, провокативная тема | `POST /api/pca9685/scene name=interest` |
| `warm` (расположение) | `Pa-Or` + краткий `Ac` по `lo` | искренний или уязвимый собеседник, откровенная тема | `POST /api/pca9685/scene name=warm` |
| `unease` (беспокойство) | `Ac-Ch` всплеск `em`+`pe` | резкий шум, агрессия, перегрузка одновременных стимулов | `POST /api/pca9685/scene name=unease` |
| `silence` (молчание) | `Pa-Ch` по `em`, минимум `be` | долгая пауза, тишина в зале, медитативный момент | `POST /api/pca9685/scene name=silence` |

## Как оркестратор определяет состояние

Состояние — функция нескольких сигналов:

| Сигнал | Источник | Влияет на |
|--------|----------|-----------|
| Лицо в кадре (новое/удержание/потеря) | scene_text от VLM, события `face_*` | `at`, `pe` |
| Длительность речи зрителя | ASR события | `em` (короткая → нейтрально, длинная и эмоциональная → возбуждение) |
| Тон зрителя (curious/hostile/sad/playful) | анализ transcript (rule-based + lexical) | `em`, `lo` |
| Тишина / шум | VAD события | `em` (`Pa-Ch` если тихо), `pe` (overload если шумно) |
| Тема диалога | tags из echoes_gate | `im`, `sp` |
| Несколько человек одновременно | scene_text «multiple_faces» | `at` Δ↑, `be` Δ↓ |

## Cooldown и sustain

Без ограничений сцена будет дёргаться каждые несколько секунд на любую микро-эмоцию. Правила:

- **Sustain:** сцена держится минимум 8 секунд после переключения, даже если состояние изменилось
- **Cooldown между сменами:** не чаще раза в 5 секунд
- **Hysteresis:** для возврата из `interest` → `idle` нужна подтверждённая нейтральность 15+ секунд
- **Override:** `unease` имеет приоритет — переключается мгновенно, минуя cooldown
- **Manual override:** оператор через WebUI может зафиксировать любую сцену (overrides до явного снятия)

## API для action layer

Внутренний модуль (Python, в `System/adam/action.py` или новый `scene_director.py`):

```python
class SceneDirector:
    def evaluate(self, signals: SignalSnapshot, current_aiim: AIIMState) -> Optional[Scene]:
        """Возвращает новую сцену или None (продолжить текущую)."""

    async def apply(self, scene: Scene) -> None:
        """Отправляет команду на MCU через device.py HTTP клиент."""
```

`SignalSnapshot` — pydantic-объект с полями выше (face_state, vad_state, tone, themes...).

`AIIMState` — текущая раскладка `Ac/Pa × Or/Ch` по аспектам, считается `inference.py`.

## Связь с echoes_gate

Echoes имеют поле `mood_block: [hostile, overload]`. Эти строки соответствуют **внешним триггерам**, не сценам. Соответствие:

| `mood_block` метка | Когда срабатывает |
|---------------------|--------------------|
| `hostile` | scene == `unease` от агрессии (не от шума) |
| `overload` | scene == `unease` от шума/одновременных стимулов |
| `silence_deep` | scene == `silence` дольше 30 секунд |

Gate Echoes/Chinese читает текущий `mood` (отдельный поле в SignalSnapshot, не путать с AIIM-состоянием) и отсеивает фрагменты, у которых это значение в `mood_block`.

## TODO при имплементации

- Реализовать `SceneDirector` в `System/adam/scene_director.py`
- Добавить `mood` поле в SignalSnapshot (вычисляется из face/vad/tone)
- Sustain/cooldown — параметры в `Tuning.json → action`
- Тесты: unit-тест на маппинг, e2e — синтетические сигналы → ожидаемая последовательность POST на MCU
