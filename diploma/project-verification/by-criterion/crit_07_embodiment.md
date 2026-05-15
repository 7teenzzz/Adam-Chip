# Criterion 7 — Воплощённость

## Theoretical Definition

Из раздела 2.1.7: степень включённости системы в среду. Четыре уровня: символическая → мультимодальная → виртуально-воплощённая → физическая.

## Implementation Status: **FULL** (физическая)

Adam Chip — **физическая воплощённость** через ESP32 motor layer + камеру + аудио + сенсоры.

## Graphify Evidence

### Jetson-сторона (graphify-out/)

| Node | File | Edges | Role |
|---|---|---|---|
| `MCUClient` | System/adam/device.py | 25 | связь с ESP32 по HTTP |
| `ActionLayer` | System/adam/action.py | — | перевод LLM тегов в MCU команды |
| `CameraReader` | System/adam/camera.py | 23 | захват видеопотока |
| `SceneWorker` | System/Orchestrator.py | 30 | VLM анализ сцены |
| `TTSClient` | System/adam/inference.py | 15 | TTS аудио вывод (Silero) |
| `WhisperASRClient` | System/adam/inference.py | 15 | ASR аудио вход (WhisperX) |

### ESP32 прошивка (graphify-out-esp32/) — построен 2026-05-16

**780 nodes · 1262 edges · 42 communities**

| Node / Community | File | Edges | Role |
|---|---|---|---|
| `bootLogf()` | src/core/BootDiagnostics.cpp | 32 | god-node: пронизывает все 6 подсистем |
| `streamHandler()` | src/web/WebServerModule.cpp | 20 | MJPEG stream gate (порт 81) |
| `motorSkillsControlHandler()` | src/web/WebServerModule.cpp | 13 | PCA9685 web entry point |
| `playSystemSound()` | src/audio/SystemSoundModule.cpp | 12 | аудио-кью bridge |
| Community "Mic Audio Capture (I2S)" | src/audio/AudioModule.cpp | 37 nodes | INMP441 I2S RX, ring buffer 256KB |
| Community "Speaker Playback and Sounds" | src/audio/AudioModule.cpp | 16 nodes | PCM5102A I2S TX, ring buffer 32KB |
| Community "PCA9685 PWM Control" | src/io/Pca9685Module.cpp | 15 nodes | 16-ch PWM, NVS persistence, scenes |
| Community "Camera Capture and Presets" | src/camera/CameraModule.cpp | 38 nodes | OV5640 DVP, QVGA, MJPEG |
| Community "Environmental Sensors" | src/io/SensorModule.cpp | 5 nodes | TEMT6000 (ADC), BTE16-19 (GPIO) |
| Community "Boot Diagnostics and Init" | src/core/BootDiagnostics.cpp | 40 nodes | 10-step boot sequence |
| Community "Web Server Request Handlers" | src/web/WebServerModule.cpp | 93 nodes | 40+ API routes, порты 80+81 |

**Hyperedges (группы):**
- **ESP32 Dual HTTP Server Architecture** — port81_stream_server + api_mjpeg_stream + api_audio_stream + api_speaker_post [EXTRACTED 0.95]
- **Network Transport Priority Chain** — w5500_ethernet + wifi_fallback + ap_fallback [EXTRACTED 0.95]

## Verification Trace

1. `Config.json` → `mcu.base_url: http://192.168.0.171` — реальное физическое устройство.
2. `Config.json` → `mcu.allowed_scenes: ["boot_idle", "all_on", "alternating"]` — physical motor scenes.
3. `Config.json` → `safety.motor_max_duration_ms: 2500`, `motor_cooldown_ms: 250` — физические ограничения.
4. `Config.json` → `tts.output_device: plughw:1,3` — реальный HDMI ALSA выход.
5. `Subsystem/AdamsServer/` — реальная прошивка ESP32-S3.
6. Hardware spec из README: ESP32-S3 + PCA9685 (16×12bit PWM) + OV5640 camera + 2×INMP441 mic + PCM5102A + PAM8403 + W5500 Ethernet + TEMT6000 light + BTE16-19 sensors.
7. `power.py` — Jetson power gate (MAXN, jetson_clocks).

## Findings

**Соответствует «физической воплощённости» (таблица 9):**

- ✅ Светофлора (LED via PCA9685)
- ✅ Аудиофлора (PCM5102A speaker)
- ✅ Виброфлора (ESP32 GPIO motors)
- ✅ Камера (OV5640)
- ✅ Микрофоны (2× INMP441 stereo)
- ✅ Сенсоры (light, rip — TEMT6000, BTE16-19)
- ✅ Network gateway (W5500 SPI Ethernet)
- ✅ Power management (Jetson power gate)

**Полный embodiment stack present.**

## Связь с главой 3

- **Раздел 3.3.1** (техническая реализация) — описание соответствует hardware.
- **Раздел 3.3.2** (перцептивный/моторный слои) — соответствует трём типам технофлоры.
- **Раздел 3.3.3** (программирование МК) — соответствует прошивке ESP32-S3.
- **Раздел 3.3.4** (сценарий) — четыре режима поведения опираются на embodiment.

## Recommendations for Chapter 3

В разделе 3.3.2 явно перечислить hardware: PCA9685, OV5640, INMP441×2, PCM5102A, PAM8403, W5500, TEMT6000, BTE16-19. В разделе 3.3.3 — описать `Subsystem/AdamsServer/` blocks: communication, motor, sensor + safety reset.
