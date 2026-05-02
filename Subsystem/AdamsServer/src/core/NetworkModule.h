#pragma once

#include <Arduino.h>

bool initNetwork();
void serviceNetwork();
bool networkIsConnected();
IPAddress networkIp();
const char *networkTransportName();
int32_t networkWifiRssi();
bool networkEthernetConnected();
bool networkEthernetLinkUp();
