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

enum class AdamsNetworkTransport : uint8_t {
  None,
  WiFi,
  EthernetW5500,
  AccessPoint
};

inline constexpr uint8_t kWifiStaticIp[4] = {192, 168, kWifiSubnetOctet3, kWifiHostOctet};
inline constexpr uint8_t kWifiGateway[4] = {192, 168, kWifiSubnetOctet3, kWifiGatewayHostOctet};
inline constexpr uint8_t kWifiSubnet[4] = {kWifiSubnetMask[0], kWifiSubnetMask[1], kWifiSubnetMask[2], kWifiSubnetMask[3]};

inline constexpr bool kEthernetUseStaticIp = true;
// Crossover-cable point-to-point with Jetson eno1. Isolated subnet 10.10.10.0/24:
//   Jetson eno1 = 10.10.10.1, ESP W5500 = 10.10.10.171. No gateway (no L3 routing).
// Wi-Fi config (kWifi*) stays at 192.168.0.171 for setup/OTA on a normal LAN.
inline constexpr uint8_t kEthernetStaticIp[4] = {10, 10, 10, 171};
inline constexpr uint8_t kEthernetGateway[4] = {0, 0, 0, 0};
inline constexpr uint8_t kEthernetSubnet[4] = {255, 255, 255, 0};
inline constexpr uint8_t kEthernetDns1[4] = {0, 0, 0, 0};
inline constexpr uint8_t kEthernetDns2[4] = {0, 0, 0, 0};
inline constexpr int32_t kEthernetPhyAddress = 1;
inline constexpr uint8_t kEthernetSpiFrequencyMhz = 20;

inline constexpr char kApSsid[] = "Adam Chip";
inline constexpr char kApPassword[] = "4D4M-CH1P4$";
inline constexpr uint8_t kApChannel = 6;
inline constexpr uint8_t kApMaxConnections = 4;
inline constexpr uint8_t kApStaticIp[4] = {192, 168, 4, 1};
inline constexpr uint8_t kApGateway[4] = {192, 168, 4, 1};
inline constexpr uint8_t kApSubnet[4] = {255, 255, 255, 0};

inline constexpr uint16_t kHttpPort = 80;
// Audio stream (/audio) + WAV clip (/api/audio/clip) + MJPEG camera (/stream)
// are served on kStreamPort. The speaker sink (/speaker) moved to its OWN
// server kSpeakerServerPort so the mic stream — which monopolizes the single
// :81 httpd task with its continuous loop — can never block speaker playback.
inline constexpr uint16_t kStreamPort = 81;
inline constexpr uint16_t kSpeakerServerPort = 82;
inline constexpr uint32_t kSerialBaudRate = 115200;
// Keep UART0 diagnostics disabled by default because this pin map uses GPIO43/44 for I2C.
inline constexpr bool kEnableUart0Diagnostics = false;
inline constexpr bool kOtaEnabled = true;
inline constexpr uint32_t kOtaRebootDelayMs = 1500;
inline constexpr uint32_t kWifiInitialConnectWindowMs = 8000;
inline constexpr uint32_t kWifiRetryIntervalMs = 15000;
inline constexpr uint32_t kEthernetInitialConnectWindowMs = 5000;
inline constexpr uint32_t kEthernetRetryIntervalMs = 15000;
inline constexpr uint32_t kWebServerRetryIntervalMs = 5000;
inline constexpr uint32_t kBootSoundStartupDelayMs = 1200;

inline constexpr framesize_t kDefaultFrameSize = FRAMESIZE_QVGA;
inline constexpr pixformat_t kDefaultPixelFormat = PIXFORMAT_JPEG;
inline constexpr int kDefaultJpegQuality = 18;
inline constexpr int kPsramJpegQuality = 18;
inline constexpr uint32_t kXclkFrequencyHz_OV5640 = 20000000;
inline constexpr uint32_t kXclkFrequencyHz_OV7670 = 24000000;
inline constexpr uint32_t kCameraProducerFrameIntervalMs = 66;
inline constexpr uint32_t kCameraProducerWarmFrameIntervalMs = 180;
inline constexpr uint32_t kCameraProducerFastGraceMs = 4000;
inline constexpr uint32_t kStreamSlowSendThresholdMs = 900;
inline constexpr uint8_t kStreamSlowSendStrikeLimit = 5;
inline constexpr size_t kStreamFrameBufferReserveBytes = 196608;

inline constexpr uint32_t kAudioSampleRate = 16000;
inline constexpr uint32_t kSpeakerSampleRate = 44100;
inline constexpr uint8_t kAudioBitsPerSample = 16;
inline constexpr uint8_t kAudioChannels = 1;
inline constexpr uint8_t kAudioPreferredSlot = 1;  // 1 = left, 2 = right
inline constexpr uint8_t kAudioI2sStdFormat = 2;   // 1 = Philips, 2 = MSB
inline constexpr uint8_t kAudioCaptureShift = 0;
inline constexpr size_t kAudioRingBufferBytes = 16384;  // 256ms stereo @ 16kHz 16-bit — caps reader lag at ~256ms (drop-oldest on overflow). Was 262144 (4s); equilibrium lag of ~2.3s caused TTS-tail echo into ASR after mic_unmute.
inline constexpr size_t kAudioReadChunkBytes = 1024;
inline constexpr size_t kSpeakerRingBufferBytes = 32768;
inline constexpr size_t kSpeakerReadChunkBytes = 1024;
inline constexpr size_t kSpeakerTxChunkSamples = 256;
inline constexpr size_t kSpeakerHttpChunkBytes = 1024;

inline constexpr uint32_t kSensorPollMs = 100;
inline constexpr uint32_t kMotionDebounceMs = 60;
inline constexpr float kLightAlpha = 0.18f;
inline constexpr uint32_t kI2cClockHz = 100000;

inline constexpr uint8_t kPca9685Address = 0x40;
inline constexpr uint16_t kPca9685DefaultFrequency = 1000;
inline constexpr char kPca9685BootScene[] = "test_all";

inline constexpr Pca9685SceneConfig kPca9685Scenes[] = {
  {"boot_idle", {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}},
  {"test_all",  {2907, 2907, 2907, 2907, 2907, 2907, 2907, 2907, 2907, 2907, 2907, 2907, 2907, 2907, 2907, 2907}},
  {"all_on", {4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095, 4095}},
  {"alternating", {4095, 0, 4095, 0, 4095, 0, 4095, 0, 4095, 0, 4095, 0, 4095, 0, 4095, 0}}
};

inline constexpr size_t kPca9685SceneCount = sizeof(kPca9685Scenes) / sizeof(kPca9685Scenes[0]);

// ---------------------------------------------------------------------------
// Technoflora animation engine (Phase 29, FLORA-01 / FLORA-06).
//
// The firmware boots and animates independently of the Jetson, so it needs its
// OWN copy of the structural flora defaults. The Jetson-side source of truth is
// the `flora` section in System/Config.json (Config.schema.json documents it);
// these constants are the firmware-tier duplicate of the *structural* defaults
// (channel masks, gamma, crossfade, vibro ceiling). Keep them consistent with
// Config.json. Per-preset numeric params (base/peak duty, period) arrive from
// the Jetson via /api/flora/state and override the in-code preset defaults.
// ---------------------------------------------------------------------------
inline constexpr uint32_t kFloraTickMs = 20;            // ~50 Hz animation task period
inline constexpr uint8_t kFloraLightChannelLo = 4;      // light = channels 4-14 (11 lamps)
inline constexpr uint8_t kFloraLightChannelHi = 14;
inline constexpr uint8_t kFloraVibroChannelLo = 0;      // vibro motors = channels 0-3 (first 4)
inline constexpr uint8_t kFloraVibroChannelHi = 3;
inline constexpr float kFloraGamma = 2.2f;              // D-13: perceptual gamma — now UNUSED by the light path (Phase 30 R5/decision A: raw PWM, no gamma)
inline constexpr uint32_t kFloraDefaultCrossfadeMs = 200;  // D-09: 150-250 ms preset crossfade
// Vibro is NOT subject to safety.motor_* clamps (D-04/FLORA-06): those guard
// action.py timed actuations. Flora vibro is continuous low-amplitude presence,
// so it gets its own intensity ceiling instead (D-12, restrained default ~30%).
inline constexpr uint16_t kFloraVibroIntensityCeiling = 3890;  // ~95% of 4095 — vibro runs strong; NOT subject to the light max_duty ceiling (per user)
// External-preset watchdog: if no HTTP /api/pca9685/* frame arrives for this long
// while flora is in External (Jetson RMS/calibration stream died), floraTask
// auto-recovers to breathe so the lamps never freeze. Mirrors Config.json
// flora.external_timeout_ms (structural default duplicated firmware-side).
inline constexpr uint32_t kFloraExternalTimeoutMs = 500;
// Safe-ceiling for all flora animation output (Phase 30 D-03). Raw PWM percent,
// mirrors Config.json flora.max_duty_pct — structural default duplicated
// firmware-side, like kFloraExternalTimeoutMs. Applied in floraTick immediately
// before writeAllChannelsRaw as defence-in-depth so no animation frame can
// exceed this ceiling regardless of preset params or Jetson-side values.
inline constexpr uint8_t kFloraMaxDutyPct = 100;

inline constexpr size_t kStatusJsonCapacity = 16384;
inline constexpr size_t kSensorJsonCapacity = 768;
inline constexpr size_t kPcaJsonCapacity = 1024;
