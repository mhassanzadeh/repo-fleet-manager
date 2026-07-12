#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SERVICE_PATH="services/audit-export-worker-service"
REMOTE_URL="${AUDIT_WORKER_REMOTE:-git@github.com:mhassanzadeh/goftaroo-audit-export-worker-service.git}"
BRANCH="${AUDIT_WORKER_BRANCH:-main}"

echo "[INFO] Bootstrapping audit-export-worker-service as a Git submodule."
echo "[INFO] Remote: $REMOTE_URL"
echo "[INFO] Path:   $SERVICE_PATH"

if ! command -v git >/dev/null 2>&1; then
  echo "[ERROR] git is not installed." >&2
  exit 1
fi

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "[ERROR] Must run inside the root git repository." >&2
  exit 1
fi

if [[ -d "$SERVICE_PATH/.git" ]] || git ls-files --stage "$SERVICE_PATH" 2>/dev/null | grep -q '^160000 '; then
  echo "[OK] $SERVICE_PATH is already a git repository/submodule."
  git config -f .gitmodules "submodule.$SERVICE_PATH.path" "$SERVICE_PATH"
  git config -f .gitmodules "submodule.$SERVICE_PATH.url" "$REMOTE_URL"
  git add .gitmodules "$SERVICE_PATH" || true
  exit 0
fi

if ! git ls-remote "$REMOTE_URL" >/dev/null 2>&1; then
  cat >&2 <<EOF
[ERROR] Remote repository is not reachable:

  $REMOTE_URL

Create it first, then rerun this script.

Suggested GitHub CLI command:

  gh repo create mhassanzadeh/goftaroo-audit-export-worker-service --private

Then rerun:

  ./scripts/bootstrap-phase3-19-audit-worker-submodule.sh

No destructive change was made.
EOF
  exit 2
fi

BACKUP_DIR=""
if [[ -d "$SERVICE_PATH" ]] && [[ -n "$(find "$SERVICE_PATH" -mindepth 1 -maxdepth 1 2>/dev/null | head -n 1)" ]]; then
  BACKUP_DIR="/tmp/goftaroo-audit-export-worker-service-backup-$(date +%Y%m%d%H%M%S)"
  echo "[INFO] Existing service directory found. Moving it to: $BACKUP_DIR"
  mkdir -p "$(dirname "$BACKUP_DIR")"
  mv "$SERVICE_PATH" "$BACKUP_DIR"
fi

echo "[INFO] Adding submodule..."
git submodule add -b "$BRANCH" "$REMOTE_URL" "$SERVICE_PATH"

if [[ -n "$BACKUP_DIR" ]]; then
  echo "[INFO] Restoring generated service files into the submodule working tree..."
  cp -a "$BACKUP_DIR"/. "$SERVICE_PATH"/
fi

(
  cd "$SERVICE_PATH"

  if ! git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    git checkout -B "$BRANCH"
  fi

  git add .
  if git diff --cached --quiet; then
    echo "[OK] No new files to commit inside audit worker submodule."
  else
    git commit -m "feat(audit-worker): add dedicated audit export worker service"
  fi

  echo "[INFO] Pushing audit worker submodule..."
  git push -u origin "$BRANCH"
)

git add .gitmodules "$SERVICE_PATH"

echo "[OK] Audit worker submodule is ready."
echo "[NEXT] Commit root repo:"
echo "      git commit -m \"feat(phase-3): add audit export worker submodule\""
