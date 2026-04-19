# Common Commands

Reference for day-to-day work on this project. Most of these are wrapped as [just](https://just.systems/) recipes; run `just` in the repo root for the list. This document shows the underlying commands so the wrappers remain transparent.

## uv

[uv](https://docs.astral.sh/uv/) manages the Python toolchain, the virtualenv (`.venv/`), and the lockfile (`uv.lock`). The venv does not need to be activated; `uv run` injects it.

### Setup

```
uv sync                         # create .venv, install deps + this project from the lockfile
uv sync --upgrade               # re-resolve and upgrade everything to latest allowed
uv python install 3.14          # install Python 3.14 if not present
```

### Dependencies

```
uv add aiomqtt                  # add a runtime dep (updates pyproject.toml + lockfile)
uv add --dev pytest ruff        # add a dev-only dep
uv remove aiomqtt               # remove a dep
uv lock                         # regenerate uv.lock without changing versions
uv lock --upgrade-package fastapi
uv tree                         # show the dependency tree
```

### Running code

```
uv run python -m hub            # start the hub (FastAPI + MQTT loop)
uv run python -c "from hub import api"
uv run pytest                   # once tests exist
```

Anything after `uv run` runs inside the project venv with `src/hub` importable.

## Mosquitto (Docker)

The broker runs as a container defined in `docker-compose.yml`, with its config bind-mounted from `deploy/mosquitto/`.

```
docker compose up -d                     # start broker in the background
docker compose ps                        # show status
docker compose logs -f mosquitto         # follow broker logs
docker compose restart mosquitto         # reload after editing deploy/mosquitto/mosquitto.conf
docker compose down                      # stop and remove the container (volumes persist)
docker compose down -v                   # also delete persisted data + log volumes
```

### Poking the broker by hand

Publish and subscribe from inside the container (no local install needed):

```
docker compose exec mosquitto mosquitto_sub -t 'demo/#' -v
docker compose exec mosquitto mosquitto_pub -t 'demo/test' -m 'hello'
```

The broker listens on `localhost:1883` on the host, so any MQTT client (mosquitto_pub/sub, MQTT Explorer, an ESP32 on the LAN pointing at this machine) can connect there.
