#include <Arduino.h>

#include <sys/unistd.h>

#include <cstdint>

#include "SghNode.h"
#include "config.h"
#include "esp32-hal.h"

// Capacitive soil moisture sensor v1.2, AOUT wired to A1 (GPIO3 / D1).
// Not A0/GPIO2: that is an ESP32-C3 strapping pin, and the sensor holding it
// low at reset forces the chip into USB download mode instead of booting.
// Raw 12-bit readings for calibration: sensor in dry air / submerged in water.
#define SOIL_PIN A0
#define SOIL_ADC_DRY 3000
#define SOIL_ADC_WET 1400

// Relay driving the water pump, IN wired to D2 (GPIO4). The module is
// active-low: driving IN low energizes the relay.
#define PUMP_PIN D1
#define PUMP_ON LOW
#define PUMP_OFF HIGH

namespace {
sgh::Node node(NODE_ID, "xiao-esp32c3", "0.1.0");

// Set by onCommand so the next loop() publishes telemetry immediately,
// confirming the new actuator state without waiting out the 5 s period.
bool pubNow = false;

void onCommand(const sgh_Command &cmd) {
    if (strcmp(cmd.actuator_id, "pump") == 0 &&
        cmd.which_value == sgh_Command_boolean_tag) {
        digitalWrite(PUMP_PIN, cmd.value.boolean ? PUMP_ON : PUMP_OFF);
        Serial.printf("pump -> %s\n", cmd.value.boolean ? "on" : "off");
        pubNow = true;
    } else {
        Serial.printf("ignoring command for actuator '%s'\n", cmd.actuator_id);
    }
}

uint64_t lastPub = 0;
} // namespace

void setup() {
    Serial.begin(115200);
    Serial.printf("%s starting setup\n", NODE_ID);

    node.addSensor("soil_moisture", "soil_moisture", "%");
    node.addSensor("soil_raw", "soil_moisture_raw", "raw");
    node.addActuator("pump", "relay");

    node.onCommand(onCommand);
    node.begin(WIFI_SSID, WIFI_PASS, MQTT_HOST);

    digitalWrite(PUMP_PIN, PUMP_OFF);
    pinMode(PUMP_PIN, OUTPUT);

    Serial.printf("%s finished setup\n", NODE_ID);
}

void loop() {
    node.loop();

    unsigned long now = millis();
    if (pubNow || now - lastPub > 5000) {
        pubNow = false;
        lastPub = now;

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
    }
}
