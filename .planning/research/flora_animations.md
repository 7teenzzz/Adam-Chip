# Технофлора: анимации для всех эмоций — исследование

**Дата:** 2026-06-11  
**Цель:** 10 новых анимационных пресетов (5 эмоций × 2 варианта) + модулируемые параметры от SubconsciousSignal

---

## 1. СУЩЕСТВУЮЩАЯ СИСТЕМА (5 пресетов)

| Пресет | base% | peak% | period_ms | vibro |
|--------|-------|-------|-----------|-------|
| breathe | 7 | 40 | 4000 | OFF |
| accent | 10 | 71 | 1400 | ON (pulse 120ms) |
| attentive | 30 | 71 | 450 (wave) | OFF (D-11) |
| think_pulse | 35 | 71 | random | double_pulse |
| wake_bloom | 0→71 | 71 | 3000 (one-shot) | ON |

Все параметры отправляются с Jetson на ESP32-S3 через `POST /api/flora/state` в виде `FloraParams`.

---

## 2. GAP: AIIM ЭМОЦИИ НЕ ВЛИЯЮТ НА ФЛОРУ

Система определяет 5 эмоций в `identity.py`: `curious`, `warm`, `unease`, `sharp`, `calm`.  
Они вычисляются в `AIIMRuntimeState`, но **НЕ маппируются на flora presets** — только pipeline-события (wake word, listening, thinking) двигают анимации.

---

## 3. НОВЫЕ ПРЕСЕТЫ (10 штук)

### Любопытство (curious)

**curious_a** — стандартное:
- base: 15%, peak: 55%, period: 2800ms
- Умеренное мерцание, spark_probability: 0.25
- vibro: OFF

**curious_b** — интенсивное:
- base: 20%, peak: 65%, period: 1800ms
- Частое мерцание, spark_probability: 0.40
- vibro: тихий continuous hum

### Тепло (warm)

**warm_a** — тихое:
- base: 25%, peak: 50%, period: 5000ms
- Медленное дыхание, smooth sine
- vibro: OFF

**warm_b** — насыщенное:
- base: 30%, peak: 60%, period: 3500ms
- Медленное дыхание + мягкий vibro на 80% intensity
- vibro: ON soft

### Тревога (unease)

**unease_a** — лёгкое беспокойство:
- base: 10%, peak: 60%, period: 1200ms
- Irregular flashes (jitter 40%), средний vibro
- vibro: ON medium

**unease_b** — сильная тревога:
- base: 5%, peak: 71%, period: 600ms
- Chaotic rapid flashes (jitter 80%), сильный vibro
- vibro: ON intense

### Острота (sharp)

**sharp_a** — сосредоточенность:
- base: 20%, peak: 71%, period: 1600ms
- Quick attack 60ms, synchronized vibro pulse
- vibro: ON sync

**sharp_b** — очень острый:
- base: 15%, peak: 71%, period: 800ms
- Very quick attack 30ms, intense synchronized vibro
- vibro: ON intense sync

### Спокойствие (calm)

**calm_a** — умиротворённость:
- base: 35%, peak: 45%, period: 6000ms
- Почти статичный, minimal pulsation (range 10%)
- vibro: OFF

**calm_b** — глубокий покой:
- base: 40%, peak: 55%, period: 4500ms
- Очень медленное дыхание, wide soft range
- vibro: OFF

---

## 4. МОДУЛИРУЕМЫЕ ПАРАМЕТРЫ ОТ ПОДСОЗНАНИЯ

Каждая эмоция получает набор параметров, которые SubconsciousSignal может варьировать:

| Эмоция | Параметры |
|--------|-----------|
| curious | `intensity` (0.0-1.0), `tempo` (0.5-2.0), `regularity` (spark chaos) |
| warm | `intensity`, `tempo`, `tenderness` (vibro amplitude %) |
| unease | `intensity`, `tempo`, `jitter` (0.0-1.0), `vibro_intensity` |
| sharp | `intensity`, `tempo`, `focus` (attack ms), `vibro_sync` (bool) |
| calm | `intensity`, `tempo`, `stillness` (range compression ratio) |

**Формула модуляции для `intensity`:**

```
effective_peak = base_peak + (max_peak - base_peak) * intensity
effective_period = base_period / tempo
effective_jitter = base_jitter * jitter_mod
```

---

## 5. FIRMWARE: НОВЫЕ ПОЛЯ FloraParams

Текущая структура (ESP32):
```c
struct FloraParams {
    uint8_t preset;       // enum FloraPreset
    uint8_t baseDuty;     // 0-255
    uint8_t peakDuty;     // 0-255
    uint16_t periodMs;    // period
    bool vibroEnabled;
};
```

Нужно добавить:
```c
struct FloraParams {
    ...
    uint8_t intensity;       // 0-100: scale peak между base и max
    uint8_t tempo;           // 50-200: period multiplier (100 = 1.0x)
    uint8_t jitter;          // 0-100: randomize period each cycle
    uint16_t attackMs;       // fast ramp-up (Sharp variant)
    bool flicker;            // stochastic dimming (Unease variant)
    uint8_t sparkProbability; // 0-100: override existing behavior
};
```

---

## 6. ИНТЕГРАЦИЯ JETSON-SIDE

**FloraController (`System/adam/flora.py`) — нужно добавить:**

```python
def _on_emotion_change(self, emotion: str, intensity: float = 0.5) -> None:
    """Called when AIIM emotion shifts. Sets P2 preset for emotion."""
    params = self._compute_emotion_params(emotion, intensity)
    self.push_preset_p2(params)

def _compute_emotion_params(self, emotion: str, intensity: float) -> dict:
    """Scale emotion preset parameters by intensity."""
    base = EMOTION_PRESETS[emotion]["a"]  # variant A
    if intensity > 0.65:
        base = EMOTION_PRESETS[emotion]["b"]  # variant B
    return {
        **base,
        "peak_pct": base["base_pct"] + (base["peak_pct"] - base["base_pct"]) * intensity,
    }
```

**Точка вызова в Orchestrator** — после применения AIIM premod:
```python
if new_emotion != aiim_state.emotion:
    flora_controller.push_preset_p2_emotion(new_emotion, intensity=premod.weight if premod else 0.5)
```

---

## 7. CONFIG.JSON: НОВЫЕ ПРЕСЕТЫ

Добавить в `flora.states` в Config.json 10 новых пресетов + секцию `flora.emotion_presets`:

```json
"emotion_presets": {
    "curious": {
        "a": { "base_pct": 15, "peak_pct": 55, "period_ms": 2800, "spark_probability": 0.25, "vibro": false },
        "b": { "base_pct": 20, "peak_pct": 65, "period_ms": 1800, "spark_probability": 0.40, "vibro": false }
    },
    "warm": {
        "a": { "base_pct": 25, "peak_pct": 50, "period_ms": 5000, "vibro": false },
        "b": { "base_pct": 30, "peak_pct": 60, "period_ms": 3500, "vibro": "soft" }
    },
    "unease": {
        "a": { "base_pct": 10, "peak_pct": 60, "period_ms": 1200, "jitter": 0.4, "vibro": "medium" },
        "b": { "base_pct": 5, "peak_pct": 71, "period_ms": 600, "jitter": 0.8, "vibro": "intense" }
    },
    "sharp": {
        "a": { "base_pct": 20, "peak_pct": 71, "period_ms": 1600, "attack_ms": 60, "vibro": "sync" },
        "b": { "base_pct": 15, "peak_pct": 71, "period_ms": 800, "attack_ms": 30, "vibro": "intense_sync" }
    },
    "calm": {
        "a": { "base_pct": 35, "peak_pct": 45, "period_ms": 6000, "vibro": false },
        "b": { "base_pct": 40, "peak_pct": 55, "period_ms": 4500, "vibro": false }
    }
}
```

---

## 8. BACKWARD COMPATIBILITY

Существующие 5 пресетов (breathe/accent/attentive/think_pulse/wake_bloom) — **без изменений**. Новые пресеты добавляются параллельно. Firmware поддерживает additive field расширение через default-значения.

---

## 9. РЕАЛИЗАЦИЯ: 4 СЛОЯ

1. **Firmware** (ESP32): добавить поля `intensity`, `tempo`, `jitter`, `attackMs` в FloraParams
2. **Config.json**: добавить `flora.emotion_presets` секцию с 10 пресетами  
3. **Config.schema.json**: документировать новые поля
4. **FloraController**: `push_preset_p2_emotion(emotion, intensity)` + `_compute_emotion_params()`
5. **Orchestrator**: вызов FloraController при смене эмоции (после AIIM блока)
