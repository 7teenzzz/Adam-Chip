# Host UI (PC/Jetson)

Легкий хост-сервис, который:
- поднимает dashboard на ПК/Jetson,
- проксирует `GET/POST /api/v1/*` на ESP,
- оставляет ESP источником данных и стримов.

## Запуск

```powershell
cd F:\Adam-Chip
$env:ESP_BASE_URL="http://192.168.0.171"
python .\System\HostUI\server.py
```

По умолчанию:
- bind: `0.0.0.0`
- порт хост-UI: `8080`
- ESP base: `http://192.168.0.171`

Можно переопределить:

```powershell
$env:ADAM_HOST_UI_BIND="0.0.0.0"
$env:ADAM_HOST_UI_PORT="8080"
$env:ESP_BASE_URL="http://192.168.0.171"
```

## Маршруты

- `GET /` — хост-дэшборд (стримы + телеметрия)
- `GET /vision/live` — хост-страница видео
- `GET/POST /api/v1/*` — proxy на ESP
- остальные UI-маршруты (`/vision`, `/hearing`, `/sensorics`, `/motor_skills`, `/system`) редиректятся на ESP

Это соответствует гибридной схеме: UI на хосте, данные/стримы на ESP.
