# Reference: Camera Streaming Pipeline (OV5640 MJPEG to Jetson VLM)

## Overview

The ESP32 firmware implements a real-time MJPEG streaming pipeline from the OV5640 camera to Jetson for VLM scene analysis. This document describes the architecture, latency profiling, and failover behavior.

## Architecture

### Hardware Layer
- **Camera:** OV5640 (5MP, DVP interface)
- **Output:** MJPEG stream at `http://192.168.0.171:81/stream` (port 81, separate HTTP server)
- **Resolution:** QVGA (320×240) at 30 fps configurable

### Software Layer (ESP32 Firmware)

#### Community: "Camera Capture and Presets" (38 nodes)
- `captureCameraFrame()` — DVP interrupt handler, frame acquisition
- `applyCameraPreset()` — resolution/quality presets (QVGA, VGA, SVGA)
- `buildCameraConfig()` — I2C configuration for OV5640 register set
- `getCameraPresetCount()`, `getPca9685SceneName()` — preset enumeration

#### Community: "Camera Streaming Pipeline" (32 nodes)
- `cameraProducerTask()` — FreeRTOS task continuously reading frames
- `copyLatestCameraFrame()` — double-buffer mechanism (lock-free producer/consumer)
- `frameTimestampUs()` — microsecond-precision frame timing for latency metrics
- `buildMetricSummaryMs()` / `buildMetricSummaryUs()` — frame delivery latency calculation
- `recordMetricMs()` (11 edges) — central latency metric accumulation

#### HTTP Stream Handler
- `streamHandler()` (20 edges, highest betweenness) — HTTP request handler for `/stream`
- Serves MJPEG boundary-encoded frames with HTTP multipart chunking
- Non-blocking per-frame HTTP streaming (single TCP connection, stream of JPEG images)

### Data Flow

```
OV5640 (DVP bus)
    ↓
captureCameraFrame() [ISR]
    ↓
copyLatestCameraFrame() [double-buffer, timestamp]
    ↓
cameraProducerTask() [FreeRTOS task loop]
    ↓
streamHandler() [HTTP GET /stream:81]
    ↓
Jetson CameraReader
    ↓
SceneWorker [VLM analysis]
```

## Latency Profiling

The firmware logs 7 video latency metric sessions (Communities 3–9 in GRAPH_REPORT.md), tracking:

- `counters_delta` — frame count delta since last poll
- `buffer_realloc_count` — dynamic buffer resizes
- `copy_frame_miss_count` — frames dropped due to buffer contention
- `frame_skipped_due_stale` — frames skipped because newer frame arrived
- `latest_mutex_timeout_count` — mutex timeout events
- `no_new_frame_poll_count` — polls with no new data
- `slow_send_strike_count` — streaming send latencies exceeding threshold
- `duration_sec` — measurement window duration

These metrics are available via `/api/video/metrics` endpoint (not directly exposed, diagnostic only).

## Configuration

From `System/Config.json`:

```json
"media": {
  "video": {
    "primary": "esp_mjpeg",
    "esp_mjpeg_url": "http://192.168.0.171:81/stream",
    "esp_fail_threshold": 3,
    "esp_retry_interval_sec": 30.0,
    "camera_capture_interval_sec": 0.5
  }
}
```

- **esp_fail_threshold:** 3 consecutive failures before fallback to GStreamer local camera
- **esp_retry_interval_sec:** 30s between reconnection attempts
- **camera_capture_interval_sec:** 0.5s (2 fps) interval for Jetson VLM polling

## Failover Behavior

1. **ESP32 camera unavailable** → Jetson CameraReader marks stream as stale
2. **3 consecutive fetch failures** → Trigger fallback to GStreamer pipeline
3. **GStreamer pipeline** → `/dev/video0` (USB/CSI camera, if available)
4. **Both unavailable** → VLM scene analysis disabled, SceneWorker returns cached last scene

Configuration knobs:
- `media.video.esp_fail_threshold` — number of failures before fallback
- `media.video.esp_retry_interval_sec` — retry delay

## Implementation Details

### Frame Buffering

The pipeline maintains a **double-buffer** for lock-free producer/consumer:
- Producer (ESP32 camera interrupt) writes to buffer A
- Consumer (HTTP streaming) reads from buffer B
- Atomic swap on new frame capture
- No mutexes in hot path (ISR-safe)

### Timestamp Precision

Each frame is stamped with `frameTimestampUs()` (microsecond precision):
- Used for latency metrics (frame age when transmitted)
- Helps identify streaming bottlenecks (Jetson-side network latency vs. ESP32-side capture delay)

### MJPEG Boundary Encoding

HTTP stream uses `multipart/x-mixed-replace` boundary:
```
--boundary
Content-Type: image/jpeg
Content-Length: NNNN

[JPEG binary data]
--boundary
...
```

Client (Jetson) decoder handles MJPEG parse + frame extraction.

## Related Components

- **OV5640 Configuration:** See `CameraModule.cpp` (Community 10, 38 nodes)
- **Camera Presets:** `boot_idle`, `active`, `engaged` video parameter sets
- **Jetson VLM Integration:** `System/adam/inference.py` — CameraReader async fetch
- **Scene Worker:** `System/Orchestrator.py` — periodic VLM invocation with latest frame

## Graphify Evidence

- Community: "Camera Streaming Pipeline" (32 nodes, cohesion 0.12)
- God node: `streamHandler()` (20 edges, betweenness 0.020)
- Surprising connection: `appendCameraJson()` → `getCameraPresetCount()` [INFERRED, confidence 0.95]
- Community: "Camera Capture and Presets" (38 nodes, cohesion 0.1)

See: `Knowledge-graphs/esp32/GRAPH_REPORT.md` (lines for camera-related communities)

## Limitations & Future Work

**Current State:**
- Single-threaded ESP32 streaming (cameraProducerTask monopolizes CPU if network delays occur)
- No frame-skip adaptive bitrate (always QVGA MJPEG)
- Metric logging is diagnostic only (not exposed to Jetson in real-time)

**Potential Improvements:**
- Separate streaming task with priority (preempt heavy I2C operations)
- Adaptive JPEG quality based on Jetson network latency
- Real-time metric push via WebSocket telemetry
