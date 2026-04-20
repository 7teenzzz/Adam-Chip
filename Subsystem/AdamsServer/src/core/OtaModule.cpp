#include "OtaModule.h"

#include <cstring>

#include <Update.h>

#include "../../config/AdamsConfig.h"
#include "BootDiagnostics.h"
#include "RuntimeState.h"

namespace {

bool sOtaInitialized = false;
bool sRebootPending = false;
uint32_t sRebootAtMs = 0;

void copyText(char *dst, size_t dstSize, const char *src) {
  if (dst == nullptr || dstSize == 0) {
    return;
  }
  const char *value = src == nullptr ? "" : src;
  strncpy(dst, value, dstSize - 1);
  dst[dstSize - 1] = '\0';
}

void setOtaState(bool inProgress, const char *result, const char *error, uint8_t progress, uint32_t received, uint32_t total) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.otaReady = kOtaEnabled;
  gRuntimeState.otaInProgress = inProgress;
  gRuntimeState.otaProgressPercent = progress;
  gRuntimeState.otaBytesReceived = received;
  gRuntimeState.otaTotalBytes = total;
  copyText(gRuntimeState.otaLastResult, sizeof(gRuntimeState.otaLastResult), result);
  copyText(gRuntimeState.otaLastError, sizeof(gRuntimeState.otaLastError), error);
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

}  // namespace

bool initOta() {
  sOtaInitialized = true;
  sRebootPending = false;
  sRebootAtMs = 0;

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.otaReady = kOtaEnabled;
  gRuntimeState.otaInProgress = false;
  gRuntimeState.otaRebootPending = false;
  gRuntimeState.otaProgressPercent = 0;
  gRuntimeState.otaBytesReceived = 0;
  gRuntimeState.otaTotalBytes = 0;
  copyText(gRuntimeState.otaLastResult, sizeof(gRuntimeState.otaLastResult), kOtaEnabled ? "ready" : "disabled");
  copyText(gRuntimeState.otaLastError, sizeof(gRuntimeState.otaLastError), "");
  portEXIT_CRITICAL(&gRuntimeStateMux);

  bootLogf("ota", "initialized, enabled=%s auth=%s", kOtaEnabled ? "true" : "false", otaAuthRequired() ? "required" : "off");
  return true;
}

void serviceOta() {
  if (!sRebootPending || millis() < sRebootAtMs) {
    return;
  }

  bootLog("ota", "rebooting into updated firmware");
  delay(100);
  ESP.restart();
}

bool otaAuthRequired() {
  return kOtaAuthToken[0] != '\0';
}

bool otaTokenValid(const char *token) {
  if (!otaAuthRequired()) {
    return true;
  }
  if (token == nullptr) {
    return false;
  }
  return strcmp(token, kOtaAuthToken) == 0;
}

bool beginOtaUpload(uint32_t totalBytes, const char *source, String &error) {
  error = "";

  if (!sOtaInitialized) {
    error = "ota_not_initialized";
    return false;
  }
  if (!kOtaEnabled) {
    error = "ota_disabled";
    return false;
  }
  if (totalBytes == 0) {
    error = "ota_empty_payload";
    return false;
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool busy = gRuntimeState.otaInProgress;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  if (busy) {
    error = "ota_busy";
    return false;
  }

  if (!Update.begin(totalBytes, U_FLASH)) {
    error = String("ota_begin_failed:") + Update.errorString();
    setOtaState(false, "begin_failed", error.c_str(), 0, 0, totalBytes);
    return false;
  }

  sRebootPending = false;
  sRebootAtMs = 0;
  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.otaRebootPending = false;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  setOtaState(true, "uploading", "", 0, 0, totalBytes);
  bootLogf("ota", "upload started from %s, bytes=%lu", source == nullptr ? "unknown" : source, static_cast<unsigned long>(totalBytes));
  return true;
}

bool writeOtaChunk(uint8_t *data, size_t length, String &error) {
  error = "";
  if (length == 0) {
    return true;
  }

  const size_t written = Update.write(data, length);
  if (written != length) {
    error = String("ota_write_failed:") + Update.errorString();
    return false;
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  uint32_t received = gRuntimeState.otaBytesReceived + static_cast<uint32_t>(length);
  const uint32_t total = gRuntimeState.otaTotalBytes;
  gRuntimeState.otaBytesReceived = received;
  gRuntimeState.otaProgressPercent = total > 0 ? static_cast<uint8_t>((received * 100UL) / total) : 0;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  return true;
}

bool finishOtaUpload(String &error) {
  error = "";

  if (!Update.end(true) || !Update.isFinished()) {
    error = String("ota_end_failed:") + Update.errorString();
    setOtaState(false, "failed", error.c_str(), 0, 0, 0);
    return false;
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.otaInProgress = false;
  gRuntimeState.otaProgressPercent = 100;
  gRuntimeState.otaRebootPending = true;
  copyText(gRuntimeState.otaLastResult, sizeof(gRuntimeState.otaLastResult), "success");
  copyText(gRuntimeState.otaLastError, sizeof(gRuntimeState.otaLastError), "");
  portEXIT_CRITICAL(&gRuntimeStateMux);

  sRebootPending = true;
  sRebootAtMs = millis() + kOtaRebootDelayMs;
  bootLog("ota", "upload completed, reboot scheduled");
  return true;
}

void abortOtaUpload(const char *error) {
  Update.abort();
  setOtaState(false, "failed", error == nullptr ? "ota_aborted" : error, 0, 0, 0);
  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.otaRebootPending = false;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  bootLogf("ota", "upload aborted: %s", error == nullptr ? "ota_aborted" : error);
}

void getOtaStatusSnapshot(OtaStatusSnapshot &snapshot) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  snapshot.enabled = kOtaEnabled;
  snapshot.ready = gRuntimeState.otaReady;
  snapshot.inProgress = gRuntimeState.otaInProgress;
  snapshot.rebootPending = gRuntimeState.otaRebootPending;
  snapshot.authRequired = otaAuthRequired();
  snapshot.progressPercent = gRuntimeState.otaProgressPercent;
  snapshot.bytesReceived = gRuntimeState.otaBytesReceived;
  snapshot.totalBytes = gRuntimeState.otaTotalBytes;
  copyText(snapshot.lastError, sizeof(snapshot.lastError), gRuntimeState.otaLastError);
  copyText(snapshot.lastResult, sizeof(snapshot.lastResult), gRuntimeState.otaLastResult);
  portEXIT_CRITICAL(&gRuntimeStateMux);
}
