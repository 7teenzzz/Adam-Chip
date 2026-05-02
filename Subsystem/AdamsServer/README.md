# AdamsServer Firmware

`AdamsServer` — это прошивка для `ESP32-S3 WROOM CAM`, которая после старта работает по `Wi‑Fi` и публикует:

- `MJPEG` видео по `HTTP`
- uplink-аудио с `INMP441` через `GET /audio`
- playback-аудио на `PCM5102` через `POST /speaker`
- telemetry по сенсорам
- low-level управление `PCA9685`

## Важно: актуальная иерархия UI/API

В текущей версии используется 2-уровневая схема:

- UI уровень 1: `/` (операционный дашборд: стримы + телеметрия + ключевые статусы)
- UI уровень 2: `/ctrldash` (управление и настройки: камера, аудио, PCA9685, OTA, endpoint-health)
- API/техдоступ: legacy маршруты `/api/*`, `/ws`, `:81/stream`, `:82/audio`, `:83/speaker`

Legacy UI пути (`/vision`, `/hearing`, `/sensorics`, `/motor_skills`, `/system`) сохранены и ведут на рабочие уровни интерфейса.

## Важное разделение аудио

В прошивке есть два независимых аудионаправления:

- `INMP441` = вход / микрофон / uplink / `GET /audio`
- `PCM5102` = выход / playback / `POST /speaker`

`PCM5102` не участвует в тракте микрофона и не должен использоваться для диагностики `INMP441`.

## Рабочая схема подключения

- `COM7` = `USB TO SERIAL` -> использовать для прошивки
- `COM6` = `USB OTG / native USB CDC` -> использовать для логов приложения

После старта устройство должно работать по `Wi‑Fi`, без постоянного USB.

## Статический IP

В прошивке можно зафиксировать IP-адрес ESP32, чтобы не искать его после каждой перезагрузки.

Приватные сетевые настройки теперь лежат в локальном файле [config/PrivateConfig.h](F:\Adam-Chip\Subsystem\AdamsServer\config\PrivateConfig.h), а шаблон — в [config/PrivateConfig.example.h](F:\Adam-Chip\Subsystem\AdamsServer\config\PrivateConfig.example.h).

Схема адреса такая:

- итоговый IP устройства = `192.168.<kWifiSubnetOctet3>.<kWifiHostOctet>`

Рекомендуемые номера хоста:

- `17`
- `71`
- `171`

Текущая локальная настройка:

- `kWifiSubnetOctet3 = 0`
- `kWifiHostOctet = 171`

Значит текущий адрес ESP32:

- `192.168.0.171`

Если у вас другая сеть, например `192.168.1.x`, достаточно поменять только:

- `kWifiSubnetOctet3 = 1`

Если хотите другой хост-адрес, меняется только:

- `kWifiHostOctet = 17` или `71` или `171`

## W5500 Ethernet

Прошивка поддерживает `W5500 MINI` через штатный `ETH.h` из Arduino-ESP32. Сейчас активный транспорт по умолчанию остаётся `Wi‑Fi`:

- `kNetworkTransport = AdamsNetworkTransport::WiFi`
- текущий адрес ESP32 остаётся `192.168.0.171`

Для прямого кабеля Jetson ↔ W5500 переключите транспорт на `AdamsNetworkTransport::EthernetW5500` или соберите с `-DADAMS_NETWORK_TRANSPORT_ETHERNET_W5500=1`.

Статическая Ethernet-схема:

- Jetson NIC: `192.168.50.1/24`
- ESP32 W5500: `192.168.50.2/24`
- `ESP_BASE_URL=http://192.168.50.2`
- `ESP_SPEAKER_URL=http://192.168.50.2:83/speaker`

После переключения те же endpoint-ы работают на Ethernet host: `http://192.168.50.2`, `:81/stream`, `:82/audio`, `:83/speaker`.

## Структура папки

- `Subsystem/AdamsServer` - входная точка скетча и build-файлы
- `Subsystem/AdamsServer/config` - конфиги платы и прошивки
- `Subsystem/AdamsServer/config/PrivateConfig.h` - локальные приватные данные, не коммитится
- `Subsystem/AdamsServer/config/PrivateConfig.example.h` - шаблон приватного конфига
- `Subsystem/AdamsServer/src/audio` - модуль микрофона и speaker playback
- `Subsystem/AdamsServer/src/camera` - камера и встроенные camera assets
- `Subsystem/AdamsServer/src/core` - runtime state и boot diagnostics
- `Subsystem/AdamsServer/src/io` - сенсоры и PCA9685
- `Subsystem/AdamsServer/src/web` - HTTP API и web UI
- `Subsystem/AdamsServer/tools` - `flash_com7.ps1` и `arduino-cli.exe`
- `Subsystem/AdamsServer/docs` - runbook и эксплуатационные инструкции
- `Subsystem/AdamsServer/artifacts` - временные диагностические файлы, клипы и HTML-дампы

## Основные endpoint-ы

- `GET /` - русифицированная диагностическая панель
- `GET /ctrldash` - панель управления и настроек
- `GET /live` - легкая страница только с видео
- `GET /ota` - страница обновления прошивки по Wi‑Fi
- `GET http://ESP32_IP:81/stream` - MJPEG video
- `GET http://ESP32_IP/audio` - бесконечный mic uplink как `WAV/PCM`
- `GET http://ESP32_IP/api/audio` - полная audio diagnostics
- `POST http://ESP32_IP/api/audio` - runtime-config capture-профиля микрофона
- `GET http://ESP32_IP/api/audio/clip?ms=2000` - конечный WAV-клип из ring buffer
- `POST http://ESP32_IP/speaker` - playback sink для `PCM5102`
- `GET http://ESP32_IP/capture` - одиночный JPEG
- `GET http://ESP32_IP/api/status` - общий runtime status
- `GET http://ESP32_IP/api/ota` - статус OTA
- `POST http://ESP32_IP/api/ota/upload` - загрузка новой прошивки по Wi‑Fi
- `GET http://ESP32_IP/api/sensors` - snapshot сенсоров
- `GET http://ESP32_IP/api/camera` - camera state/capabilities
- `POST http://ESP32_IP/api/camera` - применить camera settings
- `POST http://ESP32_IP/api/camera/preset/apply` - применить camera preset
- `POST http://ESP32_IP/api/camera/preset/save` - сохранить camera preset
- `POST http://ESP32_IP/api/camera/preset/delete` - удалить user preset
- `POST http://ESP32_IP/api/camera/preset/resetdefaults` - сбросить встроенные presets
- `GET http://ESP32_IP/api/pca9685` - состояние `PCA9685`
- `POST http://ESP32_IP/api/pca9685/channel` - один канал
- `POST http://ESP32_IP/api/pca9685/channels` - несколько каналов
- `POST http://ESP32_IP/api/pca9685/scene` - сцена
- `POST http://ESP32_IP/api/pca9685/frequency` - частота PWM
- `POST http://ESP32_IP/api/sound/play` - проиграть встроенный системный звук `boot`
- `WS http://ESP32_IP/ws` - push telemetry

## Микрофон: как проверять правильно

`GET /audio` нужен в первую очередь для `ffmpeg` / `go2rtc`, а не как главный ручной тест через браузер.

Для ручной проверки микрофона используйте:

- `GET /api/audio` — чтобы посмотреть профиль, пики `left/right`, `signal_state`, `dc_offset`, `clip_count`
- `GET /api/audio/clip?ms=2000` — чтобы открыть конечный WAV и нормально прослушать последние 2 секунды

Пример диагностики:

```powershell
curl.exe http://ESP32_IP/api/audio
```

Пример получения тестового клипа:

```powershell
curl.exe http://ESP32_IP/api/audio/clip?ms=2000 --output mic_test.wav
```

Пример смены capture-профиля без перепрошивки:

```powershell
curl.exe -X POST http://ESP32_IP/api/audio ^
  -H "Content-Type: application/json" ^
  -d "{\"profile\":\"inmp441_philips32_left\",\"software_gain\":1.0,\"dc_block\":true,\"slot\":1,\"shift\":14}"
```

Встроенные профили:

- `inmp441_philips32_left`
- `inmp441_philips32_right`
- `inmp441_msb32_left`
- `inmp441_msb32_right`
- `compat16_left`
- `compat16_right`

## go2rtc

Пример `go2rtc.yaml`:

```yaml
streams:
  adams_cam:
    - ffmpeg:http://ESP32_IP:81/stream#video=mjpeg
    - ffmpeg:http://ESP32_IP/audio#audio=pcm_s16le#audio=16000
```

Для быстрой проверки audio transport:

```powershell
ffmpeg -i http://ESP32_IP/audio -f null -
```

## Прошивка и порты

Один основной скрипт:

```powershell
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -ListPorts
```

Он умеет:

- показать диагностику по `COM`-портам
- подобрать upload/monitor порты
- собрать прошивку
- прошить ESP32
- открыть serial monitor при ключе `-Monitor`

## OTA по Wi‑Fi

Разметка `partitions.csv` уже подходит для OTA:

- есть `otadata`
- есть два app-слота: `app0` и `app1`

Это значит, что новая прошивка записывается в свободный app-слот, а затем ESP32 перезагружается уже в него.

Способы обновления:

- через встроенную страницу `http://ESP32_IP/ota`
- через PowerShell-скрипт `tools/flash_ota.ps1`
- через `curl` на `POST /api/ota/upload`

PowerShell:

```powershell
cd F:\Adam-Chip
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_ota.ps1 -Host ESP32_IP
```

Если включен токен OTA в `config/PrivateConfig.h`:

```powershell
cd F:\Adam-Chip
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_ota.ps1 -Host ESP32_IP -Token YOUR_TOKEN
```

Прямой upload через `curl`:

```powershell
curl.exe -X POST ^
  -H "Content-Type: application/octet-stream" ^
  --data-binary "@AdamsServer.ino.bin" ^
  http://ESP32_IP/api/ota/upload
```

Важно:

- нужен именно основной бинарник приложения, например `AdamsServer.ino.bin`
- не нужно отправлять `bootloader.bin`
- не нужно отправлять `partitions.bin`

## Speaker playback с ПК

`POST /speaker` ожидает:

- `mono`
- `16 kHz`
- `16-bit PCM`

WAV-файл:

```powershell
curl.exe --data-binary "@input.wav" -H "Content-Type: audio/wav" http://ESP32_IP/speaker
```

Поток через `ffmpeg`:

```powershell
ffmpeg -re -i input.wav -f s16le -acodec pcm_s16le -ac 1 -ar 16000 -chunked_post 0 http://ESP32_IP/speaker
```

## Системные звуки ESP

Boot-cue больше не отправляется с Jetson при каждом старте. Он встроен в
прошивку как flash/PROGMEM PCM и проигрывается самой ESP после успешной
инициализации `PCM5102`. `success` cue тоже встроен в прошивку и может быть
вызван вручную через тот же API.

Исходный asset:

- `Subsystem/AdamsServer/data/sounds/boot.wav`
- `Subsystem/AdamsServer/data/sounds/success.wav`
- формат embedded playback assets: `mono`, `44.1 kHz`, `16-bit PCM`

Ручной тест после прошивки:

```powershell
curl.exe -X POST "http://ESP32_IP/api/sound/play?name=boot"
curl.exe -X POST "http://ESP32_IP/api/sound/play?name=tone"
curl.exe -X POST "http://ESP32_IP/api/sound/play?name=success"
```

## PCA9685

Один канал:

```powershell
curl.exe -X POST http://ESP32_IP/api/pca9685/channel -H "Content-Type: application/json" -d "{\"channel\":0,\"mode\":\"pwm\",\"value\":2048}"
```

Сцена:

```powershell
curl.exe -X POST http://ESP32_IP/api/pca9685/scene -H "Content-Type: application/json" -d "{\"scene\":\"all_on\"}"
```
