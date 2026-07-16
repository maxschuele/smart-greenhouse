#include "SghNode.h"

#include <Preferences.h>
#include <WiFi.h>
#include <pb_decode.h>
#include <pb_encode.h>
namespace sgh {

namespace {

constexpr uint32_t ADVERT_INTERVAL_MS = 30000;

// PubSubClient's packet buffer must hold the MQTT header, the topic and the
// payload; its 256-byte default cannot fit an advert with a full capability
// list, so size it from the nanopb worst-case payload sizes plus headroom.
constexpr uint16_t MQTT_BUF =
    (sgh_NodeAdvert_size > sgh_Telemetry_size ? sgh_NodeAdvert_size
                                              : sgh_Telemetry_size) +
    64;

Node *self = nullptr;

void trampoline(char *topic, uint8_t *payload, unsigned int len) {
    if (self != nullptr)
        self->handleMqtt(topic, payload, len);
}

} // namespace

Node::Node(const char *node_id, const char *hw, const char *fw_version) noexcept
    : node_id_(node_id),
      mqtt_(tcp_) {
    const sgh_NodeAdvert zero = sgh_NodeAdvert_init_zero;
    advert_ = zero;
    strncpy(advert_.node_id, node_id, sizeof(advert_.node_id) - 1);
    strncpy(advert_.hw, hw, sizeof(advert_.hw) - 1);
    strncpy(advert_.fw_version, fw_version, sizeof(advert_.fw_version) - 1);
    self = this;
}

bool Node::addSensor(const char *sensor_id, const char *kind,
                     const char *unit) {
    constexpr size_t max =
        sizeof(advert_.sensors) / sizeof(advert_.sensors[0]);
    if (advert_.sensors_count >= max)
        return false;
    sgh_SensorCap &cap = advert_.sensors[advert_.sensors_count++];
    strncpy(cap.sensor_id, sensor_id, sizeof(cap.sensor_id) - 1);
    strncpy(cap.kind, kind, sizeof(cap.kind) - 1);
    strncpy(cap.unit, unit, sizeof(cap.unit) - 1);
    return true;
}

bool Node::addActuator(const char *actuator_id, const char *kind) {
    constexpr size_t max =
        sizeof(advert_.actuators) / sizeof(advert_.actuators[0]);
    if (advert_.actuators_count >= max)
        return false;
    sgh_ActuatorCap &cap = advert_.actuators[advert_.actuators_count++];
    strncpy(cap.actuator_id, actuator_id, sizeof(cap.actuator_id) - 1);
    strncpy(cap.kind, kind, sizeof(cap.kind) - 1);
    return true;
}

void Node::begin(const char *wifi_ssid, const char *wifi_pass,
                 const char *mqtt_host, uint16_t mqtt_port) {
    WiFi.mode(WIFI_STA);
    WiFi.onEvent(
        [](WiFiEvent_t /*event*/, WiFiEventInfo_t info) {
            Serial.printf("WiFi: disconnect reason=%d\n",
                          info.wifi_sta_disconnected.reason);
        },
        ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
    Serial.printf("WiFi: connecting to '%s'\n", wifi_ssid);
    WiFi.begin(wifi_ssid, wifi_pass);
    while (WiFi.status() != WL_CONNECTED) {
        Serial.printf("WiFi: status=%d\n", WiFi.status());
        delay(200);
    }
    Serial.printf("WiFi: connected, ip=%s\n",
                  WiFi.localIP().toString().c_str());
    if (!mqtt_.setBufferSize(MQTT_BUF))
        Serial.printf("MQTT: failed to allocate %u-byte buffer\n", MQTT_BUF);
    mqtt_.setServer(mqtt_host, mqtt_port);
    mqtt_.setCallback(trampoline);
}

void Node::loop() {
    ensureConnected();
    mqtt_.loop();
    if (millis() - last_advert_ms_ > ADVERT_INTERVAL_MS) {
        publishAdvert();
        last_advert_ms_ = millis();
    }
}

void Node::onCommand(CommandHandler handler) {
    cmd_handler_ = handler;
}

bool Node::publishTelemetry(const sgh_Telemetry &msg) {
    uint8_t buf[sgh_Telemetry_size];
    pb_ostream_t stream = pb_ostream_from_buffer(buf, sizeof(buf));
    if (!pb_encode(&stream, sgh_Telemetry_fields, &msg))
        return false;
    char topic[64];
    snprintf(topic, sizeof(topic), "nodes/%s/telemetry", node_id_);
    return mqtt_.publish(topic, buf, stream.bytes_written);
}

void Node::ensureConnected() {
    if (mqtt_.connected())
        return;

    Serial.printf("MQTT: connecting as '%s'\n", node_id_);
    if (!mqtt_.connect(node_id_)) {
        Serial.printf("MQTT: connect failed, state=%d\n", mqtt_.state());
        delay(1000);
        return;
    }

    Serial.println("MQTT: connected");
    char topic[64];
    snprintf(topic, sizeof(topic), "nodes/%s/command", node_id_);
    mqtt_.subscribe(topic);
    publishAdvert();
    last_advert_ms_ = millis();
}

void Node::publishAdvert() {
    uint8_t buf[sgh_NodeAdvert_size];
    pb_ostream_t stream = pb_ostream_from_buffer(buf, sizeof(buf));
    if (!pb_encode(&stream, sgh_NodeAdvert_fields, &advert_))
        return;

    char topic[64];
    snprintf(topic, sizeof(topic), "nodes/%s/advert", node_id_);
    mqtt_.publish(topic, buf, stream.bytes_written);
}

void Node::handleMqtt(char * /*topic*/, uint8_t *payload, unsigned int len) {
    if (cmd_handler_ == nullptr)
        return;
    sgh_Command cmd = sgh_Command_init_zero;
    pb_istream_t stream = pb_istream_from_buffer(payload, len);
    if (pb_decode(&stream, sgh_Command_fields, &cmd)) {
        cmd_handler_(cmd);
    }
}

} // namespace sgh
