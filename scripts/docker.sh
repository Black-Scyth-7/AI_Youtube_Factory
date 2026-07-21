#!/usr/bin/env bash
# Thin wrapper around docker compose for the project.
#   scripts/docker.sh up|down|logs|ps|build [args...]
set -euo pipefail
cd "$(dirname "$0")/.."
cmd="${1:-up}"; shift || true
case "$cmd" in
  up)    exec docker compose up --build "$@" ;;
  down)  exec docker compose down "$@" ;;
  logs)  exec docker compose logs -f "$@" ;;
  ps)    exec docker compose ps "$@" ;;
  build) exec docker compose build "$@" ;;
  *)     echo "Unknown command: $cmd" >&2; exit 1 ;;
esac
