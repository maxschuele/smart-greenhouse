#include "SciotNode.h"

#include <WiFi.h>
#include <pb_encode.h>
#include <pb_decode.h>

namespace sciot {

namespace {

constexpr uint32_t ADVERT_INTERVAL_MS = 30000;
constexpr size_t PAYLOAD_BUF = 256;

Node* self = nullptr;

void trampoline(char* topic, uint8_t* payload, unsigned int len) {
    if (self) self->handleMqtt(topic, payload, len);
}

}  // namespace

Node::Node(const char* node_id, const char* hw, const char* fw_version)
    : node_id_(node_id), hw_(hw), fw_version_(fw_version), mqtt_(tcp_) {
    self = this;
}

void Node::begin(const char* wifi_ssid, const char* wifi_pass,
                 const char* mqtt_host, uint16_t mqtt_port) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(wifi_ssid, wifi_pass);
    while (WiFi.status() != WL_CONNECTED) delay(200);
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

void Node::onCommand(CommandHandler handler) { cmd_handler_ = handler; }

bool Node::publishTelemetry(const sciot_Telemetry& msg) {
    uint8_t buf[PAYLOAD_BUF];
    pb_ostream_t stream = pb_ostream_from_buffer(buf, sizeof(buf));
    if (!pb_encode(&stream, sciot_Telemetry_fields, &msg)) return false;
    char topic[64];
    snprintf(topic, sizeof(topic), "nodes/%s/telemetry", node_id_);
    return mqtt_.publish(topic, buf, stream.bytes_written);
}

void Node::ensureConnected() {
    if (mqtt_.connected()) return;
    if (!mqtt_.connect(node_id_)) {
        delay(1000);
        return;
    }
    char topic[64];
    snprintf(topic, sizeof(topic), "nodes/%s/command", node_id_);
    mqtt_.subscribe(topic);
    publishAdvert();
    last_advert_ms_ = millis();
}

void Node::publishAdvert() {
    sciot_NodeAdvert msg = sciot_NodeAdvert_init_zero;
    strncpy(msg.node_id, node_id_, sizeof(msg.node_id) - 1);
    strncpy(msg.hw, hw_, sizeof(msg.hw) - 1);
    strncpy(msg.fw_version, fw_version_, sizeof(msg.fw_version) - 1);

    uint8_t buf[PAYLOAD_BUF];
    pb_ostream_t stream = pb_ostream_from_buffer(buf, sizeof(buf));
    if (!pb_encode(&stream, sciot_NodeAdvert_fields, &msg)) return;

    char topic[64];
    snprintf(topic, sizeof(topic), "nodes/%s/advert", node_id_);
    mqtt_.publish(topic, buf, stream.bytes_written);
}

void Node::handleMqtt(char* /*topic*/, uint8_t* payload, unsigned int len) {
    if (!cmd_handler_) return;
    sciot_Command cmd = sciot_Command_init_zero;
    pb_istream_t stream = pb_istream_from_buffer(payload, len);
    if (pb_decode(&stream, sciot_Command_fields, &cmd)) {
        cmd_handler_(cmd);
    }
}

}  // namespace sciot
