#include "WebServerModule.h"

#include <cctype>
#include <cinttypes>
#include <cstring>
#include <cstdlib>

#include <WiFi.h>
#include "esp_http_server.h"
#include "esp_timer.h"

#include "../../config/AdamsConfig.h"
#include "../audio/AudioModule.h"
#include "../core/BootDiagnostics.h"
#include "../core/OtaModule.h"
#include "../camera/CameraModule.h"
#include "../io/Pca9685Module.h"
#include "../core/RuntimeState.h"

namespace {

httpd_handle_t sControlServer = nullptr;
httpd_handle_t sStreamServer = nullptr;

constexpr char kStreamContentType[] = "multipart/x-mixed-replace;boundary=123456789000000000000987654321";
constexpr char kStreamBoundaryChunk[] = "\r\n--123456789000000000000987654321\r\n";
constexpr char kAudioContentType[] = "audio/wav";
constexpr size_t kOtaChunkBytes = 2048;

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

void appendCommonStatusFields(String &json) {
  json += "\"uptime_ms\":";
  json += String(millis());
  json += ",\"wifi_rssi\":";
  json += String(WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0);
  json += ",\"heap_free\":";
  json += String(ESP.getFreeHeap());
  json += ",\"psram_free\":";
  json += String(ESP.getFreePsram());
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
    json += "}";
  }
  json += "]";
  json += ",\"capabilities\":{";
  json += "\"framesize\":{\"supported\":true,\"min\":";
  json += String(FRAMESIZE_QQVGA);
  json += ",\"max\":";
  json += String(FRAMESIZE_QSXGA);
  json += "},\"quality\":{\"supported\":true,\"min\":4,\"max\":63}";
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
  char bootStage[sizeof(gRuntimeState.bootStage)];
  strncpy(bootStage, gRuntimeState.bootStage, sizeof(bootStage) - 1);
  bootStage[sizeof(bootStage) - 1] = '\0';
  char lastInitError[sizeof(gRuntimeState.lastInitError)];
  strncpy(lastInitError, gRuntimeState.lastInitError, sizeof(lastInitError) - 1);
  lastInitError[sizeof(lastInitError) - 1] = '\0';
  char wifiIp[sizeof(gRuntimeState.wifiIp)];
  strncpy(wifiIp, gRuntimeState.wifiIp, sizeof(wifiIp) - 1);
  wifiIp[sizeof(wifiIp) - 1] = '\0';
  char lastReinitReason[sizeof(gRuntimeState.lastCameraReinitReason)];
  strncpy(lastReinitReason, gRuntimeState.lastCameraReinitReason, sizeof(lastReinitReason) - 1);
  lastReinitReason[sizeof(lastReinitReason) - 1] = '\0';
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
  json += ",\"wifi_connected\":";
  json += wifiConnected ? "true" : "false";
  json += ",\"ip\":\"";
  json += wifiIp;
  json += "\"";
  json += ",\"wifi_rssi_cached\":";
  json += String(wifiRssi);
  json += ",\"psram_found\":";
  json += psramFound() ? "true" : "false";
  json += ",\"video_clients\":";
  json += String(videoClients);
  json += ",\"stream_clients\":";
  json += String(videoClients);
  json += ",\"audio_clients\":";
  json += String(audioClients);
  json += ",\"websocket_clients\":";
  json += String(websocketClients);
  json += ",\"camera_ready\":";
  json += cameraReady ? "true" : "false";
  json += ",\"camera_producer_running\":";
  json += producerRunning ? "true" : "false";
  json += ",\"camera_generation\":";
  json += String(generation);
  json += ",\"audio_ready\":";
  json += audioReady ? "true" : "false";
  json += ",\"speaker_ready\":";
  json += speakerReady ? "true" : "false";
  json += ",\"web_ready\":";
  json += webReady ? "true" : "false";
  json += ",\"speaker_client_active\":";
  json += speakerClientActive ? "true" : "false";
  json += ",\"speaker_buffer_fill\":";
  json += String(speakerBufferFill);
  json += ",\"speaker_underruns\":";
  json += String(speakerUnderruns);
  json += ",\"speaker_overflows\":";
  json += String(speakerOverflows);
  json += ",\"sensors_ready\":";
  json += sensorsReady ? "true" : "false";
  json += ",\"frame_time_ms\":";
  json += String(frameTimeMs);
  json += ",\"fps\":";
  json += String(frameRateTimes10 / 10.0f, 1);
  json += ",\"last_frame_size\":";
  json += String(lastFrameSize);
  json += ",\"capture_frame_time_ms\":";
  json += String(captureFrameTimeMs);
  json += ",\"capture_fps\":";
  json += String(captureFpsTimes10 / 10.0f, 1);
  json += ",\"last_jpeg_size\":";
  json += String(lastJpegSize);
  json += ",\"stream_restarts\":";
  json += String(streamRestarts);
  json += ",\"stream_drops\":";
  json += String(streamDrops);
  json += ",\"camera_reinit_count\":";
  json += String(cameraReinitCount);
  json += ",\"stream_send_time_ms\":";
  json += String(streamSendTimeMs);
  json += ",\"last_camera_reinit_reason\":\"";
  json += lastReinitReason;
  json += "\",";
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
  json += String(lightRaw);
  json += ",\"light_norm\":";
  json += String(lightNorm, 3);
  json += ",\"motion\":";
  json += motion ? "true" : "false";
  json += ",\"motion_changed_ms_ago\":";
  json += String(millis() - motionChangedAtMs);
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
  const bool wifiConnected = gRuntimeState.wifiConnected;
  const int32_t wifiRssi = gRuntimeState.wifiRssi;
  const bool cameraReady = gRuntimeState.cameraReady;
  const bool producerRunning = gRuntimeState.cameraProducerRunning;
  const uint32_t generation = gRuntimeState.cameraGeneration;
  const uint32_t captureFrameTimeMs = gRuntimeState.captureFrameTimeMs;
  const uint32_t captureFpsTimes10 = gRuntimeState.captureFrameRateTimes10;
  const uint32_t lastJpegSize = gRuntimeState.lastJpegSize;
  const uint32_t videoClients = gRuntimeState.videoClients;
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
  char wifiIp[sizeof(gRuntimeState.wifiIp)];
  strncpy(wifiIp, gRuntimeState.wifiIp, sizeof(wifiIp) - 1);
  wifiIp[sizeof(wifiIp) - 1] = '\0';
  char cameraPreset[sizeof(gRuntimeState.cameraPreset)];
  strncpy(cameraPreset, gRuntimeState.cameraPreset, sizeof(cameraPreset) - 1);
  cameraPreset[sizeof(cameraPreset) - 1] = '\0';
  portEXIT_CRITICAL(&gRuntimeStateMux);

  json.reserve(768);
  json = "{";
  appendCommonStatusFields(json);
  json += ",\"wifi_connected\":";
  json += wifiConnected ? "true" : "false";
  json += ",\"wifi_rssi_cached\":";
  json += String(wifiRssi);
  json += ",\"ip\":\"";
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
  json += ",\"audio_ready\":";
  json += audioReady ? "true" : "false";
  json += ",\"speaker_ready\":";
  json += speakerReady ? "true" : "false";
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

bool readHeaderValue(httpd_req_t *req, const char *name, String &value) {
  value = "";
  const size_t headerLen = httpd_req_get_hdr_value_len(req, name);
  if (headerLen == 0) {
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
    update.preferredSlot = intValue == 2 ? 2 : 1;
  }
  if (extractJsonInt(body, "shift", intValue)) {
    update.hasShiftOverride = true;
    update.sampleShift = static_cast<uint8_t>(constrain(intValue, 0, 24));
  }

  return update.hasProfile || update.hasSoftwareGain || update.hasDcBlock || update.hasSlotOverride || update.hasShiftOverride;
}

String formatDashboardPage() {
  String html;
  html.reserve(18000);
  html += R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>AdamS Server</title><meta name="viewport" content="width=device-width,initial-scale=1">)HTML";
  html += R"HTML(<style>
  :root{--bg:#0b1117;--panel:#131b24;--panel2:#192432;--line:#2a3949;--text:#e7edf4;--muted:#93a4b4;--accent:#65c9ff;--good:#4fd59d;--warn:#f4c26b;--bad:#ff837b}
  *{box-sizing:border-box} body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:linear-gradient(180deg,#091017,#0f1720 55%,#0d141b);color:var(--text)}
  .wrap{max-width:1280px;margin:0 auto;padding:18px}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px}.span-12{grid-column:span 12}.span-8{grid-column:span 8}.span-6{grid-column:span 6}.span-4{grid-column:span 4}.span-3{grid-column:span 3}
  .card{background:rgba(19,27,36,.94);border:1px solid var(--line);border-radius:16px;padding:16px;box-shadow:0 10px 26px rgba(0,0,0,.26)}
  .hero{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:16px}.hero h1{margin:0;font-size:28px}.hero p{margin:6px 0 0;color:var(--muted)}
  .badge{display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}.ok{background:rgba(79,213,157,.14);color:var(--good)}.warn{background:rgba(244,194,107,.14);color:var(--warn)}.bad{background:rgba(255,131,123,.14);color:var(--bad)}
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.kpi{padding:14px;border-radius:14px;background:var(--panel2);border:1px solid var(--line)}.kpi .label{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}.kpi .value{margin-top:6px;font-size:22px;font-weight:700}
  .video{width:100%;aspect-ratio:4/3;background:#06090d;border:1px solid var(--line);border-radius:14px;display:block;object-fit:contain}
  .meta,.muted{color:var(--muted)} .list{display:flex;flex-direction:column;gap:10px}.row{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid rgba(42,57,73,.45)}.row:last-child{border-bottom:none}
  .controls{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.field{display:flex;flex-direction:column;gap:6px}.field label{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
  input,select,button{font:inherit} input,select{width:100%;padding:10px 12px;border-radius:12px;border:1px solid var(--line);background:#0f151c;color:var(--text)}
  .actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.btn{padding:10px 14px;border-radius:12px;border:1px solid var(--line);background:#102130;color:var(--text);cursor:pointer}.btn.secondary{background:#111820}.btn:hover{border-color:var(--accent)}
  .links{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px}.links a{color:var(--accent);text-decoration:none}.mono{font-family:Consolas,Menlo,monospace} details{margin-top:12px} pre{margin:8px 0 0;padding:12px;border-radius:12px;background:#0c1218;border:1px solid var(--line);white-space:pre-wrap;word-break:break-word}
  @media (max-width:980px){.span-8,.span-6,.span-4,.span-3{grid-column:span 12}.kpis{grid-template-columns:repeat(2,1fr)}.controls{grid-template-columns:1fr}}
  </style></head><body><div class="wrap">
  <div class="hero"><div><h1>AdamS Server</h1><p>Диагностическая панель ESP32-S3. Микрофон `INMP441` и playback на `PCM5102` показаны отдельно, чтобы не путать независимые аудиоканалы.</p></div><div class="muted">ESP32-S3 AV + telemetry</div></div>
  <div class="grid">
    <section class="card span-12"><div class="kpis" id="top-kpis"></div></section>
    <section class="card span-8"><div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px"><div><h2 style="margin:0">Видео</h2><div class="meta" id="video-meta">ожидание потока</div></div><div class="links"><a href="/live" target="_blank">/live</a><a href="/stream" target="_blank">/stream</a><a href="javascript:void(0)" id="reload-video">перезагрузить поток</a><a href="javascript:void(0)" id="refresh-camera">обновить камеру</a></div></div><img id="video-stream" class="video" alt="Live stream"><div class="links muted"><a href="/capture" target="_blank">/capture</a><a href="/api/dashboard" target="_blank">/api/dashboard</a><a href="/api/status" target="_blank">/api/status</a><a href="/api/camera" target="_blank">/api/camera</a></div></section>
    <section class="card span-4"><h2 style="margin-top:0">Состояние</h2><div class="list" id="runtime-card"></div></section>
    <section class="card span-3"><h2 style="margin-top:0">Сеть</h2><div class="list" id="network-card"></div></section>
    <section class="card span-3"><h2 style="margin-top:0">Камера</h2><div class="list" id="camera-card"></div></section>
    <section class="card span-3"><h2 style="margin-top:0">Микрофон</h2><div class="list" id="mic-card"></div></section>
    <section class="card span-3"><h2 style="margin-top:0">Выход PCM5102</h2><div class="list" id="speaker-card"></div></section>
    <section class="card span-4"><h2 style="margin-top:0">Сенсоры</h2><div class="list" id="sensor-card"></div></section>
    <section class="card span-4"><h2 style="margin-top:0">PCA9685</h2><div class="list" id="pca-card"></div></section>
    <section class="card span-4"><h2 style="margin-top:0">Эндпоинты</h2><div class="links" id="endpoint-links"></div></section>
    <section class="card span-6"><h2 style="margin-top:0">Настройки камеры</h2><div class="controls">
      <div class="field"><label>Пресет</label><select id="preset"></select></div>
      <div class="field"><label>Имя пресета</label><input id="preset_name" type="text" placeholder="my_preset"></div>
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
    </div><div class="actions"><button class="btn" id="apply-preset">Применить</button><button class="btn secondary" id="save-preset">Сохранить новый/текущий</button><button class="btn secondary" id="reset-presets">Сбросить встроенные</button><button class="btn secondary" id="delete-preset">Удалить пресет</button></div><div id="camera-feedback" class="muted" style="margin-top:10px"></div></section>
    <section class="card span-6"><h2 style="margin-top:0">Расширенная аудиодиагностика</h2><div class="controls">
      <div class="field"><label>Capture profile</label><select id="audio_profile"></select></div>
      <div class="field"><label>Software gain</label><input id="audio_gain" type="number" min="0.25" max="32" step="0.25"></div>
      <div class="field"><label>DC block</label><select id="audio_dc_block"><option value="true">включено</option><option value="false">выключено</option></select></div>
      <div class="field"><label>Слот</label><select id="audio_slot"><option value="1">left</option><option value="2">right</option></select></div>
      <div class="field"><label>Shift</label><input id="audio_shift" type="number" min="0" max="24"></div>
      <div class="field"><label>Длина тест-клипа, мс</label><input id="audio_clip_ms" type="number" min="250" max="5000" step="250" value="2000"></div>
    </div><div class="actions"><button class="btn" id="apply-audio">Применить аудио-настройки</button><a class="btn secondary" id="audio_clip_link" href="/api/audio/clip?ms=2000" target="_blank">Открыть тестовый WAV</a><a class="btn secondary" href="/audio" target="_blank">Открыть бесконечный /audio</a></div><div id="audio-feedback" class="muted" style="margin-top:10px"></div><details><summary class="muted">Сырые аудио-данные</summary><pre id="raw-audio"></pre></details></section>
    <section class="card span-12"><h2 style="margin-top:0">Детали</h2><details><summary class="muted">Показать raw dashboard JSON</summary><pre id="raw-dashboard"></pre></details><details><summary class="muted">Подсказки для go2rtc / ffmpeg</summary><pre class="mono">go2rtc:
  streams:
    adams_cam: ffmpeg:http://ESP32_IP:81/stream#video=h264

ffmpeg test:
  ffmpeg -fflags nobuffer -flags low_delay -f mjpeg -i http://ESP32_IP:81/stream -f null -

audio clip:
  http://ESP32_IP/api/audio/clip?ms=2000

audio stream:
  ffmpeg -i http://ESP32_IP/audio -f null -</pre></details></section>
  </div>)HTML";
  html += R"HTML(<script>
  const state={dashboard:null,camera:null,audio:null,pca:null};
  const frameOptions=[
    {value:0,label:'QQVGA'},{value:3,label:'HQVGA'},{value:5,label:'QVGA'},{value:6,label:'CIF'},
    {value:8,label:'VGA'},{value:9,label:'SVGA'},{value:10,label:'XGA'},{value:11,label:'HD'},{value:12,label:'SXGA'},{value:13,label:'UXGA'}
  ];
  const framesizeSelect=document.getElementById('framesize');
  const presetSelect=document.getElementById('preset');
  const videoEl=document.getElementById('video-stream');
  let videoBackoffMs=500;
  let videoReloadTimer=null;
  let lastGeneration=-1;
  frameOptions.forEach(opt=>{const el=document.createElement('option');el.value=opt.value;el.textContent=`${opt.label} (${opt.value})`;framesizeSelect.appendChild(el);});
  function badge(text,kind){return `<span class="badge ${kind}">${text}</span>`;}
  function fmtMs(ms){if(ms===undefined||ms===null) return 'n/a'; if(ms<1000) return `${ms} ms`; return `${(ms/1000).toFixed(1)} s`;}
  function fmtPct(v){return `${(v*100).toFixed(1)}%`;}
  function fmtBytes(v){if(!v) return '0 KB'; if(v>=1024*1024) return `${(v/1024/1024).toFixed(2)} MB`; return `${(v/1024).toFixed(0)} KB`;}
  async function fetchJson(url){const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`${url} -> ${r.status}`); return r.json();}
  async function postJson(url,payload){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); if(!r.ok) throw new Error(await r.text()); return r.json();}
  function currentPayload(){
    return {
      framesize:Number(document.getElementById('framesize').value),
      quality:Number(document.getElementById('quality').value),
      brightness:Number(document.getElementById('brightness').value),
      contrast:Number(document.getElementById('contrast').value),
      saturation:Number(document.getElementById('saturation').value),
      sharpness:Number(document.getElementById('sharpness').value),
      denoise:Number(document.getElementById('denoise').value),
      gain_ceiling:Number(document.getElementById('gain_ceiling').value),
      awb:document.getElementById('awb').value==='true',
      agc:document.getElementById('agc').value==='true',
      aec:document.getElementById('aec').value==='true',
      hmirror:document.getElementById('hmirror').value==='true',
      vflip:document.getElementById('vflip').value==='true'
    };
  }
  function fillCameraControls(){
    const c=(state.camera&&state.camera.camera)?state.camera.camera:state.camera||{};
    const presets=Array.isArray(c.presets)?c.presets:[];
    presetSelect.innerHTML='';
    presets.forEach(p=>{const opt=document.createElement('option');opt.value=p.name;opt.textContent=p.builtin?`${p.name} [builtin]`:p.name;presetSelect.appendChild(opt);});
    if(c.preset) presetSelect.value=c.preset;
    document.getElementById('preset_name').value=c.preset||'';
    if(c.framesize!==undefined) document.getElementById('framesize').value=String(c.framesize);
    if(c.quality!==undefined) document.getElementById('quality').value=c.quality;
    if(c.brightness!==undefined) document.getElementById('brightness').value=c.brightness;
    if(c.contrast!==undefined) document.getElementById('contrast').value=c.contrast;
    if(c.saturation!==undefined) document.getElementById('saturation').value=c.saturation;
    if(c.sharpness!==undefined) document.getElementById('sharpness').value=c.sharpness;
    if(c.denoise!==undefined) document.getElementById('denoise').value=c.denoise;
    if(c.gain_ceiling!==undefined) document.getElementById('gain_ceiling').value=c.gain_ceiling;
    if(c.awb!==undefined) document.getElementById('awb').value=String(!!c.awb);
    if(c.agc!==undefined) document.getElementById('agc').value=String(!!c.agc);
    if(c.aec!==undefined) document.getElementById('aec').value=String(!!c.aec);
    if(c.hmirror!==undefined) document.getElementById('hmirror').value=String(!!c.hmirror);
    if(c.vflip!==undefined) document.getElementById('vflip').value=String(!!c.vflip);
  }
  function fillAudioControls(){
    const a=state.audio&&state.audio.capture?state.audio.capture:{};
    const profiles=Array.isArray(a.profiles)?a.profiles:[];
    const select=document.getElementById('audio_profile');
    select.innerHTML='';
    profiles.forEach(name=>{const opt=document.createElement('option');opt.value=name;opt.textContent=name;select.appendChild(opt);});
    if(a.profile) select.value=a.profile;
    document.getElementById('audio_gain').value=a.software_gain!==undefined?Number(a.software_gain).toFixed(2):'1.00';
    document.getElementById('audio_dc_block').value=String(!!a.dc_block);
    document.getElementById('audio_slot').value=String(a.preferred_slot||1);
    document.getElementById('audio_shift').value=a.sample_shift!==undefined?a.sample_shift:0;
    updateAudioClipLink();
  }
  function updateAudioClipLink(){
    const clipMs=Math.max(250,Math.min(5000,Number(document.getElementById('audio_clip_ms').value||2000)));
    document.getElementById('audio_clip_link').href=`/api/audio/clip?ms=${clipMs}`;
  }
  function render(){
    const d=state.dashboard||{};
    const c=(state.camera&&state.camera.camera)?state.camera.camera:state.camera||{};
    const a=state.audio&&state.audio.capture?state.audio.capture:{};
    const playback=state.audio&&state.audio.playback?state.audio.playback:{};
    const p=(state.pca&&state.pca.pca9685)?state.pca.pca9685:(state.pca||{}).pca9685||{};
    document.getElementById('top-kpis').innerHTML=[
      ['Сеть', d.wifi_connected? 'подключена':'повтор', d.wifi_connected ? 'ok':'warn'],
      ['Камера', d.camera_ready? 'готова':'ошибка', d.camera_ready ? 'ok':'bad'],
      ['Микрофон', d.audio_ready? 'готов':'ошибка', d.audio_ready ? 'ok':'bad'],
      ['PCM5102', d.speaker_ready? 'готов':'ошибка', d.speaker_ready ? 'ok':'bad']
    ].map(([label,val,kind])=>`<div class="kpi"><div class="label">${label}</div><div class="value">${val}</div><div style="margin-top:8px">${badge(val,kind)}</div></div>`).join('');
    document.getElementById('runtime-card').innerHTML=`
      <div class="row"><span>IP</span><span class="mono">${d.ip||'0.0.0.0'}</span></div>
      <div class="row"><span>Стадия загрузки</span><span>${d.boot_stage||'unknown'}</span></div>
      <div class="row"><span>Последняя ошибка</span><span class="mono">${d.last_init_error||'нет'}</span></div>
      <div class="row"><span>OTA</span><span>${d.ota_in_progress ? badge(`обновление ${d.ota_progress_pct||0}%`,'warn') : (d.ota_ready ? badge('готово','ok') : badge('выкл','bad'))}</span></div>
      <div class="row"><span>Пресет / поколение</span><span>${d.camera_preset||'custom'} / ${d.camera_generation||0}</span></div>
      <div class="row"><span>FPS / кадр</span><span>${d.fps||0} fps / ${fmtMs(d.frame_time_ms)}</span></div>
      <div class="row"><span>Последний JPEG / зрители</span><span>${fmtBytes(d.last_frame_size||0)} / ${d.video_clients||0}</span></div>
      <div class="row"><span>Heap / PSRAM</span><span>${fmtBytes(d.heap_free||0)} / ${fmtBytes(d.psram_free||0)}</span></div>`;
    document.getElementById('network-card').innerHTML=`
      <div class="row"><span>Wi‑Fi</span><span>${d.wifi_connected ? badge('подключено','ok') : badge('повтор','warn')}</span></div>
      <div class="row"><span>RSSI</span><span>${d.wifi_rssi_cached ?? d.wifi_rssi ?? 'n/a'}</span></div>
      <div class="row"><span>API</span><span><a href="/api/status" target="_blank">/api/status</a></span></div>`;
    document.getElementById('camera-card').innerHTML=`
      <div class="row"><span>Состояние</span><span>${d.camera_ready ? badge('готова','ok') : badge('ошибка','bad')}</span></div>
      <div class="row"><span>Producer</span><span>${d.camera_producer_running ? badge('идёт','ok') : badge('стоп','warn')}</span></div>
      <div class="row"><span>Пресет</span><span>${d.camera_preset||'balanced'}</span></div>
      <div class="row"><span>Поток</span><span><a href="/stream" target="_blank">/stream</a></span></div>`;
    document.getElementById('mic-card').innerHTML=`
      <div class="row"><span>Состояние</span><span>${a.ready ? badge('готов','ok') : badge('ошибка','bad')}</span></div>
      <div class="row"><span>Профиль</span><span class="mono">${a.profile||'n/a'}</span></div>
      <div class="row"><span>Уровень</span><span>${a.selected_peak||0} / avg ${a.average_level||0}</span></div>
      <div class="row"><span>Сигнал</span><span>${badge(a.signal_state||'silence', (a.signal_state==='active')?'ok':((a.signal_state==='weak'||a.signal_state==='silence')?'warn':'bad'))}</span></div>
      <div class="row"><span>Тестовый поток</span><span><a href="/audio" target="_blank">/audio</a></span></div>`;
    document.getElementById('speaker-card').innerHTML=`
      <div class="row"><span>Состояние</span><span>${playback.ready ? badge('готов','ok') : badge('ошибка','bad')}</span></div>
      <div class="row"><span>Клиент</span><span>${playback.client_active ? badge('активен','warn') : badge('нет','ok')}</span></div>
      <div class="row"><span>Буфер</span><span>${fmtBytes(playback.buffer_fill||0)}</span></div>
      <div class="row"><span>Underruns / overflows</span><span>${playback.underruns||0} / ${playback.overflows||0}</span></div>`;
    document.getElementById('sensor-card').innerHTML=`
      <div class="row"><span>Движение</span><span>${d.motion ? badge('обнаружено','warn') : badge('нет','ok')}</span></div>
      <div class="row"><span>Свет raw</span><span>${d.light_raw ?? 'n/a'}</span></div>
      <div class="row"><span>Свет нормализованный</span><span>${d.light_norm!==undefined ? fmtPct(d.light_norm) : 'n/a'}</span></div>
      <div class="row"><span>Изменение движения</span><span>${fmtMs(d.motion_changed_ms_ago)}</span></div>`;
    document.getElementById('pca-card').innerHTML=`
      <div class="row"><span>Состояние</span><span>${d.pca9685_ready ? badge('готов','ok') : badge('ошибка','bad')}</span></div>
      <div class="row"><span>Адрес</span><span>${p.address!==undefined ? '0x'+Number(p.address).toString(16) : 'n/a'}</span></div>
      <div class="row"><span>Частота</span><span>${p.frequency||0} Hz</span></div>
      <div class="row"><span>Сцена</span><span>${p.active_scene||'n/a'}</span></div>
      <div class="row"><span>Активные каналы</span><span>${p.active_channels||0}</span></div>`;
    document.getElementById('endpoint-links').innerHTML=['/','/live','/ota','/capture','/stream','/audio','/speaker','/api/dashboard','/api/status','/api/audio','/api/audio/clip?ms=2000','/api/camera','/api/sensors','/api/pca9685','/api/ota','/ws']
      .map(url=>`<a href="${url}" target="_blank">${url}</a>`).join('');
    document.getElementById('video-meta').textContent=`${d.camera_preset||'balanced'} | ${d.fps||0} FPS | ${fmtMs(d.frame_time_ms)} | gen ${d.camera_generation||0}`;
    document.getElementById('raw-dashboard').textContent=JSON.stringify({dashboard:d,camera:state.camera,audio:state.audio,pca:state.pca},null,2);
    document.getElementById('raw-audio').textContent=JSON.stringify(state.audio,null,2);
  }
  function streamUrl(){return `http://${location.hostname}:81/stream?gen=${lastGeneration}&ts=${Date.now()}`;}
  function attachVideo(force=false){
    if(force || !videoEl.src || !videoEl.src.includes(`/stream?gen=${lastGeneration}`)){ videoEl.src=streamUrl(); }
  }
  function scheduleVideoReload(force=false){
    if(videoReloadTimer){ clearTimeout(videoReloadTimer); }
    videoReloadTimer=setTimeout(()=>{ attachVideo(true); }, force ? 120 : videoBackoffMs);
  }
  videoEl.onload=()=>{ videoBackoffMs=500; };
  videoEl.onerror=()=>{ videoBackoffMs=Math.min(videoBackoffMs*2,2000); scheduleVideoReload(false); };
  async function refreshDashboard(maybeReload=false){
    const [dashboard,audio,pca]=await Promise.all([fetchJson('/api/dashboard'),fetchJson('/api/audio'),fetchJson('/api/pca9685')]);
    state.dashboard=dashboard; state.audio=audio; state.pca=pca;
    if(lastGeneration!==dashboard.camera_generation){ const changed=lastGeneration!==-1; lastGeneration=dashboard.camera_generation||0; if(changed || maybeReload){ scheduleVideoReload(true); } else { attachVideo(true); } }
    fillAudioControls();
    render();
  }
  async function loadCamera(){ state.camera=await fetchJson('/api/camera'); fillCameraControls(); fillAudioControls(); render(); }
  async function runCameraAction(action){
    try{
      await action();
      await loadCamera();
      await refreshDashboard(true);
      document.getElementById('camera-feedback').textContent='Настройки камеры применены';
    }catch(err){
      document.getElementById('camera-feedback').textContent=String(err);
    }
  }
  async function runAudioAction(action){
    try{
      await action();
      await refreshDashboard(false);
      fillAudioControls();
      render();
      document.getElementById('audio-feedback').textContent='Настройки аудио применены';
    }catch(err){
      document.getElementById('audio-feedback').textContent=String(err);
    }
  }
  document.getElementById('apply-preset').onclick=()=>runCameraAction(async()=>{
    await postJson('/api/camera/preset/apply',{preset:presetSelect.value});
  });
  document.getElementById('save-preset').onclick=()=>runCameraAction(async()=>{
    const name=document.getElementById('preset_name').value.trim();
    if(!name) throw new Error('Введите имя пресета');
    await postJson('/api/camera', currentPayload());
    await postJson('/api/camera/preset/save',{preset:name});
  });
  document.getElementById('reset-presets').onclick=()=>runCameraAction(async()=>{
    await postJson('/api/camera/preset/resetdefaults',{});
  });
  document.getElementById('delete-preset').onclick=()=>runCameraAction(async()=>{
    await postJson('/api/camera/preset/delete',{preset:presetSelect.value});
  });
  document.getElementById('refresh-camera').onclick=async()=>{ await loadCamera(); };
  document.getElementById('reload-video').onclick=()=>scheduleVideoReload(true);
  document.getElementById('apply-audio').onclick=()=>runAudioAction(async()=>{
    await postJson('/api/audio',{
      profile:document.getElementById('audio_profile').value,
      software_gain:Number(document.getElementById('audio_gain').value),
      dc_block:document.getElementById('audio_dc_block').value==='true',
      slot:Number(document.getElementById('audio_slot').value),
      shift:Number(document.getElementById('audio_shift').value)
    });
  });
  document.getElementById('audio_clip_ms').oninput=updateAudioClipLink;
  Promise.all([loadCamera(),refreshDashboard(false)]).catch(err=>{document.getElementById('camera-feedback').textContent=String(err);document.getElementById('audio-feedback').textContent=String(err);});
  setInterval(()=>{ refreshDashboard(false).catch(err=>{document.getElementById('camera-feedback').textContent=String(err); }); }, 2000);
  </script></div></body></html>)HTML";
  return html;
}

String formatLivePage() {
  String html;
  html.reserve(2200);
  html += R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>AdamS Live</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  body{margin:0;background:#05080c;color:#e7edf4;font-family:Segoe UI,Arial,sans-serif;display:flex;flex-direction:column;gap:12px;min-height:100vh}
  .bar{padding:12px 16px;display:flex;justify-content:space-between;gap:12px;align-items:center;background:#0d141b;border-bottom:1px solid #23313f}.meta{color:#9aabba;font-size:14px}.video{width:min(100vw,960px);aspect-ratio:4/3;object-fit:contain;margin:0 auto;border:1px solid #23313f;background:#000}
  a{color:#65c9ff;text-decoration:none}
  </style></head><body><div class="bar"><div><strong>AdamS Live</strong> <span class="meta" id="meta">ожидание потока</span></div><div><a href="/" target="_blank">панель</a></div></div><img id="video" class="video" alt="live"><script>
  const img=document.getElementById('video'); const meta=document.getElementById('meta'); let generation=0; let backoff=500; let timer=null;
  function reload(force=false){ if(timer) clearTimeout(timer); timer=setTimeout(()=>{ img.src=`http://${location.hostname}:81/stream?gen=${generation}&ts=${Date.now()}`; }, force?100:backoff); }
  img.onload=()=>{ backoff=500; };
  img.onerror=()=>{ backoff=Math.min(backoff*2,2000); reload(false); };
  async function refresh(){ try{ const r=await fetch('/api/dashboard',{cache:'no-store'}); const d=await r.json(); meta.textContent=`${d.camera_preset||'balanced'} | ${d.fps||0} FPS | ${(d.frame_time_ms||0)} ms | gen ${d.camera_generation||0}`; if(generation!==d.camera_generation){ generation=d.camera_generation||0; reload(true); } }catch(_err){} }
  refresh(); reload(true); setInterval(refresh,2000);
  </script></body></html>)HTML";
  return html;
}

String formatOtaPage() {
  String html;
  html.reserve(5200);
  html += R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>AdamS OTA</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
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
  return html;
}

esp_err_t indexHandler(httpd_req_t *req) {
  const String html = formatDashboardPage();
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, html.c_str(), html.length());
}

esp_err_t liveHandler(httpd_req_t *req) {
  const String html = formatLivePage();
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, html.c_str(), html.length());
}

esp_err_t otaPageHandler(httpd_req_t *req) {
  const String html = formatOtaPage();
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, html.c_str(), html.length());
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
  while (remaining > 0) {
    const int toRead = min(remaining, static_cast<int>(kOtaChunkBytes));
    const int read = httpd_req_recv(req, reinterpret_cast<char *>(buffer), toRead);
    if (read == HTTPD_SOCK_ERR_TIMEOUT) {
      continue;
    }
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
  broadcastTelemetry();
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
  uint32_t clipMs = 2000;
  const size_t queryLength = httpd_req_get_url_query_len(req);
  if (queryLength > 0) {
    char query[96] = {};
    if (queryLength < sizeof(query) && httpd_req_get_url_query_str(req, query, sizeof(query)) == ESP_OK) {
      char value[16] = {};
      if (httpd_query_key_value(query, "ms", value, sizeof(value)) == ESP_OK) {
        clipMs = static_cast<uint32_t>(constrain(atoi(value), 250, 5000));
      }
    }
  }

  const size_t clipBytes = getAudioClipBytesForDurationMs(clipMs);
  if (clipBytes == 0) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"audio_clip_unavailable\"}");
  }

  uint8_t *clipBuffer = static_cast<uint8_t *>(malloc(clipBytes));
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
  if (result == ESP_OK) {
    result = httpd_resp_send_chunk(req, reinterpret_cast<const char *>(clipBuffer), outBytes);
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
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool cameraReady = gRuntimeState.cameraReady;
  const uint32_t startingGeneration = gRuntimeState.cameraGeneration;
  gRuntimeState.videoClients++;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  if (!cameraReady) {
    portENTER_CRITICAL(&gRuntimeStateMux);
    if (gRuntimeState.videoClients > 0) {
      gRuntimeState.videoClients--;
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

  while (result == ESP_OK) {
    portENTER_CRITICAL(&gRuntimeStateMux);
    const uint32_t currentGeneration = gRuntimeState.cameraGeneration;
    portEXIT_CRITICAL(&gRuntimeStateMux);
    if (currentGeneration != startingGeneration) {
      portENTER_CRITICAL(&gRuntimeStateMux);
      gRuntimeState.streamRestarts++;
      portEXIT_CRITICAL(&gRuntimeStateMux);
      break;
    }

    camera_fb_t *fb = captureCameraFrame();
    if (fb == nullptr) {
      result = ESP_FAIL;
      break;
    }

    const int64_t sendStartedUs = esp_timer_get_time();
    result = httpd_resp_send_chunk(req, kStreamBoundaryChunk, strlen(kStreamBoundaryChunk));
    if (result == ESP_OK) {
      const int64_t timestampUs =
        static_cast<int64_t>(fb->timestamp.tv_sec) * 1000000LL +
        static_cast<int64_t>(fb->timestamp.tv_usec);
      const long tsSec = static_cast<long>(timestampUs / 1000000LL);
      const long tsUsec = static_cast<long>(timestampUs % 1000000LL);
      char header[160];
      const size_t headerLen = snprintf(
        header,
        sizeof(header),
        "Content-Type: image/jpeg\r\nContent-Length: %u\r\nX-Sequence: %lu\r\nX-Timestamp: %ld.%06ld\r\n\r\n",
        static_cast<unsigned>(fb->len),
        static_cast<unsigned long>(getLatestCameraFrameSequence()),
        tsSec,
        tsUsec
      );
      result = httpd_resp_send_chunk(req, header, headerLen);
    }
    if (result == ESP_OK) {
      result = httpd_resp_send_chunk(req, reinterpret_cast<const char *>(fb->buf), fb->len);
    }

    const int64_t nowUs = esp_timer_get_time();
    const uint32_t frameTimeMs = lastFrameAtUs == 0 ? 0 : static_cast<uint32_t>((nowUs - lastFrameAtUs) / 1000);
    lastFrameAtUs = nowUs;
    const uint32_t sendTimeMs = static_cast<uint32_t>((esp_timer_get_time() - sendStartedUs) / 1000);
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.streamSendTimeMs = sendTimeMs;
    gRuntimeState.frameTimeMs = frameTimeMs;
    if (frameTimeMs > 0) {
      gRuntimeState.frameRateTimes10 = static_cast<uint32_t>(10000.0f / static_cast<float>(frameTimeMs));
      gRuntimeState.captureFrameTimeMs = frameTimeMs;
      gRuntimeState.captureFrameRateTimes10 = gRuntimeState.frameRateTimes10;
    }
    gRuntimeState.lastFrameSize = static_cast<uint32_t>(fb->len);
    gRuntimeState.lastJpegSize = static_cast<uint32_t>(fb->len);
    portEXIT_CRITICAL(&gRuntimeStateMux);

    releaseCameraFrame(fb);
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  if (gRuntimeState.videoClients > 0) {
    gRuntimeState.videoClients--;
  }
  portEXIT_CRITICAL(&gRuntimeStateMux);

  return result;
}

WavHeader makeWavHeader(uint32_t dataBytes) {
  WavHeader header = {};
  memcpy(header.riff, "RIFF", 4);
  header.chunkSize = dataBytes == 0xFFFFFFFFUL ? 0xFFFFFFFFUL : (36 + dataBytes);
  memcpy(header.wave, "WAVE", 4);
  memcpy(header.fmt, "fmt ", 4);
  header.subchunk1Size = 16;
  header.audioFormat = 1;
  header.numChannels = kAudioChannels;
  header.sampleRate = kAudioSampleRate;
  header.bitsPerSample = kAudioBitsPerSample;
  header.byteRate = kAudioSampleRate * kAudioChannels * (kAudioBitsPerSample / 8);
  header.blockAlign = kAudioChannels * (kAudioBitsPerSample / 8);
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
  httpd_resp_set_hdr(req, "X-Audio-Sample-Rate", "16000");
  httpd_resp_set_hdr(req, "X-Audio-Bits", "16");
  httpd_resp_set_hdr(req, "X-Audio-Channels", "1");

  const WavHeader header = makeWavHeader();
  esp_err_t result = httpd_resp_send_chunk(req, reinterpret_cast<const char *>(&header), sizeof(header));
  if (result != ESP_OK) {
    return result;
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.audioClients++;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  uint8_t chunk[kAudioReadChunkBytes];
  uint64_t cursor = getAudioWriteSequence();

  while (result == ESP_OK) {
    size_t bytesRead = 0;
    if (!readAudioChunk(chunk, sizeof(chunk), bytesRead, cursor)) {
      result = ESP_FAIL;
      break;
    }

    if (bytesRead == 0) {
      vTaskDelay(pdMS_TO_TICKS(8));
      continue;
    }

    result = httpd_resp_send_chunk(req, reinterpret_cast<const char *>(chunk), bytesRead);
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  if (gRuntimeState.audioClients > 0) {
    gRuntimeState.audioClients--;
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
      if (received >= static_cast<int>(sizeof(WavHeader)) && memcmp(buffer, "RIFF", 4) == 0 && memcmp(buffer + 8, "WAVE", 4) == 0) {
        payload = buffer + sizeof(WavHeader);
        payloadLen = received - sizeof(WavHeader);
      }
    }

    if (payloadLen > 0) {
      writeSpeakerData(payload, payloadLen);
    }
  }

  endSpeakerStream();
  if (result != ESP_OK) {
    return sendError(req, "500 Internal Server Error", "{\"error\":\"speaker_stream_failed\"}");
  }

  httpd_resp_set_type(req, "application/json");
  return httpd_resp_send(req, "{\"status\":\"ok\"}", HTTPD_RESP_USE_STRLEN);
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
  broadcastTelemetry();
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
  broadcastTelemetry();
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
  broadcastTelemetry();
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
  broadcastTelemetry();
  return sendJson(req, json);
}

esp_err_t wsHandler(httpd_req_t *req) {
  if (req->method == HTTP_GET) {
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.websocketClients++;
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
  httpd_uri_t indexUri = {.uri = "/", .method = HTTP_GET, .handler = indexHandler, .user_ctx = nullptr};
  httpd_uri_t liveUri = {.uri = "/live", .method = HTTP_GET, .handler = liveHandler, .user_ctx = nullptr};
  httpd_uri_t otaPageUri = {.uri = "/ota", .method = HTTP_GET, .handler = otaPageHandler, .user_ctx = nullptr};
  httpd_uri_t sensorsUri = {.uri = "/api/sensors", .method = HTTP_GET, .handler = sensorsHandler, .user_ctx = nullptr};
  httpd_uri_t statusUri = {.uri = "/api/status", .method = HTTP_GET, .handler = statusHandler, .user_ctx = nullptr};
  httpd_uri_t dashboardUri = {.uri = "/api/dashboard", .method = HTTP_GET, .handler = dashboardHandler, .user_ctx = nullptr};
  httpd_uri_t otaStatusUri = {.uri = "/api/ota", .method = HTTP_GET, .handler = otaStatusHandler, .user_ctx = nullptr};
  httpd_uri_t otaUploadUri = {.uri = "/api/ota/upload", .method = HTTP_POST, .handler = otaUploadHandler, .user_ctx = nullptr};
  httpd_uri_t pcaStatusUri = {.uri = "/api/pca9685", .method = HTTP_GET, .handler = pcaStatusHandler, .user_ctx = nullptr};
  httpd_uri_t audioStatusUri = {.uri = "/api/audio", .method = HTTP_GET, .handler = audioStatusHandler, .user_ctx = nullptr};
  httpd_uri_t audioConfigUri = {.uri = "/api/audio", .method = HTTP_POST, .handler = audioConfigHandler, .user_ctx = nullptr};
  httpd_uri_t audioClipUri = {.uri = "/api/audio/clip", .method = HTTP_GET, .handler = audioClipHandler, .user_ctx = nullptr};
  httpd_uri_t cameraStatusUri = {.uri = "/api/camera", .method = HTTP_GET, .handler = cameraStatusHandler, .user_ctx = nullptr};
  httpd_uri_t cameraUpdateUri = {.uri = "/api/camera", .method = HTTP_POST, .handler = cameraUpdateHandler, .user_ctx = nullptr};
  httpd_uri_t cameraPresetApplyUri = {.uri = "/api/camera/preset/apply", .method = HTTP_POST, .handler = cameraPresetApplyHandler, .user_ctx = nullptr};
  httpd_uri_t cameraPresetSaveUri = {.uri = "/api/camera/preset/save", .method = HTTP_POST, .handler = cameraPresetSaveHandler, .user_ctx = nullptr};
  httpd_uri_t cameraPresetDeleteUri = {.uri = "/api/camera/preset/delete", .method = HTTP_POST, .handler = cameraPresetDeleteHandler, .user_ctx = nullptr};
  httpd_uri_t cameraPresetResetDefaultsUri = {.uri = "/api/camera/preset/resetdefaults", .method = HTTP_POST, .handler = cameraPresetResetDefaultsHandler, .user_ctx = nullptr};
  httpd_uri_t captureUri = {.uri = "/capture", .method = HTTP_GET, .handler = captureHandler, .user_ctx = nullptr};
  httpd_uri_t audioUri = {.uri = "/audio", .method = HTTP_GET, .handler = audioHandler, .user_ctx = nullptr};
  httpd_uri_t speakerUri = {.uri = "/speaker", .method = HTTP_POST, .handler = speakerHandler, .user_ctx = nullptr};
  httpd_uri_t pcaChannelUri = {.uri = "/api/pca9685/channel", .method = HTTP_POST, .handler = pcaChannelHandler, .user_ctx = nullptr};
  httpd_uri_t pcaChannelsUri = {.uri = "/api/pca9685/channels", .method = HTTP_POST, .handler = pcaChannelsHandler, .user_ctx = nullptr};
  httpd_uri_t pcaSceneUri = {.uri = "/api/pca9685/scene", .method = HTTP_POST, .handler = pcaSceneHandler, .user_ctx = nullptr};
  httpd_uri_t pcaFrequencyUri = {.uri = "/api/pca9685/frequency", .method = HTTP_POST, .handler = pcaFrequencyHandler, .user_ctx = nullptr};
  httpd_uri_t wsUri = {.uri = "/ws", .method = HTTP_GET, .handler = wsHandler, .user_ctx = nullptr, .is_websocket = true, .handle_ws_control_frames = false, .supported_subprotocol = nullptr};

  httpd_register_uri_handler(server, &indexUri);
  httpd_register_uri_handler(server, &liveUri);
  httpd_register_uri_handler(server, &otaPageUri);
  httpd_register_uri_handler(server, &sensorsUri);
  httpd_register_uri_handler(server, &statusUri);
  httpd_register_uri_handler(server, &dashboardUri);
  httpd_register_uri_handler(server, &otaStatusUri);
  httpd_register_uri_handler(server, &otaUploadUri);
  httpd_register_uri_handler(server, &pcaStatusUri);
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
  httpd_register_uri_handler(server, &audioUri);
  httpd_register_uri_handler(server, &speakerUri);
  httpd_register_uri_handler(server, &pcaChannelUri);
  httpd_register_uri_handler(server, &pcaChannelsUri);
  httpd_register_uri_handler(server, &pcaSceneUri);
  httpd_register_uri_handler(server, &pcaFrequencyUri);
  httpd_register_uri_handler(server, &wsUri);
}

void registerStreamHandlers(httpd_handle_t server) {
  httpd_uri_t streamUri = {.uri = "/stream", .method = HTTP_GET, .handler = streamHandler, .user_ctx = nullptr};
  httpd_register_uri_handler(server, &streamUri);
}

}  // namespace

bool startWebServer() {
  if (sControlServer != nullptr && sStreamServer != nullptr) {
    return true;
  }

  if (sControlServer != nullptr && sStreamServer == nullptr) {
    httpd_stop(sControlServer);
    sControlServer = nullptr;
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.webReady = false;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  httpd_config_t controlConfig = HTTPD_DEFAULT_CONFIG();
  controlConfig.server_port = kHttpPort;
  controlConfig.max_uri_handlers = 28;

  if (httpd_start(&sControlServer, &controlConfig) != ESP_OK) {
    bootLog("web", "failed to start control HTTP server");
    return false;
  }
  registerControlHandlers(sControlServer);

  httpd_config_t streamConfig = HTTPD_DEFAULT_CONFIG();
  streamConfig.server_port = kStreamPort;
  streamConfig.ctrl_port = controlConfig.ctrl_port + 1;
  streamConfig.max_uri_handlers = 4;

  if (httpd_start(&sStreamServer, &streamConfig) != ESP_OK) {
    bootLog("web", "failed to start stream HTTP server");
    httpd_stop(sControlServer);
    sControlServer = nullptr;
    return false;
  }
  registerStreamHandlers(sStreamServer);

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.webReady = true;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  bootLogf("web", "ready on ports %u and %u", kHttpPort, kStreamPort);

  return true;
}

void broadcastTelemetry() {
  if (sControlServer == nullptr) {
    return;
  }

  size_t clients = 8;
  int clientFds[8] = {};
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
