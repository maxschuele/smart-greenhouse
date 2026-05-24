import asyncio
import logging
import os

import aiomqtt

from hub import bus, db

log = logging.getLogger(__name__)

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))


async def _publisher(client: aiomqtt.Client) -> None:
    counter = 0
    while True:
        await client.publish("demo/heartbeat", payload=f"hello {counter}")
        counter += 1
        await asyncio.sleep(5)


async def _subscriber(client: aiomqtt.Client) -> None:
    await client.subscribe("demo/#")
    async for msg in client.messages:
        topic = str(msg.topic)
        payload = msg.payload.decode()
        await db.insert_message(topic, payload)
        bus.publish({"topic": topic, "payload": payload})
        log.info("recv %s: %s", topic, payload)


async def run() -> None:
    async with aiomqtt.Client(hostname=MQTT_HOST, port=MQTT_PORT) as client:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_subscriber(client))
            tg.create_task(_publisher(client))
