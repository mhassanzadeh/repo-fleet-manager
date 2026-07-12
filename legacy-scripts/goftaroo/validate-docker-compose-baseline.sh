#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/infra-compose/docker-compose.yml"
REGISTRY_FILE="${ROOT_DIR}/scripts/phase2-service-registry.sh"
source "${REGISTRY_FILE}"
echo "[INFO] Validating Docker Compose baseline..."
if [[ ! -f "${COMPOSE_FILE}" ]]; then echo "[ERROR] Missing ${COMPOSE_FILE}" >&2; exit 1; fi
python3 - "$COMPOSE_FILE" "$ROOT_DIR" <<'PYBLOCK'
from pathlib import Path
import re, sys
compose=Path(sys.argv[1]); root=Path(sys.argv[2]); text=compose.read_text()
for block in ["services:", "networks:", "volumes:"]:
    if block not in text:
        raise SystemExit(f"[ERROR] Missing root block: {block}")
service_names=["postgres","redis","minio","api-gateway","identity-service","tenant-service","device-registry-service","usage-metering-service","voice-session-service","conversation-service","speech-provider-service","llm-gateway-service","agent-orchestrator-service","billing-service","subscription-service","notification-service","skill-registry-service"]
for name in service_names:
    if not re.search(rf"^  {re.escape(name)}:\s*$", text, re.MULTILINE):
        raise SystemExit(f"[ERROR] Missing or incorrectly indented service block: {name}")
for name in service_names[3:]:
    service_dir=root/"services"/name
    if not (service_dir/"Dockerfile").is_file():
        raise SystemExit(f"[ERROR] Missing Dockerfile for {name}: {service_dir/'Dockerfile'}")
    if f"context: ../services/{name}" not in text:
        raise SystemExit(f"[ERROR] Missing compose build context for {name}")
    if f"GOFTAROO_SERVICE_NAME: {name}" not in text:
        raise SystemExit(f"[ERROR] Missing service name env var for {name}")
for bad in ["billing-service:","subscription-service:","notification-service:","skill-registry-service:"]:
    if re.search(rf"^{re.escape(bad)}$", text, re.MULTILINE):
        raise SystemExit(f"[ERROR] Incorrect top-level service indentation detected: {bad}")
print("[OK] Docker Compose baseline validation passed.")
PYBLOCK
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose --env-file "${ROOT_DIR}/infra-compose/.env.example" -f "${COMPOSE_FILE}" config >/dev/null
  echo "[OK] docker compose config validation passed."
else
  echo "[WARN] Docker Compose CLI not available; skipped parser-level compose validation."
fi
