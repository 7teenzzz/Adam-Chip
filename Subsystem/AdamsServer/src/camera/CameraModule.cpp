#include "CameraModule.h"

#include <cstring>

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

#include "../../config/AdamsConfig.h"
#include "../core/BootDiagnostics.h"
#include "../core/RuntimeState.h"

namespace {

enum class CameraPreset {
  LowLatency,
  Balanced,
  Quality,
};

struct StoredCameraPreset {
  char name[16];
  CameraControlUpdate update;
  bool builtin;
  bool inUse;
};

StaticSemaphore_t sCameraMutexBuffer;
SemaphoreHandle_t sCameraMutex = nullptr;
constexpr size_t kMaxStoredPresets = 8;
StoredCameraPreset sStoredPresets[kMaxStoredPresets];
volatile uint32_t sCameraConfigRevision = 0;
volatile uint32_t sCameraGeneration = 0;
volatile uint32_t sLastFrameSequence = 0;
volatile bool sCameraInitialized = false;

void copyPresetName(char *dst, size_t dstSize, const char *src) {
  if (dst == nullptr || dstSize == 0) {
    return;
  }
  strncpy(dst, src == nullptr ? "" : src, dstSize - 1);
  dst[dstSize - 1] = '\0';
}

void setPresetName(const char *presetName) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  copyPresetName(gRuntimeState.cameraPreset, sizeof(gRuntimeState.cameraPreset), presetName == nullptr ? "custom" : presetName);
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

void setLastReinitReason(const char *reason) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  copyPresetName(gRuntimeState.lastCameraReinitReason, sizeof(gRuntimeState.lastCameraReinitReason), reason == nullptr ? "" : reason);
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

void saveCameraState(const CameraControlState &state) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.cameraFramesize = static_cast<int8_t>(state.framesize);
  gRuntimeState.cameraQuality = static_cast<int8_t>(state.quality);
  gRuntimeState.cameraBrightness = static_cast<int8_t>(state.brightness);
  gRuntimeState.cameraContrast = static_cast<int8_t>(state.contrast);
  gRuntimeState.cameraSaturation = static_cast<int8_t>(state.saturation);
  gRuntimeState.cameraSharpness = static_cast<int8_t>(state.sharpness);
  gRuntimeState.cameraDenoise = static_cast<int8_t>(state.denoise);
  gRuntimeState.cameraGainCeiling = static_cast<int8_t>(state.gainCeiling);
  gRuntimeState.cameraAwb = state.awb;
  gRuntimeState.cameraAgc = state.agc;
  gRuntimeState.cameraAec = state.aec;
  gRuntimeState.cameraHmirror = state.hmirror;
  gRuntimeState.cameraVflip = state.vflip;
  gRuntimeState.cameraConfigRevision = sCameraConfigRevision;
  gRuntimeState.cameraGeneration = sCameraGeneration;
  gRuntimeState.cameraProducerRunning = false;
  copyPresetName(gRuntimeState.cameraPreset, sizeof(gRuntimeState.cameraPreset), state.preset);
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

camera_config_t buildCameraConfig(const CameraControlState &state) {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_1;
  config.ledc_timer = LEDC_TIMER_1;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = kXclkFrequencyHz;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = static_cast<framesize_t>(state.framesize);
  config.jpeg_quality = constrain(state.quality, 4, 63);
  config.fb_count = 1;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_DRAM;

  if (psramFound()) {
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.fb_count = 2;
    config.grab_mode = CAMERA_GRAB_LATEST;
  }

  return config;
}

void fillStateFromSensor(sensor_t *sensor, CameraControlState &state) {
  memset(&state, 0, sizeof(state));
  if (sensor == nullptr) {
    copyPresetName(state.preset, sizeof(state.preset), "balanced");
    return;
  }

  state.framesize = sensor->status.framesize;
  state.quality = sensor->status.quality;
  state.brightness = sensor->status.brightness;
  state.contrast = sensor->status.contrast;
  state.saturation = sensor->status.saturation;
  state.sharpness = sensor->status.sharpness;
  state.denoise = sensor->status.denoise;
  state.gainCeiling = sensor->status.gainceiling;
  state.awb = sensor->status.awb;
  state.agc = sensor->status.agc;
  state.aec = sensor->status.aec;
  state.hmirror = sensor->status.hmirror;
  state.vflip = sensor->status.vflip;
  portENTER_CRITICAL(&gRuntimeStateMux);
  copyPresetName(state.preset, sizeof(state.preset), gRuntimeState.cameraPreset);
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

bool clampAndSet(sensor_t *sensor, int value, int minValue, int maxValue, int (*setter)(sensor_t *, int)) {
  if (sensor == nullptr || setter == nullptr) {
    return false;
  }
  return setter(sensor, constrain(value, minValue, maxValue)) == 0;
}

bool setBool(sensor_t *sensor, bool value, int (*setter)(sensor_t *, int)) {
  if (sensor == nullptr || setter == nullptr) {
    return false;
  }
  return setter(sensor, value ? 1 : 0) == 0;
}

bool setGainCeiling(sensor_t *sensor, int value) {
  if (sensor == nullptr || sensor->set_gainceiling == nullptr) {
    return false;
  }
  return sensor->set_gainceiling(sensor, static_cast<gainceiling_t>(constrain(value, 0, 6))) == 0;
}

void applyPresetDefaults(CameraPreset preset, CameraControlUpdate &update) {
  update = CameraControlUpdate{};

  if (preset == CameraPreset::LowLatency) {
    update.hasFramesize = true;
    update.framesize = FRAMESIZE_VGA;
    update.hasQuality = true;
    update.quality = 20;
  } else if (preset == CameraPreset::Quality) {
    update.hasFramesize = true;
    update.framesize = FRAMESIZE_VGA;
    update.hasQuality = true;
    update.quality = 10;
  } else {
    update.hasFramesize = true;
    update.framesize = FRAMESIZE_VGA;
    update.hasQuality = true;
    update.quality = 18;
  }

  update.hasBrightness = true;
  update.brightness = 0;
  update.hasContrast = true;
  update.contrast = 0;
  update.hasSaturation = true;
  update.saturation = preset == CameraPreset::Quality ? 1 : 0;
  update.hasSharpness = true;
  update.sharpness = preset == CameraPreset::Quality ? 2 : 1;
  update.hasDenoise = true;
  update.denoise = preset == CameraPreset::Quality ? 1 : 0;
  update.hasGainCeiling = true;
  update.gainCeiling = preset == CameraPreset::Quality ? 2 : 1;
  update.hasAwb = true;
  update.awb = true;
  update.hasAgc = true;
  update.agc = true;
  update.hasAec = true;
  update.aec = true;
  update.hasVflip = true;
  update.vflip = true;
  update.hasHmirror = true;
  update.hmirror = false;
}

bool parsePreset(const char *presetName, CameraPreset &preset) {
  if (presetName == nullptr) {
    return false;
  }
  if (strcmp(presetName, "low_latency") == 0) {
    preset = CameraPreset::LowLatency;
    return true;
  }
  if (strcmp(presetName, "quality") == 0) {
    preset = CameraPreset::Quality;
    return true;
  }
  if (strcmp(presetName, "balanced") == 0) {
    preset = CameraPreset::Balanced;
    return true;
  }
  return false;
}

bool isBuiltInPresetName(const char *presetName) {
  return presetName != nullptr &&
         (strcmp(presetName, "low_latency") == 0 ||
          strcmp(presetName, "balanced") == 0 ||
          strcmp(presetName, "quality") == 0);
}

int findStoredPresetIndex(const char *presetName) {
  if (presetName == nullptr || presetName[0] == '\0') {
    return -1;
  }
  for (size_t i = 0; i < kMaxStoredPresets; ++i) {
    if (sStoredPresets[i].inUse && strcmp(sStoredPresets[i].name, presetName) == 0) {
      return static_cast<int>(i);
    }
  }
  return -1;
}

int findFreePresetSlot() {
  for (size_t i = 0; i < kMaxStoredPresets; ++i) {
    if (!sStoredPresets[i].inUse) {
      return static_cast<int>(i);
    }
  }
  return -1;
}

void initializeBuiltInPresets() {
  memset(sStoredPresets, 0, sizeof(sStoredPresets));

  const char *names[] = {"low_latency", "balanced", "quality"};
  const CameraPreset presets[] = {CameraPreset::LowLatency, CameraPreset::Balanced, CameraPreset::Quality};
  for (size_t i = 0; i < 3; ++i) {
    sStoredPresets[i].inUse = true;
    sStoredPresets[i].builtin = true;
    copyPresetName(sStoredPresets[i].name, sizeof(sStoredPresets[i].name), names[i]);
    applyPresetDefaults(presets[i], sStoredPresets[i].update);
  }
}

void mergeState(CameraControlState &state, const CameraControlUpdate &update, const char *presetName) {
  if (update.hasFramesize) state.framesize = constrain(update.framesize, FRAMESIZE_QQVGA, FRAMESIZE_QSXGA);
  if (update.hasQuality) state.quality = constrain(update.quality, 4, 63);
  if (update.hasBrightness) state.brightness = constrain(update.brightness, -2, 2);
  if (update.hasContrast) state.contrast = constrain(update.contrast, -2, 2);
  if (update.hasSaturation) state.saturation = constrain(update.saturation, -2, 2);
  if (update.hasSharpness) state.sharpness = constrain(update.sharpness, -2, 2);
  if (update.hasDenoise) state.denoise = constrain(update.denoise, 0, 1);
  if (update.hasGainCeiling) state.gainCeiling = constrain(update.gainCeiling, 0, 6);
  if (update.hasAwb) state.awb = update.awb;
  if (update.hasAgc) state.agc = update.agc;
  if (update.hasAec) state.aec = update.aec;
  if (update.hasHmirror) state.hmirror = update.hmirror;
  if (update.hasVflip) state.vflip = update.vflip;
  copyPresetName(state.preset, sizeof(state.preset), presetName == nullptr ? "custom" : presetName);
}

bool applyLiveSettings(sensor_t *sensor, const CameraControlState &state) {
  bool ok = true;
  ok = ok && clampAndSet(sensor, state.quality, 4, 63, sensor->set_quality);
  ok = ok && clampAndSet(sensor, state.brightness, -2, 2, sensor->set_brightness);
  ok = ok && clampAndSet(sensor, state.contrast, -2, 2, sensor->set_contrast);
  ok = ok && clampAndSet(sensor, state.saturation, -2, 2, sensor->set_saturation);
  ok = ok && setBool(sensor, state.hmirror, sensor->set_hmirror);
  ok = ok && setBool(sensor, state.vflip, sensor->set_vflip);
  return ok;
}

bool reinitializeCamera(const CameraControlState &state, const char *reason) {
  if (sCameraMutex != nullptr) {
    xSemaphoreTake(sCameraMutex, portMAX_DELAY);
  }

  if (sCameraInitialized) {
    esp_camera_deinit();
    sCameraInitialized = false;
  }

  camera_config_t config = buildCameraConfig(state);
  const esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    if (sCameraMutex != nullptr) {
      xSemaphoreGive(sCameraMutex);
    }
    bootLogf("camera", "reinit failed: 0x%x", err);
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.cameraReady = false;
    portEXIT_CRITICAL(&gRuntimeStateMux);
    return false;
  }

  sensor_t *sensor = esp_camera_sensor_get();
  bool ok = sensor != nullptr && applyLiveSettings(sensor, state);
  if (!ok) {
    esp_camera_deinit();
    sCameraInitialized = false;
    if (sCameraMutex != nullptr) {
      xSemaphoreGive(sCameraMutex);
    }
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.cameraReady = false;
    portEXIT_CRITICAL(&gRuntimeStateMux);
    return false;
  }

  sCameraInitialized = true;
  sCameraGeneration++;
  sCameraConfigRevision++;
  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.cameraReady = true;
  gRuntimeState.cameraProducerRunning = false;
  gRuntimeState.cameraGeneration = sCameraGeneration;
  gRuntimeState.cameraConfigRevision = sCameraConfigRevision;
  gRuntimeState.cameraReinitCount++;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  setPresetName(state.preset);
  setLastReinitReason(reason);
  saveCameraState(state);

  if (sCameraMutex != nullptr) {
    xSemaphoreGive(sCameraMutex);
  }

  bootLogf("camera", "reinitialized: reason=%s framesize=%d quality=%d",
    reason == nullptr ? "unknown" : reason, state.framesize, state.quality);
  return true;
}

bool getCurrentCameraUpdate(CameraControlUpdate &update) {
  CameraControlState state;
  if (!getCameraControlState(state)) {
    return false;
  }

  update = CameraControlUpdate{};
  update.hasFramesize = true;
  update.framesize = state.framesize;
  update.hasQuality = true;
  update.quality = state.quality;
  update.hasBrightness = true;
  update.brightness = state.brightness;
  update.hasContrast = true;
  update.contrast = state.contrast;
  update.hasSaturation = true;
  update.saturation = state.saturation;
  update.hasSharpness = true;
  update.sharpness = state.sharpness;
  update.hasDenoise = true;
  update.denoise = state.denoise;
  update.hasGainCeiling = true;
  update.gainCeiling = state.gainCeiling;
  update.hasAwb = true;
  update.awb = state.awb;
  update.hasAgc = true;
  update.agc = state.agc;
  update.hasAec = true;
  update.aec = state.aec;
  update.hasHmirror = true;
  update.hmirror = state.hmirror;
  update.hasVflip = true;
  update.vflip = state.vflip;
  return true;
}

}  // namespace

bool initCamera() {
  if (sCameraMutex == nullptr) {
    sCameraMutex = xSemaphoreCreateMutexStatic(&sCameraMutexBuffer);
  }
  if (sCameraMutex == nullptr) {
    bootLog("camera", "failed to create mutex");
    return false;
  }

  initializeBuiltInPresets();

  CameraControlUpdate balanced;
  applyPresetDefaults(CameraPreset::Balanced, balanced);

  CameraControlState state = {};
  state.framesize = FRAMESIZE_VGA;
  state.quality = 18;
  state.brightness = 0;
  state.contrast = 0;
  state.saturation = 0;
  state.sharpness = 1;
  state.denoise = 0;
  state.gainCeiling = 1;
  state.awb = true;
  state.agc = true;
  state.aec = true;
  state.hmirror = false;
  state.vflip = true;
  copyPresetName(state.preset, sizeof(state.preset), "balanced");
  mergeState(state, balanced, "balanced");

  if (!reinitializeCamera(state, "boot")) {
    return false;
  }

  bootLogf("camera", "ready, framesize=%d, quality=%d, psram=%s",
    state.framesize,
    state.quality,
    psramFound() ? "yes" : "no");
  return true;
}

sensor_t *getCameraSensor() {
  return esp_camera_sensor_get();
}

camera_fb_t *captureCameraFrame() {
  camera_fb_t *fb = sCameraInitialized ? esp_camera_fb_get() : nullptr;
  if (fb != nullptr) {
    sLastFrameSequence++;
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.lastFrameSize = static_cast<uint32_t>(fb->len);
    gRuntimeState.lastJpegSize = static_cast<uint32_t>(fb->len);
    gRuntimeState.latestFrameSequence = sLastFrameSequence;
    portEXIT_CRITICAL(&gRuntimeStateMux);
  }
  return fb;
}

void releaseCameraFrame(camera_fb_t *fb) {
  if (fb != nullptr) {
    esp_camera_fb_return(fb);
  }
}

bool getCameraControlState(CameraControlState &state) {
  sensor_t *sensor = sCameraInitialized ? esp_camera_sensor_get() : nullptr;
  if (sensor == nullptr) {
    return false;
  }
  fillStateFromSensor(sensor, state);
  return true;
}

bool applyCameraControlUpdate(const CameraControlUpdate &update, const char *presetName) {
  CameraControlState currentState;
  if (!getCameraControlState(currentState)) {
    return false;
  }

  CameraControlState targetState = currentState;
  mergeState(targetState, update, presetName);

  const bool requiresReinit = update.hasFramesize && targetState.framesize != currentState.framesize;
  if (requiresReinit) {
    return reinitializeCamera(targetState, "framesize_change");
  }

  if (sCameraMutex != nullptr) {
    xSemaphoreTake(sCameraMutex, portMAX_DELAY);
  }
  sensor_t *sensor = sCameraInitialized ? esp_camera_sensor_get() : nullptr;
  const bool ok = sensor != nullptr && applyLiveSettings(sensor, targetState);
  if (ok) {
    sCameraConfigRevision++;
    setPresetName(targetState.preset);
    saveCameraState(targetState);
  }
  if (sCameraMutex != nullptr) {
    xSemaphoreGive(sCameraMutex);
  }
  return ok;
}

bool applyCameraPreset(const char *presetName) {
  const int presetIndex = findStoredPresetIndex(presetName);
  if (presetIndex < 0) {
    return false;
  }
  return applyCameraControlUpdate(sStoredPresets[presetIndex].update, sStoredPresets[presetIndex].name);
}

uint32_t getCameraConfigRevision() {
  return sCameraConfigRevision;
}

uint32_t getCameraGeneration() {
  return sCameraGeneration;
}

uint32_t getLatestCameraFrameSequence() {
  return sLastFrameSequence;
}

bool getLatestCameraFrameView(CameraFrameView &view, uint32_t minimumSequence) {
  (void)view;
  (void)minimumSequence;
  return false;
}

void releaseCameraFrameView(const CameraFrameView &view) {
  (void)view;
}

bool copyLatestCameraFrame(uint8_t *dst, size_t capacity, size_t &outLength, int64_t &outTimestampUs, uint32_t &outSequence) {
  (void)dst;
  (void)capacity;
  outLength = 0;
  outTimestampUs = 0;
  outSequence = 0;
  return false;
}

size_t getCameraPresetCount() {
  size_t count = 0;
  for (size_t i = 0; i < kMaxStoredPresets; ++i) {
    if (sStoredPresets[i].inUse) {
      count++;
    }
  }
  return count;
}

bool getCameraPresetDescriptor(size_t index, CameraPresetDescriptor &descriptor) {
  size_t current = 0;
  for (size_t i = 0; i < kMaxStoredPresets; ++i) {
    if (!sStoredPresets[i].inUse) {
      continue;
    }
    if (current == index) {
      memset(&descriptor, 0, sizeof(descriptor));
      copyPresetName(descriptor.name, sizeof(descriptor.name), sStoredPresets[i].name);
      descriptor.builtin = sStoredPresets[i].builtin;
      descriptor.exists = true;
      return true;
    }
    current++;
  }
  return false;
}

bool saveCameraPreset(const char *presetName) {
  if (presetName == nullptr || presetName[0] == '\0') {
    return false;
  }

  CameraControlUpdate currentUpdate;
  if (!getCurrentCameraUpdate(currentUpdate)) {
    return false;
  }

  int presetIndex = findStoredPresetIndex(presetName);
  if (presetIndex < 0) {
    presetIndex = findFreePresetSlot();
    if (presetIndex < 0) {
      return false;
    }
  }

  sStoredPresets[presetIndex].inUse = true;
  sStoredPresets[presetIndex].builtin = isBuiltInPresetName(presetName);
  copyPresetName(sStoredPresets[presetIndex].name, sizeof(sStoredPresets[presetIndex].name), presetName);
  sStoredPresets[presetIndex].update = currentUpdate;
  setPresetName(presetName);
  return true;
}

bool deleteCameraPreset(const char *presetName) {
  if (presetName == nullptr || presetName[0] == '\0' || isBuiltInPresetName(presetName)) {
    return false;
  }

  const int presetIndex = findStoredPresetIndex(presetName);
  if (presetIndex < 0) {
    return false;
  }

  memset(&sStoredPresets[presetIndex], 0, sizeof(sStoredPresets[presetIndex]));
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool wasActive = strcmp(gRuntimeState.cameraPreset, presetName) == 0;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  if (wasActive) {
    setPresetName("balanced");
  }
  return true;
}

void resetBuiltInCameraPresets() {
  for (size_t i = 0; i < kMaxStoredPresets; ++i) {
    if (!sStoredPresets[i].inUse || !sStoredPresets[i].builtin) {
      continue;
    }
    CameraPreset preset;
    if (parsePreset(sStoredPresets[i].name, preset)) {
      applyPresetDefaults(preset, sStoredPresets[i].update);
    }
  }
}
