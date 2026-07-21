#!/usr/bin/env bash
# Remove build artifacts, caches, and virtual environments.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Removing Node artifacts"
find . -type d \( -name node_modules -o -name .next -o -name .turbo -o -name dist \) \
  -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> Removing Python artifacts"
find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache \
  -o -name .ruff_cache -o -name .venv -o -name '*.egg-info' \) \
  -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> Clean complete."
