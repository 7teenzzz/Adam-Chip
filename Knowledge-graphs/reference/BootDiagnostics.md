# Reference: Boot Diagnostics — 10-Step Firmware Initialization

## Overview

The `BootDiagnostics` module provides transparent, verifiable firmware initialization with real-time logging. The `bootLogf()` function is the #1 god-node in the firmware graph (32 edges), bridging all 6 subsystems during startup.

## 10-Step Boot Sequence

Observed from `artifacts/_serial_log.txt` (typical boot timeline ~3 seconds):

1. **Sensors** (TEMT6000, BTE16-19) — ADC/GPIO initialization
2. **Ethernet** (W5500 SPI) — Network stack bringup, static IP assignment
3. **OTA** (firmware update module) — Memory regions, OTA state validation
4. **Sounds** (SystemSound module) — WAV data loading, DAC initialization
5. **Camera** (OV5640 DVP) — I2C camera register configuration, preview buffer
6. **Mic** (INMP441, I2S RX) — I2S BCLK/WS/SD pin setup, ring buffer allocation
7. **Speaker** (PCM5102A, I2S TX) — I2S TX channel init, DMA descriptor setup
8. **PCA9685** (PWM expansion) — I2C PWM register init, NVS scene restore
9. **Web Server** (HTTP port 80/81) — Socket binding, route registration
10. **Running** — All subsystems ready, agent online

**Boot sound played:** At ~5.8 seconds (after all subsystems initialized, synchronous playback)

## Architecture

### BootDiagnostics Module
- **God-node:** `bootLogf()` (32 edges)
- **Supporting functions:**
  - `bootLog()` — legacy wrapper (23 edges, INFERRED)
  - `beginBootDiagnostics()` — initialization
  - `bootSetStage(stage)` — progress tracking
  - `bootSetLastInitError(error)` — error capture
  - `bootClearLastInitError()` — error clearing
  - `getBootDiagnosticsSnapshot()` — current state query

### Community: "Boot Diagnostics and Init" (40 nodes)
Includes all stage-setup functions, error handlers, and diagnostics state machine.

### Integration Points

Every subsystem calls `bootLogf()` at key initialization steps:
- NetworkModule: `bootLogf("ETH: W5500 init")`, `bootLogf("ETH: IP assigned")`
- AudioModule: `bootLogf("MIC: I2S RX configured")`, `bootLogf("SPK: ring buffer allocated")`
- CameraModule: `bootLogf("CAM: OV5640 DVP ready")`
- Pca9685Module: `bootLogf("PWM: scene restored from NVS")`
- WebServerModule: `bootLogf("WEB: HTTP listener on port 80")`
- OtaModule: `bootLogf("OTA: token validation")`

## Logging Infrastructure

### Serial Output
- **Port:** COM7 (UART, flashed via PlatformIO)
- **Baudrate:** 115200 bps
- **Format:** Timestamp (HH:MM:SS.mmm) + [STAGE] + Message

Example:
```
[00:00:00.123] [SENSORS] Initialized
[00:00:00.456] [ETH] W5500 SPI detected
[00:00:00.789] [ETH] IP 192.168.0.171 assigned
...
[00:00:03.120] Boot complete
[00:00:05.800] Boot sound playback
```

### Log Capture
- **Diagnostic script:** `scripts/adam_bootstrap_venv.sh` captures serial output to `artifacts/_serial_log.txt`
- **systemd service:** `adam-orchestrator.service` logs startup via journalctl
- **REST API:** BootDiagnosticsSnapshot available via `/api/system/boot_status` (diagnostic endpoint, not production)

## Failure Modes

### Subsystem Timeout
If a subsystem exceeds timeout threshold during boot:
1. `bootSetLastInitError(subsystem)` logs the failure
2. Continue to next step (don't halt boot)
3. Mark subsystem as "degraded" (fallback mode activates)
4. Report via `/api/system/health`

### Error Recovery
- **ESP32 mic unavailable** → Use Jetson PulseAudio after timeout
- **Camera initialization failure** → Use GStreamer after timeout
- **Ethernet initialization failure** → Fall back to WiFi/AP mode

## Verification & Diagnostics

### Health Check Script
```bash
./scripts/adam_healthcheck.sh
```
Verifies:
- Serial log contains all 10 boot stages
- Boot time < 5 seconds (before sound)
- No timeout errors logged
- All subsystems report "ready"

### Observability
The 10-step sequence is **verifiable end-to-end**:
- Can examine `_serial_log.txt` to see exact initialization order
- Can set `CONFIG_LOG_LEVEL_*` flags to get verbose per-module logs
- Can trace latencies (timestamp deltas) to identify slow subsystems

## Related Components

- **Runtime State:** `RuntimeState` global struct synchronized with portMUX spinlock
- **Network Failover:** W5500 Ethernet (primary) → WiFi (secondary) → AP mode (tertiary)
- **OTA Updates:** Boot diagnostics validates firmware integrity before execution
- **Safety Idle Scene:** Fallback to `boot_idle` scene if boot fails

## Graphify Evidence

- God-node: `bootLogf()` (32 edges, cohesion in "Boot Diagnostics and Init" community 0.12)
- Community: "Boot Diagnostics and Init" (40 nodes)
- Surprising connection: All 6 subsystems converge on `bootLogf()` → god-node status
- Hyperedge: "Firmware Build and Flash Workflow" [EXTRACTED 0.90]

See: `Knowledge-graphs/esp32/GRAPH_REPORT.md` (community index 2, lines 76–78)

## Future Enhancements

- **Real-time telemetry:** Push boot diagnostics via WebSocket during startup
- **Structured logging:** JSON log entries for machine parsing
- **Boot performance profiling:** Detailed per-subsystem latency breakdown
- **Predictive health:** Use boot diagnostics to warn about degradation before failures occur
