#!/usr/bin/env bash
# Bring up the full local stack via Docker Compose.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
exec docker compose up --build
