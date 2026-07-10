default:
    @just --list

# Install Python deps and the project into .venv.
sync:
    uv sync

# Start the Mosquitto broker in the background.
up:
    docker compose up -d

# Stop the Mosquitto broker.
down:
    docker compose down

# Follow broker logs.
logs:
    docker compose logs -f mosquitto

# Reload broker after editing deploy/mosquitto/mosquitto.conf.
restart-broker:
    docker compose restart mosquitto

# Run the hub (FastAPI + aiomqtt loop) on :8000.
run:
    uv run python -m hub

# Start broker (if not already up) and run the hub.
dev: up run

# Subscribe to demo/# on the broker for manual inspection.
sub:
    docker compose exec mosquitto mosquitto_sub -t 'demo/#' -v

# Publish a message: `just pub demo/test hello`.
pub topic message:
    docker compose exec mosquitto mosquitto_pub -t '{{topic}}' -m '{{message}}'

# Add a runtime dependency: `just add aiomqtt`.
add pkg:
    uv add {{pkg}}

# Send an actuator command via the hub API. Value is a JSON literal:
# `just cmd node-plant1 pump true`, `just cmd node-greenhouse fan false`.
cmd node actuator value:
    curl -s -X POST localhost:8000/api/nodes/{{node}}/command \
        -H 'Content-Type: application/json' \
        -d '{"actuator_id": "{{actuator}}", "value": {{value}}}'

# Publish a fake weather reading (cloud cover 0-1, forecast max degC, day?).
# `just weather 0.8 33` (cloudy day) or `just weather 0.1 20 false` (night)
# -> both make the planner want the grow light on.
weather cloud temp is_day="true":
    docker compose exec mosquitto mosquitto_pub -t 'virtual/weather' \
        -m '{"cloud_cover": {{cloud}}, "temp_forecast_c": {{temp}}, "is_day": {{is_day}}}'

# Regenerate Python + nanopb sources from proto/*.proto.
# Requires: `uv add --dev grpcio-tools nanopb`.
proto:
    mkdir -p src/hub/proto firmware/common/src
    uv run python -m grpc_tools.protoc -Iproto \
        --python_out=src/hub/proto proto/telemetry.proto proto/command.proto
    touch src/hub/proto/__init__.py
    uv run nanopb_generator -I proto -D firmware/common/src \
        proto/telemetry.proto proto/command.proto

# Build a node project: `just fw node-example`.
fw node:
    cd firmware/{{node}} && pio run

# Refresh compile_commands.json for a node: `just fw-compiledb node-example`.
fw-compiledb node:
    cd firmware/{{node}} && pio run -t compiledb

# Remove __pycache__ directories and the venv.
clean:
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    rm -rf .venv
