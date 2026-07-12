#!/usr/bin/env bash
set -euo pipefail

IDENTITY_BASE_URL="${IDENTITY_BASE_URL:-http://localhost:8081}"
API_GATEWAY_BASE_URL="${API_GATEWAY_BASE_URL:-http://localhost:8080}"
EMAIL="diag39-$(date +%s)-$RANDOM@goftaroo.ir"
PASSWORD="SmokePassword123!"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

echo "[INFO] Creating diagnostic token via Identity: $EMAIL"

curl -fsS -o "$tmpdir/register.json" \
  -X POST "$IDENTITY_BASE_URL/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"display_name\":\"Phase 3.9 Diagnostic\"}"

curl -fsS -o "$tmpdir/login.json" \
  -X POST "$IDENTITY_BASE_URL/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"

ACCESS_TOKEN="$(python3 - "$tmpdir/login.json" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text())
print(data.get("access_token") or data.get("token") or data.get("jwt") or "")
PY
)"

if [[ -z "$ACCESS_TOKEN" ]]; then
  echo "[ERROR] Could not extract access token" >&2
  cat "$tmpdir/login.json" >&2
  exit 1
fi

echo "[INFO] Token header/payload without trusting signature:"
python3 - "$ACCESS_TOKEN" <<'PY'
import base64, json, sys
token = sys.argv[1]
parts = token.split(".")
for label, segment in [("header", parts[0]), ("payload", parts[1])]:
    padded = segment + "=" * (-len(segment) % 4)
    print(label + ":")
    print(json.dumps(json.loads(base64.urlsafe_b64decode(padded).decode()), indent=2, sort_keys=True))
PY

echo "[INFO] API Gateway verification body:"
curl -fsS \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$API_GATEWAY_BASE_URL/v1/gateway/auth/verify" | python3 -m json.tool

echo
echo "[INFO] Identity container auth env:"
podman exec infra-compose_identity-service_1 env 2>/dev/null | grep -E 'GOFTAROO.*(SECRET|ISSUER|TOKEN|JWT)|JWT_|SECRET_KEY|AUTH_TOKEN_SECRET' | sort || true

echo
echo "[INFO] API Gateway container auth env:"
podman exec infra-compose_api-gateway_1 env 2>/dev/null | grep -E 'GOFTAROO.*(SECRET|ISSUER|TOKEN|JWT)|JWT_|SECRET_KEY|AUTH_TOKEN_SECRET' | sort || true
