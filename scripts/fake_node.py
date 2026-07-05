"""Simulate an ESP32 node over MQTT for testing the hub without hardware.

Mirrors the firmware behaviour: publishes a capability NodeAdvert on connect
and every 30 s, protobuf Telemetry every 5 s, and listens on
nodes/<id>/command, flipping the simulated actuator and confirming the new
state with an immediate telemetry publish.

Usage: uv run python scripts/fake_node.py <node_id> <plant|greenhouse>
"""

import asyncio
import math
import random
import sys
import time

import aiomqtt

sys.path.insert(0, "src")
from hub.proto import command_pb2, telemetry_pb2  # noqa: E402

ADVERT_INTERVAL_S = 30
TELEMETRY_INTERVAL_S = 5

PROFILES = {
    "plant": {
        "sensors": [
            ("soil_moisture", "soil_moisture", "%"),
            ("soil_raw", "soil_moisture_raw", "raw"),
        ],
        "actuators": [("pump", "relay")],
    },
    "greenhouse": {
        "sensors": [
            ("temperature", "temperature", "C"),
            ("humidity", "humidity", "%"),
            ("co2_ppm", "gas", "ppm"),
            ("distance_cm", "distance", "cm"),
        ],
        "actuators": [("led", "relay"), ("fan", "relay")],
    },
}

BASE_VALUES = {
    "soil_moisture": 55.0,
    "soil_raw": 2100.0,
    "temperature": 24.0,
    "humidity": 60.0,
    "co2_ppm": 480.0,
    "distance_cm": 42.0,
}


def build_advert(node_id: str, profile: dict) -> bytes:
    msg = telemetry_pb2.NodeAdvert(node_id=node_id, hw="fake", fw_version="0.1.0")
    for sensor_id, kind, unit in profile["sensors"]:
        msg.sensors.add(sensor_id=sensor_id, kind=kind, unit=unit)
    for actuator_id, kind in profile["actuators"]:
        msg.actuators.add(actuator_id=actuator_id, kind=kind)
    return msg.SerializeToString()


def build_telemetry(node_id: str, profile: dict, actuators: dict[str, bool]) -> bytes:
    msg = telemetry_pb2.Telemetry(node_id=node_id, timestamp_ms=int(time.time() * 1000))
    wobble = math.sin(time.time() / 60)
    for sensor_id, _, _ in profile["sensors"]:
        base = BASE_VALUES[sensor_id]
        reading = msg.readings.add(sensor_id=sensor_id)
        reading.number = base * (1 + 0.05 * wobble) + random.uniform(-0.5, 0.5)
    for actuator_id, state in actuators.items():
        reading = msg.readings.add(sensor_id=actuator_id)
        reading.boolean = state
    return msg.SerializeToString()


async def main() -> None:
    node_id, profile_name = sys.argv[1], sys.argv[2]
    profile = PROFILES[profile_name]
    actuators = {actuator_id: False for actuator_id, _ in profile["actuators"]}
    pub_now = asyncio.Event()

    async with aiomqtt.Client(hostname="localhost", identifier=node_id) as client:
        await client.subscribe(f"nodes/{node_id}/command")
        print(f"{node_id} ({profile_name}) connected")

        async def handle_commands() -> None:
            async for msg in client.messages:
                cmd = command_pb2.Command()
                cmd.ParseFromString(bytes(msg.payload))
                if cmd.actuator_id in actuators and cmd.WhichOneof("value") == "boolean":
                    actuators[cmd.actuator_id] = cmd.boolean
                    print(f"{node_id}: {cmd.actuator_id} -> {cmd.boolean}")
                    pub_now.set()
                else:
                    print(f"{node_id}: ignoring command for {cmd.actuator_id!r}")

        async def publish_loop() -> None:
            last_advert = 0.0
            while True:
                now = time.time()
                if now - last_advert > ADVERT_INTERVAL_S or last_advert == 0.0:
                    await client.publish(f"nodes/{node_id}/advert", build_advert(node_id, profile))
                    last_advert = now
                await client.publish(
                    f"nodes/{node_id}/telemetry", build_telemetry(node_id, profile, actuators)
                )
                pub_now.clear()
                try:
                    await asyncio.wait_for(pub_now.wait(), timeout=TELEMETRY_INTERVAL_S)
                except TimeoutError:
                    pass

        async with asyncio.TaskGroup() as tg:
            tg.create_task(handle_commands())
            tg.create_task(publish_loop())


if __name__ == "__main__":
    asyncio.run(main())
