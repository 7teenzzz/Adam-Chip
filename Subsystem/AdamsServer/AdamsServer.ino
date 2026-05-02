#include <Arduino.h>

#include "config/AdamsConfig.h"
#include "src/audio/AudioModule.h"
#include "src/audio/SystemSoundModule.h"
#include "src/core/BootDiagnostics.h"
#include "src/core/NetworkModule.h"
#include "src/core/OtaModule.h"
#include "src/camera/CameraModule.h"
#include "src/io/Pca9685Module.h"
#include "src/core/RuntimeState.h"
#include "src/io/SensorModule.h"
#include "src/web/WebServerModule.h"

namespace {

bool sSensorTaskStarted = false;
bool sWebServerStarted = false;
uint32_t sLastWebRetryAt = 0;
uint32_t sLastRuntimeHeartbeatAt = 0;

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
    if (networkIsConnected()) {
      bootLogf("web", "open http://%s", networkIp().toString().c_str());
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
  const bool networkConnected = gRuntimeState.networkConnected;
  const bool ethernetLinkUp = gRuntimeState.ethernetLinkUp;
  const bool cameraReady = gRuntimeState.cameraReady;
  const bool webReady = gRuntimeState.webReady;
  const bool audioReady = gRuntimeState.audioReady;
  const bool speakerReady = gRuntimeState.speakerReady;
  const bool pcaReady = gRuntimeState.pca9685Ready;
  char transport[sizeof(gRuntimeState.networkTransport)];
  strncpy(transport, gRuntimeState.networkTransport, sizeof(transport) - 1);
  transport[sizeof(transport) - 1] = '\0';
  char ip[sizeof(gRuntimeState.networkIp)];
  strncpy(ip, gRuntimeState.networkIp, sizeof(ip) - 1);
  ip[sizeof(ip) - 1] = '\0';
  portEXIT_CRITICAL(&gRuntimeStateMux);

  bootLogf(
    "runtime",
    "heartbeat network=%s:%s ip=%s eth_link=%s web=%s camera=%s mic=%s speaker=%s pca=%s",
    transport,
    networkConnected ? "up" : "down",
    ip,
    ethernetLinkUp ? "up" : "down",
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

  initNetwork();
  runInitStep("ota", "ota", initOta, "ota_init_failed");
  runInitStep("filesystem", "system-sounds", initSystemSounds, "system_sounds_init_failed");
  runInitStep("camera", "camera", initCamera, "camera_init_failed");
  runInitStep("mic", "audio-mic", initAudioCapture, "audio_capture_init_failed");
  const bool speakerReady = runInitStep("speaker", "speaker", initSpeakerPlayback, "speaker_init_failed");
  runInitStep("pca9685", "pca9685", initPca9685, "pca9685_init_failed");
  tryStartWebServer();

  if (!sWebServerStarted) {
    bootSetStage("running");
  }
  bootLog("boot", "initial bring-up complete");

  if (speakerReady) {
    delay(kBootSoundStartupDelayMs);
    playSystemSound("boot");
  }
}

void loop() {
  serviceNetwork();
  serviceOta();
  tryStartWebServer();
  logRuntimeHeartbeat();
  delay(250);
}
