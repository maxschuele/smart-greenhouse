import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from hub import db, mqtt

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).parent / "static"


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


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
