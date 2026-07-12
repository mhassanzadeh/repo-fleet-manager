#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/services/identity-service"

DATABASE_URL="${GOFTAROO_DATABASE_URL:-${IDENTITY_DATABASE_URL:-postgresql://goftaroo:goftaroo_dev_password@localhost:5432/goftaroo}}"

cd "$SERVICE_DIR"
GOFTAROO_DATABASE_URL="$DATABASE_URL" python -m goftaroo_identity_service.infrastructure.persistence.migrate
