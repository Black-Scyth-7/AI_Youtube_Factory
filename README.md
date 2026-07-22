# AI YouTube Factory

Production-grade SaaS platform that autonomously **researches, generates, edits,
optimizes, publishes, analyzes, and continuously improves** YouTube content using
AI. Built as a scalable, multi-tenant monorepo.

> **Status:** Phase 04 — Claude LLM Framework (on Phases 01–03).
> Adds the shared AI infrastructure every future capability depends on: a
> provider abstraction (Claude + a deterministic mock) behind a registry, a
> Jinja prompt engine with DB-backed versioning, conversation memory, structured
> output with validation retries, streaming (SSE), tool calling, a retry engine
> with circuit breaker and fallback, per-user/org/agent/project token
> accounting, cost tracking, Redis caching, and rate limiting — exposed via
> `/api/v1/llm/*` and dashboard pages. **No AI feature calls Anthropic directly;
> everything goes through the provider layer.** AI agents and the video pipeline
> arrive in later phases.

---

## Architecture at a glance

| Service      | Stack                                                  | Port |
| ------------ | ------------------------------------------------------ | ---- |
| **backend**  | FastAPI · Python 3.13 · SQLAlchemy 2 · Pydantic v2     | 8000 |
| **worker**   | Celery · RabbitMQ (broker) · Redis (backend)           | —    |
| **frontend** | Next.js (App Router) · TS · Tailwind · shadcn-style UI | 3000 |
| **admin**    | Next.js (App Router) · shared design system            | 3001 |
| PostgreSQL   | 17                                                     | 5432 |
| Redis        | 7                                                      | 6379 |
| RabbitMQ     | 4 (management UI 15672)                                | 5672 |

## Monorepo layout

```
ai-youtube-factory/
├─ apps/
│  ├─ backend/     FastAPI API + orchestration core
│  ├─ worker/      Celery background/scheduled/AI jobs
│  ├─ frontend/    Next.js web app
│  └─ admin/       Next.js admin console
├─ packages/
│  ├─ ui/                Design system (@ayf/ui)
│  ├─ shared/            Shared TS types/enums/utils (@ayf/shared)
│  ├─ config/            Env validation + feature flags (@ayf/config)
│  ├─ eslint-config/     Shared ESLint flat config
│  └─ typescript-config/ Shared tsconfig presets
├─ python/shared/  Shared Python enums/constants (ayf-shared)
├─ docker/         Dockerfiles for each service
├─ database/       PostgreSQL init + migration docs
├─ scripts/        setup / dev / lint / format / test / docker / reset / seed
├─ docs/           Architecture, setup, code style, roadmap, security
├─ infra/          Infrastructure-as-code (later phases)
├─ tests/          Cross-service / e2e placeholders
└─ .github/        CI/CD workflows
```

## Quick start

### With Docker (full stack)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend → http://localhost:3000
- Admin → http://localhost:3001
- API docs (Swagger) → http://localhost:8000/docs · ReDoc → /redoc
- Health → http://localhost:8000/api/v1/health · Readiness → /ready

### Local (without Docker)

```bash
pnpm install                                   # Node workspace
pnpm dev                                        # frontend + admin

# Backend
cd apps/backend && python -m venv .venv && .venv/Scripts/activate
pip install -e ".[dev]" && uvicorn app.main:app --reload

# Worker
cd apps/worker && pip install -e ".[dev]"
celery -A worker.celery_app:celery_app worker --loglevel=INFO
```

## Common commands

```bash
make setup        # install everything
make dev          # docker compose up
make test         # all test suites
make lint         # lint + typecheck everything
make format       # auto-format
make docker-up    # start stack
make docker-down  # stop stack
```

## Documentation

- [SETUP.md](docs/SETUP.md) — detailed environment setup
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design & conventions
- [AUTHENTICATION.md](docs/AUTHENTICATION.md) — auth flows, tokens, sessions
- [RBAC.md](docs/RBAC.md) — roles, permissions, organizations
- [DATABASE.md](docs/DATABASE.md) — schema, conventions, migrations, repositories
- [INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) — cache, events, tasks, storage, workflow
- [LLM.md](docs/LLM.md) — Claude LLM framework: providers, manager, accounting, API
- [PromptEngine.md](docs/PromptEngine.md) — prompt rendering, variables, versioning
- [Conversation.md](docs/Conversation.md) — conversations: runtime + persistence
- [Memory.md](docs/Memory.md) — working-context trimming & summarization
- [Providers.md](docs/Providers.md) — provider contract, registry, adding a provider
- [CODE_STYLE.md](docs/CODE_STYLE.md) — coding standards
- [CONTRIBUTING.md](CONTRIBUTING.md) — workflow & conventional commits
- [ROADMAP.md](docs/ROADMAP.md) — phased delivery plan
- [SECURITY.md](SECURITY.md) — security posture & reporting

## License

Proprietary — see [LICENSE](LICENSE).
