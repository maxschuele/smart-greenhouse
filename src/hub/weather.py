"""Virtual weather sensor: forecast (or manual override) on virtual/weather.

One of the software-based sensors required by the project. Two modes,
switchable at runtime from the dashboard's Weather card (PUT /api/weather):

  auto    fetch cloud cover / daylight / today's max from Open-Meteo for the
          configured coordinates. Seeded from WEATHER_LAT / WEATHER_LON
          (e.g. 48.78 / 9.18 for Stuttgart); without coordinates nothing is
          published until they are entered in the UI.
  manual  publish the values set in the UI as-is — the demo/fake mode that
          used to require `just weather 0.8 33`. Starts with neutral values
          (clear warm day) that trigger no planner action.

Payload (JSON): {"cloud_cover": 0.0-1.0, "temp_forecast_c": <today's max>,
"is_day": bool, "source": "open-meteo" | "manual"} — is_day drives the grow
light after dark; source is display-only for the dashboard.

Published over MQTT rather than fed to the planner directly, so it flows
through the same persist/fan-out pipeline as every hardware sensor.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.request
from dataclasses import dataclass

from hub import mqtt

log = logging.getLogger(__name__)

TOPIC = "virtual/weather"
INTERVAL_S = 900
RETRY_S = 60

_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&current=cloud_cover,is_day&daily=temperature_2m_max&forecast_days=1&timezone=auto"
)


@dataclass
class WeatherConfig:
    mode: str = "manual"  # "auto" (Open-Meteo) | "manual" (UI-set values)
    lat: float | None = None
    lon: float | None = None
    # Manual-mode values; defaults are a clear warm day (planner-neutral).
    cloud_cover: float = 0.2
    temp_forecast_c: float = 22.0
    is_day: bool = True


def _env_float(name: str) -> float | None:
    value = os.environ.get(name)
    try:
        return float(value) if value else None
    except ValueError:
        log.warning("ignoring non-numeric %s=%r", name, value)
        return None


def _initial_config() -> WeatherConfig:
    lat, lon = _env_float("WEATHER_LAT"), _env_float("WEATHER_LON")
    mode = "auto" if lat is not None and lon is not None else "manual"
    return WeatherConfig(mode=mode, lat=lat, lon=lon)


# Edited via PUT /api/weather; notify_changed() makes the loop apply it now.
config = _initial_config()
_changed = asyncio.Event()


def notify_changed() -> None:
    _changed.set()


def _fetch(lat: float, lon: float) -> dict:
    with urllib.request.urlopen(_URL.format(lat=lat, lon=lon), timeout=15) as resp:
        data = json.load(resp)
    return {
        "cloud_cover": data["current"]["cloud_cover"] / 100.0,
        "is_day": bool(data["current"]["is_day"]),
        "temp_forecast_c": data["daily"]["temperature_2m_max"][0],
        "source": "open-meteo",
    }


async def run() -> None:
    delay = 5.0  # give the MQTT client a moment to connect on startup
    while True:
        try:
            await asyncio.wait_for(_changed.wait(), timeout=delay)
        except TimeoutError:
            pass
        _changed.clear()
        delay = INTERVAL_S

        if config.mode == "manual":
            payload = {
                "cloud_cover": config.cloud_cover,
                "temp_forecast_c": config.temp_forecast_c,
                "is_day": config.is_day,
                "source": "manual",
            }
        elif config.lat is None or config.lon is None:
            log.info("weather: auto mode without coordinates, nothing published")
            continue  # the loop stays alive so the UI can configure it later
        else:
            try:
                payload = await asyncio.to_thread(_fetch, config.lat, config.lon)
            except Exception as e:
                log.warning("weather fetch failed (%s), retrying in %ds", e, RETRY_S)
                delay = RETRY_S
                continue

        try:
            await mqtt.publish(TOPIC, json.dumps(payload))
            log.info("weather: %s", payload)
        except RuntimeError:  # MQTT not connected (yet); retry shortly
            delay = 5.0
