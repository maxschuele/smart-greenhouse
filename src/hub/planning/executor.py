"""Plan Executor — dispatch plan steps as MQTT actuator commands.

Maps domain actions onto the generic nodes/<id>/command protocol. Plant
objects in the plan ARE node ids, so irrigation needs no lookup table; the
greenhouse-wide light/fan commands go to whichever node advertised those
actuators (carried in the Snapshot).

Irrigation is dosed, not latched: pump = true starts a fixed-length dose and
the plant firmware stops the pump by itself a few seconds later (PUMP_RUN_MS
in node-plant), so a lost command or a dead hub can never leave a pump
running. One dose rarely lifts moisture past the threshold, so the service
calls execute_irrigation() on the cycles in between to repeat the dose until
the sensor reading crosses it.

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


async def execute_irrigation(steps: list[PlanStep]) -> None:
    """Re-dispatch only the irrigate doses of an already-executed plan.

    Called on cycles where the problem did not change: the latching
    actuators (light, fan) already hold their commanded state, but pump
    doses are time-limited by the firmware, so a still-dry plant needs a
    fresh dose each cycle. Skipped entirely while the plan waits on a tank
    refill — the pumps must not run dry.
    """
    if any(s.action == "refill-tank" for s in steps):
        return
    for step in steps:
        if step.action == "irrigate":
            await mqtt.send_command(step.args[0], PUMP_ACTUATOR, True)
