"""Planning loop: snapshot -> PDDL problem -> Fast Downward -> execute.

Runs as a background task next to the MQTT loop (started from api.lifespan).
Every cycle it rebuilds the problem from the current state; Fast Downward is
only invoked when the problem actually changed — the raw readings fluctuate
constantly, but the boolean facts they induce (soil-dry, temp-high, ...)
only flip on threshold crossings, so this is the debounce.

The generated problem and the resulting plan are published over MQTT on
planning/problem and planning/plan. The hub subscribes to planning/#, so
both flow through the normal persist + WebSocket pipeline and reach the
dashboard (and survive restarts) like any sensor message.

This also closes the control loop without extra machinery: a dispatched
command changes the node's echoed actuator reading, which changes the next
snapshot, which changes the problem, which triggers a replan — until the
world satisfies all goals and generate_problem returns None (status idle).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict

from hub import db, mqtt, registry

from .executor import execute, execute_irrigation
from .planner import PlannerError, PlanStep, solve
from .problem_generator import Thresholds, build_snapshot, generate_problem

log = logging.getLogger(__name__)

INTERVAL_S = 30 #Replan interval
PROBLEM_TOPIC = "planning/problem"
PLAN_TOPIC = "planning/plan"

# Edited via PUT /api/planning/thresholds; the next cycle picks changes up.
thresholds = Thresholds()

# Latest planning state, mirrored for GET /api/planning. The same dict is
# serialized onto planning/plan for the dashboard.
state: dict = {"status": "startup", "steps": [], "cost": None, "detail": None, "generated_at": None}


def _set_state(
    status: str,
    steps: list[PlanStep] = [],
    cost: int | None = None,
    detail: str | None = None,
) -> str:
    state.update(
        status=status,
        steps=[asdict(s) for s in steps],
        cost=cost,
        detail=detail,
        generated_at=time.time(),
    )
    return json.dumps(state)


async def run() -> None:
    last_problem: str | None = "\0never"  # never equal to a real cycle result
    last_steps: list[PlanStep] = []
    while True:
        await asyncio.sleep(INTERVAL_S)
        try:
            last_problem, last_steps = await _tick(last_problem, last_steps)
        except RuntimeError as e:
            log.warning("planning cycle skipped: %s", e)  # MQTT not connected yet
        except Exception:
            log.exception("planning cycle failed")


async def _tick(
    last_problem: str | None, last_steps: list[PlanStep]
) -> tuple[str | None, list[PlanStep]]:
    snap = build_snapshot(registry.snapshot(), await db.latest_per_topic())
    problem = generate_problem(snap, thresholds)
    if problem == last_problem:
        # No fact flipped, so no replan — but irrigation is dosed (the pump
        # stops itself after a few seconds), so plants that are still dry
        # get their dose repeated until the moisture threshold is crossed.
        await execute_irrigation(last_steps)
        return last_problem, last_steps

    if problem is None:
        await mqtt.publish(PLAN_TOPIC, _set_state("idle"))
        return None, []

    await mqtt.publish(PROBLEM_TOPIC, problem)
    try:
        plan = await solve(problem)
    except PlannerError as e:
        log.error("%s", e)
        await mqtt.publish(PLAN_TOPIC, _set_state("error", detail=str(e)))
        return problem, []
    if plan is None:
        await mqtt.publish(PLAN_TOPIC, _set_state("unsolvable"))
        return problem, []

    await mqtt.publish(PLAN_TOPIC, _set_state("planned", steps=plan.steps, cost=plan.cost))
    await execute(plan.steps, snap)
    return problem, plan.steps
