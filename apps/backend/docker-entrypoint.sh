#!/usr/bin/env sh
# Backend container entrypoint: apply database migrations, then run the app.
# Migrations are idempotent (`alembic upgrade head`), so this is safe to run on
# every container start. Any command passed to the container runs afterwards.
set -e

echo "[entrypoint] Applying database migrations (alembic upgrade head)…"
alembic upgrade head

echo "[entrypoint] Starting: $*"
exec "$@"
