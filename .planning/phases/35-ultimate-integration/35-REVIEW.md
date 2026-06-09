# Phase 35 — Code Review

**Reviewed:** 2026-06-09
**Depth:** standard (deep cross-file checks on critical paths)
**Branch:** LuxFlora-modes_V1.2
**Files reviewed:**
- `System/adam/skills.py`
- `System/adam/echoes_gate.py`
- `System/adam/flora.py`
- `System/adam/config.py`
- `System/adam/prompt.py`
- `System/Orchestrator.py` (skills wiring sections)
- `Subsystem/AdamsServer/config/AdamsConfig.h`
- `Subsystem/AdamsServer/src/io/FloraModule.cpp`

---

## Critical

### CR-01: JokeGate cooldown файл совпадает с echoes cooldown файлом

**File:** `System/adam/memory.py:389-392`
**Issue:** Метод `_gate_log_path(pool)` возвращает `echoes_used.jsonl` для любого пула, кроме `"chinese"`. Пул `"jokes"` тоже попадает в `echoes_used.jsonl`. Это означает:
1. IDs шуток записываются в тот же файл, что и IDs эхо-фраз. Cooldown шуток работает, только если ID шутки уникален относительно ID любой эхо-фразы.
2. `config.schema.json` документирует отдельный файл `data/adam/jokes_used.jsonl`, но код его не создаёт.
3. При росте выставки логи шуток засоряют echoes_used.jsonl, что может случайно заблокировать несвязанные эхо-фразы.

**Fix:**
```python
# memory.py, _gate_log_path:
def _gate_log_path(self, pool: str) -> Path:
    if pool == "chinese":
        return self.chinese_used_path
    if pool == "jokes":
        # Lazy-init, аналогично echoes_used_path
        return self.root / "jokes_used.jsonl"
    return self.echoes_used_path
```

Добавить атрибут `self.jokes_used_path = self.root / "jokes_used.jsonl"` в `__init__` рядом с `chinese_used_path`.

---

### CR-02: Устаревший комментарий в FloraModule.cpp — неверная раскладка каналов

**File:** `Subsystem/AdamsServer/src/io/FloraModule.cpp:15`
**Issue:** Заголовочный комментарий файла гласит `Light = ch 0-10, vibro = ch 11-14`, тогда как после ремапа Phase 35 реальные константы `kFloraLightChannelLo=4`, `kFloraLightChannelHi=14`, `kFloraVibroChannelLo=0`, `kFloraVibroChannelHi=3`. То же расхождение на строке 253 (`// --- Light channels 0-10 (D-02) ---`). Оба комментария указывают на старую раскладку. Это не просто стиль — следующий разработчик, читающий файл, получит неверное представление о том, какие каналы приводят вибро, что критично при отладке шума в микрофоне (D-11 инвариант).

**Fix:**
```cpp
// Строка 15 — заменить:
// writeAllChannelsRaw. Light = ch 0-10, vibro = ch 11-14.
// На:
// writeAllChannelsRaw. Light = ch 4-14 (11 lamps), vibro = ch 0-3 (4 motors).

// Строка 253 — заменить:
// --- Light channels 0-10 (D-02) ---
// На:
// --- Light channels 4-14 (kFloraLightChannelLo..Hi, D-02) ---

// Строка 287 — заменить:
// --- Vibro channels 11-14 (D-11 / D-12 / FLORA-06) ---
// На:
// --- Vibro channels 0-3 (kFloraVibroChannelLo..Hi, D-11 / D-12 / FLORA-06) ---
```

---

## Warning

### WR-01: flora.py — speech params не hot-reload (несоответствие с _build_params)

**File:** `System/adam/flora.py:61, 72-76`
**Issue:** `_vibro_intensity_pct`, `_frame_interval_ms`, `_hdmi_offset_ms`, `_base_duty_pct`, `_peak_duty_pct`, `_spark_probability` кэшируются один раз в `__init__` и никогда не обновляются. `_rms_stream` (строка 496) использует `self._vibro_intensity_pct` из кеша. Для сравнения, `_build_params` (строка 286) читает `vibro_intensity_pct` свежим через `_live_flora_cfg()` на каждый вызов. Результат: preset-параметры (breathe/accent/think_pulse) обновляются при hot-reload Config.json, а параметры RMS speech stream — нет. Изменение `flora.speech.peak_duty_pct` или `flora.vibro.intensity_pct` через WebUI вступит в силу для пресетов, но не для stream RMS-кадров без рестарта оркестратора.

**Fix:** В `_rms_stream` заменить кешированные значения на чтение из `_live_flora_cfg()`:
```python
async def _rms_stream(self, duties: list[int]) -> None:
    t0 = perf_counter()
    # Hot-reload-aware: read speech params fresh.
    flora = self._live_flora_cfg()
    speech_cfg = flora.get("speech", {}) or {}
    frame_interval_ms = int(speech_cfg.get("frame_interval_ms", self._frame_interval_ms))
    hdmi_offset_ms = int(speech_cfg.get("hdmi_latency_offset_ms", self._hdmi_offset_ms))
    spark_probability = float(speech_cfg.get("spark_probability", self._spark_probability))
    vibro_intensity_pct = int((flora.get("vibro") or {}).get("intensity_pct", self._vibro_intensity_pct))
    # ... использовать локальные переменные вместо self._*
```

Либо принять, что RMS stream не hot-reload, и явно задокументировать это в комментарии.

---

### WR-02: DEFAULT_CONFIG в config.py расходится с Config.json по flora.speech параметрам

**File:** `System/adam/config.py:152, 160`
**Issue:** `DEFAULT_CONFIG` содержит `speech.peak_duty_pct: 90` и `states.breathe.peak_pct: 30`, `states.breathe.period_ms: 7000`, тогда как `Config.json` содержит `speech.peak_duty_pct: 71`, `states.breathe.peak_pct: 71`, `states.breathe.period_ms: 4000`. При утере `Config.json` (например, на новой Jetson) FloraController инициализируется с неверными значениями. `speech.peak_duty_pct: 90` — это пиковая яркость при речи значительно выше реальных 71%; при новой инсталляции лампы будут светить ярче, чем задумано.

**Fix:** Синхронизировать `DEFAULT_CONFIG` с `Config.json`:
```python
# config.py, DEFAULT_CONFIG, flora.speech:
"speech": {
    "frame_interval_ms": 80,
    "hdmi_latency_offset_ms": 150,
    "base_duty_pct": 25,
    "peak_duty_pct": 71,   # было 90
    "spark_probability": 0.15,
},
# flora.states.breathe:
"breathe": {"base_pct": 7, "peak_pct": 71, "period_ms": 4000, "vibro": False},
# flora.states.accent:
"accent": {"base_pct": 10, "peak_pct": 71, "attack_ms": 250, "vibro": True,
           "vibro_pulse_ms": 120, "period_ms": 1400},
```

---

### WR-03: vibro_duty в _rms_stream базируется на post-clamped light duty

**File:** `System/adam/flora.py:505-532`
**Issue:** `vibro_duty = int(round(duty * vibro_scale))` — здесь `duty` — это значение после light-ceiling clamp (`duty = min(duty, max_duty)`, строка 506). При `max_duty_pct < 100` вибро будет ограничено light-ceiling'ом через цепочку `duty → vibro_duty`, несмотря на то что комментарий явно говорит "NOT clamped to the light max_duty ceiling". Например, при `max_duty_pct=71` и `vibro_intensity_pct=95%`: light duty clamp'ится до 2908, vibro_duty = round(2908 * 0.95) = 2763, тогда как без light-clamp с peak=90% duty=3686: vibro_duty = round(3686 * 0.95) = 3502. Вибро получает на 27% меньше энергии.

**Fix:** Вычислять `vibro_duty` из некламп'нутого значения:
```python
# Сохранить pre-clamp duty
raw_duty = duties[i]  # перед min(duty, max_duty)
duty = min(raw_duty, max_duty)  # clamp только для light
...
# Vibro использует raw_duty, ограниченный только vibro_intensity ceiling
vibro_max = int(round(self._value_max * vibro_scale))
vibro_duty = int(round(raw_duty * vibro_scale))
vibro_duty = min(vibro_duty, vibro_max)
```

---

### WR-04: _jokes_cfg enabled-check использует False как default вместо True

**File:** `System/Orchestrator.py:3240`
**Issue:** `bool(_jokes_cfg.get("enabled", False))` — default `False`. Если `_jokes_cfg` пуст (Skills секция не найдена в конфиге), шутки отключены даже если пользователь ожидает их работы. Аналогично строка 3254 для weather: `bool(_weather_cfg.get("enabled", False))`. Однако DEFAULT_CONFIG явно содержит `"enabled": True` для обоих. Несоответствие: DEFAULT_CONFIG → `True`, Orchestrator guard → `False`. При нормальном запуске `_deep_merge` подхватит DEFAULT_CONFIG, но если `section("skills")` вернёт `{}` по какой-то причине, оба skill'а молча выключатся.

**Fix:** Использовать `True` как default, отражая намерение DEFAULT_CONFIG:
```python
if intent == "joke" and bool(_jokes_cfg.get("enabled", True)):
    ...
elif intent == "weather" and bool(_weather_cfg.get("enabled", True)):
    ...
```

---

## Info

### IN-01: vibro_intensity_pct default в flora.py не совпадает с Config

**File:** `System/adam/flora.py:61`
**Issue:** `int(self._vibro_cfg.get("intensity_pct", 30))` — hardcoded default `30`, тогда как Config.json и DEFAULT_CONFIG содержат `95`. При нормальном запуске это не проявляется (Config.json всегда загружается), но при пустом `settings_section` вибро будет слабее в 3 раза.

**Fix:** Заменить `30` на `95` для согласованности с Config.json.

---

### IN-02: Устаревший комментарий к vibro_channels default в flora.py

**File:** `System/adam/flora.py:65`
**Issue:** `self._vibro_channels: list[int] = list(self._cfg.get("vibro_channels", [11, 12, 13, 14]))` — default `[11, 12, 13, 14]` отражает старую раскладку. После ремапа правильный default `[0, 1, 2, 3]` (как в DEFAULT_CONFIG и Config.json).

**Fix:**
```python
self._vibro_channels: list[int] = list(self._cfg.get("vibro_channels", [0, 1, 2, 3]))
```

---

### IN-03: IntentRouter не hot-reload (keywords из Config.json)

**File:** `System/Orchestrator.py:124-127`
**Issue:** `intent_router` создаётся один раз при старте модуля с ключевыми словами из Config.json. Изменение `skills.jokes.intent_keywords` через WebUI (`/api/config`) не вступит в силу без перезапуска оркестратора. Это ожидаемо (большинство синглтонов так работают), но стоит задокументировать в коде, чтобы не путать будущих разработчиков.

**Fix:** Добавить комментарий:
```python
# NOTE: keywords are loaded once at startup. Config.json edits to
# skills.*.intent_keywords require an orchestrator restart to take effect.
intent_router = IntentRouter(...)
```

---

### IN-04: weather_provider.cached() вызывается дважды подряд (TOCTOU)

**File:** `System/Orchestrator.py:3257-3260`
**Issue:**
```python
weather_ctx = weather_provider.cached() or "(датчик улицы сейчас недоступен)"
event_log.append(
    "skill_weather",
    {"ctx": weather_ctx, "cached": weather_provider.cached() is not None},  # второй вызов
```
Второй вызов `weather_provider.cached()` избыточен и может (теоретически) вернуть другой результат если кеш устарел между двумя вызовами. Логгируемое поле `"cached"` будет `False` если кеш устарел между вызовами, хотя `weather_ctx` содержит offline-заглушку.

**Fix:**
```python
cached_str = weather_provider.cached()
weather_ctx = cached_str or "(датчик улицы сейчас недоступен)"
event_log.append("skill_weather", {"ctx": weather_ctx, "cached": cached_str is not None}, turn_id=turn_id)
```

---

### IN-05: `_with_word_target` в prompt.py не обновляет целевое слово для значений != 30

**File:** `System/adam/prompt.py:279-283`
**Issue:**
```python
def _with_word_target(base: str, target: Optional[int]) -> str:
    if not target or target == 30:
        return base
    return base.replace("~30 слов", f"~{target} слов")
```
Функция ищет точную строку `"~30 слов"` в персона-файле. Если файл не содержит этой строки (например, редактировался вручную), замена молча не произойдёт и `response_word_target` из tuning будет проигнорирован. Нет предупреждения об этом.

**Fix:** Добавить опциональный лог при отсутствии замены:
```python
def _with_word_target(base: str, target: Optional[int]) -> str:
    if not target or target == 30:
        return base
    result = base.replace("~30 слов", f"~{target} слов")
    # Optionally warn if substitution had no effect:
    # if result == base and "~30 слов" not in base:
    #     log.debug("_with_word_target: marker '~30 слов' not found in persona")
    return result
```

---

## Summary

**2 Critical, 4 Warning, 5 Info**

| # | Severity | Файл | Проблема |
|---|----------|------|----------|
| CR-01 | CRITICAL | `memory.py:389` | JokeGate cooldown пишет в `echoes_used.jsonl` — смешение пулов, нарушение изоляции cooldown |
| CR-02 | CRITICAL | `FloraModule.cpp:15,253,287` | Устаревший комментарий с неверной раскладкой каналов (ch 0-10/11-14 вместо 4-14/0-3) — дезориентирует при отладке D-11 |
| WR-01 | WARNING | `flora.py:61,72-76` | Speech/vibro params в `_rms_stream` не hot-reload в отличие от `_build_params` |
| WR-02 | WARNING | `config.py:152,160` | `DEFAULT_CONFIG` расходится с `Config.json` по flora.speech и flora.states.breathe |
| WR-03 | WARNING | `flora.py:505-532` | `vibro_duty` базируется на post-light-clamp `duty`, де-факто ограничивая вибро light-ceiling'ом вопреки документации |
| WR-04 | WARNING | `Orchestrator.py:3240,3254` | enabled-default `False` для skills в Orchestrator vs `True` в DEFAULT_CONFIG |
| IN-01 | INFO | `flora.py:61` | `vibro_intensity_pct` default `30` не совпадает с Config `95` |
| IN-02 | INFO | `flora.py:65` | `vibro_channels` default `[11,12,13,14]` — старая раскладка |
| IN-03 | INFO | `Orchestrator.py:124` | `IntentRouter` не hot-reload, не задокументировано |
| IN-04 | INFO | `Orchestrator.py:3257-3260` | `weather_provider.cached()` вызывается дважды подряд |
| IN-05 | INFO | `prompt.py:279` | `_with_word_target` молча не работает если `"~30 слов"` отсутствует в персона-файле |

**Приоритет исправлений:**
1. CR-01 — исправить до мержа (данные могут смешаться уже после первого запуска)
2. CR-02 — исправить до мержа (риск неверной отладки D-11 инварианта)
3. WR-03 — исправить, если `max_duty_pct < 100` планируется для реальной инсталляции
4. WR-01, WR-02, WR-04 — желательно исправить в том же PR
