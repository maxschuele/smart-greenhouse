"""Problem Generator — turns the current greenhouse state into a PDDL problem.

Two pure steps, both easy to unit test:

  1. build_snapshot()    registry view + latest-per-topic rows -> Snapshot
  2. generate_problem()  Snapshot + Thresholds -> PDDL problem string (or
                         None when every care condition is already satisfied,
                         which tells the service not to invoke the planner)

The planner never changes when thresholds change — all the "is it dry?",
"is it hot?" logic lives here, driven by the Thresholds dataclass (edited via
PUT /api/planning/thresholds).

Domain concepts are matched to nodes by advertised capability, not by node
id: any online node advertising a soil_moisture sensor plus a pump actuator
is a plant (its node id becomes the PDDL object), and greenhouse-wide
readings come from whichever online node advertises the matching sensor
kind. New nodes therefore enter the planning problem with no code change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

# Capability names as advertised by the firmware (sensor kinds, actuator ids).
SOIL_KIND = "soil_moisture"
TEMP_KIND = "temperature"
HUMIDITY_KIND = "humidity"
GAS_KIND = "gas"
DISTANCE_KIND = "distance"
PUMP_ACTUATOR = "pump"
LIGHT_ACTUATOR = "led"
FAN_ACTUATOR = "fan"

WEATHER_TOPIC = "virtual/weather"


# ---------------------------------------------------------------------------
# Configuration — this is what the "Automation Config" panel edits.
# ---------------------------------------------------------------------------


@dataclass
class Thresholds:
    moisture_dry_pct: float = 30.0       # below this -> soil-dry
    moisture_dry_pct_hot: float = 40.0   # tighter threshold when hot forecast
    temp_high_c: float = 28.0            # above this -> temp-high
    humidity_high_pct: float = 70.0      # above this -> humidity-high
    co2_high_ppm: float = 1000.0         # above this -> co2-high
    tank_low_pct: float = 25.0           # below this -> tank-low
    cloud_cover_threshold: float = 0.60  # above this -> light-needed
    hot_forecast_c: float = 30.0         # forecast above this -> hot mode
    # Ultrasonic calibration: distance from the sensor to the water surface
    # when the tank is empty resp. full, for the distance -> % conversion.
    tank_empty_cm: float = 30.0
    tank_full_cm: float = 5.0


# ---------------------------------------------------------------------------
# Snapshot — the current world state, already decoded from registry + DB.
# ---------------------------------------------------------------------------


@dataclass
class Snapshot:
    moisture: dict[str, float] = field(default_factory=dict)    # per plant node
    pump_active: dict[str, bool] = field(default_factory=dict)  # per plant node
    temperature_c: float | None = None
    humidity_pct: float | None = None
    co2_ppm: float | None = None
    tank_distance_cm: float | None = None
    light_active: bool = False
    fan_active: bool = False
    # Which node carries the greenhouse-wide actuators; the executor needs
    # these to address activate-light / activate-fan commands.
    light_node: str | None = None
    fan_node: str | None = None
    cloud_cover: float | None = None
    temp_forecast_c: float | None = None
    is_day: bool | None = None  # from sunrise/sunset; None = no weather data


def _readings(latest: dict[str, dict], node_id: str) -> dict[str, float | bool | str]:
    """Latest telemetry readings for one node as {sensor_id: value}."""
    row = latest.get(f"nodes/{node_id}/telemetry")
    if row is None:
        return {}
    try:
        readings = json.loads(row["payload"]).get("readings", [])
    except (ValueError, TypeError):
        return {}
    out: dict[str, float | bool | str] = {}
    for r in readings:
        value = r.get("number", r.get("boolean", r.get("text")))
        if value is not None:
            out[r["sensor_id"]] = value
    return out


def _number(readings: dict, sensor_id: str | None) -> float | None:
    value = readings.get(sensor_id) if sensor_id is not None else None
    return float(value) if isinstance(value, int | float) else None


def build_snapshot(nodes: dict[str, dict], latest: dict[str, dict]) -> Snapshot:
    """Pure function: registry.snapshot() + db.latest_per_topic() -> Snapshot.

    Offline nodes are skipped entirely so the planner never acts on stale
    readings or dispatches commands to a node that cannot receive them.
    """
    snap = Snapshot()
    for node_id, info in sorted(nodes.items()):
        if not info.get("online"):
            continue
        advert = info.get("advert", {})
        by_kind = {s.get("kind"): s.get("sensor_id") for s in advert.get("sensors", [])}
        actuators = {a.get("actuator_id") for a in advert.get("actuators", [])}
        readings = _readings(latest, node_id)

        if SOIL_KIND in by_kind and PUMP_ACTUATOR in actuators:
            moisture = _number(readings, by_kind[SOIL_KIND])
            if moisture is not None:
                snap.moisture[node_id] = moisture
            snap.pump_active[node_id] = readings.get(PUMP_ACTUATOR) is True

        for kind, attr in (
            (TEMP_KIND, "temperature_c"),
            (HUMIDITY_KIND, "humidity_pct"),
            (GAS_KIND, "co2_ppm"),
            (DISTANCE_KIND, "tank_distance_cm"),
        ):
            value = _number(readings, by_kind.get(kind))
            if value is not None:
                setattr(snap, attr, value)

        if LIGHT_ACTUATOR in actuators:
            snap.light_node = node_id
            snap.light_active = readings.get(LIGHT_ACTUATOR) is True
        if FAN_ACTUATOR in actuators:
            snap.fan_node = node_id
            snap.fan_active = readings.get(FAN_ACTUATOR) is True

    weather_row = latest.get(WEATHER_TOPIC)
    if weather_row is not None:
        try:
            weather = json.loads(weather_row["payload"])
            snap.cloud_cover = _opt_float(weather.get("cloud_cover"))
            snap.temp_forecast_c = _opt_float(weather.get("temp_forecast_c"))
            if weather.get("is_day") is not None:
                snap.is_day = bool(weather["is_day"])
        except (ValueError, TypeError):
            pass
    return snap


def _opt_float(v) -> float | None:
    return None if v is None else float(v)


# ---------------------------------------------------------------------------
# Render a PDDL problem from the snapshot + thresholds.
# ---------------------------------------------------------------------------


def tank_pct(snap: Snapshot, th: Thresholds) -> float | None:
    """Ultrasonic distance -> % full (larger distance = emptier tank)."""
    if snap.tank_distance_cm is None:
        return None
    span = th.tank_empty_cm - th.tank_full_cm
    if span <= 0:
        return None
    pct = 100.0 * (th.tank_empty_cm - snap.tank_distance_cm) / span
    return max(0.0, min(100.0, pct))


def generate_problem(
    snap: Snapshot,
    th: Thresholds,
    problem_name: str = "greenhouse-auto",
) -> str | None:
    """Return a PDDL problem string, or None if nothing needs doing.

    Returning None is the signal to the planning service that no planning is
    required this cycle (every care condition is already satisfied and no
    actuator is running unnecessarily), so it should not invoke Fast Downward.
    """
    hot = snap.temp_forecast_c is not None and snap.temp_forecast_c >= th.hot_forecast_c
    dry_threshold = th.moisture_dry_pct_hot if hot else th.moisture_dry_pct

    init: list[str] = ["(= (total-cost) 0)"]
    goal: list[str] = []

    # ---- per-plant irrigation --------------------------------------------
    plants = sorted(set(snap.moisture) | set(snap.pump_active))
    for p in plants:
        m = snap.moisture.get(p)
        is_dry = m is not None and m < dry_threshold
        if is_dry:
            init.append(f"(soil-dry {p})")
            goal.append(f"(not (soil-dry {p}))")
        if snap.pump_active.get(p):
            init.append(f"(pump-active {p})")
            if not is_dry:                       # running but no longer needed
                goal.append(f"(not (pump-active {p}))")

    # ---- ventilation conditions (DHT11 + MQ135) --------------------------
    temp_high = snap.temperature_c is not None and snap.temperature_c > th.temp_high_c
    hum_high = snap.humidity_pct is not None and snap.humidity_pct > th.humidity_high_pct
    co2_high = snap.co2_ppm is not None and snap.co2_ppm > th.co2_high_ppm
    ventilation_needed = temp_high or hum_high or co2_high
    # A running fan is already addressing these conditions — ventilation acts
    # over time, and asserting the goals anyway would make the planner
    # power-cycle the fan (activate-fan is the only action clearing them and
    # requires (not (fan-active))). So emit them only while the fan is off;
    # the fan-off goal below stays gated on ventilation_needed, which keeps
    # the fan running until the readings recover.
    if not snap.fan_active:
        if temp_high:
            init.append("(temp-high)")
            goal.append("(not (temp-high))")
        if hum_high:
            init.append("(humidity-high)")
            goal.append("(not (humidity-high))")
        if co2_high:
            init.append("(co2-high)")
            goal.append("(not (co2-high))")

    # ---- lighting (weather-driven) ---------------------------------------
    # The grow light is needed after dark (sunset..sunrise, from the weather
    # API's is_day) or when heavy cloud cover blocks daylight. Unlike the
    # other facts this one comes from a nodeless source (the weather API),
    # so gate it on a light actuator being online — otherwise the planner
    # would "solve" light-needed with nothing to execute on.
    dark = snap.is_day is False
    cloudy = snap.cloud_cover is not None and snap.cloud_cover >= th.cloud_cover_threshold
    light_needed = (dark or cloudy) and snap.light_node is not None
    # Same treatment as the fan below: a light that is already on satisfies
    # the need, so emit the goal only while it is off — otherwise every
    # cloudy/dark cycle would re-plan (and re-send) activate-light.
    if light_needed and not snap.light_active:
        init.append("(light-needed)")
        goal.append("(not (light-needed))")

    # ---- tank ------------------------------------------------------------
    tank = tank_pct(snap, th)
    tank_low = tank is not None and tank < th.tank_low_pct
    if tank_low:
        init.append("(tank-low)")
        goal.append("(not (tank-low))")

    # ---- actuator-off goals for greenhouse devices -----------------------
    # (fan-active) is asserted only together with its off-goal: while the fan
    # is needed it must stay invisible to the planner, or a cost-tied optimal
    # plan could smuggle in a gratuitous 0-cost deactivate-fan.
    if snap.fan_active and not ventilation_needed:
        init.append("(fan-active)")
        goal.append("(not (fan-active))")
    if snap.light_active and not light_needed:
        init.append("(light-active)")
        goal.append("(not (light-active))")

    if not goal:
        return None  # nothing to plan for this cycle

    objects = " ".join(plants) if plants else "plant1"
    init_block = "\n    ".join(init)
    goal_block = "\n      ".join(goal)

    return (
        f"(define (problem {problem_name})\n"
        f"  (:domain greenhouse)\n"
        f"  (:objects {objects} - plant)\n"
        f"  (:init\n    {init_block}\n  )\n"
        f"  (:goal (and\n      {goal_block}\n  ))\n"
        f"  (:metric minimize (total-cost))\n"
        f")\n"
    )


if __name__ == "__main__":
    # Quick demo without a database.
    demo = Snapshot(
        moisture={"node-plant1": 24.0, "node-plant2": 55.0},
        pump_active={"node-plant1": False, "node-plant2": True},
        temperature_c=32.0,
        humidity_pct=48.0,
        co2_ppm=1100.0,
        tank_distance_cm=26.0,
        light_node="node-greenhouse",
        fan_node="node-greenhouse",
        cloud_cover=0.7,
        temp_forecast_c=29.0,
    )
    print(generate_problem(demo, Thresholds()))
