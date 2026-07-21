# syntax=docker/dockerfile:1
# AI YouTube Factory — Celery worker image. Build context is the repo root.

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app

FROM base AS deps
COPY apps/worker/pyproject.toml apps/worker/README.md ./
RUN uv pip install --system --no-cache -e "."

FROM base AS runtime
COPY --from=deps /usr/local /usr/local
COPY apps/worker/ ./

RUN groupadd --system app && useradd --system --gid app --home /app app \
    && chown -R app:app /app
USER app

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=5 \
    CMD celery -A worker.celery_app:celery_app inspect ping -d celery@$HOSTNAME || exit 1

CMD ["celery", "-A", "worker.celery_app:celery_app", "worker", "--loglevel=INFO"]
