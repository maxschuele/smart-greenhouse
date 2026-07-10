"""Plan Executor — dispatch plan steps as MQTT actuator commands.

Maps domain actions onto the generic nodes/<id>/command protocol. Plant
objects in the plan ARE node ids, so irrigation needs no lookup table; the
greenhouse-wide light/fan commands go to whichever node advertised those
actuators (carried in the Snapshot).

refill-tank is the human actuator: it publishes an alert on planning/alert
for the dashboard and defers the plan's irrigate steps — they are the only
actions that causally depend on the tank, and the pumps must not run dry.
Independent steps (light, fan) still execute. Once a human refills the tank
the ultrasonic reading rises and the next planning cycle produces a fresh
plan without (tank-low), which irrigates normally.
"""

from __future__ import annotations

import json
import logging
import time

from hub import mqtt

from .planner import PlanStep
from .problem_generator import FAN_ACTUATOR, LIGHT_ACTUATOR, PUMP_ACTUATOR, Snapshot

log = logging.getLogger(__name__)

ALERT_TOPIC = "planning/alert"


async def execute(steps: list[PlanStep], snap: Snapshot) -> None:
    awaiting_refill = False
    for step in steps:
        node, actuator, value = None, None, None
        if step.action == "irrigate":
            if awaiting_refill:
                log.info("deferring %s until the tank is refilled", step)
                continue
            node, actuator, value = step.args[0], PUMP_ACTUATOR, True
        elif step.action == "deactivate-pump":
            node, actuator, value = step.args[0], PUMP_ACTUATOR, False
        elif step.action == "activate-light":
            node, actuator, value = snap.light_node, LIGHT_ACTUATOR, True
        elif step.action == "deactivate-light":
            node, actuator, value = snap.light_node, LIGHT_ACTUATOR, False
        elif step.action == "activate-fan":
            node, actuator, value = snap.fan_node, FAN_ACTUATOR, True
        elif step.action == "deactivate-fan":
            node, actuator, value = snap.fan_node, FAN_ACTUATOR, False
        elif step.action == "refill-tank":
            await mqtt.publish(
                ALERT_TOPIC,
                json.dumps({"message": "Water tank is low — please refill it.", "ts": time.time()}),
            )
            log.info("refill-tank: alert raised, deferring irrigation until a human refills")
            awaiting_refill = True
            continue
        else:
            log.warning("skipping unknown plan action %r", step.action)
            continue

        if node is None:
            log.warning("no node advertises the actuator for %r; skipping", step.action)
            continue
        await mqtt.send_command(node, actuator, value)
