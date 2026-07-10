"""Virtual weather sensor: Open-Meteo forecast published on virtual/weather.

One of the software-based sensors required by the project. Enabled by
setting WEATHER_LAT and WEATHER_LON (e.g. 48.78 / 9.18 for Stuttgart);
without them the task exits immediately and the planner simply sees no
weather facts.

Payload (JSON): {"cloud_cover": 0.0-1.0, "temp_forecast_c": <today's max>,
"is_day": bool} — is_day comes from Open-Meteo's sunrise/sunset model for
the configured coordinates and drives the grow light after dark.

Published over MQTT rather than fed to the planner directly, so it flows
through the same persist/fan-out pipeline as every hardware sensor and can
be faked for demos with `just weather 0.8 33`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.request

from hub import mqtt

log = logging.getLogger(__name__)

TOPIC = "virtual/weather"
INTERVAL_S = 900
RETRY_S = 60

LAT = os.environ.get("WEATHER_LAT")
LON = os.environ.get("WEATHER_LON")

_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&current=cloud_cover,is_day&daily=temperature_2m_max&forecast_days=1&timezone=auto"
)


def _fetch() -> dict:
    with urllib.request.urlopen(_URL.format(lat=LAT, lon=LON), timeout=15) as resp:
        data = json.load(resp)
    return {
        "cloud_cover": data["current"]["cloud_cover"] / 100.0,
        "is_day": bool(data["current"]["is_day"]),
        "temp_forecast_c": data["daily"]["temperature_2m_max"][0],
    }


async def run() -> None:
    if not (LAT and LON):
        log.info("weather sensor disabled (set WEATHER_LAT and WEATHER_LON to enable)")
        return
    delay = 5.0  # give the MQTT client a moment to connect on startup
    while True:
        await asyncio.sleep(delay)
        try:
            payload = await asyncio.to_thread(_fetch)
            await mqtt.publish(TOPIC, json.dumps(payload))
            log.info("weather: %s", payload)
            delay = INTERVAL_S
        except Exception as e:
            log.warning("weather fetch failed (%s), retrying in %ds", e, RETRY_S)
            delay = RETRY_S
