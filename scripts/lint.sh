#!/usr/bin/env bash
# Lint and type-check all code.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Node lint + typecheck"
pnpm lint
pnpm typecheck

echo "==> Backend ruff + mypy"
( cd apps/backend && ruff check app tests && mypy app )

echo "==> Worker ruff + mypy"
( cd apps/worker && ruff check worker tests && mypy worker )

echo "==> Lint complete."
