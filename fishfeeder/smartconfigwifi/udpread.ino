bool autoConfig()
{
  WiFi.mode(WIFI_STA);
  WiFi.hostname(newHostname.c_str());
  WiFi.begin();
  for (size_t i = 0; i < 20; i++)
  {
    int wifiStatus = WiFi.status();
    if (wifiStatus == WL_CONNECTED)
    {
      Serial.println("自动连接成功!");
      return 1;
    }
    else
    {
      delay(1000);
      Serial.println("等待自动配网中...");
    }
  }
  Serial.println("无法自动配网!");
  return 0;
}
void smartConfig()
{
  WiFi.mode(WIFI_STA); //设置WIFI模块为STA模式
  WiFi.hostname(newHostname.c_str());
  Serial.println("\r\nWaiting for connection");
  //smartconfig进行初始化
  WiFi.beginSmartConfig();
  while (1) //等待连接成功
  {
    Serial.print(">");
    digitalWrite(LED_BUILTIN, 0);
    delay(100);
    digitalWrite(LED_BUILTIN, 1);
    delay(100);
    //如果连接成功后就打印出连接的WIFI信息
    if (WiFi.smartConfigDone())
    {
      Serial.println("SmartConfig Success");
      Serial.printf("SSID:%s", WiFi.SSID().c_str());
      Serial.printf("PW:%s", WiFi.psk().c_str());//打印出密码
      Serial.println("");
      WiFi.setAutoConnect(true);
      delay(10000);
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
      break;
    }
  }

}

void udpRcv()
{
  packetSizeRcv = udp.parsePacket();
  if (packetSizeRcv == 3)
  {
    udp.read(buf, packetSizeRcv);
    if (buf[0] == verify[0] && buf[1] == verify[1])
    {
      ledcur1 = buf[2];
      Serial.print("rcv: ");
      Serial.println(ledcur1);
    }
    udp.beginPacket(udp.remoteIP(), udp.remotePort());
    udp.write((const uint8_t*)buf, packetSizeRcv);
    udp.endPacket();
  }
}
