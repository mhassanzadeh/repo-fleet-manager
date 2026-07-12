#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT_DIR"
echo "== Compose containers =="
if [[ -f .goftaroo-build/compose.env && -f .goftaroo-build/docker-compose.build-metadata.yml ]]; then podman-compose --env-file .goftaroo-build/compose.env -f infra-compose/docker-compose.yml -f .goftaroo-build/docker-compose.build-metadata.yml ps || true; else podman-compose --env-file infra-compose/.env.example -f infra-compose/docker-compose.yml ps || true; fi
echo; echo "== Source fingerprint verification =="; ./scripts/verify-container-source-digests.sh || true
echo; echo "== Health endpoints =="
python3 - <<'PYSTATUS'
import json, urllib.request, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()/"scripts"))
from goftaroo_service_catalog import SERVICES
for s in SERVICES:
    url=f"http://localhost:{s['host_port']}/healthz"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            data=json.loads(resp.read().decode()); print(f"[OK] {s['name']:<31} {url} build_sha={data.get('build_sha')} status={data.get('status')}")
    except Exception as exc: print(f"[FAIL] {s['name']:<29} {url} {exc}")
PYSTATUS
echo; echo "== Phase 3 runtime route checks =="; ./scripts/verify-phase3-runtime-routes.sh || true
