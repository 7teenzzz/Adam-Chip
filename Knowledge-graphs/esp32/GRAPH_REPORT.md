# Graph Report - Subsystem/AdamsServer/  (2026-05-16)

## Corpus Check
- 65 files · ~354,118 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 780 nodes · 1262 edges · 42 communities (41 shown, 1 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 156 edges (avg confidence: 0.81)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Web Server Request Handlers|Web Server Request Handlers]]
- [[_COMMUNITY_Firmware Docs and API Reference|Firmware Docs and API Reference]]
- [[_COMMUNITY_Boot Diagnostics and Init|Boot Diagnostics and Init]]
- [[_COMMUNITY_Video Latency Metrics (session A)|Video Latency Metrics (session A)]]
- [[_COMMUNITY_Video Latency Metrics (session B)|Video Latency Metrics (session B)]]
- [[_COMMUNITY_Video Latency Metrics (session C)|Video Latency Metrics (session C)]]
- [[_COMMUNITY_Video Latency Metrics (session D)|Video Latency Metrics (session D)]]
- [[_COMMUNITY_Video Latency Metrics (session E)|Video Latency Metrics (session E)]]
- [[_COMMUNITY_Video Latency Metrics (session F)|Video Latency Metrics (session F)]]
- [[_COMMUNITY_Video Latency Metrics (session G)|Video Latency Metrics (session G)]]
- [[_COMMUNITY_Camera Capture and Presets|Camera Capture and Presets]]
- [[_COMMUNITY_Mic Audio Capture (I2S)|Mic Audio Capture (I2S)]]
- [[_COMMUNITY_Camera Streaming Pipeline|Camera Streaming Pipeline]]
- [[_COMMUNITY_Speaker Playback and Sounds|Speaker Playback and Sounds]]
- [[_COMMUNITY_PCA9685 PWM Control|PCA9685 PWM Control]]
- [[_COMMUNITY_OTA Firmware Update|OTA Firmware Update]]
- [[_COMMUNITY_Mic Test Data (gain 4.0 ref)|Mic Test Data (gain 4.0 ref)]]
- [[_COMMUNITY_Mic Test Data (gain 7.0)|Mic Test Data (gain 7.0)]]
- [[_COMMUNITY_Mic Test Data (gain 2.5)|Mic Test Data (gain 2.5)]]
- [[_COMMUNITY_Mic Test Data (gain 1.0)|Mic Test Data (gain 1.0)]]
- [[_COMMUNITY_Mic Test Data (gain 4.0)|Mic Test Data (gain 4.0)]]
- [[_COMMUNITY_USB Flash Tool (COM7)|USB Flash Tool (COM7)]]
- [[_COMMUNITY_Environmental Sensors|Environmental Sensors]]

## God Nodes (most connected - your core abstractions)
1. `bootLogf()` - 32 edges
2. `sendJson()` - 24 edges
3. `bootLog()` - 23 edges
4. `AdamsServer ESP32-S3 Firmware` - 21 edges
5. `streamHandler()` - 20 edges
6. `sendError()` - 18 edges
7. `motorSkillsControlHandler()` - 13 edges
8. `playSystemSound()` - 12 edges
9. `appendCameraJson()` - 12 edges
10. `recordMetricMs()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `appendCameraJson()` --calls--> `getCameraPresetCount()`  [INFERRED]
  src/web/WebServerModule.cpp → src/camera/CameraModule.cpp
- `serviceOta()` --calls--> `bootLog()`  [INFERRED]
  src/core/OtaModule.cpp → src/core/BootDiagnostics.cpp
- `allocateRingBuffer()` --calls--> `bootLogf()`  [INFERRED]
  src/audio/AudioModule.cpp → src/core/BootDiagnostics.cpp
- `initAudioStdRxChannelLocked()` --calls--> `bootLogf()`  [INFERRED]
  src/audio/AudioModule.cpp → src/core/BootDiagnostics.cpp
- `reconfigureAudioCaptureLocked()` --calls--> `bootLogf()`  [INFERRED]
  src/audio/AudioModule.cpp → src/core/BootDiagnostics.cpp

## Hyperedges (group relationships)
- **ESP32 Dual HTTP Server Audio/Video Stream Architecture** — port81_stream_server, api_mjpeg_stream, api_audio_stream, api_speaker_post [EXTRACTED 0.95]
- **Network Transport Priority Failover Chain** — w5500_ethernet, wifi_fallback, ap_fallback, network_priority_design [EXTRACTED 0.95]
- **Firmware Build and Flash Workflow** — platformio_build, flash_com7_script, com7_flash_port, adamsserver_ino [EXTRACTED 0.90]

## Communities (42 total, 1 thin omitted)

### Community 0 - "Web Server Request Handlers"
Cohesion: 0.05
Nodes (93): resetBuiltInCameraPresets(), videoLatencyReset(), applyPca9685Update(), applyPca9685Updates(), resolveDutyFromUpdate(), appendCameraJson(), appendCommonStatusFields(), appendLatencySummaryJson() (+85 more)

### Community 1 - "Firmware Docs and API Reference"
Cohesion: 0.06
Nodes (52): AdamsConfig.h Compile-time Constants, AdamsServer Claude Code Context, AdamsServer ESP32-S3 Firmware, AdamsServer.ino Sketch Entry Point, AdamsServer Windows COM7 Runbook, AdamsServer Serial Boot Log, AP Fallback Mode (192.168.4.1), GET /api/audio/clip Endpoint (+44 more)

### Community 2 - "Boot Diagnostics and Init"
Cohesion: 0.12
Nodes (40): initSpeakerPlayback(), initSpeakerStdTxChannel(), beginBootDiagnostics(), bootClearLastInitError(), bootLog(), bootLogf(), bootSetLastInitError(), bootSetStage() (+32 more)

### Community 3 - "Video Latency Metrics (session A)"
Cohesion: 0.04
Nodes (45): counters_delta, buffer_realloc_count, copy_frame_miss_count, frame_skipped_due_stale, latest_mutex_timeout_count, no_new_frame_poll_count, slow_send_strike_count, duration_sec (+37 more)

### Community 4 - "Video Latency Metrics (session B)"
Cohesion: 0.04
Nodes (45): counters_delta, buffer_realloc_count, copy_frame_miss_count, frame_skipped_due_stale, latest_mutex_timeout_count, no_new_frame_poll_count, slow_send_strike_count, duration_sec (+37 more)

### Community 5 - "Video Latency Metrics (session C)"
Cohesion: 0.04
Nodes (45): counters_delta, buffer_realloc_count, copy_frame_miss_count, frame_skipped_due_stale, latest_mutex_timeout_count, no_new_frame_poll_count, slow_send_strike_count, duration_sec (+37 more)

### Community 6 - "Video Latency Metrics (session D)"
Cohesion: 0.04
Nodes (45): counters_delta, buffer_realloc_count, copy_frame_miss_count, frame_skipped_due_stale, latest_mutex_timeout_count, no_new_frame_poll_count, slow_send_strike_count, duration_sec (+37 more)

### Community 7 - "Video Latency Metrics (session E)"
Cohesion: 0.04
Nodes (45): counters_delta, buffer_realloc_count, copy_frame_miss_count, frame_skipped_due_stale, latest_mutex_timeout_count, no_new_frame_poll_count, slow_send_strike_count, duration_sec (+37 more)

### Community 8 - "Video Latency Metrics (session F)"
Cohesion: 0.04
Nodes (45): counters_delta, buffer_realloc_count, copy_frame_miss_count, frame_skipped_due_stale, latest_mutex_timeout_count, no_new_frame_poll_count, slow_send_strike_count, duration_sec (+37 more)

### Community 9 - "Video Latency Metrics (session G)"
Cohesion: 0.04
Nodes (44): counters_delta, buffer_realloc_count, copy_frame_miss_count, frame_skipped_due_stale, latest_mutex_timeout_count, no_new_frame_poll_count, slow_send_strike_count, duration_sec (+36 more)

### Community 10 - "Camera Capture and Presets"
Cohesion: 0.1
Nodes (38): allocateLatestFrameBuffer(), applyCameraControlUpdate(), applyCameraPreset(), applyLiveSettings(), buildCameraConfig(), captureCameraFrame(), clampAndSet(), clearLatestCameraFrameLocked() (+30 more)

### Community 11 - "Mic Audio Capture (I2S)"
Cohesion: 0.11
Nodes (37): allocateRingBuffer(), appendAudioBytes(), applyAudioRuntimeUpdate(), applyDcBlockFilter(), applyProfileDefaults(), audioCaptureTask(), classifySignalState(), convertRawSampleToPcm() (+29 more)

### Community 12 - "Camera Streaming Pipeline"
Cohesion: 0.12
Nodes (32): cameraProducerTask(), copyLatestCameraFrame(), frameTimestampUs(), buildMetricSummaryMs(), buildMetricSummaryUs(), clampMetricValueMs(), clampMetricValueUs(), recordMetricMs() (+24 more)

### Community 13 - "Speaker Playback and Sounds"
Cohesion: 0.24
Nodes (16): beginSpeakerStream(), endSpeakerStream(), speakerPlaybackTask(), updateSpeakerFillRuntime(), writeSpeakerData(), initSystemSounds(), pathForSound(), playSystemSound() (+8 more)

### Community 14 - "PCA9685 PWM Control"
Cohesion: 0.25
Nodes (15): applyPca9685Scene(), fillChannelPayload(), findScene(), getPca9685SceneCount(), getPca9685SceneName(), initPca9685(), nvsSaveFrequency(), nvsSaveScene() (+7 more)

### Community 15 - "OTA Firmware Update"
Cohesion: 0.27
Nodes (14): abortOtaUpload(), beginOtaUpload(), copyText(), finishOtaUpload(), getOtaStatusSnapshot(), initOta(), otaAuthRequired(), otaTokenValid() (+6 more)

### Community 16 - "Mic Test Data (gain 4.0 ref)"
Cohesion: 0.17
Nodes (11): clip_count, duration_s, gain, headroom_db, neg_pct, peak, profile, rate (+3 more)

### Community 17 - "Mic Test Data (gain 7.0)"
Cohesion: 0.18
Nodes (10): clip_count_in_capture, duration_s, gain, headroom_db, peak, profile, rate, rms (+2 more)

### Community 18 - "Mic Test Data (gain 2.5)"
Cohesion: 0.18
Nodes (10): clip_count_in_capture, duration_s, gain, headroom_db, peak, profile, rate, rms (+2 more)

### Community 19 - "Mic Test Data (gain 1.0)"
Cohesion: 0.18
Nodes (10): clip_count_in_capture, duration_s, gain, headroom_db, peak, profile, rate, rms (+2 more)

### Community 20 - "Mic Test Data (gain 4.0)"
Cohesion: 0.18
Nodes (10): clip_count_in_capture, duration_s, gain, headroom_db, peak, profile, rate, rms (+2 more)

### Community 21 - "USB Flash Tool (COM7)"
Cohesion: 0.36
Nodes (6): Get-AvailablePortNames(), Get-PortNameFromText(), Get-PortRole(), Get-SerialPorts(), Resolve-UploadPort(), Wait-ForUploadPort()

## Knowledge Gaps
- **327 isolated node(s):** `scenario`, `notes`, `preset_switch`, `target_ip`, `warmup_sec` (+322 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `bootLogf()` connect `Boot Diagnostics and Init` to `Web Server Request Handlers`, `Camera Capture and Presets`, `Mic Audio Capture (I2S)`, `Speaker Playback and Sounds`, `PCA9685 PWM Control`, `OTA Firmware Update`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `streamHandler()` connect `Camera Streaming Pipeline` to `Web Server Request Handlers`, `Camera Capture and Presets`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `startWebServer()` connect `Web Server Request Handlers` to `Boot Diagnostics and Init`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `bootLogf()` (e.g. with `allocateRingBuffer()` and `initAudioStdRxChannelLocked()`) actually correct?**
  _`bootLogf()` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `bootLog()` (e.g. with `reconfigureAudioCaptureLocked()` and `initAudioCapture()`) actually correct?**
  _`bootLog()` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `streamHandler()` (e.g. with `noteCameraStreamDemand()` and `getLatestCameraFrameSize()`) actually correct?**
  _`streamHandler()` has 17 INFERRED edges - model-reasoned connections that need verification._
- **What connects `scenario`, `notes`, `preset_switch` to the rest of the system?**
  _327 weakly-connected nodes found - possible documentation gaps or missing edges._