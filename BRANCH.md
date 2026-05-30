# Branch: V-R09.2-OV7670-fix

**Diverged from:** main @ 597fb61
**Goal:** Перевести видео-ввод Адама исключительно на камеру ESP32 (OV7670, подключена напрямую к ESP32-S3 по DVP). Сейчас Адам использует Jetson-вебкамеру, потому что `CameraReader` свалился в `jetson_fallback` на сломанном OV5640. Цель — убрать fallback на вебкамеру: ESP32-камера используется эксклюзивно, при сбое — бесконечный retry (как у микрофона `disable_local_fallback`). Логика стрима и VLM не меняется — только устройство ввода.
**Status:** executing
**Merge target:** main
**Merge conditions:**

- Firmware OV7670 прошита на ESP32 (dual-path detection из commit 597fb61), `/capture` (порт 80) отдаёт валидный JPEG
- На Jetson проверено: `camera_reader.active_source == "esp"` стабильно, `jetson_fallback` не активируется
- VLM получает кадры с ESP32 (`vlm_request_started` события с `camera_source: esp`)
- Smoke-тест: отключение/сбой ESP32 → `camera_error` с `fallback: disabled`, после восстановления кадры идут снова, вебкамера ни разу не использована

**Modified areas:**

- `System/Config.json` — `media.video.disable_jetson_fallback = true` (branch-only эксперимент)
- `System/Config.schema.json` — документация `disable_jetson_fallback`
- `System/adam/camera.py` — `CameraReader`: флаг `disable_jetson_fallback`, блокировка перехода в `jetson_fallback`, throttle `camera_error` во время сбоя, re-read флага в `apply_config`
- `BRANCH.md` — этот файл (был устаревший от V-S09.1-Audio_out)

**Не трогаем (готово в коде):**

- `Subsystem/AdamsServer/` — firmware OV7670 dual-path уже в commit 597fb61 (detection, SW-JPEG `frame2jpg`, per-model XCLK, preset filter)
- `System/Orchestrator.py` / `SceneWorker` — источник-независимы, читают `camera_reader.get_latest()`, изменений не требуют
- `System/adam/inference.py` `VLMClient` — без изменений

**Global changes:**

- Изменение Config.json помечено как **branch-only**: `disable_jetson_fallback=true` живёт на этой ветке, в main попадёт только после проверки на железе. Schema-дефолт = `false` (обратная совместимость для dev без ESP).

**Notes for agents:**

- Распиновка OV7670↔ESP32 совпадает с `Subsystem/AdamsServer/config/PinsConfig.h` (XCLK→15, SIOD→4, SIOC→5, D7→16…D0→11, VSYNC→6, HREF→7, PCLK→13). RESET→3.3V, PWDN→GND ⇒ оба пина `-1` (не управляются GPIO).
- `esp_mjpeg_url = http://10.10.10.171:81/stream`; snapshot URL для per-frame захвата выводится из hostname → `http://10.10.10.171/capture` (порт 80). Не путать с MJPEG-стримом на `:81`.
- ⚠️ Гигиена истории: эта ветка несёт неслитые в main коммиты Phase 29 (Audio Out на ESP32, `feat(29)…`). Они НЕ относятся к камере — разбирать/мёржить отдельно, не смешивать с камерным PR.
- `disable_jetson_fallback` влияет только при `primary='esp_mjpeg'`. Для разработки без ESP32 ставить `primary='jetson_gstreamer'` (флаг тогда иррелевантен) — не выключать флаг в Config.json.
