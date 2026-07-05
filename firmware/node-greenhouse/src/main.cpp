#include <Arduino.h>

#include <cmath>
#include <cstdint>

#include "DHT.h"

#include "SghNode.h"
#include "config.h"

// DHT11 temperature/humidity, DATA on D0 (GPIO2).
#define DHT_PIN D0
#define DHTTYPE DHT11

// MQ-135 air quality, AO on A1 (D1 / GPIO3). Wired through a 2:1 divider from a
// 5 V supply, so the analog helpers below scale the pin voltage back up. CO2
// curve and calibration constants come from the datasheet-fitted example sketch
// (mq135_dht11_xiao_esp32c3.ino).
#define MQ135_PIN A1
const float SUPPLY_VOLTAGE = 5.0F;
const float DIVIDER_RATIO = 2.0F; // two equal resistors halve the voltage
const float RL_KOHM = 10.0F;
const float CLEAN_AIR_RATIO = 3.6F;
const float CURVE_A = 116.6020682F;  // ppm = A * (Rs/R0)^B
const float CURVE_B = -2.769034857F;
const float R0_CLEAN_AIR = 76.63F;   // kOhm, replace with a calibrated value

// Relays, active-low modules (driving the pin LOW energizes the relay), same as
// the plant node's pump. LED on D6, fan on D5.
#define LED_PIN D6
#define FAN_PIN D5
#define RELAY_ON LOW
#define RELAY_OFF HIGH

// HC-SR04 ultrasonic distance: TRIG on D7, ECHO on D8.
#define TRIG_PIN D7
#define ECHO_PIN D8
#define ECHO_TIMEOUT_US 30000UL // ~5 m round trip; returns 0 on no echo

namespace {
sgh::Node node(NODE_ID, "xiao-esp32c3", "0.1.0");
DHT dht(DHT_PIN, DHTTYPE);

// Average MQ-135 pin voltage over many samples, scaled back through the divider.
float readSensorVoltage() {
    uint32_t sum = 0;
    const int samples = 64;
    for (int i = 0; i < samples; i++) {
        sum += analogReadMilliVolts(MQ135_PIN);
        delay(2);
    }
    float pinVolts = (sum / (float)samples) / 1000.0F;
    return pinVolts * DIVIDER_RATIO;
}

float readRs() {
    float vOut = readSensorVoltage();
    if (vOut < 0.05F)
        vOut = 0.05F;
    return RL_KOHM * (SUPPLY_VOLTAGE - vOut) / vOut;
}

float readCO2ppm() {
    float ratio = readRs() / R0_CLEAN_AIR;
    return CURVE_A * pow(ratio, CURVE_B);
}

// HC-SR04: 10 us trigger pulse, then measure the echo high time. Speed of sound
// gives cm = duration_us / 58. Returns NAN on timeout (no echo).
float readDistanceCm() {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    unsigned long duration = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
    if (duration == 0)
        return NAN;
    return duration / 58.0F;
}

// Set by onCommand so the next loop() publishes telemetry immediately,
// confirming the new actuator state without waiting out the 5 s period.
bool pubNow = false;

void onCommand(const sgh_Command &cmd) {
    if (strcmp(cmd.actuator_id, "led") == 0 &&
        cmd.which_value == sgh_Command_boolean_tag) {
        digitalWrite(LED_PIN, cmd.value.boolean ? RELAY_ON : RELAY_OFF);
        Serial.printf("led -> %s\n", cmd.value.boolean ? "on" : "off");
        pubNow = true;
    } else if (strcmp(cmd.actuator_id, "fan") == 0 &&
               cmd.which_value == sgh_Command_boolean_tag) {
        digitalWrite(FAN_PIN, cmd.value.boolean ? RELAY_ON : RELAY_OFF);
        Serial.printf("fan -> %s\n", cmd.value.boolean ? "on" : "off");
        pubNow = true;
    } else {
        Serial.printf("ignoring command for actuator '%s'\n", cmd.actuator_id);
    }
}

// Append a number reading only when the value is finite, keeping readings_count
// in step so failed sensor reads are simply omitted from the batch.
void addNumber(sgh_Telemetry &msg, const char *sensor_id, float value) {
    if (isnan(value))
        return;
    sgh_Reading &r = msg.readings[msg.readings_count++];
    strncpy(r.sensor_id, sensor_id, sizeof(r.sensor_id) - 1);
    r.which_value = sgh_Reading_number_tag;
    r.value.number = value;
}

void addBoolean(sgh_Telemetry &msg, const char *sensor_id, bool value) {
    sgh_Reading &r = msg.readings[msg.readings_count++];
    strncpy(r.sensor_id, sensor_id, sizeof(r.sensor_id) - 1);
    r.which_value = sgh_Reading_boolean_tag;
    r.value.boolean = value;
}

uint64_t lastPub = 0;
} // namespace

void setup() {
    Serial.begin(115200);
    Serial.printf("%s starting setup\n", NODE_ID);

    node.addSensor("temperature", "temperature", "C");
    node.addSensor("humidity", "humidity", "%");
    node.addSensor("co2_ppm", "gas", "ppm");
    node.addSensor("distance_cm", "distance", "cm");
    node.addActuator("led", "relay");
    node.addActuator("fan", "relay");

    node.onCommand(onCommand);
    node.begin(WIFI_SSID, WIFI_PASS, MQTT_HOST);

    dht.begin();
    analogSetPinAttenuation(MQ135_PIN, ADC_11db);

    // Drive relays off before enabling the pins so they do not glitch on at boot.
    digitalWrite(LED_PIN, RELAY_OFF);
    digitalWrite(FAN_PIN, RELAY_OFF);
    pinMode(LED_PIN, OUTPUT);
    pinMode(FAN_PIN, OUTPUT);

    pinMode(TRIG_PIN, OUTPUT);
    digitalWrite(TRIG_PIN, LOW);
    pinMode(ECHO_PIN, INPUT);

    Serial.printf("%s finished setup\n", NODE_ID);
}

void loop() {
    node.loop();

    uint64_t now = millis();
    if (pubNow || now - lastPub > 5000) {
        pubNow = false;
        lastPub = now;

        sgh_Telemetry msg = sgh_Telemetry_init_zero;
        strncpy(msg.node_id, NODE_ID, sizeof(msg.node_id) - 1);
        msg.timestamp_ms = now;

        addNumber(msg, "temperature", dht.readTemperature());
        addNumber(msg, "humidity", dht.readHumidity());
        addNumber(msg, "co2_ppm", readCO2ppm());
        addNumber(msg, "distance_cm", readDistanceCm());
        addBoolean(msg, "led", digitalRead(LED_PIN) == RELAY_ON);
        addBoolean(msg, "fan", digitalRead(FAN_PIN) == RELAY_ON);

        bool success = node.publishTelemetry(msg);
        Serial.println(success ? "published telemetry message"
                               : "failed to publish telemetry message");
    }
}
