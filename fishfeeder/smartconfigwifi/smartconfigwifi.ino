#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
const int localPort = 3333;
WiFiUDP udp;
uint8_t verify[2] = {0xff, 0x01};
int packetSizeRcv;
char buf[3];
uint32_t now_ms = 0;

int ledcur1 = 0;
String newHostname = "ESP-Feeder01";
void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, 1);
  pinMode(0, OUTPUT);
  digitalWrite(0, 1);
  if (!autoConfig())
  {
    Serial.println("Start module");
    smartConfig();
  }
  else
  {
    Serial.println("wifi auto configed");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("ESP Mac Address: ");
    Serial.println(WiFi.macAddress());
    Serial.print("Subnet Mask: ");
    Serial.println(WiFi.subnetMask());
    Serial.print("Gateway IP: ");
    Serial.println(WiFi.gatewayIP());
    Serial.print("DNS: ");
    Serial.println(WiFi.dnsIP());
  }
  udp.begin(localPort);
  digitalWrite(LED_BUILTIN, HIGH);
}

void loop() {
  udpRcv();
  if (millis() - now_ms > 30)
  {
    now_ms = millis();
    per_003sec();
  }
}
