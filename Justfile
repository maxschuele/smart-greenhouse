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

# Remove __pycache__ directories and the venv.
clean:
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    rm -rf .venv
