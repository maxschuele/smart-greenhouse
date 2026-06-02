#include <Arduino.h>

#include "SghNode.h"
#include "config.h"

namespace {
sgh::Node node(NODE_ID, "xiao-esp32c3", "0.1.0");

void onCommand(const sgh_Command &cmd) {
    (void)cmd; // dispatch on cmd.actuator_id, act on cmd.value
}

int i = 0;
const int led = D10;
} // namespace

void setup() {
    Serial.begin(115200);
    node.onCommand(onCommand);
    node.begin(WIFI_SSID, WIFI_PASS, MQTT_HOST);

    pinMode(led, OUTPUT);
    digitalWrite(led, HIGH); // turn the LED on

    Serial.printf("%s finished setup\n", NODE_ID);
}

void loop() {
    Serial.printf("Starting loop iteration %d\n", i);
    i++;
    node.loop();

    sgh_Telemetry msg = sgh_Telemetry_init_zero;
    strncpy(msg.node_id, NODE_ID, sizeof(msg.node_id) - 1);
    msg.timestamp_ms = millis();

    // No real sensors on this example node yet; report node vitals as demo
    // readings. Each reading is a oneof: set which_value to the field tag,
    // then the matching union member.
    msg.readings_count = 3;

    strncpy(msg.readings[0].sensor_id, "uptime_s",
            sizeof(msg.readings[0].sensor_id) - 1);
    msg.readings[0].which_value = sgh_Reading_number_tag;
    msg.readings[0].value.number = millis() / 1000.0;

    strncpy(msg.readings[1].sensor_id, "loop_count",
            sizeof(msg.readings[1].sensor_id) - 1);
    msg.readings[1].which_value = sgh_Reading_number_tag;
    msg.readings[1].value.number = i;

    strncpy(msg.readings[2].sensor_id, "led",
            sizeof(msg.readings[2].sensor_id) - 1);
    msg.readings[2].which_value = sgh_Reading_boolean_tag;
    msg.readings[2].value.boolean = digitalRead(led) == HIGH;

    bool success = node.publishTelemetry(msg);
    Serial.println(success ? "published telemetry message"
                           : "failed to publish telemetry message");

    delay(5000);
}
