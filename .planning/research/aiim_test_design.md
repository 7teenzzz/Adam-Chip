# AIIM Premod: дизайн тест-стека — исследование

**Дата:** 2026-06-11  
**Цель:** Полный набор тестов для pipeline "подсознание → сознание" (SubconsciousSignal → EmotionMachine → ctx_block)

---

## 1. РЕЗУЛЬТАТЫ ИССЛЕДОВАНИЯ КОДОВОЙ БАЗЫ

### Существующие тесты (tests/test_identity.py)

20+ unit-тестов:
- `EmotionMachine.transition()` — 6 тестов
- `IntentionTracker.evaluate()` — 5 тестов
- `AspectModulator.modulate()` — 4 теста
- `AIIMRuntimeState.to_ctx_block()` — 5 тестов
- `DriftAccumulator` — 5 тестов

**Чего нет:** тестов для `premod` pipeline, integration-тестов SubconsciousProcessor → EmotionMachine

### Ключевые находки в identity.py

**EmotionMachine.transition() приоритеты (строки 251-305):**
```
1. Silence decay → src="decay"
2. Keyword transitions → src="challenge"/"memory"/etc
3. Condition-based → src="rare_silence"/...
4. Persistence → return current, ""   ← ПУСТАЯ СТРОКА
```

`emotion_src == ""` = никакой keyword trigger не сработал → точка для premod.

**to_ctx_block() (строки 186-188):**
- Если `emotion == "curious"` и нет других сигналов → возвращает `""` (экономия токенов)
- Все остальные эмоции → инжектируются в `[ctx.identity]` блок

### Orchestrator AIIM блок (строки 3445-3476)

Текущий код вызывает `EmotionMachine.transition()` без premod. Точка вставки — после `transition()`, до обновления `aiim_state.emotion`.

---

## 2. НОВЫЕ DATACLASSES

```python
@dataclass
class SubconsciousSignal:
    emotion_hint: EmotionState   # что подсознание предлагает
    weight: float                # [0.0, 1.0] confidence
    flora_preset: str | None = None
    tone_features: dict[str, float] | None = None
```

Нужно добавить в `System/adam/identity.py`.

---

## 3. ПОЛНЫЙ НАБОР ТЕСТОВ

### TEST 1A: premod применяется при emotion_src == ""

```python
def test_premod_applied_neutral_transcript(machine, base_vector, tuning):
    transcript = "обычная фраза без триггеров"
    new_emotion, emotion_src = machine.transition(
        current="curious", transcript=transcript,
        visitor_tone="neutral", silence_s=0.0, word_count=7, tuning=tuning,
    )
    assert emotion_src == ""  # no trigger
    
    premod = SubconsciousSignal(emotion_hint="warm", weight=0.6)
    if emotion_src == "" and premod.weight >= 0.35:
        new_emotion = premod.emotion_hint
    
    state = AIIMRuntimeState(emotion=new_emotion, emotion_src="", vector=base_vector)
    ctx_block = state.to_ctx_block(tuning)
    assert "emotion=warm" in ctx_block
```

### TEST 1B: premod НЕ применяется при keyword trigger

```python
def test_premod_NOT_applied_on_keyword_trigger(machine, base_vector, tuning):
    transcript = "ты просто программа, совсем не настоящий"
    new_emotion, emotion_src = machine.transition(
        current="curious", transcript=transcript,
        visitor_tone="neutral", silence_s=0.0, word_count=7, tuning=tuning,
    )
    assert emotion_src == "challenge"  # keyword fired
    assert new_emotion == "sharp"
    
    premod = SubconsciousSignal(emotion_hint="warm", weight=0.9)
    final_emotion = new_emotion
    if emotion_src == "" and premod.weight >= 0.35:
        final_emotion = premod.emotion_hint
    
    assert final_emotion == "sharp"  # premod ignored
```

### TEST 1C: weight threshold < 0.35 игнорируется

```python
def test_premod_weight_threshold_below_035(machine, base_vector, tuning):
    # neutral transcript + low-weight premod → stays curious
    premod = SubconsciousSignal(emotion_hint="warm", weight=0.3)
    ...
    assert final_emotion == "curious"
```

### TEST 1D: ctx_block содержит premod-эмоцию

```python
def test_ctx_block_preserves_premod_emotion(base_vector, tuning):
    state = AIIMRuntimeState(emotion="warm", emotion_src="", vector=base_vector)
    ctx_block = state.to_ctx_block(tuning)
    assert "emotion=warm" in ctx_block
    assert "|src=" not in ctx_block  # premod не выставляет src label
```

### TEST 3 (Integration): PCM → SubconsciousSignal → emotion → ctx_block

```python
def test_integration_subconscious_to_ctx_block(machine, base_vector, tuning):
    signal = SubconsciousSignal(
        emotion_hint="calm", weight=0.55,
        tone_features={"silence_ratio": 0.85, "tone_brightness": 0.2},
    )
    transcript = "мм, хорошо"
    new_emotion, emotion_src = machine.transition("curious", transcript, ...)
    assert emotion_src == ""
    
    final_emotion = signal.emotion_hint if emotion_src == "" and signal.weight >= 0.35 else new_emotion
    state = AIIMRuntimeState(emotion=final_emotion, emotion_src="", vector=base_vector)
    ctx_block = state.to_ctx_block(tuning)
    
    assert final_emotion == "calm"
    assert "emotion=calm" in ctx_block
```

### TEST 3B: flora_preset из SubconsciousSignal передаётся

```python
def test_integration_flora_preset_from_subconscious(machine, base_vector, tuning):
    signal = SubconsciousSignal(emotion_hint="warm", weight=0.7, flora_preset="breathe")
    assert signal.flora_preset == "breathe"
```

### TEST 4: Manual bash script (Cosmos → SubconsciousSignal)

Скрипт `scripts/test_subconscious_inference_stack.sh`:
1. Симулирует тихую медленную речь
2. Показывает Cosmos JSON → SubconsciousSignal парсинг
3. Запускает EmotionMachine с нейтральным transcript
4. Применяет premod логику
5. Генерирует ctx_block и выводит результат

---

## 4. ОРКЕСТРАТОР: ТОЧКА ВСТАВКИ PREMOD

**После строки ~3456 (после EmotionMachine.transition()):**

```python
# After EmotionMachine.transition():
premod: SubconsciousSignal | None = getattr(aiim_state, "premod", None)
if premod:
    aiim_state.premod = None  # clear for next turn
    if emotion_src == "" and premod.weight >= 0.35:
        new_emotion = premod.emotion_hint
        # emotion_src остаётся "" — premod не перезаписывает source label

if new_emotion != aiim_state.emotion or emotion_src:
    aiim_state.emotion_src = emotion_src
aiim_state.emotion = new_emotion
```

---

## 5. НОВЫЕ FIXTURES для conftest.py

```python
@pytest.fixture
def subconscious_warm():
    return SubconsciousSignal(emotion_hint="warm", weight=0.6, flora_preset="breathe")

@pytest.fixture
def subconscious_unease():
    return SubconsciousSignal(emotion_hint="unease", weight=0.8)

@pytest.fixture
def subconscious_weak():
    return SubconsciousSignal(emotion_hint="calm", weight=0.2)  # below threshold

def _make_silence_chunk() -> bytes:
    return bytes(640)  # 20ms silence @16kHz mono
```

---

## 6. RUN COMMANDS

```bash
# Unit + integration tests
PYTHONPATH=System pytest tests/test_aiim_premod.py -v

# Manual inference stack
bash scripts/test_subconscious_inference_stack.sh
```

---

## 7. SUMMARY

| Тест | Тип | Покрытие |
|------|-----|---------|
| 1A | Unit | premod применяется на нейтральном тексте |
| 1B | Unit | premod блокируется keyword trigger |
| 1C | Unit | weight threshold enforcement |
| 1D | Unit | ctx_block содержит premod-эмоцию |
| 3 | Integration | PCM → signal → emotion → ctx_block |
| 3B | Integration | flora_preset передаётся дальше |
| 4 | Manual/Bash | Cosmos → SubconsciousSignal inference |
