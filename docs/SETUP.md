# Setup

## Prerequisites

| Tool             | Version | Notes                             |
| ---------------- | ------- | --------------------------------- |
| Node.js          | ≥ 20    | via `corepack` for pnpm           |
| pnpm             | ≥ 9     | `corepack enable`                 |
| Python           | 3.13    | backend & worker                  |
| uv               | latest  | Python package manager (or `pip`) |
| Docker + Compose | latest  | to run the full stack             |

## First-time setup

```bash
git clone <repo> ai-youtube-factory && cd ai-youtube-factory
cp .env.example .env        # fill in secrets as needed
make setup                  # installs Node + Python deps
```

## Run the stack

```bash
docker compose up --build
```

| URL                                | What                             |
| ---------------------------------- | -------------------------------- |
| http://localhost:3000              | Frontend                         |
| http://localhost:3001              | Admin                            |
| http://localhost:8000/docs         | Swagger UI                       |
| http://localhost:8000/redoc        | ReDoc                            |
| http://localhost:8000/api/v1/ready | Readiness (503 if a dep is down) |
| http://localhost:15672             | RabbitMQ management              |

## Backend only (no Docker)

```bash
cd apps/backend
python -m venv .venv && .venv/Scripts/activate    # Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload
pytest                                            # run tests
```

## Migrations

```bash
cd apps/backend
alembic revision --autogenerate -m "message"
alembic upgrade head
```

## Troubleshooting

- **Config error on startup** — a required env var is missing/invalid. Compare
  your `.env` against `.env.example`.
- **`/ready` returns 503** — one of PostgreSQL/Redis/RabbitMQ is not reachable;
  the response body names the failing component.
