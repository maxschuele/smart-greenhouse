#pragma once

#include <Arduino.h>
#include <PubSubClient.h>
#include <WiFiClient.h>

#include "telemetry.pb.h"
#include "command.pb.h"

namespace sciot {

using CommandHandler = void (*)(const sciot_Command& cmd);

class Node {
  public:
    Node(const char* node_id, const char* hw, const char* fw_version);

    void begin(const char* wifi_ssid, const char* wifi_pass,
               const char* mqtt_host, uint16_t mqtt_port = 1883);
    void loop();

    void onCommand(CommandHandler handler);
    bool publishTelemetry(const sciot_Telemetry& msg);
    void handleMqtt(char* topic, uint8_t* payload, unsigned int len);

  private:
    void ensureConnected();
    void publishAdvert();

    const char* node_id_;
    const char* hw_;
    const char* fw_version_;
    WiFiClient tcp_;
    PubSubClient mqtt_;
    CommandHandler cmd_handler_ = nullptr;
    uint32_t last_advert_ms_ = 0;
};

}  // namespace sciot
