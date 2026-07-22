# Roadmap

Phased delivery. Each phase meets a Definition of Done (backend + frontend +
DB + tests + docs + Docker + CI) before the next begins.

| Phase  | Focus                                                                                                                                            | Status     |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- |
| **01** | **Project foundation** — monorepo, tooling, Docker, CI, shared packages, backend skeleton, web apps                                              | ✅ Done    |
| **02** | **Authentication & identity** — users, orgs, teams, RBAC, JWT, sessions, OAuth, API keys, invitations, audit, email                              | ✅ Done    |
| **03** | **Database & core infrastructure** — domain models, enhanced repositories, cache, events, tasks, storage, workflow, feature flags, API framework | ✅ Done    |
| **04** | **Claude LLM framework** — provider abstraction, prompt engine, conversation memory, structured output, streaming, tools, retry/circuit-breaker, token accounting, cost tracking, caching, rate limiting | ✅ Current |
| 05     | Storage providers — S3 / MinIO / R2 / GCS / Azure (behind the existing interface)                                                                | Planned    |
| 06     | AI agent framework — goals, memory, tools, planner, executor, reflection, retries, metrics                                                       | Planned    |
| 07     | Workflow engine (visual) — triggers, conditions, loops, parallel/merge, scheduler on the Phase 03 foundation                                     | Planned    |
| 08     | Video pipeline — research → publish → analytics → learning                                                                                       | Planned    |
| 09     | Observability — OpenTelemetry, Prometheus, Grafana, tracing                                                                                      | Planned    |
| 10     | Billing, plugin ecosystem, public API, mobile                                                                                                    | Planned    |

## Phase 04 — delivered

- LLM provider abstraction (`app/core/llm/`): `AnthropicProvider` (Claude) plus a
  deterministic `MockProvider` for offline tests, resolved through a registry.
  **No AI code calls Anthropic directly — everything goes through the provider
  layer.** Models are resolved from config, never hardcoded.
- Prompt engine: Jinja rendering with variable validation/sanitization,
  DB-backed templates with immutable versioning and rollback.
- Conversation memory: persisted conversations/messages + runtime rebuild;
  rolling summaries for context compression.
- Structured output: Pydantic validation with malformed-JSON recovery and a
  service-level validation-retry loop.
- Streaming (SSE), tool calling, retry engine (exponential backoff + circuit
  breaker + fallback), per-user/org/agent/project token accounting, cost
  tracking, Redis caching, and per-key rate limiting (RPM + concurrency).
- API (`/api/v1/llm/*`), frontend pages (catalog, prompts, playground, usage),
  secrets encrypted at rest (Fernet), migration `0003_llm_framework`.

See [LLM.md](./LLM.md), [PromptEngine.md](./PromptEngine.md),
[Conversation.md](./Conversation.md), [Memory.md](./Memory.md), and
[Providers.md](./Providers.md).

## Phase 05 — next up

- Storage providers — S3 / MinIO / R2 / GCS / Azure behind the Phase 03
  storage interface.
- Remaining Phase 03 breadth: the additional catalog models (subscription/plan/
  invoice/payment, notification/webhook, cost/usage records, render/queue jobs)
  and their services, built on the same repository/service/event scaffolding.
