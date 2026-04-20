#pragma once

#include <Arduino.h>

struct OtaStatusSnapshot {
  bool enabled = false;
  bool ready = false;
  bool inProgress = false;
  bool rebootPending = false;
  bool authRequired = false;
  uint8_t progressPercent = 0;
  uint32_t bytesReceived = 0;
  uint32_t totalBytes = 0;
  char lastError[64] = "";
  char lastResult[32] = "idle";
};

bool initOta();
void serviceOta();
bool otaAuthRequired();
bool otaTokenValid(const char *token);
bool beginOtaUpload(uint32_t totalBytes, const char *source, String &error);
bool writeOtaChunk(uint8_t *data, size_t length, String &error);
bool finishOtaUpload(String &error);
void abortOtaUpload(const char *error);
void getOtaStatusSnapshot(OtaStatusSnapshot &snapshot);
