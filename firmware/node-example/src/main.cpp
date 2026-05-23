#include <Arduino.h>

#include "SciotNode.h"

static sciot::Node node(NODE_ID, "xiao-esp32c3", "0.1.0");

static void onCommand(const sciot_Command &cmd) {
    (void)cmd; // dispatch on cmd.actuator_id, act on cmd.value
}

void setup() {
    Serial.begin(115200);
    node.onCommand(onCommand);
    node.begin(WIFI_SSID, WIFI_PASS, MQTT_HOST);
    Serial.printf("%s finished setup", NODE_ID);
}

void loop() {
    node.loop();

    sciot_Telemetry msg = sciot_Telemetry_init_zero;
    // fill msg.node_id, msg.timestamp_ms, msg.readings[]
    node.publishTelemetry(msg);
    delay(5000);
}
