# AdamsServer Firmware

`AdamsServer` — прошивка для `ESP32-S3 N16R8 WROOM CAM`. После старта публикует:

- MJPEG-видео с `OV5640` по HTTP
- Uplink-аудио с `INMP441` x2 через `GET :81/audio`
- Playback на `PCM5102A` через `POST :81/speaker`
- Телеметрию сенсоров (`TEMT6000`, `BTE16-19`)
- Управление `PCA9685` (16-канальный PWM)

---

## Сеть и адрес

ESP32 автоматически выбирает транспорт в порядке приоритета:

| Приоритет | Транспорт | Статический IP |
|-----------|-----------|----------------|
| 1 | W5500 Ethernet (SPI) | `192.168.0.171` |
| 2 | Wi-Fi STA | `192.168.0.171` |
| 3 | AP-fallback (если оба недоступны) | `192.168.4.1` |

Никакого ручного переключения не нужно — прошивка сама определяет, что доступно.

Сетевые настройки (SSID, пароль, IP-схема) хранятся в:

- [`config/PrivateConfig.h`](config/PrivateConfig.h) — локальный файл, не коммитится
- [`config/PrivateConfig.example.h`](config/PrivateConfig.example.h) — шаблон

Схема IP: `192.168.<kWifiSubnetOctet3>.<kWifiHostOctet>`. Текущее значение `kWifiHostOctet = 171`.

AP-fallback: SSID `Adam Chip`, пароль `4D4M-CH1P4$`, IP `192.168.4.1`.

---

## Порты

| Порт | Назначение |
|------|-----------|
| **80** | Control-сервер: UI, весь `/api/*`, `/ws`, `/capture` |
| **81** | Stream-сервер: `/stream` (MJPEG), `/audio` (mic uplink), `/speaker` (playback) |

Пути `/audio` и `/speaker` на порту 80 возвращают `301 → :81`. Для прямого доступа используй порт 81.

---

## UI-иерархия

| Путь | Описание |
|------|---------|
| `GET /` или `/dashboard` | Панель управления: стримы, телеметрия, сенсоры. Авто-обновление 1 с |
| `GET /ctrldash` | Техническая панель: endpoint-health, raw-состояния модулей, OTA |
| `GET /live` | Только видео, минимальный интерфейс |
| `GET /ota` | Обновление прошивки через браузер |
| `GET /motor_skills` | Управление PCA9685: каналы, сцены, частота |
| `GET /vision` `/hearing` `/sensorics` `/system` | Legacy — редирект на `/dashboard` |
| `GET /vision/live` `/hearing/live` | Legacy live-страницы — работают |

---

## Аудио: два независимых тракта

| Тракт | Железо | Направление | Endpoint |
|-------|--------|-------------|---------|
| Capture (mic) | INMP441 x2 | ESP → Jetson | `GET :81/audio` |
| Playback (speaker) | PCM5102A | Jetson → ESP | `POST :81/speaker` |

`PCM5102A` не участвует в тракте микрофона и не должен использоваться для его диагностики.

### Speaker playback — формат

`POST :81/speaker` ожидает **mono, 16-bit PCM, 44100 Hz**.

Принимает:
- Сырые PCM-байты (без заголовка)
- WAV-файл — заголовок автоматически парсится и валидируется

Если WAV-заголовок не соответствует (`sampleRate ≠ 44100`, `channels ≠ 1`, `bits ≠ 16`):
ответ `400 speaker_wav_format_mismatch`.

WAV-файл:

```powershell
curl.exe --data-binary "@input.wav" -H "Content-Type: audio/wav" http://192.168.0.171:81/speaker
```

Поток через `ffmpeg`:

```powershell
ffmpeg -re -i input.wav -f s16le -acodec pcm_s16le -ac 1 -ar 44100 http://192.168.0.171:81/speaker
```

Speaker ring buffer: **32 KB** (~372 мс при 44100 Hz). Alloced в DRAM. Запись rate-limited — при переполнении ждёт I2S drain вместо дропа (4 мс backoff).

---

## Микрофон — диагностика

Основной инструмент диагностики — **не** браузерный стрим, а:

```powershell
# Статус: профиль, пики L/R, signal_state, dc_offset, clip_count
curl.exe http://192.168.0.171/api/audio

# WAV-клип последних 2 с из ring buffer
curl.exe "http://192.168.0.171/api/audio/clip?ms=2000" --output mic_test.wav

# Смена профиля без перепрошивки
curl.exe -X POST http://192.168.0.171/api/audio `
  -H "Content-Type: application/json" `
  -d '{"profile":"inmp441_philips32_stereo","software_gain":7.0,"dc_block":true}'
```

Встроенные профили:

| Профиль | Формат | Канал |
|---------|--------|-------|
| `inmp441_philips32_left` | Philips/32-bit | Левый |
| `inmp441_philips32_right` | Philips/32-bit | Правый |
| `inmp441_philips32_stereo` | Philips/32-bit | Стерео (default) |
| `inmp441_msb32_left` | MSB/32-bit | Левый |
| `inmp441_msb32_right` | MSB/32-bit | Правый |
| `inmp441_msb32_stereo` | MSB/32-bit | Стерео |
| `compat16_left` | Philips/16-bit | Левый |
| `compat16_right` | Philips/16-bit | Правый |

Mic ring buffer: **256 KB** в PSRAM (~4 с стерео при 16 kHz 16-bit).

---

## go2rtc

```yaml
streams:
  adams_cam:
    - ffmpeg:http://192.168.0.171:81/stream#video=mjpeg
    - ffmpeg:http://192.168.0.171:81/audio#audio=pcm_s16le#audio=16000
```

Быстрая проверка audio transport:

```powershell
ffmpeg -i http://192.168.0.171:81/audio -f null -
```

---

## PCA9685

Частота и активная сцена хранятся в NVS и восстанавливаются при каждой перезагрузке.

Текущие значения на устройстве: `freq=200 Hz`, `scene=test_all`.

Один канал:

```powershell
curl.exe -X POST http://192.168.0.171/api/pca9685/channel `
  -H "Content-Type: application/json" `
  -d '{"channel":0,"mode":"pwm","value":2048}'
```

Несколько каналов:

```powershell
curl.exe -X POST http://192.168.0.171/api/pca9685/channels `
  -H "Content-Type: application/json" `
  -d '{"channels":[{"channel":0,"mode":"pwm","value":2048},{"channel":1,"mode":"off"}]}'
```

Сцена:

```powershell
curl.exe -X POST http://192.168.0.171/api/pca9685/scene `
  -H "Content-Type: application/json" `
  -d '{"scene":"boot_idle"}'
```

Встроенные сцены: `boot_idle`, `test_all`, `all_on`, `alternating`.

Частота:

```powershell
curl.exe -X POST http://192.168.0.171/api/pca9685/frequency `
  -H "Content-Type: application/json" `
  -d '{"frequency":50}'
```

---

## Системные звуки

Boot-звук встроен в прошивку и проигрывается автоматически после инициализации `PCM5102A`.

Ручной тест:

```powershell
curl.exe -X POST "http://192.168.0.171/api/sound/play?name=boot"
curl.exe -X POST "http://192.168.0.171/api/sound/play?name=success"
curl.exe -X POST "http://192.168.0.171/api/sound/play?name=tone"
```

Формат embedded assets: mono, 44.1 kHz, 16-bit PCM.

---

## Полный список API-маршрутов

### Port 80 — Control

| Метод | Путь | Описание |
|-------|------|---------|
| GET | `/api/status` | Runtime-статус всех подсистем |
| GET | `/api/dashboard` | Агрегированный дашборд (для UI) |
| GET | `/api/sensors` | Сенсоры: свет, motion |
| GET | `/api/audio` | Состояние capture + playback |
| POST | `/api/audio` | Обновить профиль/параметры capture |
| GET | `/api/audio/clip?ms=N` | WAV-клип из ring buffer (250–4000 мс) |
| GET | `/api/camera` | Состояние и возможности камеры |
| POST | `/api/camera` | Применить настройки камеры |
| POST | `/api/camera/preset/apply` | Применить пресет |
| POST | `/api/camera/preset/save` | Сохранить пользовательский пресет |
| POST | `/api/camera/preset/delete` | Удалить пресет |
| POST | `/api/camera/preset/resetdefaults` | Сбросить встроенные пресеты |
| GET | `/capture` | Одиночный JPEG |
| GET | `/api/pca9685` | Состояние PCA9685 |
| POST | `/api/pca9685/channel` | Один канал |
| POST | `/api/pca9685/channels` | Несколько каналов |
| POST | `/api/pca9685/scene` | Сцена |
| POST | `/api/pca9685/frequency` | Частота PWM (сохраняется в NVS) |
| POST | `/api/sound/play?name=X` | Проиграть системный звук |
| GET | `/api/ota` | Статус OTA |
| POST | `/api/ota/upload` | Загрузить новую прошивку |
| POST | `/api/video_latency/reset` | Сбросить метрики видео-латентности |
| POST | `/api/system/reset` | Перезагрузить ESP32 |
| POST | `/api/system/stream/restart` | Перезапустить stream-сервер |
| GET | `/api/system/info` | Heap, uptime, минимальный heap |
| WS | `/ws` | Push-телеметрия |
| GET | `/audio` | → 301 redirect на `:81/audio` |
| POST | `/speaker` | → 301 redirect на `:81/speaker` |

### Port 81 — Streams

| Метод | Путь | Описание |
|-------|------|---------|
| GET | `/stream` | MJPEG-видеопоток |
| GET | `/audio` | Mic uplink (бесконечный WAV/PCM) |
| POST | `/speaker` | Playback sink (WAV или raw PCM) |

---

## Прошивка и COM-порты

```
COM7 = USB TO SERIAL (CH343)  → предпочтительный порт для прошивки
COM6 = USB OTG / CDC          → логи приложения; используется как fallback для прошивки
```

Скрипт умеет автоматически выбрать порт, откомпилировать и зашить:

```powershell
# Показать доступные COM-порты
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -ListPorts

# Сборка + прошивка (автовыбор порта)
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1

# Указать порт явно
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -Port COM6

# После прошивки сразу открыть serial monitor
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -Monitor

# Пропустить стирание flash (быстрее, NVS сохраняется)
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -SkipErase
```

Флаг `-SkipErase` сохраняет NVS-данные (частота PCA9685, сцена, camera-пресеты).

---

## OTA по Wi-Fi

Структура `partitions.csv` поддерживает двойной app-слот — OTA пишет в свободный слот, затем перезагружается.

Через браузер: `http://192.168.0.171/ota`

Через PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_ota.ps1 -Host 192.168.0.171
# С токеном:
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_ota.ps1 -Host 192.168.0.171 -Token YOUR_TOKEN
```

Нужен только основной бинарник `AdamsServer.ino.bin` (не bootloader, не partitions).

Через curl:

```powershell
curl.exe -X POST -H "Content-Type: application/octet-stream" `
  --data-binary "@AdamsServer.ino.bin" `
  http://192.168.0.171/api/ota/upload
```

---

## Структура папки

| Путь | Содержимое |
|------|-----------|
| `AdamsServer.ino` | Точка входа скетча |
| `config/AdamsConfig.h` | Все compile-time константы |
| `config/PrivateConfig.h` | Сетевые данные (не коммитится) |
| `config/PrivateConfig.example.h` | Шаблон PrivateConfig |
| `config/PinsConfig.h` | Распиновка всех модулей |
| `src/audio/` | I2S capture + playback |
| `src/camera/` | OV5640, MJPEG-стриминг |
| `src/core/` | Network (W5500/WiFi/AP), OTA, RuntimeState, boot diagnostics |
| `src/io/` | PCA9685, сенсоры |
| `src/web/` | HTTP-серверы (control + stream), весь UI |
| `tools/` | `flash_com7.ps1`, `flash_ota.ps1`, `arduino-cli.exe` |
| `artifacts/` | Диагностические файлы, WAV-клипы, логи |
| `docs/` | Runbook, эксплуатационные инструкции |
