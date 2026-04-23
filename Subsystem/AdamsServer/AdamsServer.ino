#include <Arduino.h>
#include <WiFi.h>

#include "config/AdamsConfig.h"
#include "src/audio/AudioModule.h"
#include "src/core/BootDiagnostics.h"
#include "src/core/OtaModule.h"
#include "src/camera/CameraModule.h"
#include "src/io/Pca9685Module.h"
#include "src/core/RuntimeState.h"
#include "src/io/SensorModule.h"
#include "src/web/WebServerModule.h"

namespace {

bool sSensorTaskStarted = false;
bool sWebServerStarted = false;
bool sWifiConnected = false;
bool sWifiAttemptActive = false;
IPAddress sLastLoggedIp;
uint32_t sWifiAttemptStartedAt = 0;
uint32_t sLastWifiRetryAt = 0;
uint32_t sLastWebRetryAt = 0;
uint32_t sLastRuntimeHeartbeatAt = 0;

IPAddress makeIpAddress(const uint8_t octets[4]) {
  return IPAddress(octets[0], octets[1], octets[2], octets[3]);
}

void configureWifiNetwork() {
  if (!kWifiUseStaticIp) {
    return;
  }

  const IPAddress localIp = makeIpAddress(kWifiStaticIp);
  const IPAddress gateway = makeIpAddress(kWifiGateway);
  const IPAddress subnet = makeIpAddress(kWifiSubnet);
  const IPAddress dns1 = makeIpAddress(kWifiDns1);
  const IPAddress dns2 = makeIpAddress(kWifiDns2);

  if (WiFi.config(localIp, gateway, subnet, dns1, dns2)) {
    bootLogf("wifi", "static ip configured: %s", localIp.toString().c_str());
  } else {
    bootLog("wifi", "static ip config failed, fallback to DHCP");
  }
}

void updateWifiRuntime(bool logTransitions) {
  const bool connected = WiFi.status() == WL_CONNECTED;
  const IPAddress ip = connected ? WiFi.localIP() : IPAddress();
  const int32_t rssi = connected ? WiFi.RSSI() : 0;

  bootUpdateWifiState(connected, ip, rssi);

  if (logTransitions && connected != sWifiConnected) {
    if (connected) {
      bootLogf("wifi", "connected, ip=%s, rssi=%ld", ip.toString().c_str(), static_cast<long>(rssi));
    } else {
      bootLog("wifi", "disconnected");
    }
  }

  if (logTransitions && connected && ip != sLastLoggedIp) {
    bootLogf("wifi", "current ip=%s", ip.toString().c_str());
  }

  sWifiConnected = connected;
  sLastLoggedIp = ip;
}

void beginWiFiAttempt(const char *reason) {
  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  WiFi.setSleep(false);
  configureWifiNetwork();
  if (sWifiAttemptActive) {
    WiFi.disconnect(false, true);
    delay(50);
  }
  WiFi.begin(kWifiSsid, kWifiPassword);

  sWifiAttemptStartedAt = millis();
  sLastWifiRetryAt = sWifiAttemptStartedAt;
  sWifiAttemptActive = true;
  bootLogf("wifi", "%s: ssid='%s'", reason, kWifiSsid);
}

bool waitForInitialWiFiWindow() {
  bootSetStage("wifi");
  beginWiFiAttempt("starting station connect");

  while (millis() - sWifiAttemptStartedAt < kWifiInitialConnectWindowMs) {
    updateWifiRuntime(false);
    if (WiFi.status() == WL_CONNECTED) {
      updateWifiRuntime(true);
      sWifiAttemptActive = false;
      return true;
    }
    delay(250);
  }

  updateWifiRuntime(true);
  if (!sWifiConnected) {
    bootSetLastInitError("wifi_initial_connect_timeout");
    bootLog("wifi", "initial connect window expired, continuing boot");
  }
  return sWifiConnected;
}

void serviceWiFi() {
  updateWifiRuntime(true);
  if (sWifiConnected) {
    sWifiAttemptActive = false;
    return;
  }

  const uint32_t now = millis();
  if (!sWifiAttemptActive) {
    if (sLastWifiRetryAt == 0 || now - sLastWifiRetryAt >= kWifiRetryIntervalMs) {
      beginWiFiAttempt("retrying station connect");
    }
    return;
  }

  const bool retryDue = (now - sWifiAttemptStartedAt) >= kWifiInitialConnectWindowMs &&
                        (now - sLastWifiRetryAt) >= kWifiRetryIntervalMs;
  if (retryDue) {
    beginWiFiAttempt("retrying station connect");
  }
}

bool runInitStep(const char *stage, const char *component, bool (*initFn)(), const char *errorCode) {
  bootSetStage(stage);
  bootLogf(component, "initializing");
  const bool ok = initFn();
  if (ok) {
    bootLogf(component, "ready");
    return true;
  }

  bootSetLastInitError(errorCode);
  bootLogf(component, "failed, continuing without subsystem");
  return false;
}

void ensureSensorTaskStarted() {
  if (!sSensorTaskStarted) {
    startSensorTask();
    sSensorTaskStarted = true;
    bootLog("sensors", "sensor task started");
  }
}

void tryStartWebServer() {
  if (sWebServerStarted) {
    return;
  }

  const uint32_t now = millis();
  if (sLastWebRetryAt != 0 && now - sLastWebRetryAt < kWebServerRetryIntervalMs) {
    return;
  }

  sLastWebRetryAt = now;
  bootSetStage("web");
  bootLog("web", "starting http servers");
  if (startWebServer()) {
    sWebServerStarted = true;
    bootLog("web", "http servers ready");
    if (sWifiConnected) {
      bootLogf("web", "open http://%s", WiFi.localIP().toString().c_str());
    }
    bootSetStage("running");
    return;
  }

  bootSetLastInitError("web_server_start_failed");
  bootLog("web", "start failed, will retry in loop");
}

void logRuntimeHeartbeat() {
  const uint32_t now = millis();
  if (sLastRuntimeHeartbeatAt != 0 && now - sLastRuntimeHeartbeatAt < 5000) {
    return;
  }
  sLastRuntimeHeartbeatAt = now;

  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool wifiConnected = gRuntimeState.wifiConnected;
  const bool cameraReady = gRuntimeState.cameraReady;
  const bool webReady = gRuntimeState.webReady;
  const bool audioReady = gRuntimeState.audioReady;
  const bool speakerReady = gRuntimeState.speakerReady;
  const bool pcaReady = gRuntimeState.pca9685Ready;
  char ip[sizeof(gRuntimeState.wifiIp)];
  strncpy(ip, gRuntimeState.wifiIp, sizeof(ip) - 1);
  ip[sizeof(ip) - 1] = '\0';
  portEXIT_CRITICAL(&gRuntimeStateMux);

  bootLogf(
    "runtime",
    "heartbeat wifi=%s ip=%s web=%s camera=%s mic=%s speaker=%s pca=%s",
    wifiConnected ? "up" : "down",
    ip,
    webReady ? "up" : "down",
    cameraReady ? "up" : "down",
    audioReady ? "up" : "down",
    speakerReady ? "up" : "down",
    pcaReady ? "up" : "down"
  );
}

}  // namespace

void setup() {
  beginBootDiagnostics();
  bootLogf("boot", "AdamS Server booting, heap=%lu, psram=%lu",
    static_cast<unsigned long>(ESP.getFreeHeap()),
    static_cast<unsigned long>(ESP.getFreePsram()));

  if (runInitStep("sensors", "sensors", initSensors, "sensor_init_failed")) {
    ensureSensorTaskStarted();
  }

  waitForInitialWiFiWindow();
  runInitStep("ota", "ota", initOta, "ota_init_failed");
  runInitStep("camera", "camera", initCamera, "camera_init_failed");
  runInitStep("mic", "audio-mic", initAudioCapture, "audio_capture_init_failed");
  runInitStep("speaker", "speaker", initSpeakerPlayback, "speaker_init_failed");
  runInitStep("pca9685", "pca9685", initPca9685, "pca9685_init_failed");
  tryStartWebServer();

  if (!sWebServerStarted) {
    bootSetStage("running");
  }
  bootLog("boot", "initial bring-up complete");
}

void loop() {
  serviceWiFi();
  serviceOta();
  tryStartWebServer();
  logRuntimeHeartbeat();
  delay(250);
}
