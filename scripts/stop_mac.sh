#!/usr/bin/env bash
set -euo pipefail

# FinAlly — Stop script for macOS / Linux
# Stops and removes the container but keeps the data volume.

CONTAINER_NAME="finally"

if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "Stopping '$CONTAINER_NAME' container..."
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
    echo "Container stopped and removed."
else
    echo "No '$CONTAINER_NAME' container found. Nothing to stop."
fi

echo "Data volume 'finally-data' has been preserved."
