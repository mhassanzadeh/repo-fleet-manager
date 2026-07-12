#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT_DIR"
python3 scripts/goftaroo-source-fingerprint.py --write >/dev/null
python3 - <<'PYCHECK'
from pathlib import Path
import json, subprocess
root=Path.cwd(); metadata=json.loads((root/".goftaroo-build/metadata.json").read_text())
engine="podman" if subprocess.call(["sh","-c","command -v podman >/dev/null 2>&1"])==0 else "docker"
def inspect_container(name,key):
    fmt='{{ index .Config.Labels "' + key + '" }}'
    try: return subprocess.check_output([engine,"inspect",f"infra-compose_{name}_1","--format",fmt],text=True,stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError: return ""
def inspect_image(name,key):
    fmt='{{ index .Config.Labels "' + key + '" }}'
    for image in [f"localhost/infra-compose_{name}:latest", f"infra-compose_{name}:latest", f"infra-compose-{name}:latest"]:
        try:
            v=subprocess.check_output([engine,"image","inspect",image,"--format",fmt],text=True,stderr=subprocess.DEVNULL).strip()
            if v: return v
        except subprocess.CalledProcessError: pass
    return ""
failed=False
print("SERVICE                         EXPECTED          IMAGE             CONTAINER         STATUS"); print("-"*96)
for s in metadata["services"]:
    n=s["name"]; exp=s["source_digest"]; img=inspect_image(n,"ir.goftaroo.source-digest"); cont=inspect_container(n,"ir.goftaroo.source-digest")
    ok_img=img==exp; ok_cont=cont==exp; status="OK" if ok_img and ok_cont else f"IMAGE={'OK' if ok_img else img or 'missing'};CONTAINER={'OK' if ok_cont else cont or 'missing'}"
    if status!="OK": failed=True
    print(f"{n:<31} {exp:<17} {img or '-':<17} {cont or '-':<17} {status}")
if failed: raise SystemExit("[ERROR] One or more images/containers do not match current source fingerprints.")
print("[OK] All running service containers match current source fingerprints.")
PYCHECK
