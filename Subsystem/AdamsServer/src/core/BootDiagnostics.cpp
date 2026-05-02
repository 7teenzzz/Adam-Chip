#include "BootDiagnostics.h"

#include <cstdarg>
#include <cstdio>
#include <cstring>

#include "../../config/AdamsConfig.h"
#include "RuntimeState.h"

namespace {

char sCurrentStage[24] = "boot";

void writeLine(const char *line) {
  if (line == nullptr) {
    return;
  }

  Serial.println(line);
  if (kEnableUart0Diagnostics) {
    Serial0.println(line);
  }
}

void formatAndWrite(const char *component, const char *format, va_list args) {
  char message[192];
  vsnprintf(message, sizeof(message), format, args);

  char line[256];
  snprintf(
    line,
    sizeof(line),
    "[%10lu ms][%s][%s] %s",
    static_cast<unsigned long>(millis()),
    sCurrentStage,
    component == nullptr ? "system" : component,
    message
  );
  writeLine(line);
}

void copyStage(const char *stage) {
  const char *value = stage == nullptr ? "unknown" : stage;
  strncpy(sCurrentStage, value, sizeof(sCurrentStage) - 1);
  sCurrentStage[sizeof(sCurrentStage) - 1] = '\0';
}

}  // namespace

void beginBootDiagnostics() {
  Serial.begin(kSerialBaudRate);
  const uint32_t serialWaitStartedAt = millis();
  while (!Serial && millis() - serialWaitStartedAt < 1500) {
    delay(10);
  }
  if (kEnableUart0Diagnostics) {
    Serial0.begin(kSerialBaudRate);
  }
  delay(120);

  runtimeSetBootStage("boot");
  runtimeClearLastInitError();
  runtimeSetNetworkState("none", false, IPAddress());
  runtimeSetWifiState(false, 0, IPAddress());
  runtimeSetEthernetState(false, false, IPAddress());
  copyStage("boot");

  bootLog("boot", "diagnostics online");
}

void bootSetStage(const char *stage) {
  runtimeSetBootStage(stage);
  copyStage(stage);
  bootLogf("boot", "stage=%s", sCurrentStage);
}

void bootSetLastInitError(const char *error) {
  runtimeSetLastInitError(error);
  if (error != nullptr && error[0] != '\0') {
    bootLogf("error", "last_init_error=%s", error);
  }
}

void bootClearLastInitError() {
  runtimeClearLastInitError();
}

void bootUpdateWifiState(bool connected, const IPAddress &ip, int32_t rssi) {
  runtimeSetWifiState(connected, rssi, ip);
}

void bootLog(const char *component, const char *message) {
  bootLogf(component, "%s", message == nullptr ? "" : message);
}

void bootLogf(const char *component, const char *format, ...) {
  va_list args;
  va_start(args, format);
  formatAndWrite(component, format, args);
  va_end(args);
}
