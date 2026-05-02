#include "NetworkModule.h"

#include <ETH.h>
#include <SPI.h>
#include <WiFi.h>

#include "../../config/AdamsConfig.h"
#include "BootDiagnostics.h"
#include "RuntimeState.h"

namespace {

// ──── State ────────────────────────────────────────────────────────────────

AdamsNetworkTransport sActiveTransport = AdamsNetworkTransport::None;

bool sWifiConnected = false;
bool sWifiAttemptActive = false;
IPAddress sLastLoggedIp;
uint32_t sWifiAttemptStartedAt = 0;
uint32_t sLastWifiRetryAt = 0;
size_t sWifiCandidateIndex = 0;

bool sEthernetBeginOk = false;
bool sEthernetConnected = false;
bool sEthernetLinkUp = false;
bool sEthernetEventRegistered = false;
IPAddress sLastEthernetLoggedIp;
uint32_t sLastEthernetRetryAt = 0;

// ──── Helpers ──────────────────────────────────────────────────────────────

struct WifiCandidate {
  const char *ssid;
  const char *password;
  const char *label;
};

const WifiCandidate kWifiCandidates[] = {
  {kWifiSsid, kWifiPassword, "primary"},
  {kWifi5Ssid, kWifiPassword, "wifi5"},
  {kFallbackWifiSsid, kWifiPassword, "fallback"},
};

constexpr size_t kWifiCandidateCount = sizeof(kWifiCandidates) / sizeof(kWifiCandidates[0]);

IPAddress makeIpAddress(const uint8_t octets[4]) {
  return IPAddress(octets[0], octets[1], octets[2], octets[3]);
}

void updateActiveNetworkState(bool connected, const IPAddress &ip) {
  runtimeSetNetworkState(networkTransportName(), connected, ip);
}

// ──── Wi-Fi STA ────────────────────────────────────────────────────────────

bool selectConfiguredWifiCandidate() {
  for (size_t offset = 0; offset < kWifiCandidateCount; ++offset) {
    const size_t index = (sWifiCandidateIndex + offset) % kWifiCandidateCount;
    const WifiCandidate &candidate = kWifiCandidates[index];
    if (candidate.ssid != nullptr && candidate.ssid[0] != '\0') {
      sWifiCandidateIndex = index;
      return true;
    }
  }
  return false;
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

  runtimeSetWifiState(connected, rssi, ip);
  if (sActiveTransport == AdamsNetworkTransport::WiFi) {
    updateActiveNetworkState(connected, ip);
  }

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

  if (!selectConfiguredWifiCandidate()) {
    sWifiAttemptActive = false;
    sLastWifiRetryAt = millis();
    bootLog("wifi", "no configured SSID, continuing without Wi-Fi");
    updateWifiRuntime(true);
    return;
  }

  const WifiCandidate &candidate = kWifiCandidates[sWifiCandidateIndex % kWifiCandidateCount];
  WiFi.begin(candidate.ssid, candidate.password);

  sWifiAttemptStartedAt = millis();
  sLastWifiRetryAt = sWifiAttemptStartedAt;
  sWifiAttemptActive = true;
  bootLogf("wifi", "%s: candidate=%s ssid='%s'", reason, candidate.label, candidate.ssid);
}

// Scan for any configured SSID in range; updates sWifiCandidateIndex on match.
bool scanForConfiguredWifi() {
  bootLog("wifi", "scanning for configured networks");
  WiFi.mode(WIFI_STA);

  const int found = WiFi.scanNetworks();
  if (found <= 0) {
    bootLog("wifi", "scan: no networks found");
    WiFi.scanDelete();
    return false;
  }

  for (size_t j = 0; j < kWifiCandidateCount; ++j) {
    if (kWifiCandidates[j].ssid == nullptr || kWifiCandidates[j].ssid[0] == '\0') {
      continue;
    }
    for (int i = 0; i < found; ++i) {
      if (WiFi.SSID(i) == kWifiCandidates[j].ssid) {
        sWifiCandidateIndex = j;
        bootLogf("wifi", "scan: found '%s' rssi=%d", kWifiCandidates[j].ssid, (int)WiFi.RSSI(i));
        WiFi.scanDelete();
        return true;
      }
    }
  }

  WiFi.scanDelete();
  bootLog("wifi", "scan: no configured SSIDs in range");
  return false;
}

bool waitForInitialWiFiWindow() {
  bootSetStage("wifi");
  beginWiFiAttempt("starting station connect");

  while (sWifiAttemptActive && millis() - sWifiAttemptStartedAt < kWifiInitialConnectWindowMs) {
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
    bootLog("wifi", "connect window expired");
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
    sWifiCandidateIndex = (sWifiCandidateIndex + 1) % kWifiCandidateCount;
    beginWiFiAttempt("retrying station connect");
  }
}

// ──── Ethernet ─────────────────────────────────────────────────────────────

void onNetworkEvent(arduino_event_id_t event, arduino_event_info_t info) {
  (void)info;

  switch (event) {
    case ARDUINO_EVENT_ETH_START:
      ETH.setHostname("adams-w5500");
      bootLog("eth", "started");
      break;
    case ARDUINO_EVENT_ETH_CONNECTED:
      bootLog("eth", "link connected");
      break;
    case ARDUINO_EVENT_ETH_GOT_IP:
      bootLogf("eth", "got ip=%s", ETH.localIP().toString().c_str());
      break;
    case ARDUINO_EVENT_ETH_LOST_IP:
      bootLog("eth", "lost ip");
      break;
    case ARDUINO_EVENT_ETH_DISCONNECTED:
      bootLog("eth", "link disconnected");
      break;
    case ARDUINO_EVENT_ETH_STOP:
      bootLog("eth", "stopped");
      break;
    default:
      break;
  }
}

bool configureEthernetNetwork() {
  if (!kEthernetUseStaticIp) {
    return true;
  }

  const IPAddress localIp = makeIpAddress(kEthernetStaticIp);
  const IPAddress gateway = makeIpAddress(kEthernetGateway);
  const IPAddress subnet = makeIpAddress(kEthernetSubnet);
  const IPAddress dns1 = makeIpAddress(kEthernetDns1);
  const IPAddress dns2 = makeIpAddress(kEthernetDns2);

  if (ETH.config(localIp, gateway, subnet, dns1, dns2)) {
    bootLogf("eth", "static ip configured: %s", localIp.toString().c_str());
    return true;
  }

  bootLog("eth", "static ip config failed");
  return false;
}

void updateEthernetRuntime(bool logTransitions) {
  const bool linkUp = ETH.linkUp();
  const bool connected = ETH.connected() && ETH.hasIP();
  const IPAddress ip = connected ? ETH.localIP() : IPAddress();

  runtimeSetEthernetState(connected, linkUp, ip);
  if (sActiveTransport == AdamsNetworkTransport::EthernetW5500) {
    updateActiveNetworkState(connected, ip);
  }

  if (logTransitions && linkUp != sEthernetLinkUp) {
    bootLogf("eth", "link=%s", linkUp ? "up" : "down");
  }

  if (logTransitions && connected != sEthernetConnected) {
    bootLogf("eth", "network=%s", connected ? "up" : "down");
  }

  if (logTransitions && connected && ip != sLastEthernetLoggedIp) {
    bootLogf("eth", "current ip=%s", ip.toString().c_str());
  }

  sEthernetLinkUp = linkUp;
  sEthernetConnected = connected;
  sLastEthernetLoggedIp = ip;
}

bool beginEthernetAttempt(const char *reason) {
  bootLogf("eth", "%s: W5500 CS=%d INT=%d RST=%d", reason, ETH_SPI_CS, ETH_INT, ETH_RST);
  if (!sEthernetEventRegistered) {
    Network.onEvent(onNetworkEvent);
    sEthernetEventRegistered = true;
  }
  sEthernetBeginOk = ETH.begin(
    ETH_PHY_W5500,
    kEthernetPhyAddress,
    ETH_SPI_CS,
    ETH_INT,
    ETH_RST,
    SPI2_HOST,
    ETH_SPI_SCK,
    ETH_SPI_MISO,
    ETH_SPI_MOSI,
    kEthernetSpiFrequencyMhz
  );

  if (!sEthernetBeginOk) {
    bootLog("eth", "ETH.begin failed");
    updateEthernetRuntime(true);
    return false;
  }

  configureEthernetNetwork();
  updateEthernetRuntime(true);
  return true;
}

bool waitForInitialEthernetWindow() {
  bootSetStage("ethernet");
  runtimeSetWifiState(false, 0, IPAddress());
  beginEthernetAttempt("starting ethernet");

  const uint32_t startedAt = millis();
  while (millis() - startedAt < kEthernetInitialConnectWindowMs) {
    updateEthernetRuntime(false);
    if (sEthernetConnected) {
      updateEthernetRuntime(true);
      return true;
    }
    delay(250);
  }

  updateEthernetRuntime(true);
  if (!sEthernetConnected) {
    bootLog("eth", "initial connect window expired");
  }
  return sEthernetConnected;
}

void serviceEthernet() {
  if (!sEthernetBeginOk) {
    const uint32_t now = millis();
    if (sLastEthernetRetryAt == 0 || now - sLastEthernetRetryAt >= kEthernetRetryIntervalMs) {
      sLastEthernetRetryAt = now;
      beginEthernetAttempt("retrying ethernet");
    }
    return;
  }

  updateEthernetRuntime(true);
}

// ──── Access Point ─────────────────────────────────────────────────────────

bool startAccessPoint() {
  bootSetStage("ap");

  if (sWifiAttemptActive) {
    WiFi.disconnect(false, true);
    delay(100);
    sWifiAttemptActive = false;
  }

  WiFi.mode(WIFI_AP);

  const IPAddress apIp = makeIpAddress(kApStaticIp);
  const IPAddress apGw = makeIpAddress(kApGateway);
  const IPAddress apSubnet = makeIpAddress(kApSubnet);
  WiFi.softAPConfig(apIp, apGw, apSubnet);

  if (!WiFi.softAP(kApSsid, kApPassword, kApChannel, 0, kApMaxConnections)) {
    bootLog("ap", "softAP failed");
    return false;
  }

  sActiveTransport = AdamsNetworkTransport::AccessPoint;
  updateActiveNetworkState(true, apIp);
  bootLogf("ap", "started ssid='%s' ip=%s", kApSsid, apIp.toString().c_str());
  return true;
}

// W5500 (SPI) coexists with Wi-Fi AP: keep attempting Ethernet for hot-plug recovery.
void serviceApWithEthernetRetry() {
  serviceEthernet();
  if (sEthernetConnected) {
    WiFi.softAPdisconnect(true);
    sActiveTransport = AdamsNetworkTransport::EthernetW5500;
    updateActiveNetworkState(true, ETH.localIP());
    bootLog("eth", "ethernet recovered, leaving AP mode");
  }
}

}  // namespace

// ──── Public API ───────────────────────────────────────────────────────────

bool initNetwork() {
  // Phase 1: Ethernet (preferred — always try first)
  if (waitForInitialEthernetWindow()) {
    sActiveTransport = AdamsNetworkTransport::EthernetW5500;
    updateActiveNetworkState(true, ETH.localIP());
    return true;
  }

  // Phase 2: Wi-Fi STA — scan first to avoid connecting to absent networks
  if (scanForConfiguredWifi()) {
    if (waitForInitialWiFiWindow()) {
      sActiveTransport = AdamsNetworkTransport::WiFi;
      updateActiveNetworkState(true, WiFi.localIP());
      return true;
    }
  }

  // Phase 3: AP fallback — always succeeds, device stays reachable
  bootLog("net", "all uplinks failed, raising own AP");
  startAccessPoint();
  return false;
}

void serviceNetwork() {
  switch (sActiveTransport) {
    case AdamsNetworkTransport::EthernetW5500:
      serviceEthernet();
      break;
    case AdamsNetworkTransport::WiFi:
      serviceWiFi();
      break;
    case AdamsNetworkTransport::AccessPoint:
      serviceApWithEthernetRetry();
      break;
    default:
      break;
  }
}

bool networkIsConnected() {
  switch (sActiveTransport) {
    case AdamsNetworkTransport::EthernetW5500: return sEthernetConnected;
    case AdamsNetworkTransport::WiFi: return sWifiConnected;
    case AdamsNetworkTransport::AccessPoint: return true;
    default: return false;
  }
}

IPAddress networkIp() {
  switch (sActiveTransport) {
    case AdamsNetworkTransport::EthernetW5500:
      return sEthernetConnected ? ETH.localIP() : IPAddress();
    case AdamsNetworkTransport::WiFi:
      return sWifiConnected ? WiFi.localIP() : IPAddress();
    case AdamsNetworkTransport::AccessPoint:
      return makeIpAddress(kApStaticIp);
    default:
      return IPAddress();
  }
}

const char *networkTransportName() {
  switch (sActiveTransport) {
    case AdamsNetworkTransport::EthernetW5500: return "ethernet_w5500";
    case AdamsNetworkTransport::WiFi: return "wifi";
    case AdamsNetworkTransport::AccessPoint: return "ap";
    default: return "none";
  }
}

int32_t networkWifiRssi() {
  return sWifiConnected ? WiFi.RSSI() : 0;
}

bool networkEthernetConnected() {
  return sEthernetConnected;
}

bool networkEthernetLinkUp() {
  return sEthernetLinkUp;
}
