#include "RuntimeState.h"

#include <cstring>

RuntimeState gRuntimeState;
portMUX_TYPE gRuntimeStateMux = portMUX_INITIALIZER_UNLOCKED;

namespace {

void copyIntoBuffer(char *dst, size_t dstSize, const char *src) {
  if (dst == nullptr || dstSize == 0) {
    return;
  }

  const char *value = src == nullptr ? "" : src;
  strncpy(dst, value, dstSize - 1);
  dst[dstSize - 1] = '\0';
}

}  // namespace

void runtimeSetBootStage(const char *stage) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  copyIntoBuffer(gRuntimeState.bootStage, sizeof(gRuntimeState.bootStage), stage);
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

void runtimeSetLastInitError(const char *error) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  copyIntoBuffer(gRuntimeState.lastInitError, sizeof(gRuntimeState.lastInitError), error);
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

void runtimeClearLastInitError() {
  runtimeSetLastInitError("");
}

void runtimeSetNetworkState(const char *transport, bool connected, const IPAddress &ip) {
  const String ipString = connected ? ip.toString() : String("0.0.0.0");

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.networkConnected = connected;
  copyIntoBuffer(gRuntimeState.networkTransport, sizeof(gRuntimeState.networkTransport), transport);
  copyIntoBuffer(gRuntimeState.networkIp, sizeof(gRuntimeState.networkIp), ipString.c_str());
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

void runtimeSetWifiState(bool connected, int32_t rssi, const IPAddress &ip) {
  const String ipString = connected ? ip.toString() : String("0.0.0.0");

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.wifiConnected = connected;
  gRuntimeState.wifiRssi = connected ? rssi : 0;
  copyIntoBuffer(gRuntimeState.wifiIp, sizeof(gRuntimeState.wifiIp), ipString.c_str());
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

void runtimeSetEthernetState(bool connected, bool linkUp, const IPAddress &ip) {
  const String ipString = connected ? ip.toString() : String("0.0.0.0");

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.ethernetConnected = connected;
  gRuntimeState.ethernetLinkUp = linkUp;
  copyIntoBuffer(gRuntimeState.ethernetIp, sizeof(gRuntimeState.ethernetIp), ipString.c_str());
  portEXIT_CRITICAL(&gRuntimeStateMux);
}
