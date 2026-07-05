import asyncio
import json
import logging
import os
import time

import aiomqtt
from google.protobuf.json_format import MessageToDict

from hub import bus, db, registry
from hub.proto import command_pb2, telemetry_pb2

log = logging.getLogger(__name__)

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

# Set by run() while the client connection is alive; send_command needs it.
_client: aiomqtt.Client | None = None

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


async def send_command(node_id: str, actuator_id: str, value: bool | float | str) -> None:
    """Publish a protobuf Command to nodes/<node_id>/command.

    The oneof field is picked from the Python type of value: bool -> boolean,
    int/float -> number, str -> text.
    """
    if _client is None:
        raise RuntimeError("MQTT client not connected")
    cmd = command_pb2.Command(actuator_id=actuator_id)
    if isinstance(value, bool):
        cmd.boolean = value
    elif isinstance(value, int | float):
        cmd.number = value
    else:
        cmd.text = value
    await _client.publish(f"nodes/{node_id}/command", payload=cmd.SerializeToString())
    log.info("sent command to %s: %s = %r", node_id, actuator_id, value)


async def _publisher(client: aiomqtt.Client) -> None:
    counter = 0
    while True:
        await client.publish("demo/heartbeat", payload=f"hello {counter}")
        counter += 1
        await asyncio.sleep(5)


async def _rehydrate(client: aiomqtt.Client) -> None:
    """Seed the registry from the latest persisted adverts on startup.

    Without this a hub restart would wait up to 30 s (the advert period) before
    re-discovering nodes and re-subscribing to their telemetry.
    """
    for topic, row in (await db.latest_per_topic()).items():
        parts = topic.split("/")
        if len(parts) != 3 or parts[0] != "nodes" or parts[2] != "advert":
            continue
        try:
            advert = json.loads(row["payload"])
        except ValueError:
            continue
        registry.upsert_advert(parts[1], advert, last_seen=row["ts"])
        await client.subscribe(f"nodes/{parts[1]}/telemetry")
        log.info("rehydrated node %s from db", parts[1])


async def _discover(client: aiomqtt.Client, node_id: str, payload: str) -> None:
    """Register a node from its advert; first sighting subscribes its telemetry."""
    try:
        advert = json.loads(payload)
    except ValueError:
        return
    if registry.upsert_advert(node_id, advert):
        await client.subscribe(f"nodes/{node_id}/telemetry")
        log.info("discovered node %s: %s", node_id, payload)


async def _subscriber(client: aiomqtt.Client) -> None:
    # Telemetry topics are subscribed per node once its advert is seen; only
    # adverts (and the plain-text demo topics) use standing subscriptions.
    await client.subscribe("demo/#")
    await client.subscribe("nodes/+/advert")
    await _rehydrate(client)
    async for msg in client.messages:
        topic = str(msg.topic)
        try:
            payload = _decode(topic, bytes(msg.payload))
        except Exception:
            log.warning("drop undecodable msg on %s (%d bytes)", topic, len(msg.payload))
            continue
        await db.insert_message(topic, payload)
        bus.publish({"topic": topic, "payload": payload, "ts": time.time()})
        parts = topic.split("/")
        if len(parts) == 3 and parts[0] == "nodes":
            if parts[2] == "advert":
                await _discover(client, parts[1], payload)
            elif parts[2] == "telemetry":
                registry.touch(parts[1])
        log.info("recv %s: %s", topic, payload)


async def run() -> None:
    global _client
    async with aiomqtt.Client(hostname=MQTT_HOST, port=MQTT_PORT) as client:
        _client = client
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(_subscriber(client))
                tg.create_task(_publisher(client))
        finally:
            _client = None
