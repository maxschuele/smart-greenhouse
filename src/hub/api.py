import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from hub import bus, db, mqtt, registry, weather
from hub.planning import service as planning

logging.basicConfig(level=logging.INFO)

# Built by the Svelte SPA (cd frontend && npm run build). Created here so the
# mount below works on a fresh checkout before the frontend has been built.
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    tasks = [
        asyncio.create_task(mqtt.run()),
        asyncio.create_task(planning.run()),
        asyncio.create_task(weather.run()),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        await db.close()


app = FastAPI(lifespan=lifespan)


@app.get("/api/messages")
async def messages() -> dict[str, dict]:
    return await db.latest_per_topic()


@app.get("/api/nodes")
async def nodes() -> dict[str, dict]:
    """Discovered nodes with their advertised capabilities and online state."""
    return registry.snapshot()


class Command(BaseModel):
    actuator_id: str
    value: bool | float | str


@app.post("/api/nodes/{node_id}/command")
async def command(node_id: str, cmd: Command) -> dict[str, str]:
    node = registry.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"unknown node {node_id!r}")
    actuators = {a["actuator_id"] for a in node["advert"].get("actuators", [])}
    if cmd.actuator_id not in actuators:
        raise HTTPException(
            status_code=400,
            detail=f"node {node_id!r} has no actuator {cmd.actuator_id!r}",
        )
    try:
        await mqtt.send_command(node_id, cmd.actuator_id, cmd.value)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"status": "sent"}


@app.get("/api/planning")
async def planning_state() -> dict:
    """Latest planning result plus the thresholds driving problem generation."""
    return {**planning.state, "thresholds": asdict(planning.thresholds)}


class ThresholdsUpdate(BaseModel):
    """Partial update; omitted fields keep their current value."""

    moisture_dry_pct: float | None = None
    moisture_dry_pct_hot: float | None = None
    temp_high_c: float | None = None
    humidity_high_pct: float | None = None
    co2_high_ppm: float | None = None
    tank_low_pct: float | None = None
    cloud_cover_threshold: float | None = None
    hot_forecast_c: float | None = None
    tank_empty_cm: float | None = None
    tank_full_cm: float | None = None


@app.put("/api/planning/thresholds")
async def update_thresholds(update: ThresholdsUpdate) -> dict:
    for key, value in update.model_dump(exclude_none=True).items():
        setattr(planning.thresholds, key, value)
    return asdict(planning.thresholds)


class WeatherUpdate(BaseModel):
    """Partial update; omitted fields keep their current value.

    lat/lon accept an explicit null to clear the coordinates, hence
    exclude_unset (not exclude_none) below.
    """

    mode: Literal["auto", "manual"] | None = None
    lat: float | None = Field(default=None, ge=-90.0, le=90.0)
    lon: float | None = Field(default=None, ge=-180.0, le=180.0)
    cloud_cover: float | None = Field(default=None, ge=0.0, le=1.0)
    temp_forecast_c: float | None = Field(default=None, ge=-60.0, le=60.0)
    is_day: bool | None = None


@app.get("/api/weather")
async def weather_config() -> dict:
    """Weather source configuration (the published values arrive via /ws)."""
    return asdict(weather.config)


@app.put("/api/weather")
async def update_weather(update: WeatherUpdate) -> dict:
    for key, value in update.model_dump(exclude_unset=True).items():
        if value is None and key not in ("lat", "lon"):
            continue  # only the coordinates are clearable
        setattr(weather.config, key, value)
    weather.notify_changed()  # wake the loop so it publishes immediately
    return asdict(weather.config)


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "snapshot", "data": await db.latest_per_topic()})
    q = bus.subscribe()
    try:
        while True:
            await websocket.send_json({"type": "message", **await q.get()})
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(q)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
