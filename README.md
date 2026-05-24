# Smart Greenhouse

Smart Cities & IoT course project: a modular smart-greenhouse system. ESP32
sensor/actuator nodes talk to a central hub over MQTT using a shared protobuf
schema. The repo has three parts:

- **`proto/`** — message schema shared by hub and firmware.
- **`firmware/`** — ESP32 nodes (PlatformIO, C++) built on a shared library.
- **`src/hub/`** — Python hub: MQTT loop, FastAPI API, SQLite store.
- **`frontend/`** — Svelte single-page dashboard, built with Vite and served by the hub.

A Mosquitto broker (Docker) sits between them.

## Prerequisites

- Python 3.14 and [uv](https://docs.astral.sh/uv/) — for the hub.
- Docker + Docker Compose — for the broker.
- [PlatformIO](https://platformio.org/) — for firmware builds (only if you're flashing nodes).
- [just](https://just.systems/) — optional, wraps the common commands.

## Quick start

```
uv sync                  # install hub deps into .venv
docker compose up -d     # start Mosquitto on :1883
uv run python -m hub     # start the hub on :8000
```

The hub serves the dashboard from `src/hub/static/`, which is the Svelte SPA
build output. Build it once (the hub serves whatever is present):

```
cd frontend && npm install && npm run build
```

Open <http://localhost:8000>. The hub publishes `demo/heartbeat` every 5 s and
subscribes to `demo/#`, so its own heartbeat appears within a few seconds.

For frontend development, run the Vite dev server instead (`cd frontend && npm
run dev`); it proxies `/api` and `/ws` to the hub on :8000 and provides hot
reload.

Stop with `docker compose down`.

## The three parts

### `proto/` — shared schema

Protobuf is the contract between hub and nodes. `telemetry.proto` covers node
adverts and sensor readings; `command.proto` covers actuator commands.
`nanopb.options` gives the firmware-side generator size hints (strings are
fixed-length on the MCU).

Regenerate Python + nanopb sources after editing a `.proto`:

```
just proto
```

This writes `src/hub/proto/*_pb2.py` and `firmware/common/src/*.pb.[ch]`. Both
are generated artifacts — edit the `.proto` files, not the output.

### `firmware/` — ESP32 nodes

PlatformIO projects, one per node.

- `common/` — shared C++ library (`sgh::Node`) that handles WiFi, MQTT
  reconnect, advertising, telemetry publish, and command dispatch. Generated
  nanopb sources live alongside it.
- `node-example/` — minimal template. Copy this directory to start a real node;
  fill in sensor reads in `loop()` and the actuator handler in `onCommand()`.

Build a node:

```
just fw node-example       # or: cd firmware/node-example && pio run
just fw-compiledb node-example   # refresh compile_commands.json for clangd
```

WiFi/MQTT credentials are passed as `build_flags` in each node's
`platformio.ini`.

### `src/hub/` — Python hub

Single async process (FastAPI + aiomqtt) launched via `python -m hub`.

```
src/hub/
  __main__.py          Entrypoint; runs uvicorn
  api.py               FastAPI app; REST + /ws; starts the MQTT task via lifespan
  mqtt.py              aiomqtt pub/sub loop (currently the demo)
  bus.py               In-process fan-out of messages to WebSocket clients
  db.py                aiosqlite store (latest payload per topic)
  proto/               Generated Python protobuf modules (`just proto`)
  static/              Built Svelte SPA (output of `frontend/`; gitignored)
```

The hub exposes two interfaces consumed by the dashboard:

- `GET /api/messages` returns the latest payload per topic as JSON.
- `WS /ws` sends a `snapshot` of the current topics on connect, then a
  `message` frame for every MQTT message as it arrives.

### `frontend/` — Svelte dashboard

Single-page app (Svelte, Vite, Tailwind, shadcn-svelte, svelte-chartjs,
lucide). It loads the current state over `/ws`, groups messages by topic, charts
numeric payloads, and has a placeholder panel for AI planning (current plan and
planning model) to be wired up later.

```
cd frontend
npm install        # install dependencies
npm run dev        # dev server on :5173, proxies /api and /ws to :8000
npm run build      # build into ../src/hub/static for the hub to serve
```

## Common commands

Wrapped as [just](https://just.systems/) recipes — run `just` to list them
(`just sync`, `just up`, `just run`, `just dev`, `just proto`, `just fw <node>`,
`just sub`, `just pub <topic> <msg>`). See [doc/commands.md](doc/commands.md)
for the underlying `uv` and `docker compose` invocations.

## Layout

```
docker-compose.yml         Mosquitto container
deploy/mosquitto/          Broker config
proto/                     Shared message schema
src/hub/                   Python hub (installed by uv sync)
frontend/                  Svelte dashboard (Vite build served by the hub)
firmware/
  common/                  Shared C++ library (SghNode + nanopb)
  node-example/            Template node project
doc/                       Architecture notes and command cheat sheet
```
