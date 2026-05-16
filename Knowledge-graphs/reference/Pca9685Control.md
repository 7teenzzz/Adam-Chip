# Reference: PCA9685 Motor Control — 16-Channel PWM + NVS Persistence

## Overview

The PCA9685 16-channel 12-bit PWM expander controls the technoflora motor layer (pneumatic actuators, servos, lights). This document describes the pin mapping, NVS scene persistence, command validation, and failover behavior.

## Hardware Layer

- **Device:** PCA9685 I2C PWM controller (16 channels, 12-bit resolution)
- **I2C interface:** Standard I2C pins on ESP32-S3 (SDA=17, SCL=18)
- **PWM frequency:** 50 Hz (configurable, typical for servo control)
- **Output voltage:** 5V (external power supply, isolated from Jetson/ESP32 logic)
- **Channels:** 0–15 (indexed), value range 0–4095 (12-bit), safety-mapped to 0–255 at REST

## Software Layer (ESP32 Firmware)

### Community: "PCA9685 and Motor Control" (16 nodes)

**Key functions:**
- `initPca9685()` — I2C device initialization at boot, scene restoration from NVS
- `setPwmChannel(ch, value)` — set single channel (1 call per request)
- `setPwmScene(name)` — bulk scene control (loads pre-calibrated motor sequences)
- `getPwmSceneCount()`, `getPwmSceneName(idx)` — scene enumeration
- `isPwmChannelValid(ch, value)` — validation gate (prevents out-of-range commands)
- `recordMotorCommand()` — telemetry / command history
- `Pca9685Module` — core class, thread-safe via portMUX spinlock access to RuntimeState.pwm_state

### NVS Persistence

**NVS namespace:** `pwm_scenes`

Each scene is stored as binary blob (JSON serialized):
```json
{
  "name": "boot_idle",
  "duration_ms": 900,
  "channels": [
    {"ch": 0, "value": 2048, "ramp_ms": 200},
    {"ch": 1, "value": 1024, "ramp_ms": 100},
    ...
  ]
}
```

**Scene restoration:** On boot, `initPca9685()` restores the last-active scene from NVS key `last_scene_name`. If key missing, defaults to `boot_idle`.

**Write-back:** After each scene activation via `/api/motor/scene`, new name is written to NVS `last_scene_name` key.

### Scene Whitelist (Safety Gate)

From `System/Config.json` → `mcu.allowed_scenes`:
```json
"allowed_scenes": ["boot_idle", "all_on", "alternating"]
```

**Validation logic:** Action layer checks every scene request:
1. LLM output parsed for scene name
2. If not in `allowed_scenes` → no action, fallback to `idle_scene` (`boot_idle`)
3. If valid → forward to `/api/motor/scene?name=<scene>`
4. MCU accepts only whitelisted names; rejects unknown scenes with HTTP 400

**Why whitelist exists:** Prevents motor runaway from hallucinated scene names, ensures museum-safe motion vocabulary.

## Configuration & Limits

From `System/Config.json`:

```json
"mcu": {
  "channels": {
    "min": 0,
    "max": 15,
    "value_min": 0,
    "value_max": 4095
  }
}
```

**Safety constraints** (from `safety` section):
- `motor_default_duration_ms`: 900 ms (default scene play duration)
- `motor_max_duration_ms`: 2500 ms (hard cap, prevents mechanical damage)
- `motor_cooldown_ms`: 250 ms (minimum time between consecutive commands)

**Channel mapping (example):**
```
Channel 0–3   : Pneumatic cylinders (fast strike, slow release)
Channel 4–7   : LED matrix (brightness levels)
Channel 8–11  : Servo motors (smooth trajectory)
Channel 12–15 : Auxiliary (reserved for future expansion)
```

## API Routes (WebServerModule, port 80)

### Set Single Channel
```
GET /api/motor/channel/<ch>/<value>
Parameters:
  ch: 0–15 (channel number)
  value: 0–4095 (PWM value)
Response: {"status": "ok", "channel": 5, "value": 2048}
Validation: isPwmChannelValid() checks range, returns 400 if invalid
Latency: <10 ms (direct I2C write)
```

### Set Scene (Bulk)
```
GET /api/motor/scene?name=<scene_name>
Parameters:
  name: must be in allowed_scenes whitelist
Response: {"status": "ok", "scene": "all_on", "duration_ms": 900}
Validation: Scene name checked against whitelist, 400 if unknown
Fallback: If request fails, motor goes to idle_scene after timeout
Latency: 5–50 ms depending on scene complexity
```

### Query Scene List
```
GET /api/motor/scenes
Response:
{
  "count": 3,
  "scenes": ["boot_idle", "all_on", "alternating"],
  "current": "boot_idle"
}
```

### Get Channel State
```
GET /api/motor/channel/<ch>
Response: {"channel": 5, "value": 2048, "last_update_ms": 1234567890}
```

## Motor Control Flow

```
Action Layer (Jetson)
  ↓
LLM outputs: "scene:alternating"
  ↓
ActionValidator.validate_scene() checks whitelist
  ↓
HTTP GET /api/motor/scene?name=alternating
  ↓
ESP32 WebServerModule::motorSceneHandler()
  ↓
Pca9685Module::setPwmScene("alternating")
  ↓
Load scene from NVS or RAM cache
  ↓
I2C write all 16 channel values (synchronized)
  ↓
Record command in RuntimeState for telemetry
  ↓
NVS write: last_scene_name = "alternating"
  ↓
HTTP 200 response to Jetson
```

## Failover & Degradation

If I2C communication fails:
1. **First failure:** Log error via `bootLogf()`, keep previous scene active
2. **Consecutive failures (>5):** Mark PCA9685 as "degraded" in RuntimeState
3. **Jetson side:** `/api/system/health` reports `pca9685_status: "degraded"`
4. **Action layer fallback:** Reject motor commands, respond `no_action`

## Telemetry & Metrics

**Command history** (stored in RuntimeState.motor_commands ring buffer, max 50 entries):
- Timestamp (microseconds since boot)
- Scene name / channel number
- Value (PWM 0–4095)
- Duration (ms)
- Result (success / error)

**Endpoint:** `/api/motor/metrics`
```json
{
  "total_commands": 1234,
  "scene_changes": 42,
  "channel_changes": 567,
  "errors": 0,
  "last_command_ms_ago": 50
}
```

## Related Components

- **Action Layer:** `System/adam/action.py` — LLM scene/channel request parsing + whitelist validation
- **Motor Safety:** `System/Config.json` → `safety.*` — duration limits, cooldown, constraints
- **Runtime State:** `RuntimeState.pwm_state` — current channel values + last scene (thread-safe spinlock access)
- **WebServerModule:** All `/api/motor/*` routes (port 80)

## Graphify Evidence

- Community: "PCA9685 and Motor Control" (16 nodes, cohesion 0.08)
- Key nodes: `Pca9685Module` (8 edges), `initPca9685()`, `setPwmScene()`, motor validation functions
- Thread-safe coupling: RuntimeState shared access via portMUX

See: `Knowledge-graphs/esp32/GRAPH_REPORT.md` (community for motor/PWM control)

## Limitations & Future Work

**Current State:**
- Scene execution is synchronous (all 16 channels written atomically in one I2C transaction)
- No per-channel ramp/interpolation on ESP32 side — trajectories pre-computed by Jetson
- NVS write-back on every scene change — slight latency penalty (~5 ms)

**Potential Improvements:**
- Async I2C writes with DMA for faster multi-channel updates
- On-device trajectory interpolation (ramp profiles per channel)
- Scene caching in DRAM (avoid NVS round-trip for repeated scenes)
- Telemetry push via WebSocket (real-time motor command streaming to Jetson)
