import asyncio
import json
import logging
import os

import aiomqtt
from google.protobuf.json_format import MessageToDict

from hub import bus, db
from hub.proto import telemetry_pb2

log = logging.getLogger(__name__)

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

# Nodes publish protobuf-encoded payloads on nodes/<id>/<kind>. The trailing
# topic segment selects which message type to decode. Other topics (demo/#)
# carry plain text.
_PROTO_BY_KIND = {
    "telemetry": telemetry_pb2.Telemetry,
    "advert": telemetry_pb2.NodeAdvert,
}


def _decode(topic: str, payload: bytes) -> str:
    """Turn a raw MQTT payload into the text stored in the messages log.

    Protobuf node topics are decoded to JSON so the existing latest-per-topic
    query, /api/messages, and WebSocket fan-out keep working unchanged. Any
    other topic is treated as a UTF-8 string.
    """
    msg_cls = _PROTO_BY_KIND.get(topic.rsplit("/", 1)[-1])
    if msg_cls is None:
        return payload.decode()
    msg = msg_cls()
    msg.ParseFromString(payload)
    return json.dumps(MessageToDict(msg, preserving_proto_field_name=True))


async def _publisher(client: aiomqtt.Client) -> None:
    counter = 0
    while True:
        await client.publish("demo/heartbeat", payload=f"hello {counter}")
        counter += 1
        await asyncio.sleep(5)


async def _subscriber(client: aiomqtt.Client) -> None:
    await client.subscribe("demo/#")
    await client.subscribe("nodes/+/telemetry")
    await client.subscribe("nodes/+/advert")
    async for msg in client.messages:
        topic = str(msg.topic)
        try:
            payload = _decode(topic, bytes(msg.payload))
        except Exception:
            log.warning("drop undecodable msg on %s (%d bytes)", topic, len(msg.payload))
            continue
        await db.insert_message(topic, payload)
        bus.publish({"topic": topic, "payload": payload})
        log.info("recv %s: %s", topic, payload)


async def run() -> None:
    async with aiomqtt.Client(hostname=MQTT_HOST, port=MQTT_PORT) as client:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_subscriber(client))
            tg.create_task(_publisher(client))
