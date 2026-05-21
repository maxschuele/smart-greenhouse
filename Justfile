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

# Regenerate Python + nanopb sources from proto/*.proto.
# Requires: `uv add --dev grpcio-tools nanopb`.
proto:
    mkdir -p src/hub/proto firmware/common/src
    uv run python -m grpc_tools.protoc -Iproto \
        --python_out=src/hub/proto proto/telemetry.proto proto/command.proto
    touch src/hub/proto/__init__.py
    uv run nanopb_generator -I proto -D firmware/common/src \
        -f proto/nanopb.options proto/telemetry.proto proto/command.proto

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
