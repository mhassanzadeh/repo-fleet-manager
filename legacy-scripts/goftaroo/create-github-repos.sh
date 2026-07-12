#!/usr/bin/env bash
set -euo pipefail

OWNER="${1:-}"
MODE="${2:-}"

if [[ -z "$OWNER" ]]; then
  echo "Usage: $0 <github-org-or-owner> [--dry-run]" >&2
  echo "Example: $0 mhassanzadeh --dry-run" >&2
  exit 1
fi

DRY_RUN=false
if [[ "$MODE" == "--dry-run" ]]; then
  DRY_RUN=true
elif [[ -n "$MODE" ]]; then
  echo "Unknown option: $MODE" >&2
  echo "Usage: $0 <github-org-or-owner> [--dry-run]" >&2
  exit 1
fi

# Canonical repository names. Keep this list aligned with:
# - scripts/replace-submodule-remotes.sh
# - scripts/goftaroo-github-remote-audit.py
# - docs/05-devops/09-repository-catalog.md
#
# Important: repository names are NOT generated from submodule paths.
REPOS=(
  "goftaroo-platform"
  "goftaroo-api-gateway"
  "goftaroo-identity-service"
  "goftaroo-tenant-service"
  "goftaroo-device-registry-service"
  "goftaroo-subscription-service"
  "goftaroo-billing-service"
  "goftaroo-usage-metering-service"
  "goftaroo-voice-session-service"
  "goftaroo-conversation-service"
  "goftaroo-speech-provider-service"
  "goftaroo-llm-gateway-service"
  "goftaroo-agent-orchestrator-service"
  "goftaroo-skill-registry-service"
  "goftaroo-notification-service"
  "goftaroo-audit-export-worker-service"
  "goftaroo-kmp-client"
  "goftaroo-admin-dashboard"
  "goftaroo-user-dashboard"
  "goftaroo-embedded-runtime"
  "goftaroo-shared-contracts"
  "goftaroo-platform-infra"
)

if [[ "$DRY_RUN" == false ]]; then
  command -v gh >/dev/null 2>&1 || {
    echo "GitHub CLI 'gh' is required. Install it and run 'gh auth login'." >&2
    exit 1
  }
  gh auth status >/dev/null
fi

for repo in "${REPOS[@]}"; do
  full="$OWNER/$repo"
  if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY-RUN] gh repo view $full || gh repo create $full --private --disable-wiki --description 'Goftaroo platform repository: $repo'"
  else
    if gh repo view "$full" >/dev/null 2>&1; then
      echo "[SKIP] Repository already exists: $full"
    else
      gh repo create "$full" --private --disable-wiki --description "Goftaroo platform repository: $repo"
      echo "[ OK ] Created $full"
    fi
  fi
done

if [[ "$DRY_RUN" == true ]]; then
  echo "[INFO] Dry-run complete. Re-run without --dry-run to create missing repositories."
else
  echo "[INFO] Repository existence pass complete."
fi
