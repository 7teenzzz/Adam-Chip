#include <Arduino.h>
#include <ETH.h>
#include <SPI.h>
#include <WebServer.h>

#include "../../config/PinsConfig.h"

namespace {

constexpr int32_t kEthPhyAddr = 1;

IPAddress kLocalIp(192, 168, 50, 2);
IPAddress kGateway(192, 168, 50, 1);
IPAddress kSubnet(255, 255, 255, 0);
IPAddress kDns1(192, 168, 50, 1);
IPAddress kDns2(1, 1, 1, 1);

WebServer server(80);
bool ethConnected = false;
uint32_t lastHeartbeatAt = 0;

void onEvent(arduino_event_id_t event, arduino_event_info_t info) {
  switch (event) {
    case ARDUINO_EVENT_ETH_START:
      Serial.println("event: ETH_START");
      ETH.setHostname("w5500-diag");
      break;
    case ARDUINO_EVENT_ETH_CONNECTED:
      Serial.println("event: ETH_CONNECTED");
      break;
    case ARDUINO_EVENT_ETH_GOT_IP:
      Serial.printf("event: ETH_GOT_IP desc=%s ip=%s\n",
                    esp_netif_get_desc(info.got_ip.esp_netif),
                    ETH.localIP().toString().c_str());
      ethConnected = true;
      break;
    case ARDUINO_EVENT_ETH_LOST_IP:
      Serial.println("event: ETH_LOST_IP");
      ethConnected = false;
      break;
    case ARDUINO_EVENT_ETH_DISCONNECTED:
      Serial.println("event: ETH_DISCONNECTED");
      ethConnected = false;
      break;
    case ARDUINO_EVENT_ETH_STOP:
      Serial.println("event: ETH_STOP");
      ethConnected = false;
      break;
    default:
      break;
  }
}

void handleRoot() {
  String body;
  body.reserve(192);
  body += "{";
  body += "\"ok\":true,";
  body += "\"link_up\":";
  body += ETH.linkUp() ? "true" : "false";
  body += ",";
  body += "\"connected\":";
  body += ETH.connected() ? "true" : "false";
  body += ",";
  body += "\"ip\":\"";
  body += ETH.localIP().toString();
  body += "\"";
  body += "}";
  server.send(200, "application/json", body);
}

}  // namespace

void setup() {
  Serial.begin(115200);
  const uint32_t serialWaitStartedAt = millis();
  while (!Serial && millis() - serialWaitStartedAt < 1500) {
    delay(10);
  }

  Serial.println();
  Serial.println("w5500-diag boot");
  Serial.printf("pins: sck=%d miso=%d mosi=%d cs=%d irq=%d rst=%d\n",
                ETH_SPI_SCK, ETH_SPI_MISO, ETH_SPI_MOSI, ETH_SPI_CS, ETH_INT, ETH_RST);

  Network.onEvent(onEvent);

  SPI.begin(ETH_SPI_SCK, ETH_SPI_MISO, ETH_SPI_MOSI);
  const bool beginOk = ETH.begin(ETH_PHY_W5500, kEthPhyAddr, ETH_SPI_CS, ETH_INT, ETH_RST, SPI);
  Serial.printf("ETH.begin -> %s\n", beginOk ? "ok" : "failed");

  const bool configOk = ETH.config(kLocalIp, kGateway, kSubnet, kDns1, kDns2);
  Serial.printf("ETH.config -> %s\n", configOk ? "ok" : "failed");

  server.on("/", handleRoot);
  server.begin();
  Serial.println("http server started");
}

void loop() {
  server.handleClient();

  const uint32_t now = millis();
  if (now - lastHeartbeatAt >= 2000) {
    lastHeartbeatAt = now;
    Serial.printf("heartbeat link=%s connected=%s ip=%s\n",
                  ETH.linkUp() ? "up" : "down",
                  ETH.connected() ? "up" : "down",
                  ETH.localIP().toString().c_str());
  }
}
