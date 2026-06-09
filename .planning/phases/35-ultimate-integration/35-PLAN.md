# Phase 35 — Ultimate Integration: PLAN

**Цель:** Ветка `ultimate-integration` содержит все четыре потока работ без регрессий.

**Базовая ветка:** `vlr-main-integrated` (43b7f2f)

---

## Wave 1 — LuxFlora-modes_V1.2 (аппаратный ремап каналов)

**Почему первой:** устанавливает канонические маски каналов для всех последующих мёрджей. Если слить MemoryFixes/Extra первыми с их старыми масками — получим обратный конфликт.

### Шаги

```
git checkout vlr-main-integrated
git checkout -b ultimate-integration
git merge --no-commit LuxFlora-modes_V1.2
```

### Ожидаемые конфликты

#### `System/Config.json`
- **Каналы флоры** (`light_channels`, `vibro_channels`): ВЗЯТЬ LuxFlora `[4..14]` / `[0,1,2,3]`
- **`vibro.intensity_pct`**: ВЗЯТЬ LuxFlora (95 вместо 30)
- **`silence_rms_threshold`**: ВЗЯТЬ LuxFlora (2100 — выставочная калибровка)
- **`input_device`**: ОСТАВИТЬ `"pulse"` (vlr wins — ответ пользователя)
- **`scene_worker_enabled`**: ОСТАВИТЬ `false` (vlr wins — ответ пользователя)
- **Поля которых нет в LuxFlora** (`pre_wake_buffer_ms`, `silence_keywords`, `asr_pre_send_min_rms`, `input_gain`): ОСТАВИТЬ vlr-значения, не удалять

#### `System/Config.schema.json`
- Channel-mask описания: ВЗЯТЬ LuxFlora (актуальные 4-14 / 0-3)
- Остальное: влитое уже из vlr-main-integrated, конфликтов мало

#### `System/adam/config.py`
- `DEFAULT_CONFIG` channel masks: ВЗЯТЬ LuxFlora (`light_channels: [4..14]`, `vibro_channels: [0,1,2,3]`)
- Аудио параметры: ОСТАВИТЬ vlr (`input_device: "pulse"`)

#### `System/adam/flora.py`
- `_rms_stream` — снят `max_duty` с vibro_duty: ВЗЯТЬ LuxFlora
- Остальное из vlr: оставить

#### `Subsystem/AdamsServer/config/AdamsConfig.h`
- `kFloraLightChannelLo/Hi`: ВЗЯТЬ LuxFlora (4/14)
- `kFloraVibroChannelLo/Hi`: ВЗЯТЬ LuxFlora (0/3)
- `kFloraVibroIntensityCeiling`: ВЗЯТЬ LuxFlora (3890)
- Остальные константы: из vlr-main-integrated

#### `Subsystem/AdamsServer/src/io/FloraModule.cpp`
- Max-duty кламп только по свет-каналам: ВЗЯТЬ LuxFlora

#### `.planning/ROADMAP.md`, `BRANCH.md`
- Объединить нарративы (оба содержат разные секции)

#### `tests/test_flora.py`
- ВЗЯТЬ LuxFlora (обновлены маски + assert отсутствия gamma)

### Завершение Wave 1
```
git add -u
git commit -m "merge(LuxFlora): hardware channel remap — vibro 0-3 / light 4-14, vibro ceiling 95%"
```

### Verify Wave 1
- `python -m py_compile System/adam/flora.py System/adam/config.py`
- `python -c "import json; c=json.load(open('System/Config.json')); assert c['flora']['light_channels'][0]==4; assert c['flora']['vibro_channels'][0]==0; print('channels OK')"` 
- `grep "kFloraLightChannelLo = 4" Subsystem/AdamsServer/config/AdamsConfig.h`

---

## Wave 2 — origin/MemoryFixes (Echoes gate + тесты памяти)

**Почему второй:** не добавляет новых Python-модулей в Orchestrator — чисто логика памяти и тесты. Extra (skills.py) зависит от prompt.py и echoes_gate — лучше иметь их уже правильными перед Extra.

```
git merge --no-commit origin/MemoryFixes
```

### Ожидаемые конфликты

#### `Subsystem/AdamsServer/config/AdamsConfig.h`
- MemoryFixes имеет СТАРЫЕ маски (light 0-10, vibro 11-14): ОСТАВИТЬ Wave 1 результат (4-14 / 0-3)

#### `Subsystem/AdamsServer/src/io/FloraModule.cpp`
- Аналогично: ОСТАВИТЬ Wave 1

#### `System/Config.json`
- MemoryFixes меняет `volume` и `sensitivity` — брать MemoryFixes значения если они явно откалиброваны
- Поля каналов: ОСТАВИТЬ Wave 1

#### `System/adam/echoes_gate.py`
- ВЗЯТЬ MemoryFixes целиком: критический баг — gate никогда не срабатывал из-за несовпадения тегов ("коридор", "物是人非" vs транскрипт пользователя). Фикс: session_tags anti-repeat + hint_text для Chinese pool (ru_hint).

#### `System/adam/device.py`
- ВЗЯТЬ MemoryFixes (если есть изменения)

#### `.planning/ROADMAP.md`, `BRANCH.md`
- Объединить. MemoryFixes добавляет Phase 30 (echoes gate) контекст.

#### Новые файлы (просто добавляются, конфликтов нет)
- `tests/test_memory.py`
- `tests/test_memory_live.py`
- `tests/test_memory_pipeline.py`
- `tests/MEMORY_TEST_PROTOCOL.md`
- `.planning/phases/30-echoes-chinese-gate-activation/30-CONTEXT.md`
- `System/WebUI/static/js/panels/flora.js`
- `scripts/adam_esp32_stream_stress.sh`, `scripts/test_esp32_stream.py`, `scripts/verify_esp32_merge.py`
- `scripts/diagnostics/flora_line_identify.py`
- `docs/PIPELINE_AUDIT.md`
- ESP32 firmware files (FloraModule.h, Pca9685Module.cpp, WebServerModule.cpp, RuntimeState.h)

### Завершение Wave 2
```
git add -u
git commit -m "merge(MemoryFixes): fix echoes/chinese gate tag-matching + memory tests"
```

### Verify Wave 2
- `python -m py_compile System/adam/echoes_gate.py`
- `grep "session_tags" System/adam/echoes_gate.py`
- `python -m py_compile tests/test_memory.py`
- Channel map в AdamsConfig.h всё ещё 4-14 / 0-3: `grep "kFloraLightChannelLo = 4" Subsystem/AdamsServer/config/AdamsConfig.h`

---

## Wave 3 — origin/Extra (Skills: шутки + погода)

**Почему третьей:** самостоятельная новая функциональность, не зависит от MemoryFixes. Но слитые echoes_gate и prompt.py из MemoryFixes дают правильный базис для skills.py.

```
git merge --no-commit origin/Extra
```

### Ожидаемые конфликты

#### `Subsystem/AdamsServer/config/AdamsConfig.h`
- Extra имеет СТАРЫЕ маски: ОСТАВИТЬ Wave 1 результат

#### `System/adam/prompt.py`
- Extra добавляет `weather_ctx` параметр — не должно конфликтовать с уже влитым, но проверить

#### `.planning/ROADMAP.md`, `BRANCH.md`
- Объединить. Extra добавляет Phase 30 (skills-jokes-weather) контекст.

#### Новые файлы (просто добавляются)
- `System/adam/skills.py` — IntentRouter, WeatherProvider, JokeGate
- `Agent-Adam-Chip/About/Jokes.md`
- `tests/test_skills.py`
- `tests/test_weather_integration.py`
- `.planning/phases/30-skills-jokes-weather/30-CONTEXT.md`

### Завершение Wave 3
```
git add -u
git commit -m "merge(Extra): Phase 30 skills — jokes + weather pre-LLM providers"
```

### Verify Wave 3
- `python -m py_compile System/adam/skills.py System/adam/prompt.py`
- `grep "weather_ctx" System/adam/prompt.py`
- `grep "IntentRouter" System/adam/skills.py`
- Channel map ещё держится: `grep "kFloraLightChannelLo = 4" Subsystem/AdamsServer/config/AdamsConfig.h`

---

## Финальная верификация

После всех трёх волн:

```bash
# 1. Нет conflict markers
grep -rn "<<<<<<\|=======\|>>>>>>>" System/ .planning/ --include="*.py" --include="*.json" --include="*.md"

# 2. Python синтаксис
python -m py_compile System/Orchestrator.py System/Speech/ASR_WhisperX.py \
  System/adam/flora.py System/adam/echoes_gate.py System/adam/skills.py \
  System/adam/prompt.py System/adam/api_runtime.py

# 3. JSON валидность + ключевые значения
python -c "
import json
c = json.load(open('System/Config.json'))
assert c['media']['audio']['input_device'] == 'pulse', 'input_device wrong'
assert c['media']['scene_worker_enabled'] == False, 'scene_worker wrong'
assert c['flora']['light_channels'][0] == 4, 'light channel wrong'
assert c['flora']['vibro_channels'][0] == 0, 'vibro channel wrong'
print('Config OK')
"

# 4. Firmware channel constants
grep "kFloraLightChannelLo = 4" Subsystem/AdamsServer/config/AdamsConfig.h
grep "kFloraVibroChannelLo = 0" Subsystem/AdamsServer/config/AdamsConfig.h
grep "kFloraVibroIntensityCeiling = 3890" Subsystem/AdamsServer/config/AdamsConfig.h

# 5. Ключевые фичи всех веток на месте
grep "_barge_in_q" System/Orchestrator.py           # VLR
grep "session_tags" System/adam/echoes_gate.py       # MemoryFixes
grep "IntentRouter" System/adam/skills.py            # Extra
grep "weather_ctx" System/adam/prompt.py             # Extra
grep "asr_filter" System/adam/asr_filter.py          # Phase 34
```

---

## Post-merge: граф + дебаг

После финальной верификации:

```bash
# Обновить knowledge graph (System/ изменился существенно)
graphify update System/
```

Затем запустить `/gsd-debug` со списком проверок:
1. Python import ошибки во всех новых модулях (skills.py, asr_filter.py)
2. Нет ли регрессий в голосовом пайплайне (barge-in, InputDSP пути)
3. echoes_gate.py — session_tags логика не ломает existing API
4. AdamsConfig.h — прошивка требует перепрошивки после channel remap

---

## Приоритеты при неожиданных конфликтах

| Тип | Приоритет |
|-----|-----------|
| Аппаратные маски каналов | LuxFlora (Wave 1) всегда |
| Аудио устройства (input_device) | vlr-main-integrated (`pulse`) |
| Голосовой пайплайн (barge-in, InputDSP) | vlr-main-integrated |
| ASR параметры (vad_onset/offset, logprob) | vlr-main-integrated (тщательнее откалибровано) |
| Echoes/Chinese логика | MemoryFixes (баг-фикс) |
| Skills (jokes/weather) | Extra (новая фича, изолирована) |
| Planning docs конфликты | Объединять нарративы, не выбирать один |
