# AI YouTube Factory

Production-grade SaaS platform that autonomously **researches, generates, edits,
optimizes, publishes, analyzes, and continuously improves** YouTube content using
AI. Built as a scalable, multi-tenant monorepo.

> **Status:** Phase 09 — Observability (on Phases 01–08).
> The product path runs end to end: research → script → voiceover → render →
> publish → analytics → learning, driven by a workflow engine with conditions,
> loops, and parallel branches, on top of an autonomous agent framework and a
> provider-independent Claude LLM framework.
>
> Every external capability — LLM, speech, rendering, publishing, analytics, and
> object storage — sits behind an interface with a deterministic mock, so the
> whole system runs offline and CI needs no API key, no TTS account, and no
> YouTube credentials.
>
> Phase 09 adds metrics at `/metrics`, W3C-compatible tracing with optional
> OpenTelemetry export, and a Prometheus + Grafana stack behind a compose
> profile. Remaining: Phase 10 — billing UI, plugin ecosystem, public API, and
> mobile.

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
| RabbitMQ     | 3.13 LTS (management UI 15672)                         | 5672 |
| MinIO        | S3-compatible object storage (console 9001)            | 9000 |
| Prometheus   | 3.1 — `--profile observability`                        | 9090 |
| Grafana      | 11.5 — `--profile observability`                       | 3002 |

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
├─ infra/          Prometheus scrape config + alert rules, Grafana provisioning
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
- Metrics → http://localhost:8000/metrics (Prometheus exposition format)

Prometheus and Grafana are behind a profile, so they stay out of the default
stack:

```bash
docker compose --profile observability up
```

- Prometheus → http://localhost:9090
- Grafana → http://localhost:3002 — datasource and dashboards pre-provisioned

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
- [Memory.md](docs/Memory.md) — working-context trimming, summarization, agent memory
- [Providers.md](docs/Providers.md) — provider contract, registry, adding a provider
- [AgentFramework.md](docs/AgentFramework.md) — autonomous agent platform overview
- [Planning.md](docs/Planning.md) — planning, reasoning & execution engines
- [Reflection.md](docs/Reflection.md) — reflection, evaluation & monitoring
- [Tools.md](docs/Tools.md) — agent tool framework & execution policies
- [Knowledge.md](docs/Knowledge.md) — agent knowledge base
- [Workflow.md](docs/Workflow.md) — agent workflow runtime
- [WorkflowEngine.md](docs/WorkflowEngine.md) — the execution engine: conditions, loops, parallelism
- [Storage.md](docs/Storage.md) — storage providers: local, S3, MinIO, R2, GCS, Azure
- [Catalog.md](docs/Catalog.md) — billing, notifications, and jobs
- [VideoPipeline.md](docs/VideoPipeline.md) — research → script → render → publish → analytics
- [Observability.md](docs/Observability.md) — metrics, tracing, Prometheus, Grafana, alerting
- [Billing.md](docs/Billing.md) — plans, subscriptions, quotas, invoices, payments
- [API.md](docs/API.md) — AI API reference (agents + LLM)
- [CODE_STYLE.md](docs/CODE_STYLE.md) — coding standards
- [CONTRIBUTING.md](CONTRIBUTING.md) — workflow & conventional commits
- [ROADMAP.md](docs/ROADMAP.md) — phased delivery plan
- [SECURITY.md](SECURITY.md) — security posture & reporting

## License

Proprietary — see [LICENSE](LICENSE).
