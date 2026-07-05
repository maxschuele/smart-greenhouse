#pragma once

#include <Arduino.h>

#include <PubSubClient.h>
#include <WiFiClient.h>

#include "command.pb.h"
#include "telemetry.pb.h"

namespace sgh {

using CommandHandler = void (*)(const sgh_Command &cmd);

class Node {
public:
    Node(const char *node_id, const char *hw, const char *fw_version) noexcept;

    void begin(const char *wifi_ssid, const char *wifi_pass,
               const char *mqtt_host, uint16_t mqtt_port = 1883);
    void loop();

    void onCommand(CommandHandler handler);
    bool publishTelemetry(const sgh_Telemetry &msg);
    void handleMqtt(char *topic, uint8_t *payload, unsigned int len);

    // Register capabilities during setup(), before begin(), so the first
    // advert already carries them. Return false when the fixed-size advert
    // arrays (see telemetry.options) are full.
    bool addSensor(const char *sensor_id, const char *kind, const char *unit);
    bool addActuator(const char *actuator_id, const char *kind);

private:
    void ensureConnected();
    void publishAdvert();

    const char *node_id_;
    WiFiClient tcp_;
    PubSubClient mqtt_;
    CommandHandler cmd_handler_ = nullptr;
    uint32_t last_advert_ms_ = 0;
    sgh_NodeAdvert advert_;
};

} // namespace sgh
