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

- **Static IP:** 192.168.0.171 (W5500 Ethernet, не Wi-Fi — не менять без прошивки)
- **Port 80:** HTTP API (`/api/*`) — основной управляющий интерфейс
- **Port 81:** отдельный HTTP-сервер — speaker (`/speaker`) + MJPEG camera (`/stream`)
- Не менять разделение 80/81 без синхронизации с `System/Config.json` (`mcu.base_url`, `mcu.speaker_url`)

## Не делать

- Не запускать pio через Python или pip — только PlatformIO CLI
- Не менять IP-адрес без обновления `Config.json mcu.base_url` и `mcu.speaker_url`
- Не коммитить `PrivateConfig.h`
