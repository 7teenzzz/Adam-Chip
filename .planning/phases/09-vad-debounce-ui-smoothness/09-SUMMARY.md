# Phase 9 — VAD debounce + UI smoothness + chat panel cleanup ✓

**Дата:** 2026-05-17
**Цель:** устранить VAD-флапп (40 emissions на одну фразу), сделать audio_level и heartbeat независимыми от блокировок `_vad_loop`, привести в порядок UI чат-панели. Дополнительно — отчёт по конфигурации ESP32 INMP441.

## Изменения

### A. UI (chat-панель) — REQ-UI-CHAT-CLEANUP

| Файл | Что |
|---|---|
| `System/WebUI/static/js/widgets/wakeMeter.js` | Убрана текстовая подпись `t=X s=Y max=Z` с эквалайзера (линии 179-186 → удалены) |
| `System/WebUI/static/js/panels/chat.js` | Убран импорт `createCalibrateButton`; удалён блок создания и плейсхолдеры `calibrateBtn`/`calibStatus`. Калибровка остаётся только на странице `Settings`. |
| `System/WebUI/static/js/panels/chat.js` | `micSourceBadge` перенесён в шапку (рядом с подписью «Микрофон · OWW», выровнен по правому краю — туда где была кнопка Калибровать). Старая отдельная строка убрана. |
| `System/WebUI/static/js/panels/chat.js` | `vuCanvas` высота: 52 px → **96 px** (под высоту эквалайзера). |

### B. Config (новый параметр) — REQ-VAD-DEBOUNCE

| Файл | Изменение |
|---|---|
| `System/Config.json` | `services.asr.endpointing_debounce_frames: 5` |
| `System/Config.schema.json` | JSON Schema entry, type=integer, default=5, min=1, max=50, English description |
| `System/adam/config.py` | `DEFAULT_CONFIG["services"]["asr"]["endpointing_debounce_frames"] = 5` |

### C. VAD debounce — REQ-VAD-DEBOUNCE

В `System/Orchestrator.py`:

- Добавлено поле `self._endpointing_debounce_frames` в `__init__` (читает `asr_cfg.get("endpointing_debounce_frames", 5)`).
- В `_vad_loop` накопителе добавлен счётчик `_silence_run_frames`. На каждом voiced-кадре сбрасывается в 0. На silenced-кадре (если speech_frames непустой) инкрементируется.
- `endpointing_started` event эмитится ТОЛЬКО когда `_silence_run_frames >= self._endpointing_debounce_frames` (default 5 = ~100 ms подряд тишины). До этого `vad_state` остаётся `speech`.
- Сброс счётчика в submission-блоке (на drain segment) и в чистом silence-state (когда speech_frames пуст).

**Эффект:** на длинной фразе вместо 21-40 emissions endpointing_started — будет 1-2 (только реальные конец речи).

### D. Heartbeat в отдельный task — REQ-HEARTBEAT-INDEPENDENT

В `System/Orchestrator.py`:

- Удалён inline-heartbeat блок из `_vad_loop` (был добавлен в Phase 8).
- Добавлен метод `_heartbeat_loop()` — рантайм-цикл с `await asyncio.sleep(5.0)` между emit'ами.
- В `start()`: `self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="adam_voice_heartbeat")`.
- В `stop()`: cancel + await heartbeat task перед основным.
- В `__init__`: `self._heartbeat_task: asyncio.Task[None] | None = None`.
- Payload heartbeat теперь содержит дополнительное поле `source: "heartbeat_task"` чтобы операторы могли отличить новые heartbeat'ы от старых inline-эмиссий в истории логов.

**Эффект:** при блокировке `_vad_loop` на ASR/TTS heartbeat продолжает идти точно каждые 5 sec. Раньше gap'ы были до 39 sec (test 1) / 27 sec (test 2).

### E. audio_level continuous emission — REQ-AUDIO-LEVEL-CONTINUOUS

В `System/adam/mic_reader.py`:

- Добавлен метод `_level_emit_loop()` — watchdog task, просыпается каждые 200 ms.
- Если `_emit_audio_level` (primary path в `_drain_loop`) фired в последние 250 ms — пропускает (drain работает, UI получает свежие).
- Иначе — синтезирует `audio_level` event из кэшированных `_last_mono_rms`, `_raw_level_l`, `_raw_level_r`, помечает `synthetic: true` для отличия в логах.
- Старт/останов в `start()` / `stop()` — рядом с основным `_run` task, с правильным cancel-ordering.
- `_emit_audio_level()` теперь обновляет кэш (`_last_mono_rms`, `_last_level_emit_t`) на каждый вызов primary path.

**Эффект:** даже при stall'е MicReader (HTTP reconnect, queue starvation, TTS-блок) UI получает обновление минимум каждые ~250 ms — не больше. Прошлый max gap 15101 ms (Test 1) станет невозможным в нормальной работе.

### F. WebUI транспорт — проверка (REQ не нужен)

`System/WebUI/static/js/api.js`:

- `subscribeEvents()` использует `EventSource("/api/agent/stream")` — **SSE уже реализован** с автоматическим reconnect и exponential backoff. Дополнительный fix не нужен.
- Дополнительно есть polling `/api/agent/status` каждые 4 sec в `main.js` — для общей health-страницы (services status, мощность, jet status). Это не источник UI lag в чате, изменения не требуются.

## ESP32 mic verification report — REQ-ESP32-AUDIO-REPORT

Источник: `Subsystem/AdamsServer/config/AdamsConfig.h` (kAudio* константы) + `Subsystem/AdamsServer/src/audio/AudioModule.cpp` (kAudioProfiles).

| Параметр | Текущее значение | Рекомендация пользователя | Соответствие |
|---|---|---|---|
| **Sample rate** | **16 000 Hz** | 44 100 или 48 000 Hz | ❌ Ниже рекомендации |
| **Bit depth (effective)** | **16 bit** | 16 bit | ✓ Соответствует |
| Slot bit width (I2S internal) | 32 bit | — | информационно |
| Data bit width (I2S internal) | 32 bit | — | информационно (INMP441 — 24-bit sensor) |
| Capture shift | 14 (>>14, оставляет 16 бит из 32) | — | конвертация в 16-bit для UDP/buffer |
| Format | Philips I2S | — | — |
| Channels | stereo (профиль `inmp441_philips32_stereo`) | — | — |
| Mic chip | INMP441 (× 2) | — | — |

**Почему 16 kHz, а не 44.1/48 kHz:**

`kAudioSampleRate = 16000` зафиксировано в прошивке потому что WhisperX ASR на Jetson принимает 16 kHz сэмпл, а `media.audio.sample_rate=16000` в `System/Config.json` совпадает. Любая частота выше требует ресэмплинг на Jetson перед отправкой в WhisperX (доп. CPU, ~0.5 ms на кадр).

**Если хочется поднять до 44.1/48 kHz** (отдельная задача, не в Phase 9):
1. `kAudioSampleRate = 44100` в `Subsystem/AdamsServer/config/AdamsConfig.h`.
2. Пересборка + flash прошивки (`tools/flash_com7.ps1` или OTA).
3. `media.audio.sample_rate = 44100` в Config.json.
4. На Jetson side — ресэмплинг 44100→16000 перед отправкой в WhisperX (`scipy.signal.resample_poly` или `av.audio.resampler`).
5. Bandwidth ↑ 2.75× (ESP32 stream ↑ ~88 KB/s mono), потребление ESP32 RAM ↑.
6. ASR качество **не изменится** (WhisperX внутренне работает на 16 kHz, выше — пустая трата).

**Рекомендация:** 16 kHz для речи — это де-факто стандарт ASR. INMP441 при 16 kHz даёт чистый сигнал, дальше его расширять не нужно для целей Адама. Bit depth 16 — соответствует. Текущая конфигурация оптимальна для этого пайплайна.

## Verify

```
$ python3 -c "import ast; ast.parse(open('System/Orchestrator.py').read())" → AST OK
$ PYTHONPATH=System python3 -c "import Orchestrator" → import OK
$ PYTHONPATH=System python3 -c "import Orchestrator; import adam.mic_reader" → all imports OK
$ python3 -m json.tool System/Config.json → OK
$ python3 -m json.tool System/Config.schema.json → OK
$ python3 -c "from adam.config import DEFAULT_CONFIG; print(...)" → endpointing_debounce_frames = 5
```

## Что нужно сделать оператору (manual UAT)

После деплоя ветки на Jetson:

1. `sudo systemctl restart adam-orchestrator.service`.
2. Открыть UI на странице Чат — убедиться:
   - В эквалайзере нет текстовой подписи `t=X s=Y max=Z`.
   - Кнопки «Калибровать» нет в чате.
   - Плашка `Mic: ESP32 stereo` отображается **над** эквалайзером по правой стороне.
   - VU-метр одной высоты с эквалайзером (96 px).
3. Поговорить ≥ 5 фраз. Запустить:
   ```
   python3 scripts/adam_test_reply_hang.py --last-minutes 5 --verbose
   ```
   Ожидается:
   - Heartbeats ≥ ~60 за 5 минут (по 12 в минуту = каждые 5 sec).
   - WARN gap'ы (>6 sec) уменьшились по сравнению с Test 1/2 — heartbeat теперь независим от ASR/TTS.
4. Проверить в events.jsonl debounce:
   ```
   tail -5000 data/adam/events.jsonl | grep -c '"type": "endpointing_started"'
   ```
   На сессии из ~5 фраз ожидается ≤ 10 emissions (а не 40 за одну фразу).

## Закрытие фазы

Все REQ покрыты. Manual UAT pending (требует Jetson + ESP32 + микрофон).
