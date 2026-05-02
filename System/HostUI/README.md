# Host UI Legacy Service

`System/HostUI/server.py` — legacy dashboard/proxy для текущей ESP32-прошивки.

Основной UI/API новой агентной системы теперь находится в:

```bash
python3 System/Orchestrator.py
```

Основные маршруты:

- `GET /` — dashboard orchestrator;
- `GET /api/agent/status` — состояние power/media/services/MCU;
- `GET /api/agent/events` — JSONL event tail;
- `POST /api/agent/turn` — тестовый диалоговый цикл;
- `POST /api/agent/say` — ручная озвучка;
- `POST /api/agent/stop` — остановка и перевод моторики в idle;
- `POST /api/agent/mode` — смена режима.

Legacy Host UI можно запускать только для диагностики ESP endpoints:

```bash
ESP_BASE_URL="http://192.168.0.171" python3 System/HostUI/server.py
```

После переключения ESP32 на прямой W5500 Ethernet с Jetson используйте:

```bash
ESP_BASE_URL="http://192.168.50.2" python3 System/HostUI/server.py
```
