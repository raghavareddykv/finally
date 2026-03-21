#!/usr/bin/env bash
set -euo pipefail

# FinAlly — Start script for macOS / Linux
# Usage: ./scripts/start_mac.sh [--build] [--open]
#   --build   Force rebuild the Docker image
#   --open    Open the browser after starting

CONTAINER_NAME="finally"
IMAGE_NAME="finally"
PORT=8000
VOLUME_NAME="finally-data"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

# Parse flags
FORCE_BUILD=false
OPEN_BROWSER=false
for arg in "$@"; do
    case "$arg" in
        --build) FORCE_BUILD=true ;;
        --open)  OPEN_BROWSER=true ;;
        *)       echo "Unknown flag: $arg"; exit 1 ;;
    esac
done

# Stop and remove existing container if running (idempotent)
if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "Stopping existing '$CONTAINER_NAME' container..."
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

# Build image if it doesn't exist or --build flag is passed
if $FORCE_BUILD || ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "Building Docker image '$IMAGE_NAME'..."
    docker build -t "$IMAGE_NAME" "$PROJECT_ROOT"
else
    echo "Docker image '$IMAGE_NAME' already exists. Use --build to rebuild."
fi

# Ensure .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Warning: .env file not found at $ENV_FILE"
    echo "Creating from .env.example..."
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
    else
        echo "No .env.example found either. Container will start without environment file."
        ENV_FILE=""
    fi
fi

# Run the container
echo "Starting '$CONTAINER_NAME' container..."
ENV_FLAG=""
if [ -n "$ENV_FILE" ]; then
    ENV_FLAG="--env-file $ENV_FILE"
fi

docker run -d \
    --name "$CONTAINER_NAME" \
    -v "$VOLUME_NAME":/app/db \
    -p "$PORT":"$PORT" \
    $ENV_FLAG \
    "$IMAGE_NAME"

echo ""
echo "FinAlly is running at http://localhost:$PORT"
echo ""

# Optionally open the browser
if $OPEN_BROWSER; then
    if command -v open >/dev/null 2>&1; then
        open "http://localhost:$PORT"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:$PORT"
    else
        echo "Could not detect a browser opener. Please visit http://localhost:$PORT manually."
    fi
fi
