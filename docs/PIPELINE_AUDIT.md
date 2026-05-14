# Аудит пайплайна: Микрофон → ASR

> Дата: 2026-05-14 | Ветка: V_S003.2--esp32-ui

---

## Два фронта работ

```
Фронт A — код (можно без ESP32)     Фронт B — железо (нужна ESP32)
────────────────────────────────    ────────────────────────────────
A1. ✅ HOTFIX критических багов      B1. Перепрошивка ESP32
A2. Валидация WAV-заголовка         B2. Проверка стрима (:81/audio)
A3. Защита от пустого чанка         B3. Тест аудио-профилей
A4. Restart-стратегия arecord       B4. End-to-end тест с wake word
A5. Тест VAD loop в обоих режимах
```

---

## ✅ Уже исправлено (коммит 3eb469d)

### Баг 1 — NameError `enough_speech` (строка 636)
**Эффект:** VAD loop падал с `NameError` при каждой попытке отправить речь в ASR.  
**Итог:** ASR никогда не вызывался. Адам вечно молчал.  
**Фикс:** `enough_speech` → `enough` (переменная правильно присвоена строкой выше).

### Баг 2 — `_start_arecord()` в ESP32-режиме (строки 646–651)
**Эффект:** После первого ASR dispatch `_vad_loop` запускал локальный `arecord` subprocess и переключал `_reader[0]` на него. Все последующие фреймы читались из ALSA, не из ESP32 стрима — тихо и навсегда.  
**Фикс:** `_using_process = self._process is not None`. В ESP32-режиме стоп/рестарт arecord пропускается, HTTP-ридер остаётся неизменным.

---

## Фронт A — Оставшиеся задачи кода

### A2. Валидация WAV-заголовка при подключении к ESP32

**Файл:** `System/Orchestrator.py`, `_run_esp32()` ~строка 440

**Проблема:** `resp.read(44)` может вернуть < 44 байт если ESP32 закрывает соединение сразу. Код не проверяет длину — дальше идут мусорные данные.

**Фикс:**
```python
header = await asyncio.to_thread(resp.read, 44)
if len(header) < 44:
    raise RuntimeError(f"ESP32 WAV header truncated: got {len(header)} bytes")
```

### A3. Пустой чанк не должен убивать весь VAD loop

**Файл:** `System/Orchestrator.py`, `_vad_loop()` ~строка 502

**Проблема:** `if not chunk: raise RuntimeError("audio source ended unexpectedly")` — одна пустая читалка убивает всю сессию.

**Фикс для ESP32-режима:** пропустить N подряд пустых чанков перед raise, дать стриму шанс восстановиться:
```python
_empty_streak = 0
# внутри loop:
if not chunk:
    _empty_streak += 1
    if _empty_streak >= 3:
        raise RuntimeError("audio source ended: 3 consecutive empty reads")
    continue
_empty_streak = 0
```

### A4. Нет backoff для локального arecord

**Файл:** `System/Orchestrator.py`, `_run_local()`

**Проблема:** При падении arecord (`voice_loop_error`) контроллер останавливается насовсем. Нет повторных попыток.

**Фикс:** добавить retry loop с экспоненциальным backoff (3 попытки, 1s / 2s / 4s).

---

## Фронт B — ESP32: перепрошивка и проверка

### B1. Перепрошивка

**С Windows dev-машины (OTA предпочтительно):**
```powershell
# OTA по Wi-Fi (если ESP32 в сети)
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_ota.ps1 -Host 192.168.0.171

# Или serial (COM7)
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1
```

### B2. Проверка стрима после прошивки

```bash
# С Jetson — проверить что стрим отдаёт данные
curl --noproxy '*' -v http://192.168.0.171:81/audio --max-time 5 | xxd | head -20
# Ожидаем: 52 49 46 46 ... (RIFF WAV header), затем поток PCM

# Статус ESP32
curl --noproxy '*' -fsS http://192.168.0.171/api/status | python3 -m json.tool

# Проверить канал захвата
curl --noproxy '*' -fsS http://192.168.0.171/api/audio | python3 -m json.tool
# Ожидаем: capture.left_peak > 0, capture.right_peak > 0, signal_state = "active"
```

### B3. Тест аудио-профилей

```bash
# Установить стерео профиль
curl --noproxy '*' -X POST http://192.168.0.171/api/audio \
  -H 'Content-Type: application/json' \
  -d '{"profile": "inmp441_philips32_stereo"}'

# Проверить отклик: оба канала активны
curl --noproxy '*' -fsS http://192.168.0.171/api/audio | python3 -m json.tool

# Тест левого канала отдельно
curl --noproxy '*' -X POST http://192.168.0.171/api/audio \
  -d '{"profile": "inmp441_philips32_left"}'

# Тест правого канала
curl --noproxy '*' -X POST http://192.168.0.171/api/audio \
  -d '{"profile": "inmp441_philips32_right"}'
```

### B4. End-to-end тест с Orchestrator

```bash
# Запустить с maintenance mode + esp32 mic
PYTHONPATH=System ADAM_MODE=maintenance ./.venv/bin/python System/Orchestrator.py

# Проверить статус VoiceLoop
curl --noproxy '*' -fsS http://127.0.0.1:8080/api/agent/status | python3 -m json.tool
# Ожидаем: voice_loop.running=true, mic_active_source="esp32"

# Отслеживать audio_level события в UI (/#/chat):
# - при речи рядом с ESP32: оба бара VU-метра должны двигаться
# - если только один бар — один INMP441 мёртв

# Тест wake word:
curl --noproxy '*' -fsS http://127.0.0.1:8080/api/agent/turn \
  -H 'Content-Type: application/json' \
  -d '{"transcript": "Адам, ты меня слышишь?"}'
```

---

## Полная карта failure points

| Шаг | Что может упасть | Severity | Статус |
|-----|-----------------|----------|--------|
| VAD loop — endpointing | `enough_speech` NameError | 🔴 CRITICAL | ✅ FIXED |
| VAD loop — arecord restart | ESP32 reader заменяется на ALSA | 🔴 CRITICAL | ✅ FIXED |
| ESP32 connect — WAV header | Partial read = мусор в потоке | 🟠 HIGH | A2 pending |
| VAD loop — пустой чанк | Один пустой → сессия умирает | 🟠 HIGH | A3 pending |
| Local arecord | Нет retry — умирает навсегда | 🟡 MEDIUM | A4 pending |
| ESP32 hardware | Слетела прошивка / I2S init | 🟠 HIGH | B фронт |
| OWW модель | Файл adam.onnx не найден → deaf | 🔴 CRITICAL | проверить вручную |
| arecord restart | stdout=None → RuntimeError | 🟡 MEDIUM | мониторинг |

---

## Конфиг — полный список аудио-параметров

| Параметр | Значение | Файл |
|----------|----------|------|
| `mic_source` | `"local"` (сейчас) | Config.json |
| `esp32_mic_profile` | `"inmp441_philips32_stereo"` | Config.json |
| `input_device` | `"pulse"` | Config.json |
| `sample_rate` | `16000` | Config.json |
| `frame_ms` | `20` | Config.json |
| `webrtc_vad_aggressiveness` | `3` | Config.json |
| `min_speech_ms` | `200` | Config.json |
| `max_command_segment_ms` | `15000` | Config.json |
| `command_endpointing_ms` | `3000` | Config.json (asr) |
| `reply_noise_gate` | `1600` | Config.json (asr) |
| `wake_word_required` | `true` | Config.json |
| `wake_silence_timeout_sec` | `6.0` | Config.json |
| ESP32 poll_interval_s | `60` | Config.json |
| ESP32 silence_threshold | `24` | Config.json |
| ESP32 ratio_threshold | `6.0` | Config.json |
