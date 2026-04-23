#include "CameraModule.h"

#include <cctype>
#include <cstring>

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <freertos/task.h>
#include <esp_heap_caps.h>
#include <esp_timer.h>

#include "../../config/AdamsConfig.h"
#include "../core/BootDiagnostics.h"
#include "../core/RuntimeState.h"
#include "../core/VideoLatencyMetrics.h"

namespace {

struct StoredCameraPreset {
  char name[16];
  CameraControlUpdate update;
  bool inUse;
};

struct BuiltInCameraPreset {
  const char *name;
  CameraControlUpdate update;
};

StaticSemaphore_t sCameraMutexBuffer;
SemaphoreHandle_t sCameraMutex = nullptr;
StaticSemaphore_t sLatestFrameMutexBuffer;
SemaphoreHandle_t sLatestFrameMutex = nullptr;
StaticTask_t sCameraProducerTaskBuffer;
StackType_t sCameraProducerTaskStack[4096];
constexpr size_t kMaxStoredPresets = 5;
StoredCameraPreset sStoredPresets[kMaxStoredPresets];
volatile uint32_t sCameraConfigRevision = 0;
volatile uint32_t sCameraGeneration = 0;
volatile uint32_t sLastFrameSequence = 0;
volatile bool sCameraInitialized = false;
volatile bool sCameraProducerTaskStarted = false;
volatile int64_t sCameraProducerFastUntilUs = 0;
uint8_t *sLatestFrameBuffers[2] = {nullptr, nullptr};
size_t sLatestFrameCapacities[2] = {0, 0};
uint8_t sLatestFrameActiveIndex = 0;
bool sLatestFrameReady = false;
size_t sLatestFrameLength = 0;
int64_t sLatestFrameTimestampUs = 0;
uint32_t sLatestFrameSequence = 0;

#define CAMERA_BALANCED_PRESET(FRAME_SIZE, JPEG_QUALITY) { \
  true, FRAME_SIZE, \
  true, JPEG_QUALITY, \
  true, 0, \
  true, 0, \
  true, 0, \
  true, 1, \
  true, 1, \
  true, 2, \
  true, true, \
  true, true, \
  true, true, \
  true, false, \
  true, true \
}

constexpr CameraControlUpdate kPresetQqvga = CAMERA_BALANCED_PRESET(FRAMESIZE_QQVGA, 18);
constexpr CameraControlUpdate kPresetHqvga = CAMERA_BALANCED_PRESET(FRAMESIZE_HQVGA, 18);
constexpr CameraControlUpdate kPresetQvga = CAMERA_BALANCED_PRESET(FRAMESIZE_QVGA, 18);
constexpr CameraControlUpdate kPresetCif = CAMERA_BALANCED_PRESET(FRAMESIZE_CIF, 14);
constexpr CameraControlUpdate kPresetVga = CAMERA_BALANCED_PRESET(FRAMESIZE_VGA, 14);
constexpr CameraControlUpdate kPresetSvga = CAMERA_BALANCED_PRESET(FRAMESIZE_SVGA, 11);
constexpr CameraControlUpdate kPresetXga = CAMERA_BALANCED_PRESET(FRAMESIZE_XGA, 11);
constexpr CameraControlUpdate kPresetHd = CAMERA_BALANCED_PRESET(FRAMESIZE_HD, 9);
constexpr CameraControlUpdate kPresetSxga = CAMERA_BALANCED_PRESET(FRAMESIZE_SXGA, 9);
constexpr CameraControlUpdate kPresetUxga = CAMERA_BALANCED_PRESET(FRAMESIZE_UXGA, 8);

constexpr BuiltInCameraPreset kBuiltInCameraPresets[] = {
  {"qqvga", kPresetQqvga},
  {"hqvga", kPresetHqvga},
  {"qvga", kPresetQvga},
  {"cif", kPresetCif},
  {"vga", kPresetVga},
  {"svga", kPresetSvga},
  {"xga", kPresetXga},
  {"hd", kPresetHd},
  {"sxga", kPresetSxga},
  {"uxga", kPresetUxga},
};

#undef CAMERA_BALANCED_PRESET

constexpr size_t kBuiltInCameraPresetCount = sizeof(kBuiltInCameraPresets) / sizeof(kBuiltInCameraPresets[0]);

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
  gRuntimeState.cameraProducerRunning = sCameraProducerTaskStarted;
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
    copyPresetName(state.preset, sizeof(state.preset), "hd");
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

const BuiltInCameraPreset *findBuiltInPreset(const char *presetName) {
  if (presetName == nullptr) {
    return nullptr;
  }
  for (const auto &preset : kBuiltInCameraPresets) {
    if (strcmp(preset.name, presetName) == 0) {
      return &preset;
    }
  }
  return nullptr;
}

bool isBuiltInPresetName(const char *presetName) {
  return findBuiltInPreset(presetName) != nullptr;
}

bool isValidPresetName(const char *presetName) {
  if (presetName == nullptr || presetName[0] == '\0') {
    return false;
  }

  for (size_t i = 0; presetName[i] != '\0'; ++i) {
    const unsigned char ch = static_cast<unsigned char>(presetName[i]);
    if (i >= sizeof(StoredCameraPreset::name) - 1) {
      return false;
    }
    if (!std::isalnum(ch) && ch != '_' && ch != '-') {
      return false;
    }
  }
  return true;
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
  ok = ok && clampAndSet(sensor, state.sharpness, -2, 2, sensor->set_sharpness);
  ok = ok && clampAndSet(sensor, state.denoise, 0, 1, sensor->set_denoise);
  ok = ok && setGainCeiling(sensor, state.gainCeiling);
  ok = ok && setBool(sensor, state.awb, sensor->set_whitebal);
  ok = ok && setBool(sensor, state.agc, sensor->set_gain_ctrl);
  ok = ok && setBool(sensor, state.aec, sensor->set_exposure_ctrl);
  ok = ok && setBool(sensor, state.hmirror, sensor->set_hmirror);
  ok = ok && setBool(sensor, state.vflip, sensor->set_vflip);
  return ok;
}

bool ensureLatestFrameMutex() {
  if (sLatestFrameMutex != nullptr) {
    return true;
  }
  sLatestFrameMutex = xSemaphoreCreateMutexStatic(&sLatestFrameMutexBuffer);
  return sLatestFrameMutex != nullptr;
}

uint8_t *allocateLatestFrameBuffer(size_t size) {
  uint8_t *buffer = nullptr;
  if (psramFound()) {
    buffer = static_cast<uint8_t *>(heap_caps_malloc(size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  }
  if (buffer == nullptr) {
    buffer = static_cast<uint8_t *>(heap_caps_malloc(size, MALLOC_CAP_8BIT));
  }
  return buffer;
}

bool ensureLatestFrameCapacity(uint8_t index, size_t required) {
  if (index >= 2 || required == 0) {
    return false;
  }
  if (sLatestFrameBuffers[index] != nullptr && sLatestFrameCapacities[index] >= required) {
    return true;
  }

  const size_t newCapacity = max(required, sLatestFrameCapacities[index] * 2);
  uint8_t *newBuffer = allocateLatestFrameBuffer(newCapacity);
  if (newBuffer == nullptr) {
    return false;
  }
  if (sLatestFrameBuffers[index] != nullptr) {
    heap_caps_free(sLatestFrameBuffers[index]);
  }
  sLatestFrameBuffers[index] = newBuffer;
  sLatestFrameCapacities[index] = newCapacity;
  bootLogf("camera", "latest-frame buffer %u allocated: %lu bytes", static_cast<unsigned>(index), static_cast<unsigned long>(newCapacity));
  return true;
}

void clearLatestCameraFrameLocked() {
  if (!ensureLatestFrameMutex()) {
    return;
  }
  if (xSemaphoreTake(sLatestFrameMutex, pdMS_TO_TICKS(100)) != pdTRUE) {
    return;
  }
  sLatestFrameReady = false;
  sLatestFrameLength = 0;
  sLatestFrameTimestampUs = 0;
  sLatestFrameSequence = 0;
  xSemaphoreGive(sLatestFrameMutex);
}

int64_t frameTimestampUs(const camera_fb_t *fb) {
  if (fb == nullptr) {
    return esp_timer_get_time();
  }
  return static_cast<int64_t>(fb->timestamp.tv_sec) * 1000000LL +
         static_cast<int64_t>(fb->timestamp.tv_usec);
}

void updateCameraProducerRuntime(bool running) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.cameraProducerRunning = running;
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

void markCameraProducerFastMode() {
  const int64_t nowUs = esp_timer_get_time();
  const int64_t fastUntilUs = nowUs + static_cast<int64_t>(kCameraProducerFastGraceMs) * 1000LL;
  if (fastUntilUs > sCameraProducerFastUntilUs) {
    sCameraProducerFastUntilUs = fastUntilUs;
  }
}

void cameraProducerTask(void *parameter) {
  (void)parameter;
  int64_t lastFrameAtUs = 0;

  while (true) {
    portENTER_CRITICAL(&gRuntimeStateMux);
    const bool cameraReady = gRuntimeState.cameraReady;
    const uint32_t videoClients = gRuntimeState.videoClients;
    portEXIT_CRITICAL(&gRuntimeStateMux);

    if (!cameraReady) {
      vTaskDelay(pdMS_TO_TICKS(100));
      continue;
    }
    const int64_t nowUs = esp_timer_get_time();
    const bool fastMode = videoClients > 0 || nowUs < sCameraProducerFastUntilUs;
    const uint32_t targetIntervalMs = fastMode
      ? kCameraProducerFrameIntervalMs
      : kCameraProducerWarmFrameIntervalMs;

    const int64_t captureStartedUs = esp_timer_get_time();
    if (sCameraMutex != nullptr) {
      xSemaphoreTake(sCameraMutex, portMAX_DELAY);
    }

    if (!sCameraInitialized) {
      if (sCameraMutex != nullptr) {
        xSemaphoreGive(sCameraMutex);
      }
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }

    const int64_t captureWaitStartedUs = esp_timer_get_time();
    camera_fb_t *fb = esp_camera_fb_get();
    const uint32_t captureWaitMs = static_cast<uint32_t>((esp_timer_get_time() - captureWaitStartedUs) / 1000);
    videoLatencyRecordCaptureWaitMs(captureWaitMs);
    if (fb == nullptr) {
      if (sCameraMutex != nullptr) {
        xSemaphoreGive(sCameraMutex);
      }
      portENTER_CRITICAL(&gRuntimeStateMux);
      gRuntimeState.streamDrops = gRuntimeState.streamDrops + 1;
      portEXIT_CRITICAL(&gRuntimeStateMux);
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }

    uint8_t writeIndex = 0;
    if (ensureLatestFrameMutex() && xSemaphoreTake(sLatestFrameMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
      writeIndex = sLatestFrameReady ? static_cast<uint8_t>(1 - sLatestFrameActiveIndex) : sLatestFrameActiveIndex;
      xSemaphoreGive(sLatestFrameMutex);
    } else {
      esp_camera_fb_return(fb);
      if (sCameraMutex != nullptr) {
        xSemaphoreGive(sCameraMutex);
      }
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }

    if (!ensureLatestFrameCapacity(writeIndex, fb->len)) {
      esp_camera_fb_return(fb);
      if (sCameraMutex != nullptr) {
        xSemaphoreGive(sCameraMutex);
      }
      portENTER_CRITICAL(&gRuntimeStateMux);
      gRuntimeState.streamDrops = gRuntimeState.streamDrops + 1;
      portEXIT_CRITICAL(&gRuntimeStateMux);
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }

    const int64_t copyStartedUs = esp_timer_get_time();
    memcpy(sLatestFrameBuffers[writeIndex], fb->buf, fb->len);
    const uint32_t copyUs = static_cast<uint32_t>(esp_timer_get_time() - copyStartedUs);
    const uint32_t copyMs = copyUs / 1000;
    videoLatencyRecordProducerCopyMs(copyMs);
    videoLatencyRecordProducerCopyUs(copyUs);
    const size_t frameLength = fb->len;
    const int64_t timestampUs = frameTimestampUs(fb);
    esp_camera_fb_return(fb);

    sLastFrameSequence = sLastFrameSequence + 1;
    const uint32_t sequence = sLastFrameSequence;
    bool published = false;
    if (xSemaphoreTake(sLatestFrameMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
      sLatestFrameActiveIndex = writeIndex;
      sLatestFrameLength = frameLength;
      sLatestFrameTimestampUs = timestampUs;
      sLatestFrameSequence = sequence;
      sLatestFrameReady = true;
      published = true;
      xSemaphoreGive(sLatestFrameMutex);
    }

    if (sCameraMutex != nullptr) {
      xSemaphoreGive(sCameraMutex);
    }
    if (!published) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }

    const int64_t frameNowUs = esp_timer_get_time();
    const uint32_t frameIntervalMs = lastFrameAtUs == 0 ? 0 : static_cast<uint32_t>((frameNowUs - lastFrameAtUs) / 1000);
    lastFrameAtUs = frameNowUs;
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.lastFrameSize = static_cast<uint32_t>(frameLength);
    gRuntimeState.lastJpegSize = static_cast<uint32_t>(frameLength);
    gRuntimeState.latestFrameSequence = sequence;
    gRuntimeState.captureFrameTimeMs = frameIntervalMs;
    if (frameIntervalMs > 0) {
      gRuntimeState.captureFrameRateTimes10 = static_cast<uint32_t>(10000.0f / static_cast<float>(frameIntervalMs));
    }
    portEXIT_CRITICAL(&gRuntimeStateMux);

    const uint32_t elapsedMs = static_cast<uint32_t>((esp_timer_get_time() - captureStartedUs) / 1000);
    if (elapsedMs < targetIntervalMs) {
      vTaskDelay(pdMS_TO_TICKS(targetIntervalMs - elapsedMs));
    } else {
      taskYIELD();
    }
  }
}

void startCameraProducerTask() {
  if (sCameraProducerTaskStarted) {
    updateCameraProducerRuntime(true);
    return;
  }
  xTaskCreateStaticPinnedToCore(
    cameraProducerTask,
    "camera_producer",
    sizeof(sCameraProducerTaskStack) / sizeof(StackType_t),
    nullptr,
    2,
    sCameraProducerTaskStack,
    &sCameraProducerTaskBuffer,
    APP_CPU_NUM);
  sCameraProducerTaskStarted = true;
  updateCameraProducerRuntime(true);
}

bool reinitializeCamera(const CameraControlState &state, const char *reason) {
  if (sCameraMutex != nullptr) {
    xSemaphoreTake(sCameraMutex, portMAX_DELAY);
  }

  if (sCameraInitialized) {
    esp_camera_deinit();
    sCameraInitialized = false;
    clearLatestCameraFrameLocked();
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
  sCameraGeneration = sCameraGeneration + 1;
  sCameraConfigRevision = sCameraConfigRevision + 1;
  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.cameraReady = true;
  gRuntimeState.cameraProducerRunning = sCameraProducerTaskStarted;
  gRuntimeState.cameraGeneration = sCameraGeneration;
  gRuntimeState.cameraConfigRevision = sCameraConfigRevision;
  gRuntimeState.cameraReinitCount = gRuntimeState.cameraReinitCount + 1;
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
  if (!ensureLatestFrameMutex()) {
    bootLog("camera", "failed to create latest-frame mutex");
    return false;
  }

  memset(sStoredPresets, 0, sizeof(sStoredPresets));

  const BuiltInCameraPreset *bootPreset = findBuiltInPreset("hd");
  const CameraControlUpdate bootUpdate = bootPreset == nullptr ? CameraControlUpdate{} : bootPreset->update;

  CameraControlState state = {};
  state.framesize = kDefaultFrameSize;
  state.quality = kDefaultJpegQuality;
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
  copyPresetName(state.preset, sizeof(state.preset), "hd");
  mergeState(state, bootUpdate, "hd");

  if (!reinitializeCamera(state, "boot")) {
    return false;
  }
  startCameraProducerTask();

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
  if (sCameraMutex != nullptr) {
    xSemaphoreTake(sCameraMutex, portMAX_DELAY);
  }

  if (!sCameraInitialized) {
    if (sCameraMutex != nullptr) {
      xSemaphoreGive(sCameraMutex);
    }
    return nullptr;
  }

  camera_fb_t *fb = esp_camera_fb_get();
  if (fb == nullptr) {
    if (sCameraMutex != nullptr) {
      xSemaphoreGive(sCameraMutex);
    }
    return nullptr;
  }

  if (fb != nullptr) {
    sLastFrameSequence = sLastFrameSequence + 1;
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
    if (sCameraMutex != nullptr) {
      xSemaphoreGive(sCameraMutex);
    }
  }
}

bool getCameraControlState(CameraControlState &state) {
  if (sCameraMutex != nullptr) {
    xSemaphoreTake(sCameraMutex, portMAX_DELAY);
  }

  sensor_t *sensor = sCameraInitialized ? esp_camera_sensor_get() : nullptr;
  if (sensor == nullptr) {
    if (sCameraMutex != nullptr) {
      xSemaphoreGive(sCameraMutex);
    }
    return false;
  }
  fillStateFromSensor(sensor, state);
  if (sCameraMutex != nullptr) {
    xSemaphoreGive(sCameraMutex);
  }
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
    sCameraConfigRevision = sCameraConfigRevision + 1;
    setPresetName(targetState.preset);
    saveCameraState(targetState);
  }
  if (sCameraMutex != nullptr) {
    xSemaphoreGive(sCameraMutex);
  }
  return ok;
}

bool applyCameraPreset(const char *presetName) {
  const BuiltInCameraPreset *builtInPreset = findBuiltInPreset(presetName);
  if (builtInPreset != nullptr) {
    return applyCameraControlUpdate(builtInPreset->update, builtInPreset->name);
  }

  const int presetIndex = findStoredPresetIndex(presetName);
  if (presetIndex < 0) {
    return false;
  }
  return applyCameraControlUpdate(sStoredPresets[presetIndex].update, sStoredPresets[presetIndex].name);
}

void noteCameraStreamDemand() {
  const int64_t nowUs = esp_timer_get_time();
  const int64_t fastUntilUs = nowUs + static_cast<int64_t>(kCameraProducerFastGraceMs) * 1000LL;
  if (fastUntilUs > sCameraProducerFastUntilUs) {
    sCameraProducerFastUntilUs = fastUntilUs;
  }
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

size_t getLatestCameraFrameSize() {
  if (sLatestFrameMutex == nullptr) {
    return 0;
  }
  size_t length = 0;
  if (xSemaphoreTake(sLatestFrameMutex, pdMS_TO_TICKS(20)) == pdTRUE) {
    length = sLatestFrameReady ? sLatestFrameLength : 0;
    xSemaphoreGive(sLatestFrameMutex);
  }
  return length;
}

bool copyLatestCameraFrame(
  uint8_t *dst,
  size_t capacity,
  size_t &outLength,
  int64_t &outTimestampUs,
  uint32_t &outSequence,
  uint32_t minimumSequence,
  LatestFrameCopyStatus *outStatus) {
  outLength = 0;
  outTimestampUs = 0;
  outSequence = 0;
  if (outStatus != nullptr) {
    *outStatus = LatestFrameCopyStatus::InvalidArgs;
  }
  if (dst == nullptr || capacity == 0 || sLatestFrameMutex == nullptr) {
    return false;
  }

  const int64_t lockWaitStartedUs = esp_timer_get_time();
  if (xSemaphoreTake(sLatestFrameMutex, pdMS_TO_TICKS(50)) != pdTRUE) {
    const uint32_t waitUs = static_cast<uint32_t>(esp_timer_get_time() - lockWaitStartedUs);
    const uint32_t waitMs = waitUs / 1000;
    videoLatencyRecordLatestLockWaitMs(waitMs);
    videoLatencyRecordLatestLockWaitUs(waitUs);
    videoLatencyIncrementLatestMutexTimeout();
    if (outStatus != nullptr) {
      *outStatus = LatestFrameCopyStatus::MutexTimeout;
    }
    return false;
  }
  const uint32_t lockWaitUs = static_cast<uint32_t>(esp_timer_get_time() - lockWaitStartedUs);
  const uint32_t lockWaitMs = lockWaitUs / 1000;
  videoLatencyRecordLatestLockWaitMs(lockWaitMs);
  videoLatencyRecordLatestLockWaitUs(lockWaitUs);
  if (!sLatestFrameReady || sLatestFrameSequence <= minimumSequence) {
    if (outStatus != nullptr) {
      *outStatus = LatestFrameCopyStatus::NoNewFrame;
    }
    xSemaphoreGive(sLatestFrameMutex);
    return false;
  }
  if (capacity < sLatestFrameLength) {
    outLength = sLatestFrameLength;
    if (outStatus != nullptr) {
      *outStatus = LatestFrameCopyStatus::CapacityTooSmall;
    }
    xSemaphoreGive(sLatestFrameMutex);
    return false;
  }

  memcpy(dst, sLatestFrameBuffers[sLatestFrameActiveIndex], sLatestFrameLength);
  outLength = sLatestFrameLength;
  outTimestampUs = sLatestFrameTimestampUs;
  outSequence = sLatestFrameSequence;
  if (outStatus != nullptr) {
    *outStatus = LatestFrameCopyStatus::Ok;
  }
  xSemaphoreGive(sLatestFrameMutex);
  return true;
}

size_t getCameraPresetCount() {
  size_t count = kBuiltInCameraPresetCount;
  for (size_t i = 0; i < kMaxStoredPresets; ++i) {
    if (sStoredPresets[i].inUse) {
      count++;
    }
  }
  return count;
}

bool getCameraPresetDescriptor(size_t index, CameraPresetDescriptor &descriptor) {
  if (index < kBuiltInCameraPresetCount) {
    memset(&descriptor, 0, sizeof(descriptor));
    copyPresetName(descriptor.name, sizeof(descriptor.name), kBuiltInCameraPresets[index].name);
    descriptor.builtin = true;
    descriptor.exists = true;
    descriptor.hasFramesize = kBuiltInCameraPresets[index].update.hasFramesize;
    descriptor.framesize = kBuiltInCameraPresets[index].update.framesize;
    return true;
  }

  const size_t userIndex = index - kBuiltInCameraPresetCount;
  size_t current = 0;
  for (size_t i = 0; i < kMaxStoredPresets; ++i) {
    if (!sStoredPresets[i].inUse) {
      continue;
    }
    if (current == userIndex) {
      memset(&descriptor, 0, sizeof(descriptor));
      copyPresetName(descriptor.name, sizeof(descriptor.name), sStoredPresets[i].name);
      descriptor.builtin = false;
      descriptor.exists = true;
      descriptor.hasFramesize = sStoredPresets[i].update.hasFramesize;
      descriptor.framesize = sStoredPresets[i].update.framesize;
      return true;
    }
    current++;
  }
  return false;
}

bool saveCameraPreset(const char *presetName) {
  if (!isValidPresetName(presetName) || isBuiltInPresetName(presetName)) {
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
    setPresetName("hd");
  }
  return true;
}

void resetBuiltInCameraPresets() {
  // Built-in presets are immutable flash constants now, so there is no RAM copy to reset.
}
