#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

fix_local_submodule_urls() {
  echo "[bootstrap] Fixing local portable submodule remotes for this extracted workspace..."
  python3 - <<'PYINNER'
from pathlib import Path
import subprocess

root = Path.cwd().resolve()
modules = []
current = {}
for line in (root / '.gitmodules').read_text().splitlines():
    s = line.strip()
    if s.startswith('[submodule'):
        if current:
            modules.append(current)
        current = {}
    elif '=' in s:
        k, v = [x.strip() for x in s.split('=', 1)]
        current[k] = v
if current:
    modules.append(current)

for m in modules:
    path = m['path']
    repo = path.replace('/', '-').split('-', 1)[-1] if path.startswith(('services/', 'clients/', 'packages/', 'infra/')) else path.replace('/', '-')
    # The portable package keeps bare remotes under _git-remotes/<leaf>.git.
    leaf = Path(path).name
    remote = root / '_git-remotes' / f'{leaf}.git'
    subprocess.run(['git', 'config', f'submodule.{path}.url', str(remote)], check=True)
    module_path = root / path
    if module_path.exists() and (module_path / '.git').exists():
        subprocess.run(['git', '-C', str(module_path), 'remote', 'set-url', 'origin', str(remote)], check=False)
PYINNER
}

fix_local_submodule_urls

echo "[bootstrap] Initializing and updating submodules..."
git -c protocol.file.allow=always submodule update --init --recursive

echo "[bootstrap] Submodule status:"
git submodule status --recursive

echo "[bootstrap] Done."
