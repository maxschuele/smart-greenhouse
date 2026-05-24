"""In-process fan-out of MQTT messages to connected WebSocket clients.

Module-level state, matching db.py and mqtt.py. Each subscriber gets a bounded
queue; the MQTT loop publishes to all of them without ever blocking (a slow or
stalled client just drops messages rather than back-pressuring the hub).
"""

import asyncio

_subscribers: set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _subscribers.discard(q)


def publish(msg: dict) -> None:
    for q in _subscribers:
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass
