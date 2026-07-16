"""In-memory node registry built from NodeAdvert messages.

The registry is a cache over the messages log: adverts are persisted there by
mqtt._subscriber, and mqtt.run() rehydrates this module from the DB on startup.
All access happens on the single event loop, so no locking is needed.
"""

import time

# node_id -> {"advert": dict (MessageToDict of NodeAdvert), "last_seen": float}
_nodes: dict[str, dict] = {}

# A node is online while its last advert/telemetry is younger than this.
# Nodes advertise every 30 s and publish telemetry every 5 s.
ONLINE_THRESHOLD_S = 30.0


def upsert_advert(node_id: str, advert: dict, last_seen: float | None = None) -> bool:
    """Store a node's advert. Returns True when the node was unknown before."""
    is_new = node_id not in _nodes
    _nodes[node_id] = {"advert": advert, "last_seen": last_seen or time.time()}
    return is_new


def touch(node_id: str) -> None:
    """Mark a node as alive (called on every telemetry message)."""
    node = _nodes.get(node_id)
    if node is not None:
        node["last_seen"] = time.time()


def get(node_id: str) -> dict | None:
    return _nodes.get(node_id)


def snapshot() -> dict[str, dict]:
    """Registry view for /api/nodes, with a derived online flag."""
    now = time.time()
    return {
        node_id: {
            "advert": node["advert"],
            "last_seen": node["last_seen"],
            "online": now - node["last_seen"] < ONLINE_THRESHOLD_S,
        }
        for node_id, node in _nodes.items()
    }
