#!/usr/bin/env bash
set -euo pipefail

if command -v tree >/dev/null 2>&1; then
  tree -a -I '.git|objects|node_modules|build|dist|.gradle|target' -L 4
else
  find .     -path './.git' -prune -o     -path './_git-remotes/*/objects' -prune -o     -path './*/node_modules' -prune -o     -print | sed 's#^./##' | sort | head -300
fi
