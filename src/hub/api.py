import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from hub import bus, db, mqtt

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
async def messages() -> dict[str, str]:
    return await db.latest_per_topic()


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
