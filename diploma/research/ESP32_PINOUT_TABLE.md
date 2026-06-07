# ESP32-S3 N16R8 WROOM CAM Pin-out Configuration

**Source:** `Subsystem/AdamsServer/config/PinsConfig.h`  
**Board:** ESP32-S3 N16R8 WROOM CAM  
**Static IP:** 192.168.0.171  
**Interfaces:** HTTP (port 80), Speaker/Video (port 81)

---

## I. Camera — OV5640

| Function | GPIO | Purpose |
|----------|------|---------|
| XCLK | 15 | Camera clock (MIPI CSI) |
| SIOD (I2C SDA) | 4 | Camera config I2C data |
| SIOC (I2C SCL) | 5 | Camera config I2C clock |
| Y9 (MSB) | 16 | Data bit 9 |
| Y8 | 17 | Data bit 8 |
| Y7 | 18 | Data bit 7 |
| Y6 | 12 | Data bit 6 |
| Y5 | 10 | Data bit 5 |
| Y4 | 8 | Data bit 4 |
| Y3 | 9 | Data bit 3 |
| Y2 | 11 | Data bit 2 |
| VSYNC | 6 | Vertical sync |
| HREF | 7 | Horizontal sync |
| PCLK | 13 | Pixel clock |

**Output:** 640×480 JPEG, quality=75, ~30fps MJPEG stream to `http://192.168.0.171:81/stream`

---

## II. Microphone — INMP441 × 2 (I2S Stereo)

| Function | GPIO | Protocol | Purpose |
|----------|------|----------|---------|
| BCLK | 48 | I2S | Bit clock (shared, mono/stereo selection via hardware) |
| LRCLK / WS | 47 | I2S | Word select (mono/stereo selection) |
| DATA | 21 | I2S | Serial data (time-division multiplex) |

**Configuration:**
- Mic 1 (L channel): activated when WS=LOW, L/R tied to GND
- Mic 2 (R channel): activated when WS=HIGH, L/R tied to VDD
- Single data line (SD) with multiplexing ensures no pin conflicts
- Inactive mic transitions to Hi-Z (high impedance)
- Sample rate: 16000 Hz (configured in `System/Config.json`)
- Format: Philips 32-bit stereo, TDM mode

**Input:** Dual INMP441 microphones → I2S data stream

---

## III. Speaker — PCM5102A (I2S DAC)

| Function | GPIO | Protocol | Purpose |
|----------|------|----------|---------|
| BCLK | 38 | I2S | Bit clock |
| LRCK / WS | 39 | I2S | Word select (left/right channel) |
| DATA | 40 | I2S | Serial audio data |
| MCLK | GND | — | Master clock (tied to ground) |

**Output:** 24kHz PCM → PCM5102A DAC → HDMI audio (via PAM8403 amplifier)  
**Control:** HTTP endpoint `http://192.168.0.171:81/speaker` for audio streaming

---

## IV. Sensors

| Function | GPIO | Protocol | Type | Purpose |
|----------|------|----------|------|---------|
| Light Sensor | 1 | ADC | TEMT6000 | Ambient light measurement (0–3.3V analog) |
| Motion Sensor | 2 | GPIO | BTE16-19 | Digital presence detection |

**Usage:** Scene context for VLM (VILA) — "Is the installation illuminated? Is someone present?"

---

## V. Motor Control — PCA9685 PWM Controller

| Function | GPIO | Protocol | Purpose |
|----------|------|----------|---------|
| SDA | 43 | I2C | Data line (4.7K pull-up resistor) |
| SCL | 44 | I2C | Clock line (4.7K pull-up resistor) |

**Channels:** 16 × 12-bit PWM outputs (channels 0–15)  
**Current usage:** Channels allocated for installation art motor control  
**Command:** `/api/pwm/channel/{N}/set?value={0-4095}` (HTTP API)

**Motor Parameters:**
- Default duration: 900ms (`safety.motor_default_duration_ms`)
- Max duration: 2500ms (`safety.motor_max_duration_ms`)
- Cooldown between commands: 250ms (`safety.motor_cooldown_ms`)
- Allowed scenes: boot_idle, all_on, alternating

---

## VI. Network — W5500 Ethernet

| Function | GPIO | Protocol | Purpose |
|----------|------|----------|---------|
| SCK | 14 | SPI | Clock |
| MISO | 42 | SPI | Input (hardware note: W5500 labels as MI, physically ESP MISO) |
| MOSI | 46 | SPI | Output (hardware note: W5500 labels as MO, physically ESP MOSI) |
| CS | 41 | SPI | Chip select |
| INT | (not connected) | — | Polling mode (W5500 not interrupt-driven) |
| RST | GND via 10kΩ | — | Reset (pulled to 3.3V via resistor) |

**Configuration:**
- Static IP: 192.168.0.171
- DNS: none (static IP only)
- Port 80: HTTP API (`/api/*` endpoints)
- Port 81: Speaker (`/speaker`) + MJPEG camera (`/stream`)
- No Wi-Fi (Ethernet only for reliability in exhibition)

---

## VII. GPIO Summary

**Used (47 pins):**
- Camera (CSI): 15, 4, 5, 16, 17, 18, 12, 10, 8, 9, 11, 6, 7, 13 (14 pins)
- Microphone (I2S): 48, 47, 21 (3 pins)
- Speaker (I2S): 38, 39, 40 (3 pins)
- Sensors: 1, 2 (2 pins)
- Motor control (I2C): 43, 44 (2 pins)
- Network (SPI): 14, 42, 46, 41 (4 pins)
- **Total: 28 pins active**

**Reserved (do not use):**
- GPIO 0: BOOT (strapping pin)
- GPIO 3: Strapping pin
- GPIO 19, 20: USB OTG
- GPIO 46: Strapping / ROM debug
- GPIO 48: WS2812 LED (internal)

**Not available on this board:**
- GPIO 33, 34: Not exposed on connectors
- GPIO 35–37: Internal PSRAM, not exposed

**Available for future expansion:**
- GPIO 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 36, 37, 45, 49, 50, 51 (partial list — check datasheet)

---

## VIII. Power Distribution

| System | Voltage | Current (approx.) |
|--------|---------|-------------------|
| ESP32-S3 SoC | 3.3V | ~100mA (avg), ~300mA (peak) |
| INMP441 × 2 Microphones | 3.3V | ~20mA |
| PCM5102A DAC | 3.3V | ~30mA (idle), ~100mA (audio) |
| OV5640 Camera | 3.3V | ~150mA (video capture) |
| W5500 Ethernet | 3.3V | ~120mA |
| PCA9685 + Motors | 5V or 3.3V (configurable) | 500mA–1A (depends on motor load) |
| TEMT6000 Light Sensor | 3.3V | ~1mA |
| BTE16-19 Motion Sensor | 3.3V | <1mA |

**Total @ 3.3V:** ~400mA (idle), ~800mA (all features active)  
**Total @ 5V (motors):** ~1A peak

---

## IX. Communication Protocol Summary

| Interface | Protocol | Speed | Devices |
|-----------|----------|-------|---------|
| MIPI CSI | Camera link | 30fps | OV5640 camera |
| I2S | Digital audio | 16kHz (input), 24kHz (output) | INMP441 × 2, PCM5102A |
| I2C | Bus | 400kHz | PCA9685, OV5640 (config) |
| SPI | Bus | 25MHz | W5500 Ethernet |
| GPIO | Digital I/O | — | Light sensor (ADC), Motion sensor (digital) |
| HTTP | TCP/IP | 100Mbps | Jetson Orchestrator (port 80, 81) |

---

## X. Jetson ↔ ESP32 Communication Flow

```
Jetson Orin NX (FastAPI Orchestrator)
    ↓ HTTP POST
    192.168.0.171:80/api/pwm/channel/N/set?value=V
    ↓
ESP32-S3 HTTP Server (port 80)
    ↓
PCA9685 I2C Driver
    ↓ I2C
GPIO 43 (SDA), GPIO 44 (SCL)
    ↓
PCA9685 PWM Controller
    ↓ PWM
GPIO channels 0–15 → Motors
```

**Example:** Agent decides on "warm" animation
1. `System/adam/action.py` → decision: scene="warm"
2. Jetson HTTP POST: `/api/pwm/channel/7/set?value=2048` (50% duty)
3. ESP32 receives, updates PCA9685 register
4. Motor 7 receives 50% PWM signal
5. Motor activation: ~100ms latency (polling-based, not interrupt-driven)

---

## XI. Configuration Files

**Hardware config:** `Subsystem/AdamsServer/config/PinsConfig.h`  
**Software config:** `System/Config.json` (Jetson-side parameters)  
**Secrets:** `Subsystem/AdamsServer/config/PrivateConfig.h` (not in git, template: `PrivateConfig.example.h`)

---

## Usage in Chapter 3

**3.3.2 (Perceptual and Motor Layers):**
- Table 3.3.1: Pin-out summary (this document)
- Figure 3.3.2: Block diagram of connections

**3.3.3 (Firmware Programming):**
- Reference PinsConfig.h for I2C/I2S/SPI protocols
- Explain why static IP (reliability for installation) instead of Wi-Fi

**3.3.4 (Interaction Scenarios):**
- Motor response time: 100ms (SPI → I2C → PWM)
- Scene analysis cycle: every 4s (Config: `media.scene_interval_sec`)
