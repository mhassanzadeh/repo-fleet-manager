#!/usr/bin/env bash
set -euo pipefail

OWNER="${1:-}"
shift || true

if [[ -z "$OWNER" ]]; then
  echo "Usage: $0 <github-org-or-owner> [--check] [--create-missing] [--sync-remotes] [--sync-local-mirrors] [--push] [--apply]" >&2
  echo "Examples:" >&2
  echo "  $0 mhassanzadeh --check" >&2
  echo "  $0 mhassanzadeh --create-missing" >&2
  echo "  $0 mhassanzadeh --apply --create-missing --sync-remotes" >&2
  echo "  $0 mhassanzadeh --apply --push" >&2
  exit 1
fi

CHECK=false
CREATE_MISSING=false
SYNC_REMOTES=false
PUSH=false
SYNC_LOCAL_MIRRORS=false
APPLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK=true ;;
    --create-missing) CREATE_MISSING=true ;;
    --sync-remotes) SYNC_REMOTES=true ;;
    --sync-local-mirrors) SYNC_LOCAL_MIRRORS=true ;;
    --push) PUSH=true ;;
    --apply) APPLY=true ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run_or_echo() {
  if [[ "$APPLY" == true ]]; then
    echo "+ $*"
    "$@"
  else
    echo "[DRY-RUN] $*"
  fi
}

if [[ "$CHECK" == true ]]; then
  echo "[CHECK] Local catalog/submodule audit"
  ./scripts/goftaroo-github-remote-audit.py --owner "$OWNER" || true
  if command -v gh >/dev/null 2>&1; then
    echo
    echo "[CHECK] GitHub repository existence"
    ./scripts/create-github-repos.sh "$OWNER" --dry-run
  else
    echo
    echo "[WARN] gh is not installed; GitHub existence cannot be checked here."
  fi
fi

if [[ "$CREATE_MISSING" == true ]]; then
  command -v gh >/dev/null 2>&1 || { echo "GitHub CLI 'gh' is required." >&2; exit 1; }
  gh auth status >/dev/null
  if [[ "$APPLY" == true ]]; then
    ./scripts/create-github-repos.sh "$OWNER"
  else
    ./scripts/create-github-repos.sh "$OWNER" --dry-run
  fi
fi

if [[ "$SYNC_REMOTES" == true ]]; then
  run_or_echo ./scripts/replace-submodule-remotes.sh "$OWNER"
fi

if [[ "$SYNC_LOCAL_MIRRORS" == true ]]; then
  run_or_echo ./scripts/normalize-local-git-remotes.sh
fi

if [[ "$PUSH" == true ]]; then
  echo "[INFO] Pushing submodules must happen after each submodule has its own commit."
  echo "[INFO] This step pushes only existing commits/branches; it does not auto-commit."
  for path in $(git config --file .gitmodules --get-regexp path | awk '{print $2}'); do
    if git -C "$path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      branch="$(git -C "$path" branch --show-current || true)"
      if [[ -z "$branch" ]]; then
        echo "[SKIP] $path is detached; push manually after choosing a branch."
        continue
      fi
      run_or_echo git -C "$path" push -u origin "$branch"
    else
      echo "[SKIP] $path is not an initialized git worktree."
    fi
  done
  root_branch="$(git branch --show-current || true)"
  if [[ -n "$root_branch" ]]; then
    run_or_echo git push -u origin "$root_branch"
  fi
fi

if [[ "$CHECK" == false && "$CREATE_MISSING" == false && "$SYNC_REMOTES" == false && "$SYNC_LOCAL_MIRRORS" == false && "$PUSH" == false ]]; then
  echo "Nothing to do. Use --check, --create-missing, --sync-remotes, or --push."
  exit 1
fi

if [[ "$APPLY" == false ]]; then
  echo
  echo "[INFO] Dry-run complete. Add --apply to perform create/sync/push steps after reviewing output."
fi
