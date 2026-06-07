# Reference: Network and Failover — W5500 Ethernet + WiFi + AP Mode

## Overview

The ESP32-S3 firmware implements a three-tier network failover strategy: W5500 SPI Ethernet (primary), WiFi (secondary), and AP mode (tertiary). This ensures the installation remains accessible even during network outages. This document describes the initialization sequence, failover mechanics, and IP assignment.

## Hardware Layer

### Primary: W5500 Ethernet (SPI)

- **Device:** W5500 Ethernet controller (SPI interface)
- **SPI pins:** CLK=36, MOSI=35, MISO=37, CS=34
- **Power:** 3.3V regulated supply
- **IP assignment:** Static 192.168.0.171 (configurable via `AdamsConfig.h`)
- **Port 80:** API routes (sensor read, motor control, diagnostics)
- **Port 81:** MJPEG camera stream + speaker audio streaming endpoint
- **MAC address:** Hardcoded in firmware (unique per device)

### Secondary: WiFi (Internal ESP32 Radio)

- **SSID:** `AdamChip_SSID` (configurable, environment-dependent, museum hardcoded)
- **Password:** Stored in NVS (`wifi_password` key)
- **Authentication:** WPA2
- **Band:** 2.4 GHz only (802.11 b/g/n)
- **IP assignment:** DHCP from local WiFi router (dynamic)
- **AP SSID fallback:** If both Ethernet and WiFi SSID connection fail

### Tertiary: Soft AP (Access Point Mode)

- **SSID:** `ADAM_CHIP_AP` (open, no password for rapid access)
- **IP:** 192.168.4.1 (ESP32 as gateway)
- **DHCP server:** Built-in, assigns 192.168.4.2–192.168.4.254 to clients
- **Purpose:** Visitors/operators can connect directly to the installation without knowing WiFi SSID
- **Ports 80/81:** Same API routes and camera stream available from AP IP

## Software Layer (ESP32 Firmware)

### Community: "Network and Failover" (24 nodes)

**Key functions:**
- `initEthernet()` — W5500 SPI initialization, static IP setup, status polling
- `initWiFi()` — WiFi driver setup, SSID/password from NVS
- `initApMode()` — Soft AP startup, DHCP server launch
- `networkMaintenanceTask()` — FreeRTOS background task, failover state machine
- `getNetworkStatus()` — current connection state (ethernet/wifi/ap)
- `isNetworkReady()` — boolean gate (used by all modules at boot)
- `recordNetworkEvent()` — telemetry: transition events, signal strength

### Boot Sequence (10-Step, Step 2)

From `BootDiagnostics`:
```
[00:00:00.456] [ETH] W5500 SPI detected
[00:00:00.789] [ETH] IP 192.168.0.171 assigned (static)
[00:00:01.200] ETH ready
[00:00:01.500] [WiFi] SSID scan + connect attempt
[00:00:02.100] WiFi connected (or skipped if Ethernet up)
[00:00:02.500] Boot complete — all subsystems ready
```

**Timeline guarantee:** Network ready within ~2.5 seconds.

### State Machine: networkMaintenanceTask()

```
STARTUP (w/ 2s timeout)
  ├─→ Try W5500 init (W5500_INIT_ATTEMPTS = 3)
  │   ├─ Success → STATE = ETHERNET_READY
  │   └─ Fail after retries → STATE = ETH_FAILED
  │
  ├─→ If ETH_FAILED: Try WiFi connect
  │   ├─ Success → STATE = WIFI_READY
  │   ├─ Timeout/invalid_ssid → STATE = WIFI_FAILED
  │   └─ User abort → go to AP_ONLY
  │
  └─→ If WIFI_FAILED: Launch Soft AP
      └─ STATE = AP_ONLY (always succeeds; no timeout)

RUNTIME POLLING (every 10 seconds)
  ├─ If STATE = ETHERNET_READY
  │   ├─ Ping test (W5500 still responding?)
  │   ├─ Success → stay ETHERNET_READY
  │   └─ Fail → mark ETHERNET_LOST, transition to WiFi attempt
  │
  ├─ If STATE = WIFI_READY
  │   ├─ Check WiFi signal (RSSI)
  │   ├─ If RSSI < threshold (-80 dBm) → attempt reconnect
  │   └─ On disconnect → transition to AP_ONLY
  │
  └─ If STATE = AP_ONLY
      └─ Wait for manual intervention or restart
```

**Transition rules:**
- Ethernet loss does NOT reboot; gracefully falls back to WiFi
- WiFi loss does NOT reboot; falls back to AP mode
- AP mode is always reachable (operators can SSH in from any client)

## NVS Configuration

**Namespace:** `network`

```
Key: wifi_ssid         Value: "Museum_Guest_5G"
Key: wifi_password     Value: "***secret***"
Key: eth_ip_static     Value: "192.168.0.171"
Key: eth_gw            Value: "192.168.0.1"
Key: eth_netmask       Value: "255.255.255.0"
Key: ap_ssid           Value: "ADAM_CHIP_AP"
Key: failover_mode     Value: 1 (0=ethernet_only, 1=full_failover, 2=wifi_only)
```

**Provisioning workflow:**
1. First boot: factory defaults (hardcoded SSID)
2. Operator configures WiFi via `/api/config/network/wifi` endpoint (requires password)
3. Settings written to NVS, persisted across resets
4. Automatic fallback always enabled (cannot be disabled without reflash)

## API Routes (WebServerModule, port 80/81)

### Network Status
```
GET /api/network/status
Response:
{
  "primary": {
    "type": "ethernet",
    "ip": "192.168.0.171",
    "mac": "AA:BB:CC:DD:EE:FF",
    "ready": true,
    "last_ping_ms": 50
  },
  "secondary": {
    "type": "wifi",
    "ssid": "Museum_Guest_5G",
    "ip": "192.168.1.42",
    "rssi": -65,
    "connected": false,
    "last_attempt_s_ago": 120
  },
  "tertiary": {
    "type": "ap",
    "ssid": "ADAM_CHIP_AP",
    "ip": "192.168.4.1",
    "clients": 1
  },
  "active_mode": "ethernet",
  "uptime_s": 3600
}
```

### Configure WiFi
```
POST /api/config/network/wifi
Body: {"ssid": "NewSSID", "password": "secret"}
Response: {"status": "saved_to_nvs", "will_connect_on_eth_loss"}
Note: Requires restart or manual Ethernet disconnect to trigger WiFi attempt
```

### Get Failover Log
```
GET /api/network/events?limit=20
Response: Array of timestamps + transition events
[
  {"ts": 1234567890, "event": "ETH_LOST", "fallback": "WIFI_ATTEMPTING"},
  {"ts": 1234567920, "event": "WIFI_CONNECTED", "ip": "192.168.1.42"},
  ...
]
```

## Failover Latency Profile

| Scenario | Latency | Recovery |
|----------|---------|----------|
| **Ethernet healthy** | <1 ms ping latency | N/A |
| **Ethernet cable unplugged** | Detection: 10–20 s (polling interval + timeout) | WiFi ready: 30–60 s |
| **WiFi signal lost** | Detection: 10–20 s (polling interval + timeout) | AP mode: <2 s (automatic) |
| **Both Ethernet + WiFi unavailable** | Detection: 20–30 s | AP mode available for local connection |

**How to expedite failover:**
1. Manual intervention: SSH into AP mode, restart network service
2. Reboot: `sudo reboot` (full reboot ~10s, network ready in 2.5s)
3. Operator panel: API endpoint to force failover (not yet implemented)

## Ethernet-Specific: W5500 Quirks

### SPI Communication
- **Clock:** 25 MHz (stable, no timing issues observed)
- **Timeout:** 1 s per read/write operation (prevents hangs on dead W5500)
- **Retry:** 3 attempts before marking W5500 as failed

### Socket Limits
- **Max sockets:** 8 (W5500 hardware limit)
- **Current usage:** 2 sockets (port 80 listener, port 81 listener) + up to 6 for simultaneous clients
- **Known issue:** If >6 clients connect simultaneously, new connections are rejected with TCP RST

### Cable Detection
- W5500 does **not** detect physical cable disconnect automatically
- Polling-based detection: ping test every 10 seconds
- If 3 consecutive pings timeout → transition to WiFi

## WiFi-Specific: ESP32 Radio

### RSSI Monitoring
- **Good signal:** RSSI > -70 dBm (typical home WiFi)
- **Acceptable:** RSSI -70 to -80 dBm (marginal but stable)
- **Poor:** RSSI < -80 dBm (frequent packet loss, reconnection attempts)
- **Decision threshold:** If RSSI < -80 for >2 polls → force WiFi reconnection

### Known Gotchas
- **Dual-band routers:** ESP32 connects to 2.4 GHz band only (802.11 b/g/n). Many modern routers hide 2.4 GHz if 5 GHz is available — explicitly enable 2.4 GHz band in router settings
- **SSID broadcast required:** Hidden SSIDs not supported (would require pre-provisioning)
- **Channel bandwidth:** 20 MHz only (no 40/80 MHz support on this hardware)

## AP Mode (Soft AP)

### Use Cases
1. **Emergency access:** Visitors/operators connect directly without WiFi SSID knowledge
2. **Offline operation:** Installation reachable even if WiFi + Ethernet both down
3. **Initial provisioning:** First-time WiFi SSID/password configuration via web UI on AP

### Limitations
- **Only 1 AP client at a time** (memory constraint, can increase in future)
- **No Internet passthrough** (AP is isolated from WAN)
- **Default password:** None (open SSID for rapid access — security reliant on museum WiFi isolation)

### Client Connection Workflow
```
Operator phone/laptop:
  1. Scan WiFi networks → see "ADAM_CHIP_AP"
  2. Connect (no password required)
  3. Browser → http://192.168.4.1/
  4. See diagnostics dashboard, configure WiFi SSID if needed
  5. After WiFi configured, Ethernet/WiFi will be primary next boot
```

## Related Components

- **Boot Sequence:** `BootDiagnostics` step 2 (Ethernet init)
- **Web Server:** All routes (`/api/network/*`, `/api/config/network/*`) implemented in `WebServerModule`
- **Runtime State:** `RuntimeState.network_mode` — current connection type (thread-safe spinlock access)
- **OTA Updates:** Uses whichever network is active (Ethernet preferred)

## Graphify Evidence

- Community: "Network and Failover" (24 nodes, cohesion 0.09)
- Key nodes: `initEthernet()`, `initWiFi()`, `initApMode()`, `networkMaintenanceTask()`
- God-node candidate: `networkMaintenanceTask()` (background task managing all transitions)
- Integration: All subsystems depend on `isNetworkReady()` before activating

See: `Knowledge-graphs/esp32/GRAPH_REPORT.md` (network community)

## Installation Notes for Exhibition

1. **Pre-installation testing:**
   ```bash
   # From Jetson, test each failover mode
   curl http://192.168.0.171/api/network/status  # Ethernet
   # Unplug Ethernet, wait 30s
   curl http://<wifi_ip>/api/network/status      # WiFi (if provisioned)
   # Turn off WiFi, check phone/laptop for ADAM_CHIP_AP SSID
   # Connect to AP, verify http://192.168.4.1 responsive
   ```

2. **Museum WiFi integration:**
   - Obtain SSID + password from museum IT
   - Provision via API: `POST /api/config/network/wifi`
   - Or via AP mode web UI (first boot)

3. **Monitoring:**
   - Set cron job: `curl http://192.168.0.171/api/network/events?limit=5` every 5 min
   - Alert if network mode changes (indicates failover event)
   - Log to `/var/log/adam_network.log`

## Limitations & Future Work

**Current State:**
- Failover decisions are silent (operators don't always know which network is active)
- No real-time notification to Jetson of network transitions
- AP mode single-client limit

**Potential Improvements:**
- WebSocket push notifications when network mode changes
- Configurable AP password (for security in museum setting)
- Multi-client AP mode (requires buffer management)
- Automatic fallback escalation (Ethernet → WiFi → AP without manual restart)
- Telemetry: push network events to Jetson via UDP (low-overhead, fire-and-forget)
