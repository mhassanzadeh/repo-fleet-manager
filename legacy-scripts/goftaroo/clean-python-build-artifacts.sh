#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[INFO] Removing Python build artifacts from services..."

find services -type d \( \
  -name build -o \
  -name dist -o \
  -name '*.egg-info' -o \
  -name __pycache__ -o \
  -name .pytest_cache -o \
  -name .ruff_cache -o \
  -name .mypy_cache \
\) -prune -print -exec rm -rf {} +

echo "[OK] Python build artifacts removed."
