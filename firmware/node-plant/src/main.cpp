#include <Arduino.h>

#include <sys/unistd.h>

#include "SghNode.h"
#include "config.h"

namespace {
sgh::Node node(NODE_ID, "xiao-esp32c3", "0.1.0");

void onCommand(const sgh_Command &cmd) {
    if (strcmp(cmd.actuator_id, "pump") == 0 &&
        cmd.which_value == sgh_Command_boolean_tag) {
        digitalWrite(PUMP_PIN, cmd.value.boolean ? PUMP_ON : PUMP_OFF);
        Serial.printf("pump -> %s\n", cmd.value.boolean ? "on" : "off");
    } else {
        Serial.printf("ignoring command for actuator '%s'\n", cmd.actuator_id);
    }
}

int i = 0;
} // namespace

void setup() {
    Serial.begin(115200);
    node.onCommand(onCommand);
    node.begin(WIFI_SSID, WIFI_PASS, MQTT_HOST);

    digitalWrite(PUMP_PIN, PUMP_OFF); // set level before OUTPUT to avoid a
    pinMode(PUMP_PIN, OUTPUT);        // low glitch that pulses the relay on

    Serial.printf("%s finished setup\n", NODE_ID);
}

void loop() {
    Serial.printf("Starting loop iteration %d\n", i);
    i++;
    node.loop();

    sgh_Telemetry msg = sgh_Telemetry_init_zero;
    strncpy(msg.node_id, NODE_ID, sizeof(msg.node_id) - 1);
    msg.timestamp_ms = millis();

    // Soil moisture: raw ADC value plus percentage mapped between the
    // dry/wet calibration points from config.h. Capacitive sensor reads
    // lower voltage when wet, hence the inverted mapping.
    int raw = analogRead(SOIL_PIN);
    float moisture =
        100.0F * (SOIL_ADC_DRY - raw) / (SOIL_ADC_DRY - SOIL_ADC_WET);
    moisture = constrain(moisture, 0.0F, 100.0F);

    msg.readings_count = 3;

    strncpy(msg.readings[0].sensor_id, "soil_moisture",
            sizeof(msg.readings[0].sensor_id) - 1);
    msg.readings[0].which_value = sgh_Reading_number_tag;
    msg.readings[0].value.number = moisture;

    strncpy(msg.readings[1].sensor_id, "soil_raw",
            sizeof(msg.readings[1].sensor_id) - 1);
    msg.readings[1].which_value = sgh_Reading_number_tag;
    msg.readings[1].value.number = raw;

    strncpy(msg.readings[2].sensor_id, "pump",
            sizeof(msg.readings[2].sensor_id) - 1);
    msg.readings[2].which_value = sgh_Reading_boolean_tag;
    msg.readings[2].value.boolean = digitalRead(PUMP_PIN) == PUMP_ON;

    bool success = node.publishTelemetry(msg);
    Serial.println(success ? "published telemetry message"
                           : "failed to publish telemetry message");

    delay(5000);
}
