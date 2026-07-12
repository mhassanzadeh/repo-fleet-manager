#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_BIN="${COMPOSE_BIN:-}"
if [[ -z "$COMPOSE_BIN" ]]; then
  if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_BIN="podman-compose"
  elif docker compose version >/dev/null 2>&1; then
    COMPOSE_BIN="docker compose"
  else
    echo "[ERROR] Neither podman-compose nor docker compose was found." >&2
    exit 1
  fi
fi

echo "[INFO] Stopping compose stack before resetting audit volume..."
# shellcheck disable=SC2086
$COMPOSE_BIN --env-file infra-compose/.env.example -f infra-compose/docker-compose.yml down || true

echo "[INFO] Removing old audit named volumes if present..."
for volume in \
  infra-compose_api_gateway_audit_data \
  goftaroo-voice-assistant-platform_api_gateway_audit_data \
  api_gateway_audit_data
do
  podman volume rm "$volume" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
done

echo "[OK] Audit volume reset complete."
echo "[NEXT] Run: ./scripts/goftaroo-compose-up-dev.sh"
