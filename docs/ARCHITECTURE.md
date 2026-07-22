# Architecture

## Principles

- **Async-first** backend (FastAPI + SQLAlchemy 2 async + asyncpg).
- **Clean layering:** API → services → repositories → models. HTTP handlers stay
  thin; business logic lives in services; data access lives in repositories.
- **Provider abstractions** for every external dependency (LLM, storage, and
  later email/payments/search). Concrete SDKs live _only_ behind the provider
  layer, so swapping or adding a provider requires zero changes elsewhere.
- **Dependency Injection** (`dependency-injector`) makes the object graph
  explicit and overridable in tests.
- **Configuration is validated on startup** (`pydantic-settings`); missing or
  malformed required variables fail fast.
- **Structured JSON logging** with request/trace correlation on every log line.

## Services

### Backend (`apps/backend`)

FastAPI app assembled by `create_app()`:

- `config/` — validated settings singleton.
- `logging/` — JSON formatter + `contextvars`-based request/trace context.
- `middleware/` — assigns request id / trace id, measures duration.
- `exceptions/` — typed `AppError` hierarchy + global handlers → one error
  envelope (`{ "error": { code, message, details, request_id } }`).
- `core/llm` — **Claude LLM framework** (Phase 04): provider abstraction
  (Anthropic + deterministic mock) behind a registry, prompt engine, conversation
  memory, structured output, streaming, tools, retry/circuit-breaker, token
  accounting, cost tracking, caching, and rate limiting. No AI code calls
  Anthropic directly. See [LLM.md](./LLM.md).
- `core/storage` — storage provider interface + factory (implementations in a
  later phase).
- `core/di` — DI container wiring settings, engine, session factory.
- `models/` — declarative `Base` + mixins: **UUID PKs, created/updated audit
  timestamps, soft delete**, deterministic constraint naming for stable Alembic
  autogenerate.
- `db/` — async engine + transactional session scope.
- `api/v1/` — versioned routes: root, version, health, live, ready, auth &
  identity, and the LLM framework (`/llm/*`: chat, stream, models, prompts,
  conversations, usage, costs).

### Worker (`apps/worker`)

Celery app with RabbitMQ broker + Redis result backend. Reliability defaults:
late acks, reject-on-worker-lost, bounded retries, and a declared **dead-letter
queue**. Beat schedule reserved for future AI jobs.

### Frontend & Admin (`apps/frontend`, `apps/admin`)

Next.js App Router. Shared `@ayf/ui` design system (CSS-variable theming, dark
mode default via `next-themes`), React Query, Zustand, Framer Motion. Frontend
ships the landing page, dashboard shell (sidebar + top nav), auth layout, the
LLM pages (model catalog & provider health, prompt library/editor, streaming
playground, usage & cost dashboard, conversation viewer), and the standard
`not-found` / `loading` / `error` routes.

## Data flow (target pipeline)

```
Research → Idea → Outline → Script → Fact Check → Storyboard → Scene Planning
→ Image Gen → Video Gen → Voice Gen → Editing → Captions → Thumbnail → SEO
→ Publishing → Analytics → Learning → (repeat)
```

Each stage becomes an autonomous agent orchestrated by the worker + workflow
engine in later phases. The stage order is encoded once in `ayf_shared`
(Python) and `@ayf/shared` (TS).

## Cross-cutting

- **Observability:** structured logs now; OpenTelemetry/Prometheus later.
- **Security:** JWT/OAuth/RBAC interfaces are placeholders in Phase 01.
- **Versioned API** under `/api/v1` with OpenAPI, Swagger (`/docs`), ReDoc.
