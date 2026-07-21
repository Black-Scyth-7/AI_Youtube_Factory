# syntax=docker/dockerfile:1
# AI YouTube Factory — backend image (FastAPI, Python 3.13, uv).
# Build context is the repository root.

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app

# ---- dependencies layer (cached on lockfile/manifest changes) ----
FROM base AS deps
COPY apps/backend/pyproject.toml apps/backend/README.md ./
RUN uv pip install --system --no-cache -e ".[dev]" || uv pip install --system --no-cache -e "."

# ---- runtime image ----
FROM base AS runtime
# Copy the resolved site-packages from the deps stage.
COPY --from=deps /usr/local /usr/local
COPY apps/backend/ ./

RUN groupadd --system app && useradd --system --gid app --home /app app \
    && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
