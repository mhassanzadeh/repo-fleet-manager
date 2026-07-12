#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <github-org-or-owner>" >&2
  echo "Example: $0 mhassanzadeh" >&2
  exit 1
fi

OWNER="$1"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Canonical submodule-to-repository mapping.
# Keep this list aligned with:
# - scripts/create-github-repos.sh
# - scripts/goftaroo-github-remote-audit.py
# - docs/05-devops/09-repository-catalog.md
#
# Important: do not derive repository names from submodule paths.
declare -A SUBMODULE_REPOS=(
  ["services/api-gateway"]="goftaroo-api-gateway"
  ["services/identity-service"]="goftaroo-identity-service"
  ["services/tenant-service"]="goftaroo-tenant-service"
  ["services/device-registry-service"]="goftaroo-device-registry-service"
  ["services/subscription-service"]="goftaroo-subscription-service"
  ["services/billing-service"]="goftaroo-billing-service"
  ["services/usage-metering-service"]="goftaroo-usage-metering-service"
  ["services/voice-session-service"]="goftaroo-voice-session-service"
  ["services/conversation-service"]="goftaroo-conversation-service"
  ["services/speech-provider-service"]="goftaroo-speech-provider-service"
  ["services/llm-gateway-service"]="goftaroo-llm-gateway-service"
  ["services/agent-orchestrator-service"]="goftaroo-agent-orchestrator-service"
  ["services/skill-registry-service"]="goftaroo-skill-registry-service"
  ["services/notification-service"]="goftaroo-notification-service"
  ["services/audit-export-worker-service"]="goftaroo-audit-export-worker-service"
  ["clients/kmp-client"]="goftaroo-kmp-client"
  ["clients/admin-dashboard"]="goftaroo-admin-dashboard"
  ["clients/user-dashboard"]="goftaroo-user-dashboard"
  ["clients/embedded-runtime"]="goftaroo-embedded-runtime"
  ["packages/shared-contracts"]="goftaroo-shared-contracts"
  ["infra/platform-infra"]="goftaroo-platform-infra"
)

ORDERED_PATHS=(
  "services/api-gateway"
  "services/identity-service"
  "services/tenant-service"
  "services/device-registry-service"
  "services/subscription-service"
  "services/billing-service"
  "services/usage-metering-service"
  "services/voice-session-service"
  "services/conversation-service"
  "services/speech-provider-service"
  "services/llm-gateway-service"
  "services/agent-orchestrator-service"
  "services/skill-registry-service"
  "services/notification-service"
  "services/audit-export-worker-service"
  "clients/kmp-client"
  "clients/admin-dashboard"
  "clients/user-dashboard"
  "clients/embedded-runtime"
  "packages/shared-contracts"
  "infra/platform-infra"
)

: > .gitmodules
for path in "${ORDERED_PATHS[@]}"; do
  repo="${SUBMODULE_REPOS[$path]}"
  url="git@github.com:${OWNER}/${repo}.git"
  {
    echo "[submodule \"$path\"]"
    printf "\tpath = %s\n" "$path"
    printf "\turl = %s\n" "$url"
  } >> .gitmodules

  if git -C "$path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$path" remote set-url origin "$url" 2>/dev/null || git -C "$path" remote add origin "$url"
  fi

done

git submodule sync --recursive

echo "[OK] Updated .gitmodules and initialized submodule origin URLs for owner: $OWNER"
echo "[NEXT] Review with: grep -n 'url =' .gitmodules && git submodule foreach 'git remote -v'"
echo "[NEXT] If audit worker has an embedded .git directory, run: ./scripts/normalize-audit-worker-submodule.sh --apply"
echo "[NEXT] Commit root change with: git add .gitmodules scripts/replace-submodule-remotes.sh scripts/create-github-repos.sh scripts/goftaroo-github-remote-audit.py scripts/goftaroo-github-remote-sync.sh scripts/normalize-audit-worker-submodule.sh && git commit -m 'fix(git): normalize repository catalog and submodule remotes'"
