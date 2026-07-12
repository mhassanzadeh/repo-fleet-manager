#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; COMPOSE_BIN="${COMPOSE_BIN:-}"
if [[ -z "$COMPOSE_BIN" ]]; then
  if command -v podman-compose >/dev/null 2>&1; then COMPOSE_BIN="podman-compose"; elif docker compose version >/dev/null 2>&1; then COMPOSE_BIN="docker compose"; else echo "[ERROR] Neither podman-compose nor docker compose was found." >&2; exit 1; fi
fi
cd "$ROOT_DIR"
echo "[INFO] Normalizing Docker build metadata blocks."; python3 scripts/normalize-docker-build-metadata.py
echo "[INFO] Building Python service base image."; if [[ -x "$ROOT_DIR/scripts/validate-phase3-19-audit-worker-integration.sh" ]]; then
  "$ROOT_DIR/scripts/validate-phase3-19-audit-worker-integration.sh" --compose-up-check || exit 1
fi

"$ROOT_DIR/scripts/build-python-service-base.sh"
echo "[INFO] Computing service source fingerprints."; python3 scripts/goftaroo-source-fingerprint.py --write; python3 scripts/generate-compose-build-override.py
COMPOSE_ENV="$ROOT_DIR/.goftaroo-build/compose.env"; COMPOSE_OVERRIDE="$ROOT_DIR/.goftaroo-build/docker-compose.build-metadata.yml"
echo "[INFO] Starting Goftaroo dev compose stack with source fingerprint metadata."
# shellcheck disable=SC2086
$COMPOSE_BIN --env-file "$COMPOSE_ENV" -f infra-compose/docker-compose.yml -f "$COMPOSE_OVERRIDE" up -d --build --force-recreate "$@"
echo "[INFO] Verifying container source fingerprints."; "$ROOT_DIR/scripts/verify-container-source-digests.sh"
echo "[OK] Goftaroo dev stack is running with current source fingerprints."
echo "[INFO] Run ./scripts/goftaroo-compose-status.sh for service health and route checks."
