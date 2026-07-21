# AI YouTube Factory — Backend

Production-grade **FastAPI** service (Python 3.13, SQLAlchemy 2, Pydantic v2,
async-first). This is the API and orchestration core of the AI YouTube Factory
platform.

## Layout

```
app/
  api/          Versioned HTTP API (api/v1)
  config/       pydantic-settings configuration + validation
  core/         DI container, LLM & storage provider abstractions
  db/           Async engine & session management
  exceptions/   Structured errors + global handlers
  logging/      Structured JSON logging + request context
  middleware/   Request id / trace id / timing
  models/       SQLAlchemy base + mixins (UUID PK, timestamps, soft delete)
  schemas/      Pydantic response schemas
  services/     Service layer (health probes, business logic)
  repositories/ Data-access layer (Repository pattern)
  workers/      Worker entrypoints
  tasks/        Task definitions
tests/          pytest suite
```

## Local development

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
pip install -e ".[dev]"

uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/api/v1/health
- Readiness: http://localhost:8000/api/v1/ready

## Quality

```bash
ruff check app tests
black --check app tests
mypy app
pytest
```

Configuration is validated on startup; missing/invalid required env vars fail
fast. See the repo-root `.env.example`.
