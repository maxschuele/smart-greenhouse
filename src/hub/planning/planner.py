"""Run Fast Downward on the greenhouse domain and parse the resulting plan.

The planner binary is taken from the FAST_DOWNWARD env var (default
"fast-downward"; point it at fast-downward.py in a source checkout). The
search configuration is cost-optimal A* with the LM-Cut heuristic, matching
the domain's total-cost metric; override with FD_SEARCH if needed.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from hub import db

log = logging.getLogger(__name__)

DOMAIN_PATH = Path(__file__).parent / "domain.pddl"
WORK_DIR = db.DB_PATH.parent / "planning"
FAST_DOWNWARD = os.environ.get("FAST_DOWNWARD", "fast-downward")
SEARCH = os.environ.get("FD_SEARCH", "astar(lmcut())")
TIMEOUT_S = 60

# Fast Downward driver exit codes for "correctly proved no plan exists"
# (translate-unsolvable, search-unsolvable, search-unsolved-incomplete).
_UNSOLVABLE = {10, 11, 12}


class PlannerError(Exception):
    """Planner missing, crashed, or timed out (as opposed to: no plan exists)."""


@dataclass
class PlanStep:
    action: str
    args: list[str] = field(default_factory=list)


@dataclass
class Plan:
    steps: list[PlanStep]
    cost: int | None = None


def parse_plan(text: str) -> Plan:
    """Parse Fast Downward's plan file: one "(action arg...)" per line, plus
    a trailing "; cost = N (...)" comment."""
    steps: list[PlanStep] = []
    cost: int | None = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(";"):
            m = re.search(r"cost = (\d+)", line)
            if m:
                cost = int(m.group(1))
        elif line.startswith("(") and line.endswith(")"):
            parts = line[1:-1].split()
            if parts:
                steps.append(PlanStep(parts[0], parts[1:]))
    return Plan(steps=steps, cost=cost)


async def solve(problem: str) -> Plan | None:
    """Solve a PDDL problem. Returns None when it is provably unsolvable;
    raises PlannerError for operational failures."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    problem_path = WORK_DIR / "problem.pddl"
    plan_path = WORK_DIR / "sas_plan"
    problem_path.write_text(problem)
    plan_path.unlink(missing_ok=True)

    argv = [
        FAST_DOWNWARD,
        "--plan-file", str(plan_path),
        str(DOMAIN_PATH), str(problem_path),
        "--search", SEARCH,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=WORK_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError as e:
        raise PlannerError(
            f"planner {FAST_DOWNWARD!r} not found; set FAST_DOWNWARD to your "
            "fast-downward(.py) executable"
        ) from e

    try:
        out, _ = await asyncio.wait_for(proc.communicate(), TIMEOUT_S)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise PlannerError(f"planner timed out after {TIMEOUT_S}s") from None

    if proc.returncode == 0:
        plan = parse_plan(plan_path.read_text())
        log.info("plan found: %d steps, cost %s", len(plan.steps), plan.cost)
        return plan
    if proc.returncode in _UNSOLVABLE:
        log.warning("problem is unsolvable")
        return None
    tail = out.decode(errors="replace")[-500:]
    raise PlannerError(f"planner exited with code {proc.returncode}: {tail}")
