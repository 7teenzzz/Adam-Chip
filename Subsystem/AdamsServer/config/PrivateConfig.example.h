#pragma once

// Copy this file to PrivateConfig.h and fill in your real private values.
// PrivateConfig.h is ignored by git and must stay only on your machine.

inline constexpr char kWifiSsid[] = "YOUR_WIFI_SSID";
inline constexpr char kWifiPassword[] = "YOUR_WIFI_PASSWORD";

// Use OTA token to protect firmware upload over Wi-Fi.
inline constexpr char kOtaAuthToken[] = "CHANGE_ME_TO_RANDOM_TOKEN";

// Static IP scheme:
// final device IP = 192.168.<kWifiSubnetOctet3>.<kWifiHostOctet>
// Recommended host octets: 17, 71, 171
inline constexpr bool kWifiUseStaticIp = true;
inline constexpr uint8_t kWifiSubnetOctet3 = 0;
inline constexpr uint8_t kWifiHostOctet = 171;
inline constexpr uint8_t kWifiGatewayHostOctet = 1;
inline constexpr uint8_t kWifiSubnetMask[4] = {255, 255, 255, 0};
inline constexpr uint8_t kWifiDns1[4] = {1, 1, 1, 1};
inline constexpr uint8_t kWifiDns2[4] = {8, 8, 8, 8};
