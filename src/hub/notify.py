"""Discord notifications: periodic status digest + water-tank refill alerts.

Sent through a Discord webhook (channel settings -> Integrations -> Webhooks,
one plain POST per message, no bot account). Enabled by setting
DISCORD_WEBHOOK_URL; without it the task exits immediately. The digest
interval defaults to hourly (DISCORD_INTERVAL_S, seconds); DISCORD_MENTION
(e.g. "@here") is prepended to tank alerts to ping the channel.

Tank alerts are event-driven: the Plan Executor publishes on planning/alert
whenever a plan contains refill-tank, and this module listens on the
in-process bus (the same fan-out the WebSocket clients use). The executor
re-publishes on every replan while the tank stays low, so alerts are
edge-triggered here: one Discord message when the alert first appears, one
all-clear once the tank reads above the threshold again — only then can the
next alert fire.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import time
import urllib.request
from datetime import UTC, datetime

from hub import bus, db, registry
from hub.planning import service as planning
from hub.planning.executor import ALERT_TOPIC
from hub.planning.problem_generator import Snapshot, build_snapshot, tank_pct

log = logging.getLogger(__name__)

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
MENTION = os.environ.get("DISCORD_MENTION", "")

STARTUP_DELAY_S = 20.0  # let rehydrate + first telemetry land before digesting
TANK_CHECK_S = 60.0  # how often to look for a refill while an alert is active

# Discord's embed accent palette.
BLURPLE = 0x5865F2
RED = 0xED4245
GREEN = 0x57F287


def _interval_s() -> float:
    try:
        return float(os.environ.get("DISCORD_INTERVAL_S", "") or 3600)
    except ValueError:
        log.warning("ignoring non-numeric DISCORD_INTERVAL_S, using hourly")
        return 3600.0


def _fmt(value: float | None, unit: str, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f} {unit}"


def _embed(title: str, color: int, fields: list[dict], description: str = "") -> dict:
    return {
        "username": "Smart Greenhouse",
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": fields,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        ],
    }


def _digest_payload(snap: Snapshot, tank: float | None) -> dict:
    fields = [
        {"name": f"🌿 {plant}", "value": _fmt(moisture, "% moisture"), "inline": True}
        for plant, moisture in sorted(snap.moisture.items())
    ]
    fields += [
        {
            "name": "🌡️ Temperature",
            "value": _fmt(snap.temperature_c, "°C"),
            "inline": True,
        },
        {"name": "💨 Humidity", "value": _fmt(snap.humidity_pct, "%"), "inline": True},
        {"name": "🫁 CO2", "value": _fmt(snap.co2_ppm, "ppm", 0), "inline": True},
        {"name": "🚰 Tank", "value": _fmt(tank, "%", 0), "inline": True},
        {"name": "🌀 Fan", "value": "on" if snap.fan_active else "off", "inline": True},
        {
            "name": "💡 Light",
            "value": "on" if snap.light_active else "off",
            "inline": True,
        },
    ]
    steps = planning.state.get("steps") or []
    plan = str(planning.state.get("status", "unknown"))
    if steps:
        plan += ": " + ", ".join(
            "(" + " ".join([s["action"], *s.get("args", [])]) + ")" for s in steps
        )
    fields.append({"name": "🧠 Plan", "value": plan, "inline": False})
    return _embed("🌱 Greenhouse status", BLURPLE, fields)


def _alert_payload(message: str, tank: float | None) -> dict:
    payload = _embed(
        "🚨 Water tank low",
        RED,
        [{"name": "🚰 Tank level", "value": _fmt(tank, "%", 0), "inline": True}],
        description=f"{message}\nIrrigation is paused until the tank is refilled.",
    )
    if MENTION:
        payload["content"] = MENTION
    return payload


def _refilled_payload(tank: float | None) -> dict:
    return _embed(
        "✅ Water tank refilled",
        GREEN,
        [{"name": "🚰 Tank level", "value": _fmt(tank, "%", 0), "inline": True}],
        description="Irrigation resumes with the next planning cycle.",
    )


def _post_sync(payload: dict) -> None:
    req = urllib.request.Request(
        WEBHOOK_URL,  # type: ignore[arg-type]  # run() guards against None
        data=json.dumps(payload).encode(),
        # Cloudflare in front of Discord rejects urllib's default
        # "Python-urllib/x.y" User-Agent with 403 (error code 1010).
        headers={
            "Content-Type": "application/json",
            "User-Agent": "smart-greenhouse-hub/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15):
        pass


async def _post(payload: dict) -> None:
    try:
        await asyncio.to_thread(_post_sync, payload)
    except Exception as e:  # a Discord outage must never kill the task
        log.warning("discord post failed: %s", e)


async def _snapshot() -> Snapshot:
    return build_snapshot(registry.snapshot(), await db.latest_per_topic())


def _tank(snap: Snapshot) -> float | None:
    return tank_pct(snap, planning.thresholds)


async def run() -> None:
    if not WEBHOOK_URL:
        log.info("discord notifications disabled (set DISCORD_WEBHOOK_URL to enable)")
        return
    q = bus.subscribe()
    interval = _interval_s()
    next_digest = time.time() + STARTUP_DELAY_S
    next_tank_check = math.inf  # only ticks while an alert is active
    alert_active = False
    log.info("discord notifications enabled (digest every %.0fs)", interval)

    while True:
        timeout = max(0.0, min(next_digest, next_tank_check) - time.time())
        msg: dict | None = None
        try:
            msg = await asyncio.wait_for(q.get(), timeout)
        except TimeoutError:
            pass

        try:
            if msg is not None and msg["topic"] == ALERT_TOPIC and not alert_active:
                alert_active = True
                next_tank_check = time.time() + TANK_CHECK_S
                try:
                    text = json.loads(msg["payload"]).get(
                        "message", "Water tank is low."
                    )
                except ValueError, TypeError:
                    text = "Water tank is low."
                await _post(_alert_payload(text, _tank(await _snapshot())))

            now = time.time()
            if alert_active and now >= next_tank_check:
                next_tank_check = now + TANK_CHECK_S
                tank = _tank(await _snapshot())
                if tank is not None and tank >= planning.thresholds.tank_low_pct:
                    alert_active = False
                    next_tank_check = math.inf
                    await _post(_refilled_payload(tank))

            if now >= next_digest:
                next_digest = now + interval
                snap = await _snapshot()
                await _post(_digest_payload(snap, _tank(snap)))
        except Exception:
            log.exception("notify cycle failed")
