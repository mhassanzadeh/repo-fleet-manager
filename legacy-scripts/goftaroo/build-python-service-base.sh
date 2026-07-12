#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER_CLI="${CONTAINER_CLI:-}"
IMAGE_NAME="${GOFTAROO_PYTHON_SERVICE_BASE_IMAGE:-goftaroo/python-service-base:dev}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.org/simple}"
PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-}"

if [[ -z "$CONTAINER_CLI" ]]; then
  if command -v podman >/dev/null 2>&1; then
    CONTAINER_CLI="podman"
  elif command -v docker >/dev/null 2>&1; then
    CONTAINER_CLI="docker"
  else
    echo "[ERROR] Neither podman nor docker was found." >&2
    exit 1
  fi
fi

echo "[INFO] Building Python service base image: $IMAGE_NAME"
"$CONTAINER_CLI" build \
  --build-arg "PIP_INDEX_URL=$PIP_INDEX_URL" \
  --build-arg "PIP_EXTRA_INDEX_URL=$PIP_EXTRA_INDEX_URL" \
  -t "$IMAGE_NAME" \
  -f "$ROOT_DIR/infra/docker/python-service-base/Dockerfile" \
  "$ROOT_DIR/infra/docker/python-service-base"

echo "[OK] Built $IMAGE_NAME"
