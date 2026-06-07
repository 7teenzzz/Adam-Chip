# AdamsServer — ESP32-S3 Firmware Context

## Build system

PlatformIO (pio), не Python/pip.

- Сборка: `pio run`
- Flash (USB): `powershell -ExecutionPolicy Bypass -File tools/flash_com7.ps1`
- OTA (по сети): `powershell -ExecutionPolicy Bypass -File tools/flash_ota.ps1 -Host 192.168.0.171`
- COM7 = прошивка, COM6 = логи приложения (мониторинг)

## Запрещённые файлы — никогда не коммитить

- `config/PrivateConfig.h` — реальные учётные данные (в .gitignore)
- `config/credentials.h` — если появится, тоже не коммитить
- Шаблон для новой установки: `config/PrivateConfig.example.h`

## Hardware

- **Static IP (Ethernet):** 10.10.10.171 (W5500, изолированная подсеть 10.10.10.0/24 point-to-point с Jetson eno1=10.10.10.1). Wi-Fi/OTA-сеть: 192.168.0.171 (только для прошивки). Не менять без обновления прошивки.
- **Port 80:** HTTP API (`/api/*`) — основной управляющий интерфейс
- **Port 81:** stream-сервер — MJPEG camera (`/stream`) + mic audio (`/audio`, `/api/audio/clip`)
- **Port 82:** выделенный speaker-сервер — только `/speaker`. Своя FreeRTOS-задача, чтобы непрерывный mic-стрим (монополизирует задачу `:81`) не блокировал воспроизведение. `stream/restart` его не трогает.
- Не менять разделение 80/81/82 без синхронизации с `System/Config.json` (`mcu.base_url`, `mcu.speaker_url`) и `AdamsConfig.h` (`kStreamPort`, `kSpeakerServerPort`)

## Не делать

- Не запускать pio через Python или pip — только PlatformIO CLI
- Не менять IP-адрес без обновления `Config.json mcu.base_url` и `mcu.speaker_url`
- Не коммитить `PrivateConfig.h`
