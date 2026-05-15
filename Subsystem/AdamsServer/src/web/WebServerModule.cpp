#include "WebServerModule.h"

#include <cctype>
#include <cinttypes>
#include <cstring>
#include <cstdlib>

#include "esp_heap_caps.h"
#include "esp_http_server.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "lwip/sockets.h"

#include "../../config/AdamsConfig.h"
#include "../audio/AudioModule.h"
#include "../audio/SystemSoundModule.h"
#include "../core/BootDiagnostics.h"
#include "../core/NetworkModule.h"
#include "../core/OtaModule.h"
#include "../camera/CameraModule.h"
#include "../io/Pca9685Module.h"
#include "../core/RuntimeState.h"
#include "../core/VideoLatencyMetrics.h"

namespace {

httpd_handle_t sControlServer = nullptr;
httpd_handle_t sStreamServer = nullptr;

constexpr char kStreamContentType[] = "multipart/x-mixed-replace;boundary=123456789000000000000987654321";
constexpr char kStreamBoundaryChunk[] = "\r\n--123456789000000000000987654321\r\n";
constexpr char kAudioContentType[] = "audio/wav";
constexpr size_t kOtaChunkBytes = 2048;
constexpr uint32_t kStreamStaleFrameThresholdMs = 1000;

struct WavHeader {
  char riff[4];
  uint32_t chunkSize;
  char wave[4];
  char fmt[4];
  uint32_t subchunk1Size;
  uint16_t audioFormat;
  uint16_t numChannels;
  uint32_t sampleRate;
  uint32_t byteRate;
  uint16_t blockAlign;
  uint16_t bitsPerSample;
  char data[4];
  uint32_t subchunk2Size;
};

WavHeader makeWavHeader(uint32_t dataBytes = 0xFFFFFFFFUL);

httpd_uri_t makeHttpUri(const char *uri, httpd_method_t method, esp_err_t (*handler)(httpd_req_t *)) {
  httpd_uri_t route = {};
  route.uri = uri;
  route.method = method;
  route.handler = handler;
  route.user_ctx = nullptr;
  return route;
}

httpd_uri_t makeWebSocketUri(const char *uri, esp_err_t (*handler)(httpd_req_t *)) {
  httpd_uri_t route = makeHttpUri(uri, HTTP_GET, handler);
  route.is_websocket = true;
  route.handle_ws_control_frames = false;
  route.supported_subprotocol = nullptr;
  return route;
}

void setLastStreamErrorLocked(const char *code) {
  const char *value = code == nullptr ? "unknown" : code;
  strncpy(gRuntimeState.lastStreamError, value, sizeof(gRuntimeState.lastStreamError) - 1);
  gRuntimeState.lastStreamError[sizeof(gRuntimeState.lastStreamError) - 1] = '\0';
}

void appendCommonStatusFields(String &json) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const int32_t wifiRssi = gRuntimeState.wifiRssi;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  json += "\"uptime_ms\":";
  json += String(millis());
  json += ",\"wifi_rssi\":";
  json += String(wifiRssi);
  json += ",\"heap_free\":";
  json += String(ESP.getFreeHeap());
  json += ",\"psram_free\":";
  json += String(ESP.getFreePsram());
}

void appendLatencySummaryJson(String &json, const LatencyMetricSummary &summary) {
  json += "{\"samples\":";
  json += String(summary.samples);
  json += ",\"min_ms\":";
  json += String(summary.minMs);
  json += ",\"avg_ms\":";
  json += String(summary.avgMs);
  json += ",\"p95_ms\":";
  json += String(summary.p95Ms);
  json += ",\"max_ms\":";
  json += String(summary.maxMs);
  json += "}";
}

void appendLatencySummaryUsJson(String &json, const LatencyMetricSummaryUs &summary) {
  json += "{\"samples\":";
  json += String(summary.samples);
  json += ",\"min_us\":";
  json += String(summary.minUs);
  json += ",\"avg_us\":";
  json += String(summary.avgUs);
  json += ",\"p95_us\":";
  json += String(summary.p95Us);
  json += ",\"max_us\":";
  json += String(summary.maxUs);
  json += "}";
}

void appendVideoLatencyJson(String &json) {
  VideoLatencySnapshot snapshot = {};
  videoLatencyGetSnapshot(snapshot);

  json += "\"video_latency\":{";
  json += "\"window_sec\":60";

  json += ",\"capture_wait_ms\":";
  appendLatencySummaryJson(json, snapshot.captureWaitMs);
  json += ",\"producer_copy_ms\":";
  appendLatencySummaryJson(json, snapshot.producerCopyMs);
  json += ",\"latest_lock_wait_ms\":";
  appendLatencySummaryJson(json, snapshot.latestLockWaitMs);
  json += ",\"frame_age_before_send_ms\":";
  appendLatencySummaryJson(json, snapshot.frameAgeBeforeSendMs);
  json += ",\"send_boundary_ms\":";
  appendLatencySummaryJson(json, snapshot.sendBoundaryMs);
  json += ",\"send_header_ms\":";
  appendLatencySummaryJson(json, snapshot.sendHeaderMs);
  json += ",\"send_payload_ms\":";
  appendLatencySummaryJson(json, snapshot.sendPayloadMs);
  json += ",\"producer_copy_us\":";
  appendLatencySummaryUsJson(json, snapshot.producerCopyUs);
  json += ",\"latest_lock_wait_us\":";
  appendLatencySummaryUsJson(json, snapshot.latestLockWaitUs);
  json += ",\"send_boundary_us\":";
  appendLatencySummaryUsJson(json, snapshot.sendBoundaryUs);
  json += ",\"send_header_us\":";
  appendLatencySummaryUsJson(json, snapshot.sendHeaderUs);
  json += ",\"send_payload_us\":";
  appendLatencySummaryUsJson(json, snapshot.sendPayloadUs);
  json += ",\"stream_loop_ms\":";
  appendLatencySummaryJson(json, snapshot.streamLoopMs);
  json += ",\"e2e_estimate_ms\":";
  appendLatencySummaryJson(json, snapshot.e2eEstimateMs);

  json += ",\"counters\":{";
  json += "\"copy_frame_miss_count\":";
  json += String(snapshot.copyFrameMissCount);
  json += ",\"no_new_frame_poll_count\":";
  json += String(snapshot.noNewFramePollCount);
  json += ",\"latest_mutex_timeout_count\":";
  json += String(snapshot.latestMutexTimeoutCount);
  json += ",\"slow_send_strike_count\":";
  json += String(snapshot.slowSendStrikeCount);
  json += ",\"buffer_realloc_count\":";
  json += String(snapshot.bufferReallocCount);
  json += ",\"frame_skipped_due_stale\":";
  json += String(snapshot.frameSkippedDueStale);
  json += "}";
  json += "}";
}

void appendPcaJson(String &json) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool ready = gRuntimeState.pca9685Ready;
  const uint8_t address = gRuntimeState.pca9685Address;
  const uint16_t frequency = gRuntimeState.pca9685Frequency;
  uint16_t channels[16] = {};
  uint8_t activeChannels = 0;
  for (size_t i = 0; i < 16; ++i) {
    channels[i] = gRuntimeState.pca9685Channels[i];
    if (channels[i] > 0) {
      activeChannels++;
    }
  }
  char activeScene[sizeof(gRuntimeState.activeScene)];
  strncpy(activeScene, gRuntimeState.activeScene, sizeof(activeScene) - 1);
  activeScene[sizeof(activeScene) - 1] = '\0';
  portEXIT_CRITICAL(&gRuntimeStateMux);

  json += "\"pca9685\":{";
  json += "\"ready\":";
  json += ready ? "true" : "false";
  json += ",\"address\":";
  json += String(address);
  json += ",\"frequency\":";
  json += String(frequency);
  json += ",\"active_scene\":\"";
  json += activeScene;
  json += "\",\"active_channels\":";
  json += String(activeChannels);
  json += ",\"channels\":[";
  for (size_t i = 0; i < 16; ++i) {
    if (i > 0) {
      json += ",";
    }
    json += String(channels[i]);
  }
  json += "],\"scenes\":[";
  for (size_t i = 0; i < getPca9685SceneCount(); ++i) {
    if (i > 0) {
      json += ",";
    }
    json += "\"";
    json += getPca9685SceneName(i);
    json += "\"";
  }
  json += "]}";
}

void appendCameraJson(String &json) {
  CameraControlState cameraState = {};
  const bool hasCameraState = getCameraControlState(cameraState);

  portENTER_CRITICAL(&gRuntimeStateMux);
  const uint32_t generation = gRuntimeState.cameraGeneration;
  const bool producerRunning = gRuntimeState.cameraProducerRunning;
  const uint32_t captureFrameTimeMs = gRuntimeState.captureFrameTimeMs;
  const uint32_t captureFpsTimes10 = gRuntimeState.captureFrameRateTimes10;
  const uint32_t latestFrameSequence = gRuntimeState.latestFrameSequence;
  const uint32_t lastJpegSize = gRuntimeState.lastJpegSize;
  const uint32_t streamDrops = gRuntimeState.streamDrops;
  const uint32_t cameraReinitCount = gRuntimeState.cameraReinitCount;
  char lastReinitReason[sizeof(gRuntimeState.lastCameraReinitReason)];
  strncpy(lastReinitReason, gRuntimeState.lastCameraReinitReason, sizeof(lastReinitReason) - 1);
  lastReinitReason[sizeof(lastReinitReason) - 1] = '\0';
  portEXIT_CRITICAL(&gRuntimeStateMux);

  json += "\"camera\":{";
  json += "\"ready\":";
  json += hasCameraState ? "true" : "false";
  json += ",\"producer_running\":";
  json += producerRunning ? "true" : "false";
  json += ",\"generation\":";
  json += String(generation);
  json += ",\"preset\":\"";
  json += hasCameraState ? cameraState.preset : "unknown";
  json += "\",\"framesize\":";
  json += String(hasCameraState ? cameraState.framesize : -1);
  json += ",\"quality\":";
  json += String(hasCameraState ? cameraState.quality : -1);
  json += ",\"brightness\":";
  json += String(hasCameraState ? cameraState.brightness : 0);
  json += ",\"contrast\":";
  json += String(hasCameraState ? cameraState.contrast : 0);
  json += ",\"saturation\":";
  json += String(hasCameraState ? cameraState.saturation : 0);
  json += ",\"sharpness\":";
  json += String(hasCameraState ? cameraState.sharpness : 0);
  json += ",\"denoise\":";
  json += String(hasCameraState ? cameraState.denoise : 0);
  json += ",\"gain_ceiling\":";
  json += String(hasCameraState ? cameraState.gainCeiling : 0);
  json += ",\"awb\":";
  json += hasCameraState && cameraState.awb ? "true" : "false";
  json += ",\"agc\":";
  json += hasCameraState && cameraState.agc ? "true" : "false";
  json += ",\"aec\":";
  json += hasCameraState && cameraState.aec ? "true" : "false";
  json += ",\"hmirror\":";
  json += hasCameraState && cameraState.hmirror ? "true" : "false";
  json += ",\"vflip\":";
  json += hasCameraState && cameraState.vflip ? "true" : "false";
  json += ",\"capture_frame_time_ms\":";
  json += String(captureFrameTimeMs);
  json += ",\"capture_fps\":";
  json += String(captureFpsTimes10 / 10.0f, 1);
  json += ",\"latest_frame_sequence\":";
  json += String(latestFrameSequence);
  json += ",\"last_jpeg_size\":";
  json += String(lastJpegSize);
  json += ",\"stream_drops\":";
  json += String(streamDrops);
  json += ",\"camera_reinit_count\":";
  json += String(cameraReinitCount);
  json += ",\"last_camera_reinit_reason\":\"";
  json += lastReinitReason;
  json += "\",\"presets\":[";
  bool firstPreset = true;
  for (size_t i = 0; i < getCameraPresetCount(); ++i) {
    CameraPresetDescriptor descriptor = {};
    if (!getCameraPresetDescriptor(i, descriptor) || !descriptor.exists) {
      continue;
    }
    if (!firstPreset) {
      json += ",";
    }
    firstPreset = false;
    json += "{\"name\":\"";
    json += descriptor.name;
    json += "\",\"builtin\":";
    json += descriptor.builtin ? "true" : "false";
    json += ",\"has_framesize\":";
    json += descriptor.hasFramesize ? "true" : "false";
    json += ",\"framesize\":";
    json += String(descriptor.framesize);
    json += "}";
  }
  json += "]";
  json += ",\"capabilities\":{";
  json += "\"framesize\":{\"supported\":true,\"min\":";
  json += String(FRAMESIZE_QQVGA);
  json += ",\"max\":";
  json += String(FRAMESIZE_QSXGA);
  json += "},\"framesize_options\":[";
  bool firstFramesizeOption = true;
  auto appendFramesizeOption = [&](const char *name, int value) {
    if (!firstFramesizeOption) {
      json += ",";
    }
    firstFramesizeOption = false;
    json += "{\"name\":\"";
    json += name;
    json += "\",\"value\":";
    json += String(value);
    json += "}";
  };
  appendFramesizeOption("QQVGA", FRAMESIZE_QQVGA);
  appendFramesizeOption("HQVGA", FRAMESIZE_HQVGA);
  appendFramesizeOption("QVGA", FRAMESIZE_QVGA);
  appendFramesizeOption("CIF", FRAMESIZE_CIF);
  appendFramesizeOption("VGA", FRAMESIZE_VGA);
  appendFramesizeOption("SVGA", FRAMESIZE_SVGA);
  appendFramesizeOption("XGA", FRAMESIZE_XGA);
  appendFramesizeOption("HD", FRAMESIZE_HD);
  appendFramesizeOption("SXGA", FRAMESIZE_SXGA);
  appendFramesizeOption("UXGA", FRAMESIZE_UXGA);
  json += "],\"quality\":{\"supported\":true,\"min\":4,\"max\":63}";
  json += ",\"brightness\":{\"supported\":true,\"min\":-2,\"max\":2}";
  json += ",\"contrast\":{\"supported\":true,\"min\":-2,\"max\":2}";
  json += ",\"saturation\":{\"supported\":true,\"min\":-2,\"max\":2}";
  json += ",\"sharpness\":{\"supported\":true,\"min\":-2,\"max\":2}";
  json += ",\"denoise\":{\"supported\":true,\"min\":0,\"max\":1}";
  json += ",\"gain_ceiling\":{\"supported\":true,\"min\":0,\"max\":6}";
  json += ",\"awb\":{\"supported\":true}";
  json += ",\"agc\":{\"supported\":true}";
  json += ",\"aec\":{\"supported\":true}";
  json += ",\"hmirror\":{\"supported\":true}";
  json += ",\"vflip\":{\"supported\":true}}}";
}

void appendOtaJson(String &json) {
  OtaStatusSnapshot snapshot = {};
  getOtaStatusSnapshot(snapshot);

  json += "\"ota\":{";
  json += "\"enabled\":";
  json += snapshot.enabled ? "true" : "false";
  json += ",\"ready\":";
  json += snapshot.ready ? "true" : "false";
  json += ",\"in_progress\":";
  json += snapshot.inProgress ? "true" : "false";
  json += ",\"reboot_pending\":";
  json += snapshot.rebootPending ? "true" : "false";
  json += ",\"auth_required\":";
  json += snapshot.authRequired ? "true" : "false";
  json += ",\"progress_pct\":";
  json += String(snapshot.progressPercent);
  json += ",\"bytes_received\":";
  json += String(snapshot.bytesReceived);
  json += ",\"total_bytes\":";
  json += String(snapshot.totalBytes);
  json += ",\"last_result\":\"";
  json += snapshot.lastResult;
  json += "\",\"last_error\":\"";
  json += snapshot.lastError;
  json += "\"}";
}

void buildStatusJson(String &json) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const uint32_t videoClients = gRuntimeState.videoClients;
  const uint32_t audioClients = gRuntimeState.audioClients;
  const uint32_t websocketClients = gRuntimeState.websocketClients;
  const uint32_t frameTimeMs = gRuntimeState.frameTimeMs;
  const uint32_t frameRateTimes10 = gRuntimeState.frameRateTimes10;
  const uint32_t lastFrameSize = gRuntimeState.lastFrameSize;
  const bool cameraReady = gRuntimeState.cameraReady;
  const bool audioReady = gRuntimeState.audioReady;
  const bool speakerReady = gRuntimeState.speakerReady;
  const bool webReady = gRuntimeState.webReady;
  const bool speakerClientActive = gRuntimeState.speakerClientActive;
  const uint32_t speakerBufferFill = gRuntimeState.speakerBufferFill;
  const uint32_t speakerUnderruns = gRuntimeState.speakerUnderruns;
  const uint32_t speakerOverflows = gRuntimeState.speakerOverflows;
  const bool sensorsReady = gRuntimeState.sensorsReady;
  const bool networkConnected = gRuntimeState.networkConnected;
  const bool ethernetConnected = gRuntimeState.ethernetConnected;
  const bool ethernetLinkUp = gRuntimeState.ethernetLinkUp;
  const bool wifiConnected = gRuntimeState.wifiConnected;
  const int32_t wifiRssi = gRuntimeState.wifiRssi;
  const bool producerRunning = gRuntimeState.cameraProducerRunning;
  const uint32_t generation = gRuntimeState.cameraGeneration;
  const uint32_t captureFrameTimeMs = gRuntimeState.captureFrameTimeMs;
  const uint32_t captureFpsTimes10 = gRuntimeState.captureFrameRateTimes10;
  const uint32_t lastJpegSize = gRuntimeState.lastJpegSize;
  const uint32_t streamRestarts = gRuntimeState.streamRestarts;
  const uint32_t streamDrops = gRuntimeState.streamDrops;
  const uint32_t cameraReinitCount = gRuntimeState.cameraReinitCount;
  const uint32_t streamSendTimeMs = gRuntimeState.streamSendTimeMs;
  const uint32_t streamTimeoutCloses = gRuntimeState.streamTimeoutCloses;
  const uint32_t streamSendFailures = gRuntimeState.streamSendFailures;
  const uint32_t streamClientResets = gRuntimeState.streamClientResets;
  const uint32_t lastSoundStartedAtMs = gRuntimeState.lastSoundStartedAtMs;
  const uint32_t lastSoundCompletedAtMs = gRuntimeState.lastSoundCompletedAtMs;
  const uint32_t lastSoundBytes = gRuntimeState.lastSoundBytes;
  const uint32_t soundPlayRequests = gRuntimeState.soundPlayRequests;
  char bootStage[sizeof(gRuntimeState.bootStage)];
  strncpy(bootStage, gRuntimeState.bootStage, sizeof(bootStage) - 1);
  bootStage[sizeof(bootStage) - 1] = '\0';
  char lastInitError[sizeof(gRuntimeState.lastInitError)];
  strncpy(lastInitError, gRuntimeState.lastInitError, sizeof(lastInitError) - 1);
  lastInitError[sizeof(lastInitError) - 1] = '\0';
  char networkTransport[sizeof(gRuntimeState.networkTransport)];
  strncpy(networkTransport, gRuntimeState.networkTransport, sizeof(networkTransport) - 1);
  networkTransport[sizeof(networkTransport) - 1] = '\0';
  char networkIp[sizeof(gRuntimeState.networkIp)];
  strncpy(networkIp, gRuntimeState.networkIp, sizeof(networkIp) - 1);
  networkIp[sizeof(networkIp) - 1] = '\0';
  char wifiIp[sizeof(gRuntimeState.wifiIp)];
  strncpy(wifiIp, gRuntimeState.wifiIp, sizeof(wifiIp) - 1);
  wifiIp[sizeof(wifiIp) - 1] = '\0';
  char ethernetIp[sizeof(gRuntimeState.ethernetIp)];
  strncpy(ethernetIp, gRuntimeState.ethernetIp, sizeof(ethernetIp) - 1);
  ethernetIp[sizeof(ethernetIp) - 1] = '\0';
  char lastReinitReason[sizeof(gRuntimeState.lastCameraReinitReason)];
  strncpy(lastReinitReason, gRuntimeState.lastCameraReinitReason, sizeof(lastReinitReason) - 1);
  lastReinitReason[sizeof(lastReinitReason) - 1] = '\0';
  char lastStreamError[sizeof(gRuntimeState.lastStreamError)];
  strncpy(lastStreamError, gRuntimeState.lastStreamError, sizeof(lastStreamError) - 1);
  lastStreamError[sizeof(lastStreamError) - 1] = '\0';
  char lastSoundName[sizeof(gRuntimeState.lastSoundName)];
  strncpy(lastSoundName, gRuntimeState.lastSoundName, sizeof(lastSoundName) - 1);
  lastSoundName[sizeof(lastSoundName) - 1] = '\0';
  char lastSoundResult[sizeof(gRuntimeState.lastSoundResult)];
  strncpy(lastSoundResult, gRuntimeState.lastSoundResult, sizeof(lastSoundResult) - 1);
  lastSoundResult[sizeof(lastSoundResult) - 1] = '\0';
  portEXIT_CRITICAL(&gRuntimeStateMux);

  json.reserve(kStatusJsonCapacity);
  json = "{";
  appendCommonStatusFields(json);
  json += ",\"boot_stage\":\"";
  json += bootStage;
  json += "\"";
  json += ",\"last_init_error\":\"";
  json += lastInitError;
  json += "\"";
  json += ",\"network_transport\":\"";
  json += networkTransport;
  json += "\"";
  json += ",\"network_connected\":";
  json += networkConnected ? "true" : "false";
  json += ",\"network_ip\":\"";
  json += networkIp;
  json += "\"";
  json += ",\"ethernet_connected\":";
  json += ethernetConnected ? "true" : "false";
  json += ",\"ethernet_link_up\":";
  json += ethernetLinkUp ? "true" : "false";
  json += ",\"ethernet_ip\":\"";
  json += ethernetIp;
  json += "\"";
  json += ",\"wifi_connected\":";
  json += wifiConnected ? "true" : "false";
  json += ",\"ip\":\"";
  json += networkIp;
  json += "\"";
  json += ",\"wifi_ip\":\"";
  json += wifiIp;
  json += "\"";
  json += ",\"wifi_rssi_cached\":";
  json += wifiRssi;
  json += ",\"psram_found\":";
  json += psramFound() ? "true" : "false";
  json += ",\"video_clients\":";
  json += videoClients;
  json += ",\"stream_clients\":";
  json += videoClients;
  json += ",\"audio_clients\":";
  json += audioClients;
  json += ",\"websocket_clients\":";
  json += websocketClients;
  json += ",\"camera_ready\":";
  json += cameraReady ? "true" : "false";
  json += ",\"camera_producer_running\":";
  json += producerRunning ? "true" : "false";
  json += ",\"camera_generation\":";
  json += generation;
  json += ",\"audio_ready\":";
  json += audioReady ? "true" : "false";
  json += ",\"speaker_ready\":";
  json += speakerReady ? "true" : "false";
  json += ",\"web_ready\":";
  json += webReady ? "true" : "false";
  json += ",\"speaker_client_active\":";
  json += speakerClientActive ? "true" : "false";
  json += ",\"speaker_buffer_fill\":";
  json += speakerBufferFill;
  json += ",\"speaker_underruns\":";
  json += speakerUnderruns;
  json += ",\"speaker_overflows\":";
  json += speakerOverflows;
  json += ",\"last_sound_name\":\"";
  json += lastSoundName;
  json += "\"";
  json += ",\"last_sound_result\":\"";
  json += lastSoundResult;
  json += "\"";
  json += ",\"last_sound_bytes\":";
  json += lastSoundBytes;
  json += ",\"last_sound_started_at_ms\":";
  json += lastSoundStartedAtMs;
  json += ",\"last_sound_completed_at_ms\":";
  json += lastSoundCompletedAtMs;
  json += ",\"sound_play_requests\":";
  json += soundPlayRequests;
  json += ",\"sensors_ready\":";
  json += sensorsReady ? "true" : "false";
  json += ",\"frame_time_ms\":";
  json += frameTimeMs;
  json += ",\"fps\":";
  json += String(frameRateTimes10 / 10.0f, 1);
  json += ",\"last_frame_size\":";
  json += lastFrameSize;
  json += ",\"capture_frame_time_ms\":";
  json += captureFrameTimeMs;
  json += ",\"capture_fps\":";
  json += String(captureFpsTimes10 / 10.0f, 1);
  json += ",\"last_jpeg_size\":";
  json += lastJpegSize;
  json += ",\"stream_restarts\":";
  json += streamRestarts;
  json += ",\"stream_drops\":";
  json += streamDrops;
  json += ",\"camera_reinit_count\":";
  json += cameraReinitCount;
  json += ",\"stream_send_time_ms\":";
  json += streamSendTimeMs;
  json += ",\"stream_timeout_closes\":";
  json += streamTimeoutCloses;
  json += ",\"stream_send_failures\":";
  json += streamSendFailures;
  json += ",\"stream_client_resets\":";
  json += streamClientResets;
  json += ",\"last_stream_error\":\"";
  json += lastStreamError;
  json += "\"";
  json += ",\"last_camera_reinit_reason\":\"";
  json += lastReinitReason;
  json += "\",";
  appendVideoLatencyJson(json);
  json += ",";
  appendCameraJson(json);
  json += ",";
  appendOtaJson(json);
  json += ",";
  appendPcaJson(json);
  json += "}";
}

void buildSensorJson(String &json) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const uint32_t lightRaw = gRuntimeState.lightRaw;
  const float lightNorm = gRuntimeState.lightNorm;
  const bool motion = gRuntimeState.motion;
  const uint32_t motionChangedAtMs = gRuntimeState.motionChangedAtMs;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  json.reserve(kSensorJsonCapacity);
  json = "{";
  appendCommonStatusFields(json);
  json += ",\"light_raw\":";
  json += lightRaw;
  json += ",\"light_norm\":";
  json += String(lightNorm, 3);
  json += ",\"motion\":";
  json += motion ? "true" : "false";
  json += ",\"motion_changed_ms_ago\":";
  json += millis() - motionChangedAtMs;
  json += "}";
}

void buildPcaStatusJson(String &json) {
  json.reserve(kPcaJsonCapacity);
  json = "{";
  appendCommonStatusFields(json);
  json += ",";
  appendPcaJson(json);
  json += "}";
}

void buildAudioStatusJson(String &json) {
  AudioStatusSnapshot snapshot = {};
  getAudioStatusSnapshot(snapshot);

  portENTER_CRITICAL(&gRuntimeStateMux);
  const uint32_t audioClients = gRuntimeState.audioClients;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  json.reserve(1400);
  json = "{";
  appendCommonStatusFields(json);
  json += ",\"audio_ready\":";
  json += snapshot.capture.ready ? "true" : "false";
  json += ",\"speaker_ready\":";
  json += snapshot.playback.ready ? "true" : "false";
  json += ",\"clients\":";
  json += String(audioClients);
  json += ",\"capture\":{";
  json += "\"ready\":";
  json += snapshot.capture.ready ? "true" : "false";
  json += ",\"profile\":\"";
  json += snapshot.capture.profile;
  json += "\",\"format\":\"";
  json += snapshot.capture.format;
  json += "\",\"sample_rate\":";
  json += String(snapshot.capture.sampleRate);
  json += ",\"pcm_bits\":";
  json += String(snapshot.capture.pcmBits);
  json += ",\"pcm_channels\":";
  json += String(snapshot.capture.pcmChannels);
  json += ",\"data_bits\":";
  json += String(snapshot.capture.dataBits);
  json += ",\"slot_bits\":";
  json += String(snapshot.capture.slotBits);
  json += ",\"preferred_slot\":";
  json += String(snapshot.capture.preferredSlot);
  json += ",\"sample_shift\":";
  json += String(snapshot.capture.sampleShift);
  json += ",\"software_gain\":";
  json += String(snapshot.capture.softwareGain, 2);
  json += ",\"dc_block\":";
  json += snapshot.capture.dcBlock ? "true" : "false";
  json += ",\"buffer_bytes\":";
  json += String(snapshot.capture.bufferBytes);
  json += ",\"writer_sequence\":";
  json += String(static_cast<unsigned long>(snapshot.capture.writerSequence & 0xFFFFFFFFULL));
  json += ",\"writer_sequence_hi\":";
  json += String(static_cast<unsigned long>(snapshot.capture.writerSequence >> 32));
  json += ",\"last_sample_ms\":";
  json += String(snapshot.capture.lastSampleMs);
  json += ",\"last_non_zero_ms\":";
  json += String(snapshot.capture.lastNonZeroMs);
  json += ",\"recent_activity_ms\":";
  json += String(snapshot.capture.recentActivityMs);
  json += ",\"stream_active\":";
  json += snapshot.capture.streamActive ? "true" : "false";
  json += ",\"left_peak\":";
  json += String(snapshot.capture.leftPeak);
  json += ",\"right_peak\":";
  json += String(snapshot.capture.rightPeak);
  json += ",\"selected_peak\":";
  json += String(snapshot.capture.selectedPeak);
  json += ",\"average_level\":";
  json += String(snapshot.capture.averageLevel);
  json += ",\"dc_offset\":";
  json += String(snapshot.capture.dcOffset);
  json += ",\"zero_cross_rate\":";
  json += String(snapshot.capture.zeroCrossRate, 3);
  json += ",\"clip_count\":";
  json += String(snapshot.capture.clipCount);
  json += ",\"detected_channels\":";
  json += String(snapshot.capture.detectedChannels);
  json += ",\"signal_state\":\"";
  json += snapshot.capture.signalState;
  json += "\",\"profiles\":[";
  for (size_t i = 0; i < getAudioProfileCount(); ++i) {
    char profileName[32];
    if (!getAudioProfileName(i, profileName, sizeof(profileName))) {
      continue;
    }
    if (i > 0) {
      json += ",";
    }
    json += "\"";
    json += profileName;
    json += "\"";
  }
  json += "]},\"playback\":{";
  json += "\"ready\":";
  json += snapshot.playback.ready ? "true" : "false";
  json += ",\"client_active\":";
  json += snapshot.playback.clientActive ? "true" : "false";
  json += ",\"buffer_fill\":";
  json += String(snapshot.playback.bufferFill);
  json += ",\"underruns\":";
  json += String(snapshot.playback.underruns);
  json += ",\"overflows\":";
  json += String(snapshot.playback.overflows);
  json += "}";
  json += "}";
}

void buildOtaStatusJson(String &json) {
  json.reserve(512);
  json = "{";
  appendCommonStatusFields(json);
  json += ",";
  appendOtaJson(json);
  json += "}";
}

void buildDashboardJson(String &json) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool networkConnected = gRuntimeState.networkConnected;
  const bool ethernetConnected = gRuntimeState.ethernetConnected;
  const bool ethernetLinkUp = gRuntimeState.ethernetLinkUp;
  const bool wifiConnected = gRuntimeState.wifiConnected;
  const int32_t wifiRssi = gRuntimeState.wifiRssi;
  const bool cameraReady = gRuntimeState.cameraReady;
  const bool producerRunning = gRuntimeState.cameraProducerRunning;
  const uint32_t generation = gRuntimeState.cameraGeneration;
  const uint32_t captureFrameTimeMs = gRuntimeState.captureFrameTimeMs;
  const uint32_t captureFpsTimes10 = gRuntimeState.captureFrameRateTimes10;
  const uint32_t lastJpegSize = gRuntimeState.lastJpegSize;
  const uint32_t streamSendTimeMs = gRuntimeState.streamSendTimeMs;
  const uint32_t streamTimeoutCloses = gRuntimeState.streamTimeoutCloses;
  const uint32_t streamSendFailures = gRuntimeState.streamSendFailures;
  const uint32_t streamClientResets = gRuntimeState.streamClientResets;
  const uint32_t videoClients = gRuntimeState.videoClients;
  const uint32_t lastSoundStartedAtMs = gRuntimeState.lastSoundStartedAtMs;
  const uint32_t lastSoundCompletedAtMs = gRuntimeState.lastSoundCompletedAtMs;
  const uint32_t lastSoundBytes = gRuntimeState.lastSoundBytes;
  const uint32_t soundPlayRequests = gRuntimeState.soundPlayRequests;
  const bool audioReady = gRuntimeState.audioReady;
  const bool speakerReady = gRuntimeState.speakerReady;
  const bool pcaReady = gRuntimeState.pca9685Ready;
  const bool otaReady = gRuntimeState.otaReady;
  const bool otaInProgress = gRuntimeState.otaInProgress;
  const uint8_t otaProgressPercent = gRuntimeState.otaProgressPercent;
  const bool motion = gRuntimeState.motion;
  const uint32_t lightRaw = gRuntimeState.lightRaw;
  const float lightNorm = gRuntimeState.lightNorm;
  const uint32_t motionChangedAtMs = gRuntimeState.motionChangedAtMs;
  char bootStage[sizeof(gRuntimeState.bootStage)];
  strncpy(bootStage, gRuntimeState.bootStage, sizeof(bootStage) - 1);
  bootStage[sizeof(bootStage) - 1] = '\0';
  char lastInitError[sizeof(gRuntimeState.lastInitError)];
  strncpy(lastInitError, gRuntimeState.lastInitError, sizeof(lastInitError) - 1);
  lastInitError[sizeof(lastInitError) - 1] = '\0';
  char networkTransport[sizeof(gRuntimeState.networkTransport)];
  strncpy(networkTransport, gRuntimeState.networkTransport, sizeof(networkTransport) - 1);
  networkTransport[sizeof(networkTransport) - 1] = '\0';
  char networkIp[sizeof(gRuntimeState.networkIp)];
  strncpy(networkIp, gRuntimeState.networkIp, sizeof(networkIp) - 1);
  networkIp[sizeof(networkIp) - 1] = '\0';
  char wifiIp[sizeof(gRuntimeState.wifiIp)];
  strncpy(wifiIp, gRuntimeState.wifiIp, sizeof(wifiIp) - 1);
  wifiIp[sizeof(wifiIp) - 1] = '\0';
  char ethernetIp[sizeof(gRuntimeState.ethernetIp)];
  strncpy(ethernetIp, gRuntimeState.ethernetIp, sizeof(ethernetIp) - 1);
  ethernetIp[sizeof(ethernetIp) - 1] = '\0';
  char cameraPreset[sizeof(gRuntimeState.cameraPreset)];
  strncpy(cameraPreset, gRuntimeState.cameraPreset, sizeof(cameraPreset) - 1);
  cameraPreset[sizeof(cameraPreset) - 1] = '\0';
  char lastStreamError[sizeof(gRuntimeState.lastStreamError)];
  strncpy(lastStreamError, gRuntimeState.lastStreamError, sizeof(lastStreamError) - 1);
  lastStreamError[sizeof(lastStreamError) - 1] = '\0';
  char lastSoundName[sizeof(gRuntimeState.lastSoundName)];
  strncpy(lastSoundName, gRuntimeState.lastSoundName, sizeof(lastSoundName) - 1);
  lastSoundName[sizeof(lastSoundName) - 1] = '\0';
  char lastSoundResult[sizeof(gRuntimeState.lastSoundResult)];
  strncpy(lastSoundResult, gRuntimeState.lastSoundResult, sizeof(lastSoundResult) - 1);
  lastSoundResult[sizeof(lastSoundResult) - 1] = '\0';
  portEXIT_CRITICAL(&gRuntimeStateMux);

  json.reserve(2048);
  json = "{";
  appendCommonStatusFields(json);
  json += ",\"network_transport\":\"";
  json += networkTransport;
  json += "\"";
  json += ",\"network_connected\":";
  json += networkConnected ? "true" : "false";
  json += ",\"network_ip\":\"";
  json += networkIp;
  json += "\"";
  json += ",\"ethernet_connected\":";
  json += ethernetConnected ? "true" : "false";
  json += ",\"ethernet_link_up\":";
  json += ethernetLinkUp ? "true" : "false";
  json += ",\"ethernet_ip\":\"";
  json += ethernetIp;
  json += "\"";
  json += ",\"wifi_connected\":";
  json += wifiConnected ? "true" : "false";
  json += ",\"wifi_rssi_cached\":";
  json += String(wifiRssi);
  json += ",\"ip\":\"";
  json += networkIp;
  json += "\"";
  json += ",\"wifi_ip\":\"";
  json += wifiIp;
  json += "\"";
  json += ",\"boot_stage\":\"";
  json += bootStage;
  json += "\"";
  json += ",\"last_init_error\":\"";
  json += lastInitError;
  json += "\"";
  json += ",\"camera_ready\":";
  json += cameraReady ? "true" : "false";
  json += ",\"camera_producer_running\":";
  json += producerRunning ? "true" : "false";
  json += ",\"camera_generation\":";
  json += String(generation);
  json += ",\"camera_preset\":\"";
  json += cameraPreset;
  json += "\"";
  json += ",\"video_clients\":";
  json += String(videoClients);
  json += ",\"fps\":";
  json += String(captureFpsTimes10 / 10.0f, 1);
  json += ",\"frame_time_ms\":";
  json += String(captureFrameTimeMs);
  json += ",\"last_frame_size\":";
  json += String(lastJpegSize);
  json += ",\"stream_send_time_ms\":";
  json += String(streamSendTimeMs);
  json += ",\"stream_timeout_closes\":";
  json += String(streamTimeoutCloses);
  json += ",\"stream_send_failures\":";
  json += String(streamSendFailures);
  json += ",\"stream_client_resets\":";
  json += String(streamClientResets);
  json += ",\"last_stream_error\":\"";
  json += lastStreamError;
  json += "\"";
  VideoLatencySnapshot latency = {};
  videoLatencyGetSnapshot(latency);
  json += ",\"video_e2e_p95_ms\":";
  json += String(latency.e2eEstimateMs.p95Ms);
  json += ",\"video_e2e_avg_ms\":";
  json += String(latency.e2eEstimateMs.avgMs);
  json += ",\"video_send_payload_p95_ms\":";
  json += String(latency.sendPayloadMs.p95Ms);
  json += ",";
  appendVideoLatencyJson(json);
  json += ",\"audio_ready\":";
  json += audioReady ? "true" : "false";
  json += ",\"speaker_ready\":";
  json += speakerReady ? "true" : "false";
  json += ",\"last_sound_name\":\"";
  json += lastSoundName;
  json += "\"";
  json += ",\"last_sound_result\":\"";
  json += lastSoundResult;
  json += "\"";
  json += ",\"last_sound_bytes\":";
  json += String(lastSoundBytes);
  json += ",\"last_sound_started_at_ms\":";
  json += String(lastSoundStartedAtMs);
  json += ",\"last_sound_completed_at_ms\":";
  json += String(lastSoundCompletedAtMs);
  json += ",\"sound_play_requests\":";
  json += String(soundPlayRequests);
  json += ",\"pca9685_ready\":";
  json += pcaReady ? "true" : "false";
  json += ",\"ota_ready\":";
  json += otaReady ? "true" : "false";
  json += ",\"ota_in_progress\":";
  json += otaInProgress ? "true" : "false";
  json += ",\"ota_progress_pct\":";
  json += String(otaProgressPercent);
  json += ",\"motion\":";
  json += motion ? "true" : "false";
  json += ",\"light_raw\":";
  json += String(lightRaw);
  json += ",\"light_norm\":";
  json += String(lightNorm, 3);
  json += ",\"motion_changed_ms_ago\":";
  json += String(millis() - motionChangedAtMs);
  json += "}";
}

esp_err_t sendJson(httpd_req_t *req, const String &json) {
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, json.c_str(), json.length());
}

esp_err_t sendError(httpd_req_t *req, const char *status, const char *message) {
  httpd_resp_set_status(req, status);
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, message, HTTPD_RESP_USE_STRLEN);
}

esp_err_t sendMovedEndpoint(httpd_req_t *req, uint16_t port, const char *path) {
  const String location = String("http://") + networkIp().toString() + ":" + String(port) + path;
  char body[192];
  snprintf(
    body,
    sizeof(body),
    "{\"error\":\"endpoint_moved\",\"url\":\"%s\"}",
    location.c_str());
  httpd_resp_set_status(req, "308 Permanent Redirect");
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Location", location.c_str());
  return httpd_resp_send(req, body, HTTPD_RESP_USE_STRLEN);
}

esp_err_t sendLocalRedirect(httpd_req_t *req, const char *path) {
  const char *target = (path == nullptr || path[0] == '\0') ? "/" : path;
  char body[192];
  snprintf(body, sizeof(body), "{\"redirect\":\"%s\"}", target);
  httpd_resp_set_status(req, "302 Found");
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Location", target);
  return httpd_resp_send(req, body, HTTPD_RESP_USE_STRLEN);
}

template <size_t N>
esp_err_t sendProgmemHtml(httpd_req_t *req, const char (&page)[N]) {
  httpd_resp_set_type(req, "text/html");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  return httpd_resp_send(req, page, N - 1);
}

esp_err_t sendHtml(httpd_req_t *req, const char *page) {
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, page, HTTPD_RESP_USE_STRLEN);
}

bool readHeaderValue(httpd_req_t *req, const char *name, String &value) {
  value = "";
  const size_t headerLen = httpd_req_get_hdr_value_len(req, name);
  if (headerLen == 0 || headerLen > 256) {
    return false;
  }
  char *buffer = static_cast<char *>(malloc(headerLen + 1));
  if (buffer == nullptr) {
    return false;
  }
  const esp_err_t result = httpd_req_get_hdr_value_str(req, name, buffer, headerLen + 1);
  if (result == ESP_OK) {
    value = buffer;
  }
  free(buffer);
  return result == ESP_OK;
}

bool readRequestBody(httpd_req_t *req, String &body, size_t maxBytes = 4096) {
  body = "";
  if (req->content_len <= 0 || static_cast<size_t>(req->content_len) > maxBytes) {
    return false;
  }
  body.reserve(req->content_len);
  int remaining = req->content_len;
  char chunk[256];
  while (remaining > 0) {
    const int toRead = min(remaining, static_cast<int>(sizeof(chunk)));
    const int read = httpd_req_recv(req, chunk, toRead);
    if (read <= 0) {
      return false;
    }
    body.concat(chunk, read);
    remaining -= read;
  }
  return true;
}

bool extractJsonInt(const String &body, const char *key, int &value) {
  const String token = String("\"") + key + "\"";
  int index = body.indexOf(token);
  if (index < 0) {
    return false;
  }
  index = body.indexOf(':', index);
  if (index < 0) {
    return false;
  }
  index++;
  while (index < body.length() && isspace(static_cast<unsigned char>(body[index]))) {
    index++;
  }
  int end = index;
  while (end < body.length() && (isdigit(static_cast<unsigned char>(body[end])) || body[end] == '-')) {
    end++;
  }
  if (end == index) {
    return false;
  }
  value = body.substring(index, end).toInt();
  return true;
}

bool extractJsonFloat(const String &body, const char *key, float &value) {
  const String token = String("\"") + key + "\"";
  int index = body.indexOf(token);
  if (index < 0) {
    return false;
  }
  index = body.indexOf(':', index);
  if (index < 0) {
    return false;
  }
  index++;
  while (index < body.length() && isspace(static_cast<unsigned char>(body[index]))) {
    index++;
  }
  int end = index;
  while (end < body.length() &&
         (isdigit(static_cast<unsigned char>(body[end])) || body[end] == '-' || body[end] == '.')) {
    end++;
  }
  if (end == index) {
    return false;
  }
  value = body.substring(index, end).toFloat();
  return true;
}

bool extractJsonBool(const String &body, const char *key, bool &value) {
  const String token = String("\"") + key + "\"";
  int index = body.indexOf(token);
  if (index < 0) {
    return false;
  }
  index = body.indexOf(':', index);
  if (index < 0) {
    return false;
  }
  index++;
  while (index < body.length() && isspace(static_cast<unsigned char>(body[index]))) {
    index++;
  }
  if (body.startsWith("true", index)) {
    value = true;
    return true;
  }
  if (body.startsWith("false", index)) {
    value = false;
    return true;
  }
  return false;
}

bool extractJsonString(const String &body, const char *key, String &value) {
  const String token = String("\"") + key + "\"";
  int index = body.indexOf(token);
  if (index < 0) {
    return false;
  }
  index = body.indexOf(':', index);
  if (index < 0) {
    return false;
  }
  index = body.indexOf('"', index + 1);
  if (index < 0) {
    return false;
  }
  const int end = body.indexOf('"', index + 1);
  if (end < 0) {
    return false;
  }
  value = body.substring(index + 1, end);
  return true;
}

bool parseChannelUpdate(const String &body, Pca9685ChannelUpdate &update) {
  int channel = -1;
  int value = 0;
  String mode;
  if (!extractJsonInt(body, "channel", channel) || !extractJsonString(body, "mode", mode)) {
    return false;
  }
  if (channel < 0 || channel > 15) {
    return false;
  }
  if (!extractJsonInt(body, "value", value)) {
    value = 0;
  }
  update.channel = static_cast<uint8_t>(channel);
  strncpy(update.mode, mode.c_str(), sizeof(update.mode) - 1);
  update.mode[sizeof(update.mode) - 1] = '\0';
  update.value = static_cast<uint16_t>(constrain(value, 0, 4095));
  return true;
}

size_t parseChannelUpdates(const String &body, Pca9685ChannelUpdate *updates, size_t maxUpdates) {
  const int updatesKey = body.indexOf("\"updates\"");
  if (updatesKey < 0) {
    return 0;
  }
  int arrayStart = body.indexOf('[', updatesKey);
  int arrayEnd = body.indexOf(']', arrayStart);
  if (arrayStart < 0 || arrayEnd < 0) {
    return 0;
  }

  size_t count = 0;
  int searchFrom = arrayStart;
  while (count < maxUpdates) {
    const int objectStart = body.indexOf('{', searchFrom);
    if (objectStart < 0 || objectStart > arrayEnd) {
      break;
    }
    const int objectEnd = body.indexOf('}', objectStart);
    if (objectEnd < 0 || objectEnd > arrayEnd) {
      break;
    }
    const String objectBody = body.substring(objectStart, objectEnd + 1);
    if (!parseChannelUpdate(objectBody, updates[count])) {
      return 0;
    }
    count++;
    searchFrom = objectEnd + 1;
  }
  return count;
}

bool parseCameraUpdate(const String &body, CameraControlUpdate &update) {
  int intValue = 0;
  bool boolValue = false;

  if (extractJsonInt(body, "framesize", intValue)) {
    update.hasFramesize = true;
    update.framesize = intValue;
  }
  if (extractJsonInt(body, "quality", intValue)) {
    update.hasQuality = true;
    update.quality = intValue;
  }
  if (extractJsonInt(body, "brightness", intValue)) {
    update.hasBrightness = true;
    update.brightness = intValue;
  }
  if (extractJsonInt(body, "contrast", intValue)) {
    update.hasContrast = true;
    update.contrast = intValue;
  }
  if (extractJsonInt(body, "saturation", intValue)) {
    update.hasSaturation = true;
    update.saturation = intValue;
  }
  if (extractJsonInt(body, "sharpness", intValue)) {
    update.hasSharpness = true;
    update.sharpness = intValue;
  }
  if (extractJsonInt(body, "denoise", intValue)) {
    update.hasDenoise = true;
    update.denoise = intValue;
  }
  if (extractJsonInt(body, "gain_ceiling", intValue)) {
    update.hasGainCeiling = true;
    update.gainCeiling = intValue;
  }
  if (extractJsonBool(body, "awb", boolValue)) {
    update.hasAwb = true;
    update.awb = boolValue;
  }
  if (extractJsonBool(body, "agc", boolValue)) {
    update.hasAgc = true;
    update.agc = boolValue;
  }
  if (extractJsonBool(body, "aec", boolValue)) {
    update.hasAec = true;
    update.aec = boolValue;
  }
  if (extractJsonBool(body, "hmirror", boolValue)) {
    update.hasHmirror = true;
    update.hmirror = boolValue;
  }
  if (extractJsonBool(body, "vflip", boolValue)) {
    update.hasVflip = true;
    update.vflip = boolValue;
  }

  return update.hasFramesize || update.hasQuality || update.hasBrightness || update.hasContrast ||
         update.hasSaturation || update.hasSharpness || update.hasDenoise || update.hasGainCeiling ||
         update.hasAwb || update.hasAgc || update.hasAec || update.hasHmirror || update.hasVflip;
}

bool parseAudioRuntimeUpdate(const String &body, AudioRuntimeUpdate &update, String &profileStorage) {
  float gain = 0.0f;
  bool boolValue = false;
  int intValue = 0;

  if (extractJsonString(body, "profile", profileStorage)) {
    update.hasProfile = true;
    update.profile = profileStorage.c_str();
  }
  if (extractJsonFloat(body, "software_gain", gain)) {
    update.hasSoftwareGain = true;
    update.softwareGain = gain;
  }
  if (extractJsonBool(body, "dc_block", boolValue)) {
    update.hasDcBlock = true;
    update.dcBlock = boolValue;
  }
  if (extractJsonInt(body, "slot", intValue)) {
    update.hasSlotOverride = true;
    update.preferredSlot = (intValue >= 0 && intValue <= 2) ? static_cast<uint8_t>(intValue) : 1;
  }
  if (extractJsonInt(body, "shift", intValue)) {
    update.hasShiftOverride = true;
    update.sampleShift = static_cast<uint8_t>(constrain(intValue, 0, 24));
  }

  return update.hasProfile || update.hasSoftwareGain || update.hasDcBlock || update.hasSlotOverride || update.hasShiftOverride;
}

const char kDashboardPage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>Панель AdamS</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  :root{--bg:#0b0d10;--card:#14181f;--sub:#10141a;--text:#e8edf4;--muted:#9aa7b8;--line:#273142;--ok:#22c55e;--bad:#ef4444;--link:#4ade80}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:Segoe UI,Arial,sans-serif}
  .wrap{max-width:1320px;margin:0 auto;padding:16px}
  .hero{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;flex-wrap:wrap}
  .hero h1{margin:0}
  .hero p{margin:6px 0 0;color:var(--muted)}
  .grid{display:grid;grid-template-columns:repeat(12,1fr);gap:12px}
  .span-12{grid-column:span 12}.span-8{grid-column:span 8}.span-6{grid-column:span 6}.span-4{grid-column:span 4}.span-3{grid-column:span 3}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px}
  .block{background:var(--sub);border:1px solid var(--line);border-radius:10px;padding:12px}
  .card h2,.card h3{margin:0 0 10px 0;font-size:16px}
  .status-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
  .status-k{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  .status-v{margin-top:4px;font-weight:700}
  .split{display:grid;grid-template-columns:2fr 1fr;gap:10px}
  .stream-meta{color:var(--muted);font-size:13px}
  .video-frame{width:100%;aspect-ratio:4/3;border:1px solid var(--line);background:#000;border-radius:10px;display:block}
  .actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
  .btn{display:inline-flex;align-items:center;gap:8px;background:#1b2330;color:var(--text);border:1px solid #324055;border-radius:10px;padding:9px 12px;cursor:pointer;text-decoration:none}
  .btn.secondary{background:#111827}.btn:hover{border-color:#4a5b75}
  .controls{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
  .field{display:flex;flex-direction:column;gap:5px}
  .field label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  input,select{width:100%;padding:9px 10px;border-radius:8px;border:1px solid #334156;background:#0f141d;color:var(--text)}
  .list{display:flex;flex-direction:column;gap:8px}
  .row{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px solid #223042}
  .row:last-child{border-bottom:none}
  .badge{display:inline-block;padding:3px 9px;border-radius:999px;font-size:12px;font-weight:700}
  .ok{background:#113223;color:var(--ok)}.bad{background:#3a1518;color:var(--bad)}
  .mono{font-family:Consolas,Menlo,monospace}.muted{color:var(--muted)}
  .vu-bar{height:8px;border-radius:4px;background:#1b2330;overflow:hidden;margin:4px 0}.vu-fill{height:100%;border-radius:4px;transition:width .15s}
  .ico{width:16px;height:16px;stroke:currentColor;stroke-width:1.75;fill:none;stroke-linecap:round;stroke-linejoin:round}
  pre{margin:8px 0 0;padding:10px;border-radius:8px;background:#0f141d;border:1px solid #2e3a4f;color:#dbe4ef;white-space:pre-wrap;word-break:break-word}
  details{margin-top:10px}
  summary{cursor:pointer;color:#b8c5d8}
  .preset-quick{display:flex;flex-wrap:wrap;gap:8px}
  .preset-chip{padding:7px 10px;border-radius:999px;border:1px solid #37556f;background:#122131;color:#d4e3f5;cursor:pointer}
  .preset-chip.active{border-color:#1fbf5f;color:#b8ffd2}
  a{color:var(--link);text-decoration:none}
  @media (max-width:980px){.span-8,.span-6,.span-4,.span-3{grid-column:span 12}.split{grid-template-columns:1fr}.controls{grid-template-columns:1fr}.status-grid{grid-template-columns:1fr 1fr}}
  </style></head><body><div class="wrap">
  <div class="hero"><div><h1>Панель управления AdamS</h1><p>Системная телеметрия обновляется автоматически (1с), сенсоры — по кнопке.</p></div><div class="actions" style="margin-top:0"><button class="btn" id="refresh-telemetry">Обновить сенсоры</button><a class="btn secondary" href="/ctrldash" target="_blank">Тех. панель</a></div></div>
  <section class="card span-12" style="margin-bottom:12px"><h2>Ключевые статусы</h2><div class="status-grid">
    <div class="block"><div class="status-k">Система</div><div class="status-v" id="top-system">загрузка...</div></div>
    <div class="block"><div class="status-k">Видео</div><div class="status-v" id="top-video">загрузка...</div></div>
    <div class="block"><div class="status-k">Аудио</div><div class="status-v" id="top-audio">загрузка...</div></div>
    <div class="block"><div class="status-k">Сенсоры</div><div class="status-v" id="top-sensors">по запросу</div></div>
  </div><div class="muted" id="telemetry-feedback" style="margin-top:8px">сенсоры не запрошены</div></section>
  <div class="grid">
    <section class="card span-12"><h2>Стримы</h2><div class="split">
      <div class="block"><div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px"><div><strong>Камера</strong><div class="stream-meta" id="video-meta">ожидание потока</div></div><div class="actions" style="margin:0"><button class="btn secondary" id="reload-video">Перезапуск</button><button class="btn secondary" id="open-live">Открыть /live</button></div></div><iframe id="video-live-frame" class="video-frame" title="Live video" loading="eager"></iframe></div>
      <div class="block"><strong>Аудио</strong><div class="list" id="audio-stream-card" style="margin-top:8px"></div><div class="actions"><a class="btn secondary" id="audio_stream_link" href="/audio" target="_blank">:81/audio</a><a class="btn secondary" id="audio_clip_link" href="/api/audio/clip?ms=4000" target="_blank">WAV тест</a></div></div>
    </div></section>
    <section class="card span-6"><h2>Камера</h2><div class="block"><div class="list" id="camera-card"></div></div><div class="block" style="margin-top:10px">
      <div class="field"><label>Быстрая смена пресета</label><div id="preset-quick" class="preset-quick"></div></div>
      <div class="controls" style="margin-top:10px">
        <div class="field"><label>Текущий пресет</label><select id="preset"></select></div>
        <div class="field"><label>Имя пресета</label><input id="preset_name" type="text" placeholder="my_preset"></div>
      </div>
      <div class="actions"><button class="btn secondary" id="apply-preset">Применить пресет</button><button class="btn secondary" id="save-preset">Сохранить</button><button class="btn secondary" id="delete-preset">Удалить</button><button class="btn secondary" id="reset-presets">Сбросить встроенные</button></div>
      <details><summary>Дополнительные настройки камеры</summary><div class="controls" style="margin-top:10px">
        <div class="field"><label>Framesize</label><select id="framesize"></select></div>
        <div class="field"><label>JPEG Quality</label><input id="quality" type="number" min="4" max="63"></div>
        <div class="field"><label>Яркость</label><input id="brightness" type="number" min="-2" max="2"></div>
        <div class="field"><label>Контраст</label><input id="contrast" type="number" min="-2" max="2"></div>
        <div class="field"><label>Насыщенность</label><input id="saturation" type="number" min="-2" max="2"></div>
        <div class="field"><label>Резкость</label><input id="sharpness" type="number" min="-2" max="2"></div>
        <div class="field"><label>Denoise</label><input id="denoise" type="number" min="0" max="1"></div>
        <div class="field"><label>Gain Ceiling</label><input id="gain_ceiling" type="number" min="0" max="6"></div>
        <div class="field"><label>AWB</label><select id="awb"><option value="true">включено</option><option value="false">выключено</option></select></div>
        <div class="field"><label>AGC</label><select id="agc"><option value="true">включено</option><option value="false">выключено</option></select></div>
        <div class="field"><label>AEC</label><select id="aec"><option value="true">включено</option><option value="false">выключено</option></select></div>
        <div class="field"><label>Зеркало</label><select id="hmirror"><option value="false">выключено</option><option value="true">включено</option></select></div>
        <div class="field"><label>Переворот</label><select id="vflip"><option value="true">включено</option><option value="false">выключено</option></select></div>
      </div><div class="actions"><button class="btn" id="apply-camera">Применить доп. настройки</button></div></details>
      <div id="camera-feedback" class="muted" style="margin-top:10px"></div></div></section>
    <section class="card span-6"><h2>Аудио и сенсоры</h2><div class="block"><div class="list" id="mic-card"></div><div class="vu-bar" style="margin-top:6px"><div id="mic-vu-fill" class="vu-fill" style="width:0%;background:var(--ok)"></div></div></div><div class="block" style="margin-top:10px"><div class="controls">
      <div class="field"><label>Профиль захвата</label><select id="audio_profile"></select></div>
      <div class="field" style="grid-column:span 2"><label>Усиление мик <span id="audio_gain_val" style="color:var(--ok);font-weight:700">1.00×</span></label><input id="audio_gain" type="range" min="0.25" max="16" step="0.25" style="accent-color:var(--ok)"></div>
      <div class="field"><label>DC block</label><select id="audio_dc_block"><option value="true">включено</option><option value="false">выключено</option></select></div>
      <div class="field"><label>Слот</label><select id="audio_slot"><option value="1">left</option><option value="2">right</option><option value="0">stereo</option></select></div>
      <div class="field"><label>Shift</label><input id="audio_shift" type="number" min="0" max="24"></div>
      <div class="field"><label>Длина WAV, мс</label><input id="audio_clip_ms" type="number" min="250" max="4000" step="250" value="4000"></div>
    </div><div class="actions"><button class="btn" id="apply-audio">Применить аудио</button></div><div id="audio-feedback" class="muted" style="margin-top:10px"></div></div>
    <div class="block" style="margin-top:10px"><h3>Сенсоры</h3><div class="list" id="sensor-card"></div></div></section>
    <section class="card span-12"><h2>PCA9685 — каналы</h2><div id="pca-info" style="margin-bottom:10px"></div><div class="block" style="margin-bottom:10px"><div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end"><div class="field"><label>Сцена</label><select id="pca-scene" style="width:130px"></select></div><button class="btn secondary" id="pca-apply-scene">Сцену</button><div class="field"><label>Частота</label><input id="pca-freq" type="number" min="24" max="1526" style="width:80px"></div><button class="btn secondary" id="pca-set-freq">Установить</button><button class="btn" id="pca-apply-all">Применить все</button></div><div id="pca-feedback" class="muted" style="margin-top:8px"></div></div><div class="block"><div id="pca-channels"></div></div></section>
  </div><script>
  const state={dashboard:null,status:null,camera:null,audio:null,pca:null,sensors:null};
  const framesizeSelect=document.getElementById('framesize'); const presetSelect=document.getElementById('preset'); const videoFrameEl=document.getElementById('video-live-frame');
  const presetExpectedFramesize={};
  let videoBackoffMs=500; let videoReloadTimer=null; let lastGeneration=-1;
  function setFramesizeOptions(c){
    const options = (c && c.capabilities && Array.isArray(c.capabilities.framesize_options)) ? c.capabilities.framesize_options : [];
    const current = c && c.framesize !== undefined ? Number(c.framesize) : NaN;
    framesizeSelect.innerHTML='';
    options.forEach(opt=>{
      const value = Number(opt.value);
      if(Number.isNaN(value)) return;
      const el=document.createElement('option');
      el.value=String(value);
      el.textContent=`${opt.name||'FS'} (${value})`;
      framesizeSelect.appendChild(el);
    });
    if(framesizeSelect.options.length===0){
      const fallback=document.createElement('option');
      fallback.value=String(Number.isNaN(current)?0:current);
      fallback.textContent=`AUTO (${fallback.value})`;
      framesizeSelect.appendChild(fallback);
    }
    if(!Number.isNaN(current)){ framesizeSelect.value=String(current); }
  }
  function refreshPresetExpectedFramesize(c){
    Object.keys(presetExpectedFramesize).forEach(k=>{ delete presetExpectedFramesize[k]; });
    const presets=Array.isArray(c && c.presets) ? c.presets : [];
    presets.forEach(p=>{
      if(p && p.name && p.has_framesize && p.framesize !== undefined){
        presetExpectedFramesize[p.name]=Number(p.framesize);
      }
    });
  }
  function icon(name){const p={apply:'M5 12l4 4 10-10',save:'M4 4h12l4 4v12H4z M8 4v6h8',del:'M4 7h16 M8 7V4h8v3 M9 7v10 M15 7v10',reset:'M4 4v5h5 M20 20v-5h-5 M6 14a6 6 0 0 0 10 4 M18 10a6 6 0 0 0-10-4',refresh:'M20 4v5h-5 M4 20v-5h5 M6 9a7 7 0 0 1 12-2 M18 15a7 7 0 0 1-12 2',stream:'M3 12s3-5 9-5 9 5 9 5-3 5-9 5-9-5-9-5z M12 10v4',status:'M4 12h16 M12 4v16'};return `<svg class="ico" viewBox="0 0 24 24"><path d="${p[name]||p.status}"/></svg>`;}
  function decorateButtons(){const m=[['refresh-telemetry','refresh'],['reload-video','refresh'],['open-live','stream'],['apply-camera','apply'],['apply-preset','apply'],['save-preset','save'],['reset-presets','reset'],['delete-preset','del'],['apply-audio','apply']];m.forEach(([id,i])=>{const el=document.getElementById(id);if(el){el.innerHTML=`${icon(i)} ${el.textContent}`;}});}
  function badge(text,ok=true){return `<span class="badge ${ok?'ok':'bad'}">${text}</span>`;}
  function fmtMs(ms){if(ms===undefined||ms===null) return 'n/a'; if(ms<1000) return `${ms} ms`; return `${(ms/1000).toFixed(1)} s`;}
  function fmtPct(v){return `${(v*100).toFixed(1)}%`;}
  function fmtBytes(v){if(!v) return '0 KB'; if(v>=1024*1024) return `${(v/1024/1024).toFixed(2)} MB`; return `${(v/1024).toFixed(0)} KB`;}
  async function fetchJson(url){const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`${url} -> ${r.status}`); return r.json();}
  async function postJson(url,payload){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); if(!r.ok) throw new Error(await r.text()); return r.json();}
  function liveUrl(){return `/live?embed=1&gen=${lastGeneration}&ts=${Date.now()}`;} function audioStreamUrl(){return `http://${location.hostname}:81/audio`;}
  function currentPayload(){return{framesize:Number(document.getElementById('framesize').value),quality:Number(document.getElementById('quality').value),brightness:Number(document.getElementById('brightness').value),contrast:Number(document.getElementById('contrast').value),saturation:Number(document.getElementById('saturation').value),sharpness:Number(document.getElementById('sharpness').value),denoise:Number(document.getElementById('denoise').value),gain_ceiling:Number(document.getElementById('gain_ceiling').value),awb:document.getElementById('awb').value==='true',agc:document.getElementById('agc').value==='true',aec:document.getElementById('aec').value==='true',hmirror:document.getElementById('hmirror').value==='true',vflip:document.getElementById('vflip').value==='true'};}
  function renderQuickPresets(c){const root=document.getElementById('preset-quick'); const presets=Array.isArray(c.presets)?c.presets:[]; root.innerHTML=''; presets.forEach(p=>{const b=document.createElement('button'); b.className=`preset-chip${c.preset===p.name?' active':''}`; b.textContent=p.name; b.onclick=()=>runCameraAction(async()=>{await postJson('/api/camera/preset/apply',{preset:p.name}); const cameraState=await fetchJson('/api/camera'); const cs=(cameraState&&cameraState.camera)?cameraState.camera:cameraState||{}; const expected=presetExpectedFramesize[p.name]; if(expected!==undefined&&Number(cs.framesize)!==expected){throw new Error(`Пресет ${p.name} применился частично: framesize=${cs.framesize}, ожидался ${expected}`);}}); root.appendChild(b);});}
  function fillCameraControls(){const c=(state.camera&&state.camera.camera)?state.camera.camera:state.camera||{}; const presets=Array.isArray(c.presets)?c.presets:[]; presetSelect.innerHTML=''; presets.forEach(p=>{const opt=document.createElement('option');opt.value=p.name;opt.textContent=p.builtin?`${p.name} [builtin]`:p.name;presetSelect.appendChild(opt);}); if(c.preset) presetSelect.value=c.preset; document.getElementById('preset_name').value=c.preset||''; setFramesizeOptions(c); refreshPresetExpectedFramesize(c); ['quality','brightness','contrast','saturation','sharpness','denoise','gain_ceiling'].forEach(k=>{if(c[k]!==undefined) document.getElementById(k).value=String(c[k]);}); if(c.awb!==undefined) document.getElementById('awb').value=String(!!c.awb); if(c.agc!==undefined) document.getElementById('agc').value=String(!!c.agc); if(c.aec!==undefined) document.getElementById('aec').value=String(!!c.aec); if(c.hmirror!==undefined) document.getElementById('hmirror').value=String(!!c.hmirror); if(c.vflip!==undefined) document.getElementById('vflip').value=String(!!c.vflip); renderQuickPresets(c);}
  function profileToSlot(name){return name&&name.endsWith('stereo')?0:name&&name.endsWith('right')?2:1;}
  function fillAudioControls(){const a=state.audio&&state.audio.capture?state.audio.capture:{}; const profiles=Array.isArray(a.profiles)?a.profiles:[]; const sel=document.getElementById('audio_profile'); sel.innerHTML=''; profiles.forEach(name=>{const opt=document.createElement('option');opt.value=name;opt.textContent=name;sel.appendChild(opt);}); if(a.profile) sel.value=a.profile; sel.onchange=function(){document.getElementById('audio_slot').value=String(profileToSlot(this.value));}; const gv=a.software_gain!==undefined?Number(a.software_gain).toFixed(2):'1.00';document.getElementById('audio_gain').value=gv;const gvEl=document.getElementById('audio_gain_val');if(gvEl)gvEl.textContent=gv+'×'; document.getElementById('audio_dc_block').value=String(!!a.dc_block); document.getElementById('audio_slot').value=String(a.preferred_slot!==undefined?a.preferred_slot:1); document.getElementById('audio_shift').value=a.sample_shift!==undefined?a.sample_shift:0; updateAudioClipLink();}
  function updateAudioClipLink(){const clipMs=Math.max(250,Math.min(4000,Number(document.getElementById('audio_clip_ms').value||2000))); document.getElementById('audio_clip_link').href=`/api/audio/clip?ms=${clipMs}`; document.getElementById('audio_stream_link').href=audioStreamUrl();}
  function renderTopStatus(){const d=state.dashboard||{};const s=state.status||{};const a=state.audio&&state.audio.capture?state.audio.capture:{};const net=d.network_transport||'wifi';const netOk=d.network_connected??d.wifi_connected;document.getElementById('top-system').innerHTML=`${netOk?badge(`${net} OK`,true):badge(`${net} down`,false)} | IP ${d.network_ip||d.ip||'0.0.0.0'} | RSSI ${d.wifi_rssi_cached??d.wifi_rssi??'n/a'} | Heap ${fmtBytes(s.heap_free||0)}`;document.getElementById('top-video').innerHTML=`${d.camera_ready?badge('камера ок',true):badge('камера fail',false)} | ${d.fps||0} FPS | ${fmtMs(d.frame_time_ms)}`;document.getElementById('top-audio').innerHTML=`${d.audio_ready?badge('аудио ок',true):badge('аудио fail',false)} | профиль ${a.profile||'n/a'}`;}
  function renderSystem(){const d=state.dashboard||{}; const s=state.status||{}; const a=state.audio&&state.audio.capture?state.audio.capture:{}; const playback=state.audio&&state.audio.playback?state.audio.playback:{}; document.getElementById('video-meta').textContent=`${d.camera_preset||'realtime'} | ${d.fps||0} FPS | ${fmtMs(d.frame_time_ms)} | gen ${d.camera_generation||0}`; document.getElementById('audio-stream-card').innerHTML=`<div class="row"><span>Capture</span><span>${d.audio_ready?badge('ok',true):badge('fail',false)}</span></div><div class="row"><span>PCM5102</span><span>${d.speaker_ready?badge('ok',true):badge('fail',false)}</span></div><div class="row"><span>Профиль</span><span class="mono">${a.profile||'n/a'}</span></div><div class="row"><span>Сигнал</span><span>${badge(a.signal_state||'n/a',a.signal_state==='active')}</span></div><div class="row"><span>Playback client</span><span>${playback.client_active?badge('active',false):badge('idle',true)}</span></div>`; document.getElementById('camera-card').innerHTML=`<div class="row"><span>Состояние</span><span>${d.camera_ready?badge('ok',true):badge('fail',false)}</span></div><div class="row"><span>Producer</span><span>${d.camera_producer_running?badge('run',true):badge('stop',false)}</span></div><div class="row"><span>Поколение</span><span>${d.camera_generation||0}</span></div><div class="row"><span>Пресет</span><span>${d.camera_preset||'realtime'}</span></div><div class="row"><span>Зрители</span><span>${d.video_clients||0}</span></div><div class="row"><span>Ошибки стрима</span><span>${d.last_stream_error||'none'}</span></div>`; document.getElementById('mic-card').innerHTML=`<div class="row"><span>Состояние</span><span>${a.ready?badge('ok',true):badge('fail',false)}</span></div><div class="row"><span>Peak / Avg</span><span>${a.selected_peak||0} / ${a.average_level||0}</span></div><div class="row"><span>DC block</span><span>${a.dc_block?'on':'off'}</span></div><div class="row"><span>Shift / slot</span><span>${a.sample_shift!==undefined?a.sample_shift:0} / ${a.preferred_slot!==undefined?a.preferred_slot:1}</span></div><div class="row"><span>PSRAM</span><span>${fmtBytes(s.psram_free||0)}</span></div>`;const vuF=document.getElementById('mic-vu-fill');if(vuF){const p=Math.min(100,Math.round((a.selected_peak||0)/327.67));vuF.style.width=p+'%';vuF.style.background=p>75?'var(--bad)':p>40?'#e8a02a':'var(--ok)';}renderTopStatus();}
  function renderSensors(){const s=state.sensors||{}; document.getElementById('sensor-card').innerHTML=`<div class="row"><span>Движение</span><span>${s.motion?badge('detected',false):badge('none',true)}</span></div><div class="row"><span>Свет raw</span><span>${s.light_raw??'n/a'}</span></div><div class="row"><span>Свет norm</span><span>${s.light_norm!==undefined?fmtPct(s.light_norm):'n/a'}</span></div><div class="row"><span>Изменение</span><span>${fmtMs(s.motion_changed_ms_ago)}</span></div>`; document.getElementById('top-sensors').innerHTML=`${s.motion?badge('движение',false):badge('спокойно',true)} | light ${s.light_raw??'n/a'}`;}
  function attachVideo(force=false){if(force||!videoFrameEl.src||!videoFrameEl.src.includes(`/live?embed=1&gen=${lastGeneration}`)){videoFrameEl.src=liveUrl();}}
  function scheduleVideoReload(force=false){if(videoReloadTimer){clearTimeout(videoReloadTimer);} videoReloadTimer=setTimeout(()=>{attachVideo(true);},force?120:videoBackoffMs);}
  videoFrameEl.onload=()=>{videoBackoffMs=500;}; videoFrameEl.onerror=()=>{videoBackoffMs=Math.min(videoBackoffMs*2,2000); scheduleVideoReload(false);};
  async function refreshSystemTelemetry(maybeReload=false){const [dashboardRes,statusRes]=await Promise.allSettled([fetchJson('/api/dashboard'),fetchJson('/api/status')]); if(dashboardRes.status==='fulfilled'){state.dashboard=dashboardRes.value;} if(statusRes.status==='fulfilled'){state.status=statusRes.value;} if(state.dashboard){if(lastGeneration!==state.dashboard.camera_generation){const changed=lastGeneration!==-1;lastGeneration=state.dashboard.camera_generation||0;if(changed||maybeReload){scheduleVideoReload(true);}else{attachVideo(true);}}} renderSystem();}
  async function refreshSensorTelemetry(){const feedback=document.getElementById('telemetry-feedback'); feedback.textContent='обновление сенсоров...'; try{state.sensors=await fetchJson('/api/sensors'); renderSensors(); feedback.textContent=`сенсоры обновлены: ${new Date().toLocaleTimeString()}`;}catch(err){feedback.textContent=String(err);}}
  async function loadCamera(){state.camera=await fetchJson('/api/camera'); fillCameraControls(); renderSystem();}
  async function loadAudio(){state.audio=await fetchJson('/api/audio'); fillAudioControls(); renderSystem();}
  async function runCameraAction(action){try{await action(); await loadCamera(); await refreshSystemTelemetry(true); document.getElementById('camera-feedback').textContent='Настройки камеры применены';}catch(err){document.getElementById('camera-feedback').textContent=String(err);}}
  async function runAudioAction(action){try{await action(); await loadAudio(); await refreshSystemTelemetry(false); document.getElementById('audio-feedback').textContent='Настройки аудио применены';}catch(err){document.getElementById('audio-feedback').textContent=String(err);}}
  document.getElementById('apply-camera').onclick=()=>runCameraAction(async()=>{await postJson('/api/camera',currentPayload());});
  document.getElementById('apply-preset').onclick=()=>runCameraAction(async()=>{const selectedPreset=presetSelect.value;await postJson('/api/camera/preset/apply',{preset:selectedPreset}); const cameraState=await fetchJson('/api/camera'); const c=(cameraState&&cameraState.camera)?cameraState.camera:cameraState||{}; const expected=presetExpectedFramesize[selectedPreset]; if(expected!==undefined&&Number(c.framesize)!==expected){throw new Error(`Пресет ${selectedPreset} применился частично: framesize=${c.framesize}, ожидался ${expected}`);}});
  document.getElementById('save-preset').onclick=()=>runCameraAction(async()=>{const name=document.getElementById('preset_name').value.trim(); if(!name) throw new Error('Введите имя пресета'); await postJson('/api/camera',currentPayload()); await postJson('/api/camera/preset/save',{preset:name});});
  document.getElementById('reset-presets').onclick=()=>runCameraAction(async()=>{await postJson('/api/camera/preset/resetdefaults',{});});
  document.getElementById('delete-preset').onclick=()=>runCameraAction(async()=>{await postJson('/api/camera/preset/delete',{preset:presetSelect.value});});
  document.getElementById('reload-video').onclick=()=>scheduleVideoReload(true);
  document.getElementById('open-live').onclick=()=>{window.open('/live','_blank');};
  document.getElementById('refresh-telemetry').onclick=refreshSensorTelemetry;
  document.getElementById('apply-audio').onclick=()=>runAudioAction(async()=>{await postJson('/api/audio',{profile:document.getElementById('audio_profile').value,software_gain:Number(document.getElementById('audio_gain').value),dc_block:document.getElementById('audio_dc_block').value==='true',slot:Number(document.getElementById('audio_slot').value),shift:Number(document.getElementById('audio_shift').value)});});
  document.getElementById('audio_clip_ms').oninput=updateAudioClipLink;
  document.getElementById('audio_gain').oninput=function(){const el=document.getElementById('audio_gain_val');if(el)el.textContent=Number(this.value).toFixed(2)+'×';};
  let gainT=null;document.getElementById('audio_gain').onchange=()=>{clearTimeout(gainT);gainT=setTimeout(()=>runAudioAction(async()=>{await postJson('/api/audio',{profile:document.getElementById('audio_profile').value,software_gain:Number(document.getElementById('audio_gain').value),dc_block:document.getElementById('audio_dc_block').value==='true',slot:Number(document.getElementById('audio_slot').value),shift:Number(document.getElementById('audio_shift').value)});}).catch(()=>{}),500);};
  decorateButtons(); updateAudioClipLink();
  Promise.all([loadCamera(),loadAudio(),refreshSystemTelemetry(false),refreshSensorTelemetry()]).catch(err=>{document.getElementById('camera-feedback').textContent=String(err);document.getElementById('audio-feedback').textContent=String(err);});
  function buildPcaRow(i,ch){return `<div style="display:grid;grid-template-columns:2.5rem 7rem 1fr 5.5rem;gap:6px;align-items:center;padding:4px 0;border-bottom:1px solid var(--line)"><span class="mono muted">Ch${i}</span><select id="pm${i}" onchange="pcaModeChange(${i})"><option value="off">off</option><option value="on">on</option><option value="pwm" selected>pwm</option></select><input type="range" id="ps${i}" min="0" max="4095" value="${ch}" oninput="document.getElementById('pv${i}').value=this.value;pcaAutoApply(${i})" style="width:100%"><input type="number" id="pv${i}" min="0" max="4095" value="${ch}" oninput="document.getElementById('ps${i}').value=this.value;pcaAutoApply(${i})" style="width:100%"></div>`;}
  const pcaDbT={};function pcaAutoApply(i){clearTimeout(pcaDbT[i]);pcaDbT[i]=setTimeout(()=>runPcaAction(async()=>postJson('/api/pca9685/channel',pcaGetRowPayload(i))),150);}
  function pcaModeChange(i){const m=document.getElementById('pm'+i).value;const sl=document.getElementById('ps'+i);const nv=document.getElementById('pv'+i);const dis=m!=='pwm';sl.disabled=dis;nv.disabled=dis;if(m==='off'){sl.value='0';nv.value='0';}else if(m==='on'){sl.value='4095';nv.value='4095';}pcaAutoApply(i);}
  function pcaGetRowPayload(i){const m=document.getElementById('pm'+i).value;return{channel:i,mode:m,value:Number(document.getElementById('pv'+i).value)};}
  async function runPcaAction(fn){const fb=document.getElementById('pca-feedback');try{await fn();await loadPca();fb.style.color='';fb.textContent='';}catch(e){fb.style.color='var(--bad)';fb.textContent=String(e);}}
  async function loadPca(){state.pca=await fetchJson('/api/pca9685');const p=state.pca.pca9685||{};const channels=p.channels||new Array(16).fill(0);const scenes=p.scenes||[];const container=document.getElementById('pca-channels');if(!container.children.length){container.innerHTML=channels.map((ch,i)=>buildPcaRow(i,ch)).join('');}else{channels.forEach((ch,i)=>{const sl=document.getElementById('ps'+i);const nv=document.getElementById('pv'+i);const md=document.getElementById('pm'+i);if(sl&&nv){sl.value=ch;nv.value=ch;sl.disabled=false;nv.disabled=false;}if(md&&md.value==='off'&&ch>0){md.value='pwm';}else if(md&&md.value==='on'&&ch<4095){md.value='pwm';}});}const ss=document.getElementById('pca-scene');if(ss.options.length!==scenes.length){ss.innerHTML=scenes.map(s=>`<option value="${s}">${s}</option>`).join('');}if(p.active_scene&&ss.value!==p.active_scene)ss.value=p.active_scene;const fq=document.getElementById('pca-freq');if(p.frequency)fq.value=p.frequency;document.getElementById('pca-info').innerHTML=`${p.ready?badge('ok',true):badge('fail',false)} <span class="muted">0x${(p.address||0).toString(16).toUpperCase()}</span> | ${p.frequency||0} Hz | сцена <strong>${p.active_scene||'none'}</strong> | активных ${p.active_channels||0}/16`;}
  document.getElementById('pca-apply-scene').onclick=()=>runPcaAction(()=>postJson('/api/pca9685/scene',{scene:document.getElementById('pca-scene').value}));
  document.getElementById('pca-set-freq').onclick=()=>runPcaAction(()=>postJson('/api/pca9685/frequency',{frequency:Number(document.getElementById('pca-freq').value)}));
  document.getElementById('pca-apply-all').onclick=()=>runPcaAction(()=>postJson('/api/pca9685/channels',{updates:Array.from({length:16},(_,i)=>pcaGetRowPayload(i))}));
  loadPca().catch(()=>{});setInterval(()=>loadPca().catch(()=>{}),2000);
  setInterval(()=>{refreshSystemTelemetry(false).catch(()=>{});},1000);
  setInterval(()=>loadAudio().catch(()=>{}),2000);
  </script></div></body></html>)HTML";

const char kLivePage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>AdamS Live</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  body{margin:0;background:#060606;color:#f3f3f3;font-family:Segoe UI,Arial,sans-serif;display:flex;flex-direction:column;min-height:100vh}
  .bar{padding:10px 14px;display:flex;justify-content:space-between;gap:12px;align-items:center;background:#101010;color:#fff;border-bottom:1px solid #2a2a2a}
  .video-wrap{width:min(100vw,960px);aspect-ratio:4/3;position:relative;margin:10px auto;border:1px solid #2a2a2a;border-radius:10px;background:#000;overflow:hidden}
  .video{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}
  .overlay{position:absolute;left:0;right:0;bottom:0;padding:6px 8px;background:rgba(0,0,0,.6);font-size:12px;color:#d0d0d0}
  a{color:#1ba73a;text-decoration:none}button{background:#fff;color:#000;border:1px solid #555;border-radius:10px;padding:8px 12px;cursor:pointer}
  .hidden{display:none}
  </style></head><body><div class="bar" id="topbar"><div><strong>AdamS Live</strong> <span id="meta">init...</span></div><div style="display:flex;gap:12px;align-items:center"><button id="reload-live">reload stream</button><a href="/dashboard" target="_blank">dashboard</a></div></div>
  <div class="video-wrap"><img id="video" class="video" alt="live"><div class="overlay" id="ov">Connecting...</div></div><script>
  const params = new URLSearchParams(location.search);
  const embedded = params.get('embed') === '1';
  if (embedded) document.getElementById('topbar').classList.add('hidden');
  const img=document.getElementById('video'); const ov=document.getElementById('ov'); const meta=document.getElementById('meta');
  let mode='stream'; let fails=0; let timer=null; let capturePollMs=700;
  let telemetryTimer=null; let serverE2eP95Ms=0; let liveFps=0;
  let serverClockOffsetMs=null; let clientE2eMs=0; let blobUrl='';
  function streamUrl(){ return `http://${location.hostname}:81/stream?ts=${Date.now()}`; }
  function captureUrl(){ return `/capture?ts=${Date.now()}`; }
  function tsHeaderToMs(ts){
    if(!ts || typeof ts!=='string') return null;
    const parts=ts.split('.');
    if(parts.length!==2) return null;
    const sec=Number(parts[0]); const usec=Number(parts[1]);
    if(Number.isNaN(sec) || Number.isNaN(usec)) return null;
    return sec*1000 + usec/1000;
  }
  function overlayText(base){
    const fpsText = liveFps>0 ? `FPS ${liveFps.toFixed(1)}` : 'FPS n/a';
    const serverText = serverE2eP95Ms>0 ? `srv E2E p95 ${serverE2eP95Ms} ms` : 'srv E2E n/a';
    const clientText = mode==='capture' && clientE2eMs>0 ? ` | cli E2E ${Math.round(clientE2eMs)} ms` : '';
    return `${base} | ${fpsText} | ${serverText}${clientText}`;
  }
  function setOverlay(text){ const v=overlayText(text); ov.textContent=v; meta.textContent=v; }
  function clearTimer(){ if(timer){ clearTimeout(timer); timer=null; } }
  function schedule(ms){ clearTimer(); timer=setTimeout(load, ms); }
  async function refreshTelemetry(){
    try{
      const r=await fetch('/api/dashboard',{cache:'no-store'});
      if(!r.ok) return;
      const d=await r.json();
      liveFps=Number(d.fps||0);
      if(d.video_latency && d.video_latency.e2e_estimate_ms){
        serverE2eP95Ms=Number(d.video_latency.e2e_estimate_ms.p95_ms||0);
      }else{
        serverE2eP95Ms=Number(d.video_e2e_p95_ms||0);
      }
    }catch(_e){}
  }
  function applyCaptureTimestamp(tsHeader){
    const serverTsMs=tsHeaderToMs(tsHeader);
    if(serverTsMs===null) return;
    const nowMs=Date.now();
    const rawOffset=nowMs-serverTsMs;
    if(serverClockOffsetMs===null){
      serverClockOffsetMs=rawOffset;
    }else{
      serverClockOffsetMs=(serverClockOffsetMs*0.9)+(rawOffset*0.1);
    }
    clientE2eMs=Math.max(0, nowMs-(serverTsMs+serverClockOffsetMs));
  }
  async function loadCaptureFrame(){
    const response=await fetch(captureUrl(),{cache:'no-store'});
    if(!response.ok) throw new Error(`capture ${response.status}`);
    applyCaptureTimestamp(response.headers.get('X-Timestamp'));
    const frameBlob=await response.blob();
    const nextUrl=URL.createObjectURL(frameBlob);
    const oldUrl=blobUrl;
    blobUrl=nextUrl;
    img.src=nextUrl;
    if(oldUrl){ URL.revokeObjectURL(oldUrl); }
  }
  function load(){
    if(mode==='stream'){ setOverlay(`stream mode | retries ${fails}`); img.src=streamUrl(); return; }
    setOverlay(`capture fallback | ${capturePollMs} ms`);
    loadCaptureFrame().catch(()=>{ if(typeof img.onerror==='function'){ img.onerror(); } });
  }
  img.onload=()=>{ fails=0; if(mode==='capture'){ schedule(capturePollMs); } else { setOverlay('stream ok'); } };
  img.onerror=()=>{
    fails++;
    if(mode==='stream' && fails>=6){ mode='capture'; capturePollMs=700; setOverlay('switch to capture fallback'); schedule(120); return; }
    if(mode==='stream'){ schedule(Math.min(2000, 250*fails)); return; }
    capturePollMs=Math.min(2000, capturePollMs+100);
    if(fails%15===0){ mode='stream'; setOverlay('retry stream...'); schedule(120); return; }
    schedule(capturePollMs);
  };
  document.getElementById('reload-live').onclick=()=>{ mode='stream'; fails=0; load(); };
  refreshTelemetry();
  telemetryTimer=setInterval(()=>{refreshTelemetry();},1000);
  load();
  </script></body></html>)HTML";

const char kOtaPage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>AdamS OTA</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  body{margin:0;background:#0b1016;color:#e7edf4;font-family:Segoe UI,Arial,sans-serif}
  .wrap{max-width:840px;margin:0 auto;padding:24px}
  .card{background:#111923;border:1px solid #23313f;border-radius:16px;padding:20px;box-shadow:0 16px 40px rgba(0,0,0,.22)}
  .muted{color:#9aabba}.mono{font-family:Consolas,monospace}
  .row{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.06)}
  .row:last-child{border-bottom:none}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}
  .btn{background:#3a9ad9;border:none;color:#071018;padding:10px 16px;border-radius:10px;font-weight:700;cursor:pointer}
  .btn.secondary{background:#182331;color:#d6e2ef}.btn:disabled{opacity:.55;cursor:not-allowed}
  input[type=file],input[type=password]{width:100%;padding:10px;border-radius:10px;border:1px solid #2b3a49;background:#0c131b;color:#e7edf4}
  progress{width:100%;height:18px;margin-top:14px} a{color:#65c9ff;text-decoration:none}
  </style></head><body><div class="wrap"><div class="card">
  <h1 style="margin-top:0">Обновление прошивки по Wi‑Fi</h1>
  <p class="muted">Здесь можно загрузить новый бинарник прошивки без USB. Нужен файл основного приложения <span class="mono">AdamsServer.ino.bin</span>, а не <span class="mono">bootloader.bin</span> и не <span class="mono">partitions.bin</span>.</p>
  <div id="ota-status"></div>
  <div style="margin-top:16px"><label>Файл прошивки (.bin)</label><input id="ota-file" type="file" accept=".bin,application/octet-stream"></div>
  <div style="margin-top:12px"><label>Токен OTA</label><input id="ota-token" type="password" placeholder="оставьте пустым, если токен отключен"></div>
  <progress id="ota-progress" value="0" max="100"></progress>
  <div id="ota-message" class="muted" style="margin-top:12px">Ожидание файла</div>
  <div class="actions">
    <button class="btn" id="ota-upload">Загрузить прошивку</button>
    <a class="btn secondary" href="/api/ota" target="_blank">/api/ota</a>
    <a class="btn secondary" href="/" target="_blank">Назад на панель</a>
  </div>
  <details style="margin-top:18px"><summary class="muted">Команда для curl</summary><pre class="mono">curl.exe -X POST ^
  -H "Content-Type: application/octet-stream" ^
  -H "X-OTA-Token: YOUR_TOKEN" ^
  --data-binary "@AdamsServer.ino.bin" ^
  http://ESP32_IP/api/ota/upload</pre></details>
  </div></div><script>
  const progress=document.getElementById('ota-progress');
  const message=document.getElementById('ota-message');
  const uploadBtn=document.getElementById('ota-upload');
  function badge(text,color){return `<span style="display:inline-block;padding:4px 10px;border-radius:999px;background:${color};font-weight:700">${text}</span>`;}
  function fmtBytes(v){if(!v) return '0 KB'; if(v>=1024*1024) return `${(v/1024/1024).toFixed(2)} MB`; return `${(v/1024).toFixed(0)} KB`;}
  async function fetchStatus(){const r=await fetch('/api/ota',{cache:'no-store'}); if(!r.ok) throw new Error(await r.text()); return r.json();}
  function renderStatus(data){
    const ota=data.ota||{};
    progress.value=Number(ota.progress_pct||0);
    document.getElementById('ota-status').innerHTML=`
      <div class="row"><span>OTA</span><span>${ota.ready ? badge('готово','#1f7a45') : badge('недоступно','#8a2b2b')}</span></div>
      <div class="row"><span>Авторизация</span><span>${ota.auth_required ? 'требуется токен' : 'отключена'}</span></div>
      <div class="row"><span>Статус</span><span>${ota.last_result||'idle'}</span></div>
      <div class="row"><span>Прогресс</span><span>${ota.progress_pct||0}% (${fmtBytes(ota.bytes_received||0)} / ${fmtBytes(ota.total_bytes||0)})</span></div>
      <div class="row"><span>Последняя ошибка</span><span class="mono">${ota.last_error||'нет'}</span></div>
      <div class="row"><span>Перезагрузка</span><span>${ota.reboot_pending ? 'ожидается' : 'нет'}</span></div>`;
  }
  async function refresh(){ try{ renderStatus(await fetchStatus()); }catch(err){ message.textContent=String(err); } }
  uploadBtn.onclick=async()=>{
    const file=document.getElementById('ota-file').files[0];
    if(!file){ message.textContent='Выберите .bin файл прошивки'; return; }
    const token=document.getElementById('ota-token').value;
    uploadBtn.disabled=true; progress.value=0; message.textContent='Загрузка прошивки...';
    try{
      const headers={'Content-Type':'application/octet-stream'};
      if(token) headers['X-OTA-Token']=token;
      const r=await fetch('/api/ota/upload',{method:'POST',headers,body:file});
      const text=await r.text();
      if(!r.ok) throw new Error(text);
      message.textContent='Прошивка загружена. Устройство сейчас перезагрузится в новый слот.';
      await refresh();
    }catch(err){
      message.textContent=String(err);
      await refresh();
    }finally{
      uploadBtn.disabled=false;
    }
  };
  refresh();
  setInterval(refresh,1500);
  </script></body></html>)HTML";

const char kRootV2Page[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>AdamS Technical Dashboard</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  :root{--bg:#090d14;--card:#121827;--line:#2a3850;--text:#e9eef7;--muted:#9fb0c7;--ok:#22c55e;--bad:#ef4444}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Segoe UI,Arial,sans-serif}
  .wrap{max-width:1320px;margin:0 auto;padding:16px}
  .head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap}
  .row{display:flex;justify-content:space-between;gap:10px}
  .grid{display:grid;grid-template-columns:2fr 1fr;gap:12px;margin-top:12px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
  .links{display:flex;flex-wrap:wrap;gap:8px}
  .links a{color:var(--ok);text-decoration:none;border:1px solid #2f5e45;padding:6px 10px;border-radius:999px}
  .group{margin-bottom:10px}.group h4{margin:0 0 6px 0;color:#c2d0e4}
  .endpoint{display:inline-block;margin:4px 6px 0 0;padding:5px 9px;border-radius:999px;border:1px solid #33506d;color:var(--ok);text-decoration:none}
  .endpoint.down{border-color:#6d3338;color:var(--bad)}
  pre{margin:8px 0 0;background:#0d1422;border:1px solid #2a3850;border-radius:10px;padding:10px;white-space:pre-wrap;word-break:break-word;max-height:320px;overflow:auto}
  .muted{color:var(--muted)} .mono{font-family:Consolas,monospace}
  @media (max-width:980px){.grid{grid-template-columns:1fr}}
  </style></head><body><div class="wrap">
    <div class="head"><div><h1 style="margin:0">Technical Dashboard</h1><div class="muted">Endpoints, health checks and raw module states (legacy API preserved).</div></div><div class="links"><a href="/dashboard" target="_blank">/dashboard</a><a href="/live" target="_blank">/live</a><a href="/ota" target="_blank">/ota</a></div></div>
    <div class="grid">
      <section class="card"><h3 style="margin:0 0 10px 0">Endpoint Categories</h3><div id="endpoints"></div></section>
      <section class="card"><h3 style="margin:0 0 10px 0">Quick Status</h3><div id="quick" class="muted">loading...</div></section>
    </div>
    <div class="grid">
      <section class="card"><h3 style="margin:0 0 10px 0">Raw: /api/dashboard</h3><pre id="raw-dashboard">loading...</pre></section>
      <section class="card"><h3 style="margin:0 0 10px 0">Raw: /api/status</h3><pre id="raw-status">loading...</pre></section>
    </div>
    <div class="grid">
      <section class="card"><h3 style="margin:0 0 10px 0">Raw: /api/camera</h3><pre id="raw-camera">loading...</pre></section>
      <section class="card"><h3 style="margin:0 0 10px 0">Raw: /api/audio</h3><pre id="raw-audio">loading...</pre></section>
    </div>
  </div><script>
  const groups=[
    {name:'UI',items:[['/dashboard','/dashboard'],['/live','/live'],['/ota','/ota']]},
    {name:'Video',items:[['/capture','/capture'],[':81/stream',()=>`http://${location.hostname}:81/stream`],['/api/camera','/api/camera'],['/api/camera/preset/apply','/api/camera/preset/apply']]},
    {name:'Audio',items:[[':81/audio',()=>`http://${location.hostname}:81/audio`],[':81/speaker',()=>`http://${location.hostname}:81/speaker`],['/api/audio','/api/audio'],['/api/audio/clip?ms=2000','/api/audio/clip?ms=2000']]},
    {name:'System',items:[['/api/status','/api/status'],['/api/dashboard','/api/dashboard'],['/api/sensors','/api/sensors'],['/api/pca9685','/api/pca9685'],['/api/ota','/api/ota'],['/ws','/ws']]}
  ];
  const state={health:{}};
  function endpointUrl(v){return typeof v==='function'?v():v;}
  function key(label,url){return `${label}|${url}`;}
  async function j(url){const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`${url} -> ${r.status}`); return r.json();}
  async function check(label,url){
    if(label.includes(':81/stream')) return true;
    if(label.includes(':81/audio')) return true;
    if(label.includes(':81/speaker')) return true;
    if(label==='/ws') return true;
    const ctl=new AbortController(); const t=setTimeout(()=>ctl.abort(),900);
    try{ const r=await fetch(url,{cache:'no-store',signal:ctl.signal}); clearTimeout(t); return r.ok; }catch(_e){ clearTimeout(t); return false; }
  }
  function renderEndpoints(){
    const root=document.getElementById('endpoints');
    root.innerHTML=groups.map(g=>`<div class="group"><h4>${g.name}</h4>${g.items.map(([label,u])=>{const url=endpointUrl(u);const down=state.health[key(label,url)]===false?'down':'';return `<a class="endpoint ${down}" href="${url}" target="_blank">${label}</a>`;}).join('')}</div>`).join('');
  }
  async function refreshHealth(){
    const tasks=[];
    groups.forEach(g=>g.items.forEach(([label,u])=>{const url=endpointUrl(u);tasks.push(check(label,url).then(ok=>{state.health[key(label,url)]=ok;}));}));
    await Promise.allSettled(tasks);
    renderEndpoints();
  }
  function pretty(data){return JSON.stringify(data,null,2);}
  async function refreshRaw(){
    try{
      const [status,dashboard,camera,audio,sensors]=await Promise.all([j('/api/status'),j('/api/dashboard'),j('/api/camera'),j('/api/audio'),j('/api/sensors')]);
      document.getElementById('raw-status').textContent=pretty(status);
      document.getElementById('raw-dashboard').textContent=pretty(dashboard);
      document.getElementById('raw-camera').textContent=pretty(camera);
      document.getElementById('raw-audio').textContent=pretty(audio);
      document.getElementById('quick').innerHTML=`<div class="row"><span>IP</span><span class="mono">${status.ip||'0.0.0.0'}</span></div><div class="row"><span>Network</span><span>${dashboard.network_transport||'wifi'} ${dashboard.network_connected?'up':'down'}</span></div><div class="row"><span>Wi-Fi</span><span>${dashboard.wifi_connected?'up':'down'}</span></div><div class="row"><span>Ethernet</span><span>${dashboard.ethernet_link_up?'link':'no link'}</span></div><div class="row"><span>FPS</span><span>${dashboard.fps||0}</span></div><div class="row"><span>Camera preset</span><span>${dashboard.camera_preset||'n/a'}</span></div><div class="row"><span>Audio profile</span><span>${audio.capture?.profile||'n/a'}</span></div><div class="row"><span>Motion</span><span>${sensors.motion?'detected':'none'}</span></div>`;
    }catch(e){
      document.getElementById('quick').textContent=String(e);
    }
  }
  renderEndpoints();
  refreshRaw().catch(()=>{});
  refreshHealth().catch(()=>{});
  setInterval(()=>{refreshRaw().catch(()=>{});},1200);
  setInterval(()=>{refreshHealth().catch(()=>{});},3500);
  </script></body></html>)HTML";

const char kVisionPage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>Vision</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  body{margin:0;background:#060606;color:#f3f3f3;font:15px Segoe UI,Arial,sans-serif}.wrap{max-width:1200px;margin:0 auto;padding:14px}
  .card{background:#111;border:1px solid #2a2a2a;border-radius:12px;padding:12px;margin-top:10px}.links a{color:#1eba4f;text-decoration:none;margin-right:10px}
  iframe{width:100%;aspect-ratio:4/3;border:1px solid #2a2a2a;border-radius:10px;background:#000}.row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1f1f1f}
  </style></head><body><div class="wrap"><h1 style="margin:0">/vision</h1><div class="links"><a href="/">/</a><a href="/vision/live">/vision/live</a></div>
  <div class="card"><iframe src="/live?embed=1"></iframe></div><div class="card"><div id="status">loading...</div></div>
  <script>async function j(u){const r=await fetch(u,{cache:'no-store'});if(!r.ok)throw new Error(r.status);return r.json();} function row(k,v){return `<div class="row"><span>${k}</span><span>${v}</span></div>`;}
  async function refresh(){const s=await j('/api/v1/vision/status');const c=s.camera||{};const d=s.dashboard||{};document.getElementById('status').innerHTML=row('Preset',c.preset||'n/a')+row('Framesize',String(c.framesize??'n/a'))+row('FPS',String(d.fps??0))+row('Clients',String(d.video_clients??0))+row('Last err',d.last_stream_error||'none');}
  refresh();setInterval(()=>refresh().catch(()=>{}),1000);</script></div></body></html>)HTML";

const char kHearingPage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>Hearing</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  body{margin:0;background:#060606;color:#f3f3f3;font:15px Segoe UI,Arial,sans-serif}.wrap{max-width:1100px;margin:0 auto;padding:14px}.card{background:#111;border:1px solid #2a2a2a;border-radius:12px;padding:12px;margin-top:10px}.links a{color:#1eba4f;text-decoration:none;margin-right:10px}.row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1f1f1f}
  </style></head><body><div class="wrap"><h1 style="margin:0">/hearing</h1><div class="links"><a href="/">/</a><a href="/hearing/live">/hearing/live</a></div>
  <div class="card"><a style="color:#1eba4f" href="" id="astream" target="_blank">Открыть аудиопоток :81/audio</a></div><div class="card"><div id="status">loading...</div></div>
  <script>document.getElementById('astream').href=`http://${location.hostname}:81/audio`;async function j(u){const r=await fetch(u,{cache:'no-store'});if(!r.ok)throw new Error(r.status);return r.json();} function row(k,v){return `<div class="row"><span>${k}</span><span>${v}</span></div>`;}
  async function refresh(){const s=await j('/api/v1/hearing/status');const a=s.audio||{};const c=a.capture||{};document.getElementById('status').innerHTML=row('Ready',String(c.ready??false))+row('Profile',c.profile||'n/a')+row('Signal',c.signal_state||'n/a')+row('Peak',String(c.selected_peak??0))+row('Avg',String(c.average_level??0));}
  refresh();setInterval(()=>refresh().catch(()=>{}),1000);</script></div></body></html>)HTML";

const char kSensoricsPage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>Sensorics</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  body{margin:0;background:#060606;color:#f3f3f3;font:15px Segoe UI,Arial,sans-serif}.wrap{max-width:900px;margin:0 auto;padding:14px}.card{background:#111;border:1px solid #2a2a2a;border-radius:12px;padding:12px;margin-top:10px}.links a{color:#1eba4f;text-decoration:none;margin-right:10px}.row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1f1f1f}
  </style></head><body><div class="wrap"><h1 style="margin:0">/sensorics</h1><div class="links"><a href="/">/</a><a href="/sensorics/live">/sensorics/live</a></div><div class="card" id="status">loading...</div>
  <script>async function j(u){const r=await fetch(u,{cache:'no-store'});if(!r.ok)throw new Error(r.status);return r.json();} function row(k,v){return `<div class="row"><span>${k}</span><span>${v}</span></div>`;}
  async function refresh(){const s=await j('/api/v1/sensorics/status');document.getElementById('status').innerHTML=row('Motion',String(s.motion??false))+row('Light raw',String(s.light_raw??'n/a'))+row('Light norm',s.light_norm!==undefined?Number(s.light_norm).toFixed(3):'n/a')+row('Changed',`${s.motion_changed_ms_ago??0} ms ago`);}
  refresh();setInterval(()=>refresh().catch(()=>{}),1000);</script></div></body></html>)HTML";

const char kMotorSkillsPage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>Motor Skills</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  body{margin:0;background:#060606;color:#f3f3f3;font:15px Segoe UI,Arial,sans-serif}.wrap{max-width:980px;margin:0 auto;padding:14px}.card{background:#111;border:1px solid #2a2a2a;border-radius:12px;padding:12px;margin-top:10px}.links a{color:#1eba4f;text-decoration:none;margin-right:10px}.row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1f1f1f} input,select{width:100%;padding:8px;background:#000;color:#fff;border:1px solid #333;border-radius:8px}
  </style></head><body><div class="wrap"><h1 style="margin:0">/motor_skills</h1><div class="links"><a href="/">/</a><a href="/api/v1/motor_skills/status" target="_blank">status json</a></div>
  <div class="card"><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px"><input id="channel" type="number" min="0" max="15" placeholder="channel"><input id="value" type="number" min="0" max="4095" placeholder="value"><button id="apply">apply channel</button></div><div style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:8px"><input id="scene" type="text" placeholder="scene"><button id="apply-scene">apply scene</button></div><div style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:8px"><input id="freq" type="number" min="40" max="1600" placeholder="frequency"><button id="apply-freq">apply frequency</button></div></div>
  <div class="card" id="status">loading...</div>
  <script>async function j(u,o){const r=await fetch(u,o);if(!r.ok)throw new Error(await r.text());return r.json();} function row(k,v){return `<div class="row"><span>${k}</span><span>${v}</span></div>`;}
  async function refresh(){const s=await j('/api/v1/motor_skills/status',{cache:'no-store'});const p=s.pca9685||{};document.getElementById('status').innerHTML=row('Ready',String(p.ready??false))+row('Address',String(p.address??'n/a'))+row('Frequency',String(p.frequency??'n/a'))+row('Scene',p.active_scene||'none')+row('Active',String(p.active_channels??0));}
  document.getElementById('apply').onclick=async()=>{await j('/api/v1/motor_skills/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel:Number(channel.value),mode:'pwm',value:Number(value.value)})});refresh();};
  document.getElementById('apply-scene').onclick=async()=>{await j('/api/v1/motor_skills/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scene:scene.value})});refresh();};
  document.getElementById('apply-freq').onclick=async()=>{await j('/api/v1/motor_skills/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({frequency:Number(freq.value)})});refresh();};
  refresh();setInterval(()=>refresh().catch(()=>{}),1000);</script></div></body></html>)HTML";

const char kSystemPage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>System</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  body{margin:0;background:#060606;color:#f3f3f3;font:15px Segoe UI,Arial,sans-serif}.wrap{max-width:900px;margin:0 auto;padding:14px}.card{background:#111;border:1px solid #2a2a2a;border-radius:12px;padding:12px;margin-top:10px}.links a{color:#1eba4f;text-decoration:none;margin-right:10px}.row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1f1f1f}
  </style></head><body><div class="wrap"><h1 style="margin:0">/system</h1><div class="links"><a href="/">/</a><a href="/system/status">/system/status</a><a href="/system/ota">/system/ota</a></div><div class="card" id="status">loading...</div>
  <script>async function j(u){const r=await fetch(u,{cache:'no-store'});if(!r.ok)throw new Error(r.status);return r.json();} function row(k,v){return `<div class="row"><span>${k}</span><span>${v}</span></div>`;}
  async function refresh(){const s=await j('/api/v1/system/status');document.getElementById('status').innerHTML=row('IP',s.ip||'0.0.0.0')+row('Boot',s.boot_stage||'unknown')+row('Heap',String(s.heap_free??0))+row('PSRAM',String(s.psram_free??0))+row('Web',String(s.web_ready??false));}
  refresh();setInterval(()=>refresh().catch(()=>{}),1000);</script></div></body></html>)HTML";

const char kVisionLivePage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>Vision Live</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  body{margin:0;background:#060606;color:#f3f3f3;font:15px Segoe UI,Arial,sans-serif}.wrap{max-width:1100px;margin:0 auto;padding:14px}.card{background:#111;border:1px solid #2a2a2a;border-radius:12px;padding:12px;margin-top:10px}
  .video{width:100%;aspect-ratio:4/3;object-fit:contain;border:1px solid #2a2a2a;border-radius:10px;background:#000}.links a{color:#1eba4f;text-decoration:none;margin-right:10px}
  select,input,button{padding:8px;background:#000;color:#fff;border:1px solid #333;border-radius:8px}
  </style></head><body><div class="wrap"><h1 style="margin:0">/vision/live</h1><div class="links"><a href="/vision">/vision</a><a href="/">/</a></div>
  <div class="card" style="position:relative"><img id="v" class="video" alt="vision"><div id="vmeta" style="position:absolute;left:22px;right:22px;bottom:18px;background:rgba(0,0,0,.6);padding:6px 8px;font-size:12px;color:#d0d0d0;border-radius:6px">init...</div></div>
  <div class="card"><div style="display:flex;gap:8px;flex-wrap:wrap"><select id="preset"></select><button id="ap">apply preset</button><input id="fs" type="number" min="0" max="13" placeholder="framesize"><input id="q" type="number" min="4" max="63" placeholder="quality"><button id="ac">apply controls</button></div><div id="msg" style="margin-top:8px;color:#9f9f9f"></div></div>
  <script>const img=document.getElementById('v'); const vmeta=document.getElementById('vmeta'); let streamPaused=false; let streamRetryTimer=null;
  let mode='stream'; let fails=0; let capturePollMs=500; let applyInProgress=false; let stabilizeUntilMs=0;
  function setMeta(t){vmeta.textContent=t;}
  function streamUrl(){return `http://${location.hostname}:81/stream?ts=${Date.now()}`;}
  function captureUrl(){return `/api/v1/vision/capture?ts=${Date.now()}`;}
  function load(){if(streamPaused) return; img.src=(mode==='stream'?streamUrl():captureUrl()); setMeta(mode==='stream'?`stream mode | retries ${fails}`:`capture fallback | ${capturePollMs} ms`);}
  function scheduleReload(delayMs){if(streamPaused) return; if(streamRetryTimer){clearTimeout(streamRetryTimer);} streamRetryTimer=setTimeout(load,delayMs);}
  img.onerror=()=>{
    if(applyInProgress){ setMeta('applying preset...'); return scheduleReload(280); }
    fails++;
    if(mode==='stream'&&fails>=6){mode='capture';capturePollMs=500;setMeta('switch to capture fallback');return scheduleReload(120);}
    if(mode==='stream'){return scheduleReload(Math.min(2200,250*fails));}
    capturePollMs=Math.min(2000,capturePollMs+100);
    if(Date.now()<stabilizeUntilMs){ return scheduleReload(capturePollMs); }
    if(fails%20===0){mode='stream';setMeta('retry stream...'); return scheduleReload(120);}
    scheduleReload(capturePollMs);
  };
  img.onload=()=>{fails=0; if(mode==='capture'){scheduleReload(capturePollMs);} else {setMeta('stream ok');}};
  async function j(u,o){const r=await fetch(u,o);if(!r.ok)throw new Error(await r.text());return r.json();}
  async function fill(){const s=await j('/api/v1/vision/camera');const c=s.camera||{};const p=(c.presets||[]);const sel=document.getElementById('preset');sel.innerHTML='';p.forEach(x=>{const o=document.createElement('option');o.value=x.name;o.textContent=x.name;sel.appendChild(o);}); if(c.preset) sel.value=c.preset; fs.value=c.framesize??''; q.value=c.quality??'';}
  ap.onclick=async()=>{
    try{
      applyInProgress=true; streamPaused=true; setMeta('applying preset...');
      await j('/api/v1/vision/preset/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preset:preset.value})});
      msg.textContent='preset applied';
      await fill();
      mode='capture'; fails=0; capturePollMs=500; stabilizeUntilMs=Date.now()+2200;
      streamPaused=false; applyInProgress=false; scheduleReload(120);
    }catch(e){applyInProgress=false; streamPaused=false; msg.textContent=String(e);}
  };
  ac.onclick=async()=>{
    try{
      applyInProgress=true; streamPaused=true; setMeta('applying controls...');
      await j('/api/v1/vision/camera',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({framesize:Number(fs.value),quality:Number(q.value)})});
      msg.textContent='controls applied';
      await fill();
      mode='capture'; fails=0; capturePollMs=500; stabilizeUntilMs=Date.now()+1800;
      streamPaused=false; applyInProgress=false; scheduleReload(120);
    }catch(e){applyInProgress=false; streamPaused=false; msg.textContent=String(e);}
  };
  function lockStream(){streamPaused=true;} function unlockStream(){streamPaused=false; scheduleReload(80);}
  ['preset','fs','q'].forEach(id=>{const el=document.getElementById(id); if(el){el.addEventListener('focus',lockStream); el.addEventListener('blur',unlockStream);}});
  fill().catch(e=>{msg.textContent=String(e);}); load();</script></div></body></html>)HTML";

const char kHearingLivePage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>Hearing Live</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  body{margin:0;background:#060606;color:#f3f3f3;font:15px Segoe UI,Arial,sans-serif}.wrap{max-width:980px;margin:0 auto;padding:14px}.card{background:#111;border:1px solid #2a2a2a;border-radius:12px;padding:12px;margin-top:10px}.links a{color:#1eba4f;text-decoration:none;margin-right:10px}
  input,select,button{padding:8px;background:#000;color:#fff;border:1px solid #333;border-radius:8px}
  </style></head><body><div class="wrap"><h1 style="margin:0">/hearing/live</h1><div class="links"><a href="/hearing">/hearing</a><a href="/">/</a></div>
  <div class="card"><a id="audio" target="_blank" style="color:#1eba4f"></a></div><div class="card"><div style="display:flex;gap:8px;flex-wrap:wrap"><select id="profile"></select><input id="gain" type="number" min="0.25" max="32" step="0.25"><select id="dc"><option value="true">dc on</option><option value="false">dc off</option></select><select id="slot"><option value="1">left</option><option value="2">right</option></select><input id="shift" type="number" min="0" max="24"><button id="apply">apply</button></div><div id="msg" style="margin-top:8px;color:#9f9f9f"></div></div>
  <script>audio.href=`http://${location.hostname}:81/audio`;audio.textContent=audio.href;
  async function j(u,o){const r=await fetch(u,o);if(!r.ok)throw new Error(await r.text());return r.json();}
  async function fill(){const a=await j('/api/v1/hearing/audio');const c=a.audio?.capture||{};profile.innerHTML='';(c.profiles||[]).forEach(p=>{const o=document.createElement('option');o.value=p;o.textContent=p;profile.appendChild(o);});if(c.profile)profile.value=c.profile;gain.value=Number(c.software_gain??1).toFixed(2);dc.value=String(!!c.dc_block);slot.value=String(c.preferred_slot||1);shift.value=c.sample_shift??0;}
  apply.onclick=async()=>{try{await j('/api/v1/hearing/audio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:profile.value,software_gain:Number(gain.value),dc_block:dc.value==='true',slot:Number(slot.value),shift:Number(shift.value)})}); msg.textContent='applied'; await fill();}catch(e){msg.textContent=String(e);}};
  fill().catch(e=>msg.textContent=String(e));</script></div></body></html>)HTML";

const char kSensoricsLivePage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>Sensorics Live</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  body{margin:0;background:#060606;color:#f3f3f3;font:15px Segoe UI,Arial,sans-serif}.wrap{max-width:860px;margin:0 auto;padding:14px}.card{background:#111;border:1px solid #2a2a2a;border-radius:12px;padding:12px;margin-top:10px}.links a{color:#1eba4f;text-decoration:none;margin-right:10px} pre{background:#000;border:1px solid #2a2a2a;padding:10px;border-radius:10px;white-space:pre-wrap}
  </style></head><body><div class="wrap"><h1 style="margin:0">/sensorics/live</h1><div class="links"><a href="/sensorics">/sensorics</a><a href="/">/</a></div><div class="card"><pre id="raw">loading...</pre></div>
  <script>async function tick(){try{const r=await fetch('/api/v1/sensorics/status',{cache:'no-store'});document.getElementById('raw').textContent=JSON.stringify(await r.json(),null,2);}catch(e){document.getElementById('raw').textContent=String(e);}} tick(); setInterval(tick,1000);</script></div></body></html>)HTML";

const char kSystemStatusPage[] PROGMEM =
  R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>System Status</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;background:#060606;color:#f3f3f3;font:15px Segoe UI,Arial,sans-serif}.wrap{max-width:900px;margin:0 auto;padding:14px}pre{background:#000;border:1px solid #2a2a2a;padding:10px;border-radius:10px;white-space:pre-wrap}</style></head><body><div class="wrap"><h1>/system/status</h1><pre id="raw">loading...</pre></div><script>async function t(){const r=await fetch('/api/v1/system/status',{cache:'no-store'});raw.textContent=JSON.stringify(await r.json(),null,2);} t(); setInterval(()=>t().catch(()=>{}),1000);</script></body></html>)HTML";

esp_err_t indexHandler(httpd_req_t *req) {
  return sendLocalRedirect(req, "/dashboard");
}

esp_err_t dashboardPageHandler(httpd_req_t *req) {
  return sendProgmemHtml(req, kDashboardPage);
}

esp_err_t ctrlDashHandler(httpd_req_t *req) {
  return sendProgmemHtml(req, kRootV2Page);
}

esp_err_t liveHandler(httpd_req_t *req) {
  return sendProgmemHtml(req, kLivePage);
}

esp_err_t otaPageHandler(httpd_req_t *req) {
  return sendProgmemHtml(req, kOtaPage);
}

esp_err_t visionPageHandler(httpd_req_t *req) {
  return sendLocalRedirect(req, "/dashboard");
}

esp_err_t hearingPageHandler(httpd_req_t *req) {
  return sendLocalRedirect(req, "/dashboard");
}

esp_err_t sensoricsPageHandler(httpd_req_t *req) {
  return sendLocalRedirect(req, "/dashboard");
}

esp_err_t motorSkillsPageHandler(httpd_req_t *req) {
  return sendLocalRedirect(req, "/dashboard");
}

esp_err_t systemPageHandler(httpd_req_t *req) {
  return sendLocalRedirect(req, "/ctrldash");
}

esp_err_t visionLivePageHandler(httpd_req_t *req) {
  return sendLocalRedirect(req, "/live");
}

esp_err_t hearingLivePageHandler(httpd_req_t *req) {
  return sendLocalRedirect(req, "/dashboard");
}

esp_err_t sensoricsLivePageHandler(httpd_req_t *req) {
  return sendLocalRedirect(req, "/dashboard");
}

esp_err_t systemStatusPageHandler(httpd_req_t *req) {
  return sendLocalRedirect(req, "/ctrldash");
}

esp_err_t systemOtaPageHandler(httpd_req_t *req) {
  return sendProgmemHtml(req, kOtaPage);
}

esp_err_t sensorsHandler(httpd_req_t *req) {
  String json;
  buildSensorJson(json);
  return sendJson(req, json);
}

esp_err_t statusHandler(httpd_req_t *req) {
  String json;
  buildStatusJson(json);
  return sendJson(req, json);
}

esp_err_t dashboardHandler(httpd_req_t *req) {
  String json;
  buildDashboardJson(json);
  return sendJson(req, json);
}

esp_err_t videoLatencyResetHandler(httpd_req_t *req) {
  videoLatencyReset();
  String json;
  json.reserve(64);
  json = "{\"ok\":true,\"message\":\"video_latency_reset\"}";
  return sendJson(req, json);
}

esp_err_t soundPlayHandler(httpd_req_t *req) {
  char name[16] = "boot";
  const size_t queryLength = httpd_req_get_url_query_len(req);
  if (queryLength > 0) {
    char query[64] = {};
    if (queryLength < sizeof(query) && httpd_req_get_url_query_str(req, query, sizeof(query)) == ESP_OK) {
      httpd_query_key_value(query, "name", name, sizeof(name));
    }
  }
  if (strcmp(name, "boot") != 0 && strcmp(name, "tone") != 0 && strcmp(name, "success") != 0) {
    return sendError(req, "400 Bad Request", "{\"ok\":false,\"error\":\"invalid_sound\"}");
  }

  const bool ok = playSystemSound(name);
  if (!ok) {
    String error = "{\"ok\":false,\"error\":\"sound_play_failed\",\"name\":\"";
    error += name;
    error += "\"}";
    return sendError(req, "503 Service Unavailable", error.c_str());
  }

  String json = "{\"ok\":true,\"name\":\"";
  json += name;
  json += "\"}";
  return sendJson(req, json);
}

esp_err_t pcaStatusHandler(httpd_req_t *req) {
  String json;
  buildPcaStatusJson(json);
  return sendJson(req, json);
}


esp_err_t audioStatusHandler(httpd_req_t *req) {
  String json;
  buildAudioStatusJson(json);
  return sendJson(req, json);
}

esp_err_t otaStatusHandler(httpd_req_t *req) {
  String json;
  buildOtaStatusJson(json);
  return sendJson(req, json);
}

esp_err_t otaUploadHandler(httpd_req_t *req) {
  if (!kOtaEnabled) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"ota_disabled\"}");
  }
  if (req->content_len <= 0) {
    return sendError(req, "400 Bad Request", "{\"error\":\"ota_empty_payload\"}");
  }

  String token;
  readHeaderValue(req, "X-OTA-Token", token);
  if (!otaTokenValid(token.c_str())) {
    return sendError(req, "401 Unauthorized", "{\"error\":\"ota_auth_failed\"}");
  }

  String beginError;
  if (!beginOtaUpload(static_cast<uint32_t>(req->content_len), req->uri, beginError)) {
    const String body = String("{\"error\":\"") + beginError + "\"}";
    return sendError(req, "409 Conflict", body.c_str());
  }

  uint8_t *buffer = static_cast<uint8_t *>(malloc(kOtaChunkBytes));
  if (buffer == nullptr) {
    abortOtaUpload("ota_buffer_alloc_failed");
    return sendError(req, "500 Internal Server Error", "{\"error\":\"ota_buffer_alloc_failed\"}");
  }

  int remaining = req->content_len;
  int timeoutStrikes = 0;
  while (remaining > 0) {
    const int toRead = min(remaining, static_cast<int>(kOtaChunkBytes));
    const int read = httpd_req_recv(req, reinterpret_cast<char *>(buffer), toRead);
    if (read == HTTPD_SOCK_ERR_TIMEOUT) {
      if (++timeoutStrikes >= 10) {
        free(buffer);
        abortOtaUpload("ota_recv_timeout");
        return sendError(req, "500 Internal Server Error", "{\"error\":\"ota_recv_timeout\"}");
      }
      continue;
    }
    timeoutStrikes = 0;
    if (read <= 0) {
      free(buffer);
      abortOtaUpload("ota_recv_failed");
      return sendError(req, "500 Internal Server Error", "{\"error\":\"ota_recv_failed\"}");
    }

    String writeError;
    if (!writeOtaChunk(buffer, static_cast<size_t>(read), writeError)) {
      free(buffer);
      abortOtaUpload(writeError.c_str());
      const String body = String("{\"error\":\"") + writeError + "\"}";
      return sendError(req, "500 Internal Server Error", body.c_str());
    }
    remaining -= read;
  }
  free(buffer);

  String endError;
  if (!finishOtaUpload(endError)) {
    const String body = String("{\"error\":\"") + endError + "\"}";
    return sendError(req, "500 Internal Server Error", body.c_str());
  }

  httpd_resp_set_hdr(req, "Connection", "close");
  return sendJson(req, "{\"ok\":true,\"message\":\"ota_uploaded_reboot_pending\"}");
}

esp_err_t audioConfigHandler(httpd_req_t *req) {
  String body;
  if (!readRequestBody(req, body)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  }

  AudioRuntimeUpdate update;
  String profileStorage;
  if (!parseAudioRuntimeUpdate(body, update, profileStorage) || !applyAudioRuntimeUpdate(update)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_audio_update\"}");
  }

  String json;
  buildAudioStatusJson(json);
  return sendJson(req, json);
}

esp_err_t audioClipHandler(httpd_req_t *req) {
  uint32_t clipMs = 4000;
  const size_t queryLength = httpd_req_get_url_query_len(req);
  if (queryLength > 0) {
    char query[96] = {};
    if (queryLength < sizeof(query) && httpd_req_get_url_query_str(req, query, sizeof(query)) == ESP_OK) {
      char value[16] = {};
      if (httpd_query_key_value(query, "ms", value, sizeof(value)) == ESP_OK) {
        clipMs = static_cast<uint32_t>(constrain(atoi(value), 250, 4000));
      }
    }
  }

  const size_t clipBytes = getAudioClipBytesForDurationMs(clipMs);
  if (clipBytes == 0) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"audio_clip_unavailable\"}");
  }

  uint8_t *clipBuffer = static_cast<uint8_t *>(heap_caps_malloc(clipBytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (clipBuffer == nullptr) {
    clipBuffer = static_cast<uint8_t *>(malloc(clipBytes));
  }
  if (clipBuffer == nullptr) {
    return sendError(req, "500 Internal Server Error", "{\"error\":\"audio_clip_alloc_failed\"}");
  }

  size_t outBytes = 0;
  const bool ok = copyRecentAudioClip(clipMs, clipBuffer, clipBytes, outBytes);
  if (!ok || outBytes == 0) {
    free(clipBuffer);
    return sendError(req, "503 Service Unavailable", "{\"error\":\"audio_clip_empty\"}");
  }

  const WavHeader header = makeWavHeader(static_cast<uint32_t>(outBytes));
  httpd_resp_set_type(req, kAudioContentType);
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=audio_clip.wav");

  esp_err_t result = httpd_resp_send_chunk(req, reinterpret_cast<const char *>(&header), sizeof(header));
  constexpr size_t kClipSendChunk = 4096;
  for (size_t offset = 0; offset < outBytes && result == ESP_OK; offset += kClipSendChunk) {
    const size_t sendSize = min(kClipSendChunk, outBytes - offset);
    result = httpd_resp_send_chunk(req, reinterpret_cast<const char *>(clipBuffer) + offset, sendSize);
  }
  if (result == ESP_OK) {
    result = httpd_resp_send_chunk(req, nullptr, 0);
  }

  free(clipBuffer);
  return result;
}

esp_err_t cameraStatusHandler(httpd_req_t *req) {
  String json;
  json.reserve(1024);
  json = "{";
  appendCameraJson(json);
  json += "}";
  return sendJson(req, json);
}

esp_err_t cameraUpdateHandler(httpd_req_t *req) {
  String body;
  if (!readRequestBody(req, body)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  }

  CameraControlUpdate update;
  if (!parseCameraUpdate(body, update) || !applyCameraControlUpdate(update)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_camera_update\"}");
  }

  String json;
  json.reserve(1024);
  json = "{";
  appendCameraJson(json);
  json += "}";
  return sendJson(req, json);
}

esp_err_t cameraPresetApplyHandler(httpd_req_t *req) {
  String body;
  if (!readRequestBody(req, body)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  }

  String preset;
  if (!extractJsonString(body, "preset", preset) || !applyCameraPreset(preset.c_str())) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_camera_preset\"}");
  }

  String json;
  json.reserve(1024);
  json = "{";
  appendCameraJson(json);
  json += "}";
  return sendJson(req, json);
}

esp_err_t cameraPresetSaveHandler(httpd_req_t *req) {
  String body;
  if (!readRequestBody(req, body)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  }
  String preset;
  if (!extractJsonString(body, "preset", preset) || !saveCameraPreset(preset.c_str())) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_camera_preset_save\"}");
  }
  String json;
  json.reserve(1024);
  json = "{";
  appendCameraJson(json);
  json += "}";
  return sendJson(req, json);
}

esp_err_t cameraPresetDeleteHandler(httpd_req_t *req) {
  String body;
  if (!readRequestBody(req, body)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  }
  String preset;
  if (!extractJsonString(body, "preset", preset) || !deleteCameraPreset(preset.c_str())) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_camera_preset_delete\"}");
  }
  String json;
  json.reserve(1024);
  json = "{";
  appendCameraJson(json);
  json += "}";
  return sendJson(req, json);
}

esp_err_t cameraPresetResetDefaultsHandler(httpd_req_t *req) {
  (void)req;
  resetBuiltInCameraPresets();
  String json;
  json.reserve(1024);
  json = "{";
  appendCameraJson(json);
  json += "}";
  return sendJson(req, json);
}

esp_err_t captureHandler(httpd_req_t *req) {
  noteCameraStreamDemand();
  size_t latestFrameBytes = getLatestCameraFrameSize();
  if (latestFrameBytes > 0) {
    uint8_t *frameBuffer = static_cast<uint8_t *>(malloc(latestFrameBytes));
    if (frameBuffer != nullptr) {
      size_t frameLength = 0;
      int64_t timestampUs = 0;
      uint32_t sequence = 0;
      if (copyLatestCameraFrame(frameBuffer, latestFrameBytes, frameLength, timestampUs, sequence)) {
        httpd_resp_set_type(req, "image/jpeg");
        httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
        httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
        char ts[32];
        snprintf(ts, sizeof(ts), "%ld.%06ld", static_cast<long>(timestampUs / 1000000LL), static_cast<long>(timestampUs % 1000000LL));
        httpd_resp_set_hdr(req, "X-Timestamp", ts);
        const esp_err_t result = httpd_resp_send(req, reinterpret_cast<const char *>(frameBuffer), frameLength);
        free(frameBuffer);
        return result;
      }
      free(frameBuffer);
    }
  }

  camera_fb_t *fb = captureCameraFrame();
  if (fb == nullptr) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"camera_frame_not_ready\"}");
  }

  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  char ts[32];
  snprintf(ts, sizeof(ts), "%" PRIu32 ".%06" PRIu32, (uint32_t)fb->timestamp.tv_sec, (uint32_t)fb->timestamp.tv_usec);
  httpd_resp_set_hdr(req, "X-Timestamp", ts);
  const esp_err_t result = httpd_resp_send(req, reinterpret_cast<const char *>(fb->buf), fb->len);
  releaseCameraFrame(fb);
  return result;
}

esp_err_t streamHandler(httpd_req_t *req) {
  noteCameraStreamDemand();
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool cameraReady = gRuntimeState.cameraReady;
  const uint32_t startingGeneration = gRuntimeState.cameraGeneration;
  gRuntimeState.videoClients = gRuntimeState.videoClients + 1;
  setLastStreamErrorLocked("none");
  portEXIT_CRITICAL(&gRuntimeStateMux);

  if (!cameraReady) {
    portENTER_CRITICAL(&gRuntimeStateMux);
    setLastStreamErrorLocked("camera_not_ready");
    if (gRuntimeState.videoClients > 0) {
      gRuntimeState.videoClients = gRuntimeState.videoClients - 1;
    }
    portEXIT_CRITICAL(&gRuntimeStateMux);
    return sendError(req, "503 Service Unavailable", "{\"error\":\"camera_not_ready\"}");
  }

  httpd_resp_set_type(req, kStreamContentType);
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  httpd_resp_set_hdr(req, "X-Accel-Buffering", "no");

  esp_err_t result = ESP_OK;
  int64_t lastFrameAtUs = 0;
  uint8_t *frameBuffer = static_cast<uint8_t *>(malloc(kStreamFrameBufferReserveBytes));
  if (frameBuffer == nullptr) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"frame_buffer_alloc_failed\"}");
  }
  size_t frameBufferCapacity = kStreamFrameBufferReserveBytes;
  uint32_t lastSentSequence = 0;
  uint8_t slowSendStrikes = 0;
  const char *streamErrorCode = "client_closed";
  bool sendFailed = false;
  bool clientResetLikely = false;

  while (result == ESP_OK) {
    const int64_t loopStartedUs = esp_timer_get_time();
    noteCameraStreamDemand();
    portENTER_CRITICAL(&gRuntimeStateMux);
    const uint32_t currentGeneration = gRuntimeState.cameraGeneration;
    portEXIT_CRITICAL(&gRuntimeStateMux);
    if (currentGeneration != startingGeneration) {
      portENTER_CRITICAL(&gRuntimeStateMux);
      gRuntimeState.streamRestarts = gRuntimeState.streamRestarts + 1;
      portEXIT_CRITICAL(&gRuntimeStateMux);
      streamErrorCode = "generation_change";
      break;
    }

    size_t requiredFrameBytes = getLatestCameraFrameSize();
    if (requiredFrameBytes == 0) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }

    if (frameBufferCapacity < requiredFrameBytes) {
      uint8_t *newBuffer = static_cast<uint8_t *>(realloc(frameBuffer, requiredFrameBytes));
      if (newBuffer == nullptr) {
        result = ESP_ERR_NO_MEM;
        streamErrorCode = "buffer_alloc";
        break;
      }
      frameBuffer = newBuffer;
      frameBufferCapacity = requiredFrameBytes;
      videoLatencyIncrementBufferRealloc();
    }

    size_t frameLength = 0;
    int64_t timestampUs = 0;
    uint32_t frameSequence = 0;
    LatestFrameCopyStatus copyStatus = LatestFrameCopyStatus::InvalidArgs;
    if (!copyLatestCameraFrame(
        frameBuffer,
        frameBufferCapacity,
        frameLength,
        timestampUs,
        frameSequence,
        lastSentSequence,
        &copyStatus)) {
      if (copyStatus == LatestFrameCopyStatus::NoNewFrame) {
        videoLatencyIncrementNoNewFramePoll();
        vTaskDelay(pdMS_TO_TICKS(5));
        continue;
      }
      if (copyStatus == LatestFrameCopyStatus::CapacityTooSmall || frameLength > frameBufferCapacity) {
        continue;
      }
      if (copyStatus == LatestFrameCopyStatus::MutexTimeout || copyStatus == LatestFrameCopyStatus::InvalidArgs) {
        videoLatencyIncrementCopyFrameMiss();
      }
      vTaskDelay(pdMS_TO_TICKS(5));
      continue;
    }

    const int64_t frameCopiedAtUs = esp_timer_get_time();
    const uint32_t frameAgeBeforeSendMs = static_cast<uint32_t>((frameCopiedAtUs - timestampUs) / 1000);
    videoLatencyRecordFrameAgeBeforeSendMs(frameAgeBeforeSendMs);
    if (frameAgeBeforeSendMs >= kStreamStaleFrameThresholdMs) {
      videoLatencyIncrementFrameSkippedDueStale();
      continue;
    }

    const int64_t sendStartedUs = esp_timer_get_time();
    const int64_t boundaryStartedUs = sendStartedUs;
    result = httpd_resp_send_chunk(req, kStreamBoundaryChunk, strlen(kStreamBoundaryChunk));
    const uint32_t boundaryUs = static_cast<uint32_t>(esp_timer_get_time() - boundaryStartedUs);
    videoLatencyRecordSendBoundaryMs(boundaryUs / 1000);
    videoLatencyRecordSendBoundaryUs(boundaryUs);
    if (result != ESP_OK) {
      sendFailed = true;
      clientResetLikely = true;
      streamErrorCode = "send_boundary_fail";
      break;
    }
    if (result == ESP_OK) {
      const long tsSec = static_cast<long>(timestampUs / 1000000LL);
      const long tsUsec = static_cast<long>(timestampUs % 1000000LL);
      char header[160];
      const size_t headerLen = snprintf(
        header,
        sizeof(header),
        "Content-Type: image/jpeg\r\nContent-Length: %u\r\nX-Sequence: %lu\r\nX-Timestamp: %ld.%06ld\r\n\r\n",
        static_cast<unsigned>(frameLength),
        static_cast<unsigned long>(frameSequence),
        tsSec,
        tsUsec
      );
      const int64_t headerStartedUs = esp_timer_get_time();
      result = httpd_resp_send_chunk(req, header, headerLen);
      const uint32_t headerUs = static_cast<uint32_t>(esp_timer_get_time() - headerStartedUs);
      videoLatencyRecordSendHeaderMs(headerUs / 1000);
      videoLatencyRecordSendHeaderUs(headerUs);
      if (result != ESP_OK) {
        sendFailed = true;
        clientResetLikely = true;
        streamErrorCode = "send_header_fail";
        break;
      }
    }
    if (result == ESP_OK) {
      const int64_t payloadStartedUs = esp_timer_get_time();
      result = httpd_resp_send_chunk(req, reinterpret_cast<const char *>(frameBuffer), frameLength);
      const uint32_t payloadUs = static_cast<uint32_t>(esp_timer_get_time() - payloadStartedUs);
      videoLatencyRecordSendPayloadMs(payloadUs / 1000);
      videoLatencyRecordSendPayloadUs(payloadUs);
      if (result != ESP_OK) {
        sendFailed = true;
        clientResetLikely = true;
        streamErrorCode = "send_frame_fail";
        break;
      }
    }

    const int64_t nowUs = esp_timer_get_time();
    const uint32_t frameTimeMs = lastFrameAtUs == 0 ? 0 : static_cast<uint32_t>((nowUs - lastFrameAtUs) / 1000);
    lastFrameAtUs = nowUs;
    const uint32_t sendTimeMs = static_cast<uint32_t>((esp_timer_get_time() - sendStartedUs) / 1000);
    const uint32_t droppedFrames = (lastSentSequence != 0 && frameSequence > lastSentSequence + 1)
      ? (frameSequence - lastSentSequence - 1)
      : 0;
    lastSentSequence = frameSequence;
    const uint32_t e2eEstimateMs = static_cast<uint32_t>((nowUs - timestampUs) / 1000);
    videoLatencyRecordE2eEstimateMs(e2eEstimateMs);
    videoLatencyRecordStreamLoopMs(static_cast<uint32_t>((nowUs - loopStartedUs) / 1000));
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.streamSendTimeMs = sendTimeMs;
    gRuntimeState.frameTimeMs = frameTimeMs;
    if (frameTimeMs > 0) {
      gRuntimeState.frameRateTimes10 = static_cast<uint32_t>(10000.0f / static_cast<float>(frameTimeMs));
    }
    gRuntimeState.lastFrameSize = static_cast<uint32_t>(frameLength);
    gRuntimeState.lastJpegSize = static_cast<uint32_t>(frameLength);
    gRuntimeState.streamDrops = gRuntimeState.streamDrops + droppedFrames;
    portEXIT_CRITICAL(&gRuntimeStateMux);

    if (sendTimeMs >= kStreamSlowSendThresholdMs) {
      slowSendStrikes = static_cast<uint8_t>(slowSendStrikes + 1);
      videoLatencyIncrementSlowSendStrike();
      if (slowSendStrikes >= kStreamSlowSendStrikeLimit) {
        result = ESP_ERR_TIMEOUT;
        portENTER_CRITICAL(&gRuntimeStateMux);
        gRuntimeState.streamTimeoutCloses = gRuntimeState.streamTimeoutCloses + 1;
        portEXIT_CRITICAL(&gRuntimeStateMux);
        streamErrorCode = "slow_client_timeout";
        break;
      }
    } else {
      slowSendStrikes = 0;
    }
  }

  free(frameBuffer);

  portENTER_CRITICAL(&gRuntimeStateMux);
  if (sendFailed) {
    gRuntimeState.streamSendFailures = gRuntimeState.streamSendFailures + 1;
  }
  if (clientResetLikely) {
    gRuntimeState.streamClientResets = gRuntimeState.streamClientResets + 1;
  }
  setLastStreamErrorLocked(streamErrorCode);
  if (gRuntimeState.videoClients > 0) {
    gRuntimeState.videoClients = gRuntimeState.videoClients - 1;
  }
  portEXIT_CRITICAL(&gRuntimeStateMux);

  return result;
}

WavHeader makeWavHeader(uint32_t dataBytes) {
  WavHeader header = {};
  const uint16_t channels = getAudioOutputChannels();
  memcpy(header.riff, "RIFF", 4);
  header.chunkSize = dataBytes == 0xFFFFFFFFUL ? 0xFFFFFFFFUL : (36 + dataBytes);
  memcpy(header.wave, "WAVE", 4);
  memcpy(header.fmt, "fmt ", 4);
  header.subchunk1Size = 16;
  header.audioFormat = 1;
  header.numChannels = channels;
  header.sampleRate = kAudioSampleRate;
  header.bitsPerSample = kAudioBitsPerSample;
  header.byteRate = kAudioSampleRate * channels * (kAudioBitsPerSample / 8);
  header.blockAlign = channels * (kAudioBitsPerSample / 8);
  memcpy(header.data, "data", 4);
  header.subchunk2Size = dataBytes;
  return header;
}

esp_err_t audioHandler(httpd_req_t *req) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool audioReady = gRuntimeState.audioReady;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  if (!audioReady) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"audio_not_ready\"}");
  }

  httpd_resp_set_type(req, kAudioContentType);
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  httpd_resp_set_hdr(req, "X-Accel-Buffering", "no");
  char audioChBuf[4];
  snprintf(audioChBuf, sizeof(audioChBuf), "%u", getAudioOutputChannels());
  httpd_resp_set_hdr(req, "X-Audio-Sample-Rate", "16000");
  httpd_resp_set_hdr(req, "X-Audio-Bits", "16");
  httpd_resp_set_hdr(req, "X-Audio-Channels", audioChBuf);

  const WavHeader header = makeWavHeader();
  esp_err_t result = httpd_resp_send_chunk(req, reinterpret_cast<const char *>(&header), sizeof(header));
  if (result != ESP_OK) {
    return result;
  }

  auto *chunk = static_cast<uint8_t *>(malloc(kAudioReadChunkBytes));
  if (chunk == nullptr) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"audio_chunk_alloc_failed\"}");
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.audioClients = gRuntimeState.audioClients + 1;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  uint64_t cursor = getAudioWriteSequence();

  while (result == ESP_OK) {
    size_t bytesRead = 0;
    if (!readAudioChunk(chunk, kAudioReadChunkBytes, bytesRead, cursor)) {
      result = ESP_FAIL;
      break;
    }

    if (bytesRead == 0) {
      vTaskDelay(pdMS_TO_TICKS(8));
      continue;
    }

    result = httpd_resp_send_chunk(req, reinterpret_cast<const char *>(chunk), bytesRead);
  }

  free(chunk);

  portENTER_CRITICAL(&gRuntimeStateMux);
  if (gRuntimeState.audioClients > 0) {
    gRuntimeState.audioClients = gRuntimeState.audioClients - 1;
  }
  portEXIT_CRITICAL(&gRuntimeStateMux);

  return result;
}

esp_err_t speakerHandler(httpd_req_t *req) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool speakerReady = gRuntimeState.speakerReady;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  if (!speakerReady) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"speaker_not_ready\"}");
  }

  if (req->method != HTTP_POST) {
    return sendError(req, "405 Method Not Allowed", "{\"error\":\"method_not_allowed\"}");
  }
  if (!beginSpeakerStream()) {
    return sendError(req, "409 Conflict", "{\"error\":\"speaker_sink_busy\"}");
  }

  uint8_t buffer[kSpeakerHttpChunkBytes];
  bool wavHeaderHandled = false;
  int remaining = req->content_len;
  esp_err_t result = ESP_OK;

  while (remaining > 0) {
    const int toRead = min(remaining, static_cast<int>(sizeof(buffer)));
    const int received = httpd_req_recv(req, reinterpret_cast<char *>(buffer), toRead);
    if (received <= 0) {
      result = ESP_FAIL;
      break;
    }
    remaining -= received;

    const uint8_t *payload = buffer;
    size_t payloadLen = received;
    if (!wavHeaderHandled) {
      wavHeaderHandled = true;
      if (memcmp(buffer, "RIFF", 4) == 0 && memcmp(buffer + 8, "WAVE", 4) == 0) {
        if (received < static_cast<int>(sizeof(WavHeader))) {
          // Header fragmented across TCP chunks — reject to avoid playing header bytes as audio.
          endSpeakerStream();
          return sendError(req, "400 Bad Request", "{\"error\":\"speaker_wav_header_incomplete\"}");
        }
        const WavHeader *hdr = reinterpret_cast<const WavHeader *>(buffer);
        if (hdr->audioFormat != 1
            || hdr->numChannels != 1
            || hdr->sampleRate != kSpeakerSampleRate
            || hdr->bitsPerSample != 16) {
          endSpeakerStream();
          return sendError(req, "400 Bad Request", "{\"error\":\"speaker_wav_format_mismatch\"}");
        }
        payload = buffer + sizeof(WavHeader);
        payloadLen = received - sizeof(WavHeader);
      }
    }

    if (payloadLen > 0) {
      // Pace writes to I2S drain rate — if the ring is full, yield CPU so
      // speakerPlaybackTask can drain it rather than silently dropping data.
      // Ring drains at kSpeakerSampleRate × 2 B/s ≈ 88 KB/s; a 4 ms yield
      // frees ~353 bytes, so a 1024 B chunk needs at most ~3 retries.
      size_t offset = 0;
      while (offset < payloadLen) {
        offset += writeSpeakerData(payload + offset, payloadLen - offset);
        if (offset < payloadLen) {
          vTaskDelay(pdMS_TO_TICKS(4));
        }
      }
    }
  }

  endSpeakerStream();
  if (result != ESP_OK) {
    return sendError(req, "500 Internal Server Error", "{\"error\":\"speaker_stream_failed\"}");
  }

  httpd_resp_set_type(req, "application/json");
  return httpd_resp_send(req, "{\"status\":\"ok\"}", HTTPD_RESP_USE_STRLEN);
}

esp_err_t audioMovedHandler(httpd_req_t *req) {
  return sendMovedEndpoint(req, kStreamPort, "/audio");
}

esp_err_t speakerMovedHandler(httpd_req_t *req) {
  return sendMovedEndpoint(req, kStreamPort, "/speaker");
}

esp_err_t pcaChannelHandler(httpd_req_t *req) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool ready = gRuntimeState.pca9685Ready;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  if (!ready) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"pca9685_not_ready\"}");
  }

  String body;
  if (!readRequestBody(req, body)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  }

  Pca9685ChannelUpdate update = {};
  if (!parseChannelUpdate(body, update) || !applyPca9685Update(update)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_channel_update\"}");
  }

  String json;
  buildPcaStatusJson(json);
  return sendJson(req, json);
}

esp_err_t pcaChannelsHandler(httpd_req_t *req) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool ready = gRuntimeState.pca9685Ready;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  if (!ready) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"pca9685_not_ready\"}");
  }

  String body;
  if (!readRequestBody(req, body)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  }

  Pca9685ChannelUpdate updates[16] = {};
  const size_t count = parseChannelUpdates(body, updates, 16);
  if (count == 0 || !applyPca9685Updates(updates, count)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_channel_updates\"}");
  }

  String json;
  buildPcaStatusJson(json);
  return sendJson(req, json);
}

esp_err_t pcaSceneHandler(httpd_req_t *req) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool ready = gRuntimeState.pca9685Ready;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  if (!ready) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"pca9685_not_ready\"}");
  }

  String body;
  if (!readRequestBody(req, body)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  }

  String scene;
  if (!extractJsonString(body, "scene", scene) || !applyPca9685Scene(scene.c_str())) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_scene\"}");
  }

  String json;
  buildPcaStatusJson(json);
  return sendJson(req, json);
}

esp_err_t pcaFrequencyHandler(httpd_req_t *req) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool ready = gRuntimeState.pca9685Ready;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  if (!ready) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"pca9685_not_ready\"}");
  }

  String body;
  if (!readRequestBody(req, body)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  }

  int frequency = 0;
  if (!extractJsonInt(body, "frequency", frequency) || !setPca9685Frequency(static_cast<uint16_t>(frequency))) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_frequency\"}");
  }

  String json;
  buildPcaStatusJson(json);
  return sendJson(req, json);
}

esp_err_t motorSkillsStatusHandler(httpd_req_t *req) {
  return pcaStatusHandler(req);
}

esp_err_t motorSkillsControlHandler(httpd_req_t *req) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool ready = gRuntimeState.pca9685Ready;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  if (!ready) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"pca9685_not_ready\"}");
  }

  String body;
  if (!readRequestBody(req, body)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  }

  String scene;
  int intValue = 0;
  bool ok = false;
  if (extractJsonString(body, "scene", scene)) {
    ok = applyPca9685Scene(scene.c_str());
  } else if (extractJsonInt(body, "frequency", intValue)) {
    ok = setPca9685Frequency(static_cast<uint16_t>(intValue));
  } else {
    Pca9685ChannelUpdate updates[16] = {};
    const size_t count = parseChannelUpdates(body, updates, 16);
    if (count > 0) {
      ok = applyPca9685Updates(updates, count);
    } else {
      Pca9685ChannelUpdate update = {};
      ok = parseChannelUpdate(body, update) && applyPca9685Update(update);
    }
  }

  if (!ok) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_motor_skills_control\"}");
  }

  String json;
  buildPcaStatusJson(json);
  return sendJson(req, json);
}

esp_err_t v1VisionStatusHandler(httpd_req_t *req) {
  String json;
  String dashboard;
  buildDashboardJson(dashboard);
  json.reserve(1536);
  json = "{";
  appendCameraJson(json);
  json += ",\"dashboard\":";
  json += dashboard;
  json += "}";
  return sendJson(req, json);
}

esp_err_t v1HearingStatusHandler(httpd_req_t *req) {
  String json;
  String audio;
  String dashboard;
  buildAudioStatusJson(audio);
  buildDashboardJson(dashboard);
  json.reserve(2048);
  json = "{";
  json += "\"audio\":";
  json += audio;
  json += ",\"dashboard\":";
  json += dashboard;
  json += "}";
  return sendJson(req, json);
}

esp_err_t v1SensoricsStatusHandler(httpd_req_t *req) { return sensorsHandler(req); }
esp_err_t v1SystemStatusHandler(httpd_req_t *req) { return statusHandler(req); }
esp_err_t v1SystemDashboardHandler(httpd_req_t *req) { return dashboardHandler(req); }
esp_err_t v1SystemOtaStatusHandler(httpd_req_t *req) { return otaStatusHandler(req); }
esp_err_t v1SystemOtaUploadHandler(httpd_req_t *req) { return otaUploadHandler(req); }
esp_err_t v1VisionCameraGetHandler(httpd_req_t *req) { return cameraStatusHandler(req); }
esp_err_t v1VisionCameraPostHandler(httpd_req_t *req) { return cameraUpdateHandler(req); }
esp_err_t v1VisionPresetApplyHandler(httpd_req_t *req) { return cameraPresetApplyHandler(req); }
esp_err_t v1VisionPresetSaveHandler(httpd_req_t *req) { return cameraPresetSaveHandler(req); }
esp_err_t v1VisionPresetDeleteHandler(httpd_req_t *req) { return cameraPresetDeleteHandler(req); }
esp_err_t v1VisionPresetResetDefaultsHandler(httpd_req_t *req) { return cameraPresetResetDefaultsHandler(req); }
esp_err_t v1VisionCaptureHandler(httpd_req_t *req) { return captureHandler(req); }
esp_err_t v1HearingAudioGetHandler(httpd_req_t *req) { return audioStatusHandler(req); }
esp_err_t v1HearingAudioPostHandler(httpd_req_t *req) { return audioConfigHandler(req); }
esp_err_t v1HearingClipHandler(httpd_req_t *req) { return audioClipHandler(req); }

esp_err_t wsHandler(httpd_req_t *req) {
  if (req->method == HTTP_GET) {
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.websocketClients = gRuntimeState.websocketClients + 1;
    portEXIT_CRITICAL(&gRuntimeStateMux);
    return ESP_OK;
  }

  httpd_ws_frame_t frame = {};
  frame.type = HTTPD_WS_TYPE_TEXT;
  esp_err_t result = httpd_ws_recv_frame(req, &frame, 0);
  if (result != ESP_OK) {
    return result;
  }

  if (frame.len > 0) {
    static constexpr size_t kWsMaxIncomingFrameBytes = 8192;
    if (frame.len > kWsMaxIncomingFrameBytes) {
      return ESP_ERR_INVALID_SIZE;
    }
    uint8_t *buffer = static_cast<uint8_t *>(malloc(frame.len + 1));
    if (buffer == nullptr) {
      return ESP_ERR_NO_MEM;
    }
    frame.payload = buffer;
    result = httpd_ws_recv_frame(req, &frame, frame.len);
    free(buffer);
    if (result != ESP_OK) {
      return result;
    }
  }

  String json;
  buildStatusJson(json);
  httpd_ws_frame_t reply = {};
  reply.type = HTTPD_WS_TYPE_TEXT;
  reply.payload = reinterpret_cast<uint8_t *>(const_cast<char *>(json.c_str()));
  reply.len = json.length();
  return httpd_ws_send_frame(req, &reply);
}

void registerControlHandlers(httpd_handle_t server) {
  httpd_uri_t indexUri = makeHttpUri("/", HTTP_GET, indexHandler);
  httpd_uri_t dashboardPageUri = makeHttpUri("/dashboard", HTTP_GET, dashboardPageHandler);
  httpd_uri_t ctrlDashUri = makeHttpUri("/ctrldash", HTTP_GET, ctrlDashHandler);
  httpd_uri_t liveUri = makeHttpUri("/live", HTTP_GET, liveHandler);
  httpd_uri_t otaPageUri = makeHttpUri("/ota", HTTP_GET, otaPageHandler);

  httpd_uri_t visionUiUri = makeHttpUri("/vision", HTTP_GET, visionPageHandler);
  httpd_uri_t hearingUiUri = makeHttpUri("/hearing", HTTP_GET, hearingPageHandler);
  httpd_uri_t sensoricsUiUri = makeHttpUri("/sensorics", HTTP_GET, sensoricsPageHandler);
  httpd_uri_t motorSkillsUiUri = makeHttpUri("/motor_skills", HTTP_GET, motorSkillsPageHandler);
  httpd_uri_t systemUiUri = makeHttpUri("/system", HTTP_GET, systemPageHandler);
  httpd_uri_t visionLiveUiUri = makeHttpUri("/vision/live", HTTP_GET, visionLivePageHandler);
  httpd_uri_t hearingLiveUiUri = makeHttpUri("/hearing/live", HTTP_GET, hearingLivePageHandler);
  httpd_uri_t sensoricsLiveUiUri = makeHttpUri("/sensorics/live", HTTP_GET, sensoricsLivePageHandler);
  httpd_uri_t systemStatusUiUri = makeHttpUri("/system/status", HTTP_GET, systemStatusPageHandler);
  httpd_uri_t systemOtaUiUri = makeHttpUri("/system/ota", HTTP_GET, systemOtaPageHandler);

  httpd_uri_t sensorsUri = makeHttpUri("/api/sensors", HTTP_GET, sensorsHandler);
  httpd_uri_t statusUri = makeHttpUri("/api/status", HTTP_GET, statusHandler);
  httpd_uri_t dashboardUri = makeHttpUri("/api/dashboard", HTTP_GET, dashboardHandler);
  httpd_uri_t videoLatencyResetUri = makeHttpUri("/api/video_latency/reset", HTTP_POST, videoLatencyResetHandler);
  httpd_uri_t soundPlayUri = makeHttpUri("/api/sound/play", HTTP_POST, soundPlayHandler);
  httpd_uri_t otaStatusUri = makeHttpUri("/api/ota", HTTP_GET, otaStatusHandler);
  httpd_uri_t otaUploadUri = makeHttpUri("/api/ota/upload", HTTP_POST, otaUploadHandler);
  httpd_uri_t pcaStatusUri = makeHttpUri("/api/pca9685", HTTP_GET, pcaStatusHandler);
  httpd_uri_t pcaChannelUri = makeHttpUri("/api/pca9685/channel", HTTP_POST, pcaChannelHandler);
  httpd_uri_t pcaChannelsUri = makeHttpUri("/api/pca9685/channels", HTTP_POST, pcaChannelsHandler);
  httpd_uri_t pcaSceneUri = makeHttpUri("/api/pca9685/scene", HTTP_POST, pcaSceneHandler);
  httpd_uri_t pcaFrequencyUri = makeHttpUri("/api/pca9685/frequency", HTTP_POST, pcaFrequencyHandler);
  httpd_uri_t audioStatusUri = makeHttpUri("/api/audio", HTTP_GET, audioStatusHandler);
  httpd_uri_t audioConfigUri = makeHttpUri("/api/audio", HTTP_POST, audioConfigHandler);
  httpd_uri_t audioClipUri = makeHttpUri("/api/audio/clip", HTTP_GET, audioClipHandler);
  httpd_uri_t cameraStatusUri = makeHttpUri("/api/camera", HTTP_GET, cameraStatusHandler);
  httpd_uri_t cameraUpdateUri = makeHttpUri("/api/camera", HTTP_POST, cameraUpdateHandler);
  httpd_uri_t cameraPresetApplyUri = makeHttpUri("/api/camera/preset/apply", HTTP_POST, cameraPresetApplyHandler);
  httpd_uri_t cameraPresetSaveUri = makeHttpUri("/api/camera/preset/save", HTTP_POST, cameraPresetSaveHandler);
  httpd_uri_t cameraPresetDeleteUri = makeHttpUri("/api/camera/preset/delete", HTTP_POST, cameraPresetDeleteHandler);
  httpd_uri_t cameraPresetResetDefaultsUri = makeHttpUri("/api/camera/preset/resetdefaults", HTTP_POST, cameraPresetResetDefaultsHandler);
  httpd_uri_t captureUri = makeHttpUri("/capture", HTTP_GET, captureHandler);
  httpd_uri_t wsUri = makeWebSocketUri("/ws", wsHandler);
  httpd_uri_t audioMovedUri = makeHttpUri("/audio", HTTP_GET, audioMovedHandler);
  httpd_uri_t speakerMovedUri = makeHttpUri("/speaker", HTTP_POST, speakerMovedHandler);

  httpd_register_uri_handler(server, &indexUri);
  httpd_register_uri_handler(server, &dashboardPageUri);
  httpd_register_uri_handler(server, &ctrlDashUri);
  httpd_register_uri_handler(server, &liveUri);
  httpd_register_uri_handler(server, &otaPageUri);
  httpd_register_uri_handler(server, &visionUiUri);
  httpd_register_uri_handler(server, &hearingUiUri);
  httpd_register_uri_handler(server, &sensoricsUiUri);
  httpd_register_uri_handler(server, &motorSkillsUiUri);
  httpd_register_uri_handler(server, &systemUiUri);
  httpd_register_uri_handler(server, &visionLiveUiUri);
  httpd_register_uri_handler(server, &hearingLiveUiUri);
  httpd_register_uri_handler(server, &sensoricsLiveUiUri);
  httpd_register_uri_handler(server, &systemStatusUiUri);
  httpd_register_uri_handler(server, &systemOtaUiUri);

  httpd_register_uri_handler(server, &sensorsUri);
  httpd_register_uri_handler(server, &statusUri);
  httpd_register_uri_handler(server, &dashboardUri);
  httpd_register_uri_handler(server, &videoLatencyResetUri);
  httpd_register_uri_handler(server, &soundPlayUri);
  httpd_register_uri_handler(server, &otaStatusUri);
  httpd_register_uri_handler(server, &otaUploadUri);
  httpd_register_uri_handler(server, &pcaStatusUri);
  httpd_register_uri_handler(server, &pcaChannelUri);
  httpd_register_uri_handler(server, &pcaChannelsUri);
  httpd_register_uri_handler(server, &pcaSceneUri);
  httpd_register_uri_handler(server, &pcaFrequencyUri);
  httpd_register_uri_handler(server, &audioStatusUri);
  httpd_register_uri_handler(server, &audioConfigUri);
  httpd_register_uri_handler(server, &audioClipUri);
  httpd_register_uri_handler(server, &cameraStatusUri);
  httpd_register_uri_handler(server, &cameraUpdateUri);
  httpd_register_uri_handler(server, &cameraPresetApplyUri);
  httpd_register_uri_handler(server, &cameraPresetSaveUri);
  httpd_register_uri_handler(server, &cameraPresetDeleteUri);
  httpd_register_uri_handler(server, &cameraPresetResetDefaultsUri);
  httpd_register_uri_handler(server, &captureUri);
  httpd_register_uri_handler(server, &wsUri);
  httpd_register_uri_handler(server, &audioMovedUri);
  httpd_register_uri_handler(server, &speakerMovedUri);
}

void registerStreamHandlers(httpd_handle_t server) {
  httpd_uri_t streamUri = makeHttpUri("/stream", HTTP_GET, streamHandler);
  httpd_register_uri_handler(server, &streamUri);
}

void registerAudioHandlers(httpd_handle_t server) {
  httpd_uri_t audioUri = makeHttpUri("/audio", HTTP_GET, audioHandler);
  httpd_register_uri_handler(server, &audioUri);
}

void registerSpeakerHandlers(httpd_handle_t server) {
  httpd_uri_t speakerUri = makeHttpUri("/speaker", HTTP_POST, speakerHandler);
  httpd_register_uri_handler(server, &speakerUri);
}

esp_err_t streamServerOpenFn(httpd_handle_t /*hd*/, int sockfd) {
  int nodelay = 1;
  setsockopt(sockfd, IPPROTO_TCP, TCP_NODELAY, &nodelay, sizeof(nodelay));
  return ESP_OK;
}

// ── System management handlers ─────────────────────────────────────────────

static void doReset(void* /*arg*/) { esp_restart(); }

esp_err_t systemResetHandler(httpd_req_t *req) {
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_sendstr(req, "{\"ok\":true,\"action\":\"reset\",\"delay_ms\":300}");
  // Schedule reset after response is flushed (~300ms)
  esp_timer_handle_t t;
  esp_timer_create_args_t args = {};
  args.callback = doReset;
  args.name = "sys_reset";
  if (esp_timer_create(&args, &t) == ESP_OK) {
    esp_timer_start_once(t, 300 * 1000ULL);
  }
  return ESP_OK;
}

esp_err_t systemStreamRestartHandler(httpd_req_t *req) {
  // Stop stream server — kills all stale camera/audio/speaker connections.
  // Restarted immediately so new clients can connect without physical RST.
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  if (sStreamServer != nullptr) {
    httpd_stop(sStreamServer);
    sStreamServer = nullptr;
  }
  // Brief yield so OS cleans up sockets before we re-bind.
  vTaskDelay(pdMS_TO_TICKS(150));

  httpd_config_t streamConfig = HTTPD_DEFAULT_CONFIG();
  streamConfig.server_port = kStreamPort;
  streamConfig.ctrl_port   = kHttpPort + 1 + 1;  // avoid collision with control ctrl_port
  streamConfig.max_uri_handlers  = 6;
  streamConfig.max_open_sockets  = 4;
  streamConfig.lru_purge_enable  = true;
  streamConfig.send_wait_timeout = 10;
  streamConfig.stack_size        = 8192;
  streamConfig.open_fn           = streamServerOpenFn;

  bool ok = (httpd_start(&sStreamServer, &streamConfig) == ESP_OK);
  if (ok) {
    registerStreamHandlers(sStreamServer);
    registerAudioHandlers(sStreamServer);
    registerSpeakerHandlers(sStreamServer);
  }
  char buf[64];
  snprintf(buf, sizeof(buf), "{\"ok\":%s,\"stream_port\":%u}", ok ? "true" : "false", kStreamPort);
  httpd_resp_sendstr(req, buf);
  return ESP_OK;
}

esp_err_t systemInfoHandler(httpd_req_t *req) {
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  portENTER_CRITICAL(&gRuntimeStateMux);
  const uint32_t up = gRuntimeState.uptimeMs;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  char buf[256];
  snprintf(buf, sizeof(buf),
    "{\"uptime_ms\":%lu,\"heap_free\":%lu,\"heap_min_free\":%lu,\"psram_free\":%lu}",
    (unsigned long)up,
    (unsigned long)esp_get_free_heap_size(),
    (unsigned long)esp_get_minimum_free_heap_size(),
    (unsigned long)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
  httpd_resp_sendstr(req, buf);
  return ESP_OK;
}

void registerSystemHandlers(httpd_handle_t server) {
  httpd_uri_t resetUri       = makeHttpUri("/api/system/reset",          HTTP_POST, systemResetHandler);
  httpd_uri_t streamRestUri  = makeHttpUri("/api/system/stream/restart", HTTP_POST, systemStreamRestartHandler);
  httpd_uri_t infoUri        = makeHttpUri("/api/system/info",           HTTP_GET,  systemInfoHandler);
  httpd_register_uri_handler(server, &resetUri);
  httpd_register_uri_handler(server, &streamRestUri);
  httpd_register_uri_handler(server, &infoUri);
}

}  // namespace

bool startWebServer() {
  if (sControlServer != nullptr && sStreamServer != nullptr) {
    return true;
  }

  if (sControlServer != nullptr) {
    httpd_stop(sControlServer);
    sControlServer = nullptr;
  }
  if (sStreamServer != nullptr) {
    httpd_stop(sStreamServer);
    sStreamServer = nullptr;
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.webReady = false;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  httpd_config_t controlConfig = HTTPD_DEFAULT_CONFIG();
  controlConfig.server_port = kHttpPort;
  controlConfig.max_uri_handlers = 40;
  controlConfig.max_open_sockets = 4;
  controlConfig.lru_purge_enable = true;
  controlConfig.stack_size = 8192;

  if (httpd_start(&sControlServer, &controlConfig) != ESP_OK) {
    bootLog("web", "failed to start control HTTP server");
    return false;
  }
  registerControlHandlers(sControlServer);
  registerSystemHandlers(sControlServer);

  httpd_config_t streamConfig = HTTPD_DEFAULT_CONFIG();
  streamConfig.server_port = kStreamPort;
  streamConfig.ctrl_port = controlConfig.ctrl_port + 1;
  streamConfig.max_uri_handlers = 6;
  streamConfig.max_open_sockets = 4;
  streamConfig.lru_purge_enable = true;
  streamConfig.send_wait_timeout = 10;
  streamConfig.stack_size = 8192;
  streamConfig.open_fn = streamServerOpenFn;

  if (httpd_start(&sStreamServer, &streamConfig) != ESP_OK) {
    bootLog("web", "failed to start stream HTTP server");
    httpd_stop(sControlServer);
    sControlServer = nullptr;
    return false;
  }
  registerStreamHandlers(sStreamServer);
  registerAudioHandlers(sStreamServer);
  registerSpeakerHandlers(sStreamServer);

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.webReady = true;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  bootLogf("web", "ready on ports control=%u streams=%u (video+audio+speaker)", kHttpPort, kStreamPort);

  return true;
}

void broadcastTelemetry() {
  if (sControlServer == nullptr) {
    return;
  }

  size_t clients = 16;
  int clientFds[16] = {};
  if (httpd_get_client_list(sControlServer, &clients, clientFds) != ESP_OK) {
    return;
  }

  uint32_t wsClients = 0;
  String json;
  buildStatusJson(json);

  httpd_ws_frame_t frame = {};
  frame.type = HTTPD_WS_TYPE_TEXT;
  frame.payload = reinterpret_cast<uint8_t *>(const_cast<char *>(json.c_str()));
  frame.len = json.length();

  for (size_t i = 0; i < clients; ++i) {
    if (httpd_ws_get_fd_info(sControlServer, clientFds[i]) == HTTPD_WS_CLIENT_WEBSOCKET) {
      if (httpd_ws_send_frame_async(sControlServer, clientFds[i], &frame) == ESP_OK) {
        wsClients++;
      }
    }
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.websocketClients = wsClients;
  portEXIT_CRITICAL(&gRuntimeStateMux);
}
