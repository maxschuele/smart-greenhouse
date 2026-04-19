# SCIoT Project: Central Hub

Initial scaffolding for the Smart Cities & IoT course project: a Mosquitto MQTT broker in Docker and a Python hub that runs an aiomqtt pub/sub loop alongside a FastAPI dashboard in a single async process.

## Prerequisites

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- Docker + Docker Compose

## Setup

Install Python dependencies (creates `.venv`):

```
uv sync
```

Start the Mosquitto broker:

```
docker compose up -d
```

## Run

```
uv run python -m hub
```

Open <http://localhost:8000>. The page polls `/api/messages` and shows the latest payload seen on each topic.

The hub publishes a `demo/heartbeat` message every 5 seconds and subscribes to `demo/#`, so its own heartbeat should appear within a few seconds.

## Stop

```
docker compose down
```

## More

- Common workflows are wrapped as [just](https://just.systems/) recipes. Run `just` to list them (e.g. `just sync`, `just up`, `just run`, `just dev`).
- See [doc/commands.md](doc/commands.md) for the cheat sheet of underlying `uv` and `docker compose` commands.

## Layout

```
docker-compose.yml            Mosquitto container
deploy/mosquitto/
  mosquitto.conf              Broker config
src/hub/                      Python package (installed by uv sync)
  __main__.py                 Entrypoint; runs uvicorn
  api.py                      FastAPI app, starts MQTT task via lifespan
  mqtt.py                     aiomqtt pub/sub demo
  static/index.html           Dashboard, served by FastAPI
```
