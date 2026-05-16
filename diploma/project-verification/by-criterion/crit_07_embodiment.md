<!--
GENERATED: 2026-05-16T17:35:39Z
STAGE: 2
SOURCE: evaluation_criteria.md + graphify (crit-7)
STATUS: OK complete
RUN: Manual or CI-triggered
NEXT_UPDATE: manual trigger or when source changes
-->
# Criterion 7 вЂ” Р’РѕРїР»РѕС‰С‘РЅРЅРѕСЃС‚СЊ

## Theoretical Definition

РР· СЂР°Р·РґРµР»Р° 2.1.7: СЃС‚РµРїРµРЅСЊ РІРєР»СЋС‡С‘РЅРЅРѕСЃС‚Рё СЃРёСЃС‚РµРјС‹ РІ СЃСЂРµРґСѓ. Р§РµС‚С‹СЂРµ СѓСЂРѕРІРЅСЏ: СЃРёРјРІРѕР»РёС‡РµСЃРєР°СЏ в†’ РјСѓР»СЊС‚РёРјРѕРґР°Р»СЊРЅР°СЏ в†’ РІРёСЂС‚СѓР°Р»СЊРЅРѕ-РІРѕРїР»РѕС‰С‘РЅРЅР°СЏ в†’ С„РёР·РёС‡РµСЃРєР°СЏ.

## Implementation Status: **FULL** (С„РёР·РёС‡РµСЃРєР°СЏ)

Adam Chip вЂ” **С„РёР·РёС‡РµСЃРєР°СЏ РІРѕРїР»РѕС‰С‘РЅРЅРѕСЃС‚СЊ** С‡РµСЂРµР· ESP32 motor layer + РєР°РјРµСЂСѓ + Р°СѓРґРёРѕ + СЃРµРЅСЃРѕСЂС‹.

## Graphify Evidence

### Jetson-СЃС‚РѕСЂРѕРЅР° (graphify-out/)

| Node | File | Edges | Role |
|---|---|---|---|
| `MCUClient` | System/adam/device.py | 25 | СЃРІСЏР·СЊ СЃ ESP32 РїРѕ HTTP |
| `ActionLayer` | System/adam/action.py | вЂ” | РїРµСЂРµРІРѕРґ LLM С‚РµРіРѕРІ РІ MCU РєРѕРјР°РЅРґС‹ |
| `CameraReader` | System/adam/camera.py | 23 | Р·Р°С…РІР°С‚ РІРёРґРµРѕРїРѕС‚РѕРєР° |
| `SceneWorker` | System/Orchestrator.py | 30 | VLM Р°РЅР°Р»РёР· СЃС†РµРЅС‹ |
| `TTSClient` | System/adam/inference.py | 15 | TTS Р°СѓРґРёРѕ РІС‹РІРѕРґ (Silero) |
| `WhisperASRClient` | System/adam/inference.py | 15 | ASR Р°СѓРґРёРѕ РІС…РѕРґ (WhisperX) |

### ESP32 РїСЂРѕС€РёРІРєР° (graphify-out-esp32/) вЂ” РїРѕСЃС‚СЂРѕРµРЅ 2026-05-16

**780 nodes В· 1262 edges В· 42 communities**

| Node / Community | File | Edges | Role |
|---|---|---|---|
| `bootLogf()` | src/core/BootDiagnostics.cpp | 32 | god-node: РїСЂРѕРЅРёР·С‹РІР°РµС‚ РІСЃРµ 6 РїРѕРґСЃРёСЃС‚РµРј |
| `streamHandler()` | src/web/WebServerModule.cpp | 20 | MJPEG stream gate (РїРѕСЂС‚ 81) |
| `motorSkillsControlHandler()` | src/web/WebServerModule.cpp | 13 | PCA9685 web entry point |
| `playSystemSound()` | src/audio/SystemSoundModule.cpp | 12 | Р°СѓРґРёРѕ-РєСЊСЋ bridge |
| Community "Mic Audio Capture (I2S)" | src/audio/AudioModule.cpp | 37 nodes | INMP441 I2S RX, ring buffer 256KB |
| Community "Speaker Playback and Sounds" | src/audio/AudioModule.cpp | 16 nodes | PCM5102A I2S TX, ring buffer 32KB |
| Community "PCA9685 PWM Control" | src/io/Pca9685Module.cpp | 15 nodes | 16-ch PWM, NVS persistence, scenes |
| Community "Camera Capture and Presets" | src/camera/CameraModule.cpp | 38 nodes | OV5640 DVP, QVGA, MJPEG |
| Community "Environmental Sensors" | src/io/SensorModule.cpp | 5 nodes | TEMT6000 (ADC), BTE16-19 (GPIO) |
| Community "Boot Diagnostics and Init" | src/core/BootDiagnostics.cpp | 40 nodes | 10-step boot sequence |
| Community "Web Server Request Handlers" | src/web/WebServerModule.cpp | 93 nodes | 40+ API routes, РїРѕСЂС‚С‹ 80+81 |

**Hyperedges (РіСЂСѓРїРїС‹):**
- **ESP32 Dual HTTP Server Architecture** вЂ” port81_stream_server + api_mjpeg_stream + api_audio_stream + api_speaker_post [EXTRACTED 0.95]
- **Network Transport Priority Chain** вЂ” w5500_ethernet + wifi_fallback + ap_fallback [EXTRACTED 0.95]

## Verification Trace

1. `Config.json` в†’ `mcu.base_url: http://192.168.0.171` вЂ” СЂРµР°Р»СЊРЅРѕРµ С„РёР·РёС‡РµСЃРєРѕРµ СѓСЃС‚СЂРѕР№СЃС‚РІРѕ.
2. `Config.json` в†’ `mcu.allowed_scenes: ["boot_idle", "all_on", "alternating"]` вЂ” physical motor scenes.
3. `Config.json` в†’ `safety.motor_max_duration_ms: 2500`, `motor_cooldown_ms: 250` вЂ” С„РёР·РёС‡РµСЃРєРёРµ РѕРіСЂР°РЅРёС‡РµРЅРёСЏ.
4. `Config.json` в†’ `tts.output_device: plughw:1,3` вЂ” СЂРµР°Р»СЊРЅС‹Р№ HDMI ALSA РІС‹С…РѕРґ.
5. `Subsystem/AdamsServer/` вЂ” СЂРµР°Р»СЊРЅР°СЏ РїСЂРѕС€РёРІРєР° ESP32-S3.
6. Hardware spec РёР· README: ESP32-S3 + PCA9685 (16Г—12bit PWM) + OV5640 camera + 2Г—INMP441 mic + PCM5102A + PAM8403 + W5500 Ethernet + TEMT6000 light + BTE16-19 sensors.
7. `power.py` вЂ” Jetson power gate (MAXN, jetson_clocks).

## Findings

**РЎРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ В«С„РёР·РёС‡РµСЃРєРѕР№ РІРѕРїР»РѕС‰С‘РЅРЅРѕСЃС‚РёВ» (С‚Р°Р±Р»РёС†Р° 9):**

- вњ… РЎРІРµС‚РѕС„Р»РѕСЂР° (LED via PCA9685)
- вњ… РђСѓРґРёРѕС„Р»РѕСЂР° (PCM5102A speaker)
- вњ… Р’РёР±СЂРѕС„Р»РѕСЂР° (ESP32 GPIO motors)
- вњ… РљР°РјРµСЂР° (OV5640)
- вњ… РњРёРєСЂРѕС„РѕРЅС‹ (2Г— INMP441 stereo)
- вњ… РЎРµРЅСЃРѕСЂС‹ (light, rip вЂ” TEMT6000, BTE16-19)
- вњ… Network gateway (W5500 SPI Ethernet)
- вњ… Power management (Jetson power gate)

**РџРѕР»РЅС‹Р№ embodiment stack present.**

## РЎРІСЏР·СЊ СЃ РіР»Р°РІРѕР№ 3

- **Р Р°Р·РґРµР» 3.3.1** (С‚РµС…РЅРёС‡РµСЃРєР°СЏ СЂРµР°Р»РёР·Р°С†РёСЏ) вЂ” РѕРїРёСЃР°РЅРёРµ СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ hardware.
- **Р Р°Р·РґРµР» 3.3.2** (РїРµСЂС†РµРїС‚РёРІРЅС‹Р№/РјРѕС‚РѕСЂРЅС‹Р№ СЃР»РѕРё) вЂ” СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ С‚СЂС‘Рј С‚РёРїР°Рј С‚РµС…РЅРѕС„Р»РѕСЂС‹.
- **Р Р°Р·РґРµР» 3.3.3** (РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёРµ РњРљ) вЂ” СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ РїСЂРѕС€РёРІРєРµ ESP32-S3.
- **Р Р°Р·РґРµР» 3.3.4** (СЃС†РµРЅР°СЂРёР№) вЂ” С‡РµС‚С‹СЂРµ СЂРµР¶РёРјР° РїРѕРІРµРґРµРЅРёСЏ РѕРїРёСЂР°СЋС‚СЃСЏ РЅР° embodiment.

## Recommendations for Chapter 3

Р’ СЂР°Р·РґРµР»Рµ 3.3.2 СЏРІРЅРѕ РїРµСЂРµС‡РёСЃР»РёС‚СЊ hardware: PCA9685, OV5640, INMP441Г—2, PCM5102A, PAM8403, W5500, TEMT6000, BTE16-19. Р’ СЂР°Р·РґРµР»Рµ 3.3.3 вЂ” РѕРїРёСЃР°С‚СЊ `Subsystem/AdamsServer/` blocks: communication, motor, sensor + safety reset.


