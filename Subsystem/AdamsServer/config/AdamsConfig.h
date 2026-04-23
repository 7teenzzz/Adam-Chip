#pragma once

#if __has_include(<Arduino.h>)
#include <Arduino.h>
#elif __has_include("Arduino.h")
#include "Arduino.h"
#else
#include <cstdint>
#include <cstddef>

using uint8_t = std::uint8_t;
using uint16_t = std::uint16_t;
using uint32_t = std::uint32_t;
using size_t = std::size_t;

enum framesize_t { FRAMESIZE_QVGA };
enum pixformat_t { PIXFORMAT_JPEG };
#endif

#if __has_include(<esp_camera.h>)
#include <esp_camera.h>
#elif __has_include("esp_camera.h")
#include "esp_camera.h"
#endif

#include "PinsConfig.h"
#include "PrivateConfig.h"

struct Pca9685SceneConfig {
  const char *name;
  uint16_t values[16];
};

inline constexpr uint8_t kWifiStaticIp[4] = {192, 168, kWifiSubnetOctet3, kWifiHostOctet};
inline constexpr uint8_t kWifiGateway[4] = {192, 168, kWifiSubnetOctet3, kWifiGatewayHostOctet};
inline constexpr uint8_t kWifiSubnet[4] = {kWifiSubnetMask[0], kWifiSubnetMask[1], kWifiSubnetMask[2], kWifiSubnetMask[3]};

inline constexpr uint16_t kHttpPort = 80;
inline constexpr uint16_t kStreamPort = 81;
inline constexpr uint16_t kAudioPort = 82;
inline constexpr uint16_t kSpeakerPort = 83;
inline constexpr uint32_t kSerialBaudRate = 115200;
// Keep UART0 diagnostics disabled by default because this pin map uses GPIO43/44 for I2C.
inline constexpr bool kEnableUart0Diagnostics = false;
inline constexpr bool kOtaEnabled = true;
inline constexpr uint32_t kOtaRebootDelayMs = 1500;
inline constexpr uint32_t kWifiInitialConnectWindowMs = 8000;
inline constexpr uint32_t kWifiRetryIntervalMs = 15000;
inline constexpr uint32_t kWebServerRetryIntervalMs = 5000;

inline constexpr framesize_t kDefaultFrameSize = FRAMESIZE_QVGA;
inline constexpr pixformat_t kDefaultPixelFormat = PIXFORMAT_JPEG;
inline constexpr int kDefaultJpegQuality = 18;
inline constexpr int kPsramJpegQuality = 18;
inline constexpr uint32_t kXclkFrequencyHz = 20000000;
inline constexpr uint32_t kCameraProducerFrameIntervalMs = 66;
inline constexpr uint32_t kCameraProducerWarmFrameIntervalMs = 180;
inline constexpr uint32_t kCameraProducerFastGraceMs = 4000;
inline constexpr uint32_t kStreamSlowSendThresholdMs = 900;
inline constexpr uint8_t kStreamSlowSendStrikeLimit = 5;

inline constexpr uint32_t kAudioSampleRate = 16000;
inline constexpr uint8_t kAudioBitsPerSample = 16;
inline constexpr uint8_t kAudioChannels = 1;
inline constexpr uint8_t kAudioPreferredSlot = 1;  // 1 = left, 2 = right
inline constexpr uint8_t kAudioI2sStdFormat = 2;   // 1 = Philips, 2 = MSB
inline constexpr uint8_t kAudioCaptureShift = 0;
inline constexpr size_t kAudioRingBufferBytes = 65536;
inline constexpr size_t kAudioReadChunkBytes = 1024;
inline constexpr size_t kSpeakerRingBufferBytes = 65536;
inline constexpr size_t kSpeakerReadChunkBytes = 1024;
inline constexpr size_t kSpeakerTxChunkSamples = 256;
inline constexpr size_t kSpeakerHttpChunkBytes = 1024;

inline constexpr uint32_t kSensorPollMs = 100;
inline constexpr uint32_t kMotionDebounceMs = 60;
inline constexpr float kLightAlpha = 0.18f;
inline constexpr uint32_t kI2cClockHz = 400000;

inline constexpr uint8_t kPca9685Address = 0x40;
inline constexpr uint16_t kPca9685DefaultFrequency = 1000;
inline constexpr char kPca9685BootScene[] = "boot_idle";

inline constexpr Pca9685SceneConfig kPca9685Scenes[] = {
  {"boot_idle", {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}},
  {"all_on", {4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095}},
  {"alternating", {4095, 0, 4095, 0, 4095, 0, 4095, 0, 4095, 0, 4095, 0, 4095, 0, 4095, 0}}
};

inline constexpr size_t kPca9685SceneCount = sizeof(kPca9685Scenes) / sizeof(kPca9685Scenes[0]);

inline constexpr size_t kStatusJsonCapacity = 6144;
inline constexpr size_t kSensorJsonCapacity = 768;
inline constexpr size_t kPcaJsonCapacity = 1024;
