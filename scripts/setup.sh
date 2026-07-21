#!/usr/bin/env bash
# Install all workspace dependencies (Node + Python backend/worker).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Copying .env from template (if missing)"
[ -f .env ] || cp .env.example .env

echo "==> Installing Node workspace (pnpm)"
pnpm install

echo "==> Installing backend (uv)"
( cd apps/backend && uv pip install --system -e ".[dev]" 2>/dev/null || pip install -e ".[dev]" )

echo "==> Installing worker (uv)"
( cd apps/worker && uv pip install --system -e ".[dev]" 2>/dev/null || pip install -e ".[dev]" )

echo "==> Setup complete."
