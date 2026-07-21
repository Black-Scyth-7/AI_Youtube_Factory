#!/usr/bin/env bash
# Auto-format all code (Prettier + Black + Ruff --fix).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Prettier"
pnpm format

echo "==> Backend black + ruff --fix"
( cd apps/backend && black app tests && ruff check --fix app tests )

echo "==> Worker black + ruff --fix"
( cd apps/worker && black worker tests && ruff check --fix worker tests )

echo "==> Format complete."
