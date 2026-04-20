#pragma once

#include <Arduino.h>

void beginBootDiagnostics();
void bootSetStage(const char *stage);
void bootSetLastInitError(const char *error);
void bootClearLastInitError();
void bootUpdateWifiState(bool connected, const IPAddress &ip, int32_t rssi);
void bootLog(const char *component, const char *message);
void bootLogf(const char *component, const char *format, ...);
