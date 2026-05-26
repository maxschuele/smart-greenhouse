#include <Arduino.h>

#include "SghNode.h"

static sgh::Node node(NODE_ID, "xiao-esp32c3", "0.1.0");

static void onCommand(const sgh_Command &cmd) {
    (void)cmd; // dispatch on cmd.actuator_id, act on cmd.value
}

int i = 0;

void setup() {
    Serial.begin(115200);
    node.onCommand(onCommand);
    node.begin(WIFI_SSID, WIFI_PASS, MQTT_HOST);
    Serial.printf("%s finished setup\n", NODE_ID);
}

void loop() {
    Serial.printf("Starting loop iteration %d\n", i);
    i++;
    node.loop();

    sgh_Telemetry msg = sgh_Telemetry_init_zero;
    // fill msg.node_id, msg.timestamp_ms, msg.readings[]
    bool success = node.publishTelemetry(msg);
    Serial.println(success ? "published telemetry message"
                           : "failed to publish telemetry message");

    delay(5000);
}
