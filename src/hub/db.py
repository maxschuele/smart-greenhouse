import logging
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "hub.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id      INTEGER PRIMARY KEY,
    topic   TEXT    NOT NULL,
    payload TEXT    NOT NULL,
    ts      REAL    NOT NULL DEFAULT (unixepoch('subsec'))
);
CREATE INDEX IF NOT EXISTS idx_messages_topic_id
    ON messages(topic, id DESC);
"""

_conn: aiosqlite.Connection | None = None


async def connect() -> None:
    global _conn
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn = await aiosqlite.connect(DB_PATH)
    await _conn.execute("PRAGMA journal_mode=WAL;")
    await _conn.execute("PRAGMA synchronous=NORMAL;")
    await _conn.executescript(_SCHEMA)
    await _conn.commit()
    log.info("db ready at %s", DB_PATH)


async def close() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


async def insert_message(topic: str, payload: str) -> None:
    assert _conn is not None
    await _conn.execute(
        "INSERT INTO messages(topic, payload) VALUES (?, ?)",
        (topic, payload),
    )
    await _conn.commit()


async def latest_per_topic() -> dict[str, dict]:
    """Latest message per topic as {topic: {"payload": str, "ts": float}}.

    ts is unixepoch seconds (float), the DB insert time.
    """
    assert _conn is not None
    async with _conn.execute(
        "SELECT topic, payload, ts FROM messages "
        "WHERE id IN (SELECT MAX(id) FROM messages GROUP BY topic)"
    ) as cur:
        return {topic: {"payload": payload, "ts": ts} async for topic, payload, ts in cur}
