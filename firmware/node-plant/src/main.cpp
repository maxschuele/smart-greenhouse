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
#define SOIL_PIN A1
#define SOIL_ADC_DRY 4095
#define SOIL_ADC_WET 1800

// Relay driving the water pump, IN wired to D2 (GPIO4). The module is
// active-low: driving IN low energizes the relay.
#define PUMP_PIN D2
#define PUMP_ON LOW
#define PUMP_OFF HIGH

// The pump runs in fixed-length doses: a pump=true command starts a dose and
// the firmware stops it after PUMP_RUN_MS on its own, so a lost "off" command
// or a dead hub can never leave the pump running.
#define PUMP_RUN_MS 2000

namespace {
sgh::Node node(NODE_ID, "xiao-esp32c3", "0.1.0");

// Set by onCommand so the next loop() publishes telemetry immediately,
// confirming the new actuator state without waiting out the 5 s period.
bool pubNow = false;

unsigned long pumpStartedAt = 0;

// Average the soil ADC over a short burst: the probe's physical signal cannot
// change between samples, so the spread across them is pure ADC noise.
int readSoilRaw() {
    uint32_t sum = 0;
    const int samples = 32;
    for (int i = 0; i < samples; i++) {
        sum += analogRead(SOIL_PIN);
        delay(2);
    }
    return sum / samples;
}

void onCommand(const sgh_Command &cmd) {
    if (strcmp(cmd.actuator_id, "pump") == 0 &&
        cmd.which_value == sgh_Command_boolean_tag) {
        digitalWrite(PUMP_PIN, cmd.value.boolean ? PUMP_ON : PUMP_OFF);
        if (cmd.value.boolean) {
            pumpStartedAt = millis();
        }
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

    if (digitalRead(PUMP_PIN) == PUMP_ON &&
        millis() - pumpStartedAt >= PUMP_RUN_MS) {
        digitalWrite(PUMP_PIN, PUMP_OFF);
        Serial.println("pump -> off (dose complete)");
        pubNow = true;
    }

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
        int raw = readSoilRaw();
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
