import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from hub import bus, db, mqtt, registry

logging.basicConfig(level=logging.INFO)

# Built by the Svelte SPA (cd frontend && npm run build). Created here so the
# mount below works on a fresh checkout before the frontend has been built.
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    task = asyncio.create_task(mqtt.run())
    try:
        yield
    finally:
        task.cancel()
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
