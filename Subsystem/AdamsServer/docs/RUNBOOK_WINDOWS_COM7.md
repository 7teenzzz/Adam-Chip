# AdamsServer Runbook for Windows + COM7

Готовый набор команд и проверок для вашей текущей машины.

## Порты

- `COM7` = `USB TO SERIAL` -> использовать для прошивки
- `COM6` = `USB CDC / native USB` -> использовать для логов приложения

## Сеть

Приватные сетевые настройки лежат в:

- `Subsystem/AdamsServer/config/PrivateConfig.h`

Схема адреса такая:

- `ESP32_IP = 192.168.<kWifiSubnetOctet3>.<kWifiHostOctet>`

Рекомендуемые номера хоста:

- `17`
- `71`
- `171`

Текущая локальная настройка:

- `ESP32_IP = 192.168.0.171`

Если ваш роутер не в сети `192.168.0.x`, поменяйте только `kWifiSubnetOctet3` в `config/PrivateConfig.h` и перепрошейте устройство.

## Прошивка

Из корня проекта:

```powershell
cd F:\Adam-Chip
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -ListPorts
```

Основной рабочий запуск:

```powershell
cd F:\Adam-Chip
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -Port COM7 -MonitorPort COM6 -Monitor
```

Если нужен только compile:

```powershell
cd F:\Adam-Chip
.\Subsystem\AdamsServer\tools\arduino-cli.exe compile --fqbn "esp32:esp32:esp32s3:FlashMode=qio,FlashSize=16M,PartitionScheme=custom,PSRAM=opi,CDCOnBoot=cdc" --build-property "build.partitions=F:\Adam-Chip\Subsystem\AdamsServer\partitions.csv" Subsystem\AdamsServer
```

## Что должно появиться в логах

После bootloader-строк на `COM6` ожидаются стадии:

- `stage=wifi`
- `stage=camera`
- `stage=mic`
- `stage=speaker`
- `stage=pca9685`
- `stage=web`
- `stage=running`

Главный диагностический признак нормального старта:

- heartbeat с `wifi=up`
- IP-адрес устройства
- `web=up`

## Базовые URL после старта

- `http://ESP32_IP/`
- `http://ESP32_IP/live`
- `http://ESP32_IP/ota`
- `http://ESP32_IP:81/stream`
- `http://ESP32_IP/audio`
- `http://ESP32_IP/api/audio`
- `http://ESP32_IP/api/audio/clip?ms=2000`
- `http://ESP32_IP/api/ota`
- `http://ESP32_IP/api/status`
- `http://ESP32_IP/api/sensors`
- `http://ESP32_IP/api/camera`
- `http://ESP32_IP/api/pca9685`

## OTA по Wi‑Fi

### 1. Через встроенную страницу

- откройте `http://ESP32_IP/ota`
- выберите основной файл прошивки `.bin`
- дождитесь сообщения о перезагрузке

### 2. Через PowerShell-скрипт

```powershell
cd F:\Adam-Chip
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_ota.ps1 -Host ESP32_IP
```

Если включен токен:

```powershell
cd F:\Adam-Chip
powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_ota.ps1 -Host ESP32_IP -Token YOUR_TOKEN
```

### 3. Через curl

```powershell
curl.exe -X POST ^
  -H "Content-Type: application/octet-stream" ^
  --data-binary "@AdamsServer.ino.bin" ^
  http://ESP32_IP/api/ota/upload
```

Если включен токен OTA:

```powershell
curl.exe -X POST ^
  -H "Content-Type: application/octet-stream" ^
  -H "X-OTA-Token: YOUR_TOKEN" ^
  --data-binary "@AdamsServer.ino.bin" ^
  http://ESP32_IP/api/ota/upload
```

## Микрофон и PCM5102 — не путать

В прошивке есть два независимых аудиоканала:

- `INMP441` = вход / микрофон / `GET /audio`
- `PCM5102` = выход / playback / `POST /speaker`

`PCM5102` не участвует в микрофонном capture-тракте.

## Как диагностировать микрофон

### 1. Сначала смотреть JSON, а не слушать бесконечный `/audio` в браузере

```powershell
curl.exe http://ESP32_IP/api/audio
```

Ищите:

- `capture.profile`
- `capture.left_peak`
- `capture.right_peak`
- `capture.selected_peak`
- `capture.average_level`
- `capture.signal_state`
- `playback.*` отдельно

### 2. Получить конечный WAV-клип

```powershell
curl.exe http://ESP32_IP/api/audio/clip?ms=2000 --output mic_test.wav
```

Это основной ручной тест микрофона.

### 3. Сменить runtime-profile без перепрошивки

```powershell
curl.exe -X POST http://ESP32_IP/api/audio ^
  -H "Content-Type: application/json" ^
  -d "{\"profile\":\"inmp441_philips32_left\",\"software_gain\":1.0,\"dc_block\":true,\"slot\":1,\"shift\":14}"
```

Доступные профили:

- `inmp441_philips32_left`
- `inmp441_philips32_right`
- `inmp441_msb32_left`
- `inmp441_msb32_right`
- `compat16_left`
- `compat16_right`

### 4. Машинная проверка бесконечного потока

```powershell
ffmpeg -i http://ESP32_IP/audio -f null -
```

## Видео и go2rtc

Рекомендуемая схема для `go2rtc`:

```yaml
streams:
  adams_cam:
    - ffmpeg:http://ESP32_IP:81/stream#video=mjpeg
    - ffmpeg:http://ESP32_IP/audio#audio=pcm_s16le#audio=16000
```

Локальная проверка видео:

```powershell
ffmpeg -fflags nobuffer -flags low_delay -f mjpeg -i http://ESP32_IP:81/stream -f null -
```

## Playback на PCM5102

WAV-файл:

```powershell
curl.exe --data-binary "@input.wav" -H "Content-Type: audio/wav" http://ESP32_IP/speaker
```

Поток через `ffmpeg`:

```powershell
ffmpeg -re -i input.wav -f s16le -acodec pcm_s16le -ac 1 -ar 16000 -chunked_post 0 http://ESP32_IP/speaker
```

## PCA9685

Статус:

```powershell
curl.exe http://ESP32_IP/api/pca9685
```

Один канал:

```powershell
curl.exe -X POST http://ESP32_IP/api/pca9685/channel -H "Content-Type: application/json" -d "{\"channel\":0,\"mode\":\"pwm\",\"value\":2048}"
```

Сцена:

```powershell
curl.exe -X POST http://ESP32_IP/api/pca9685/scene -H "Content-Type: application/json" -d "{\"scene\":\"all_on\"}"
```
