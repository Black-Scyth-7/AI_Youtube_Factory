# Roadmap

Phased delivery. Each phase meets a Definition of Done (backend + frontend +
DB + tests + docs + Docker + CI) before the next begins.

| Phase  | Focus                                                                                                                                                                                                      | Status         |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| **01** | **Project foundation** — monorepo, tooling, Docker, CI, shared packages, backend skeleton, web apps                                                                                                        | ✅ Done        |
| **02** | **Authentication & identity** — users, orgs, teams, RBAC, JWT, sessions, OAuth, API keys, invitations, audit, email                                                                                        | ✅ Done        |
| **03** | **Database & core infrastructure** — domain models, enhanced repositories, cache, events, tasks, storage, workflow, feature flags, API framework                                                           | ✅ Done        |
| **04** | **Claude LLM framework** — provider abstraction, prompt engine, conversation memory, structured output, streaming, tools, retry/circuit-breaker, token accounting, cost tracking, caching, rate limiting   | ✅ Done        |
| **05** | **AI agent framework** — BaseAgent, manager, registry, planner, reasoner, executor, reflection, evaluation, memory, knowledge, tools, policies, scheduler, workflows, multi-agent coordination, monitoring | ✅ Current     |
| **06** | **Storage providers** — S3 / MinIO / R2 / GCS / Azure behind the existing interface                                                                                                                        | 🚧 In progress |
| 07     | Workflow engine (visual) — triggers, conditions, loops, parallel/merge, scheduler on the Phase 03 foundation                                                                                               | Planned        |
| 08     | Video pipeline — research → publish → analytics → learning                                                                                                                                                 | Planned        |
| 09     | Observability — OpenTelemetry, Prometheus, Grafana, tracing                                                                                                                                                | Planned        |
| 10     | Billing, plugin ecosystem, public API, mobile                                                                                                                                                              | Planned        |

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

## Phase 05 — delivered

- Generic, provider-independent AI agent platform (`app/agents/`): `BaseAgent`
  lifecycle (initialize → plan → reason → execute → reflect → learn → evaluate →
  finish, plus pause/resume/cancel/health), `AgentManager`, `AgentRegistry`
  (versioning + discovery), planning (goal decomposition + dependency graph +
  replanning), the structured reasoning pipeline, execution (retries, timeouts,
  policy enforcement), reflection (lessons persisted for future runs), and
  six-dimension evaluation.
- Scoped agent memory, a separate searchable knowledge base, an `AgentTool`
  framework with built-in tools, execution policies (allow/deny, cost/token/step
  ceilings, approval gates), a sandbox, a scheduler (immediate/delayed/recurring/
  cron), an in-process workflow step engine, multi-agent coordination
  (supervisor/worker/observer), inter-agent communication, monitoring, and agent
  events on the shared bus.
- **Agents reach models only through the Phase 04 LLM framework** — the whole
  engine runs offline against the mock provider.
- 15 DB tables + migration `0004_agent_framework`, ten services, the `/api/v1`
  agent endpoints, frontend pages (console, tools, knowledge, metrics), and docs.

See [AgentFramework.md](./AgentFramework.md), [Planning.md](./Planning.md),
[Reflection.md](./Reflection.md), [Tools.md](./Tools.md),
[Knowledge.md](./Knowledge.md), [Workflow.md](./Workflow.md), and
[API.md](./API.md).

## Phase 06 — in progress

**Delivered — storage providers**

- `S3StorageProvider` serving AWS S3, MinIO and Cloudflare R2 through one
  implementation (they share the API and differ only in endpoint and addressing
  style), `GCSStorageProvider` and `AzureStorageProvider` — all behind the
  existing `StorageClient` Protocol.
- Cloud SDKs are optional extras (`.[s3]`, `.[gcs]`, `.[azure]`, `.[storage]`);
  the default local backend needs none. Providers register at import but load
  their SDK only when an operation runs, so a missing extra surfaces on first
  use with the install command, not as an import failure.
- Fixed a latent mismatch: `storage_backend` accepted `gcs` and `azure` while
  `StorageProvider` had no such members, so either value passed configuration
  validation and then raised `ValueError` when the client was built. A test now
  asserts the enum and the settings literal stay in step.
- MinIO in `docker-compose.yml` for local development, storage settings in
  `.env.example`, and [Storage.md](./Storage.md).
- Unit tests (offline, always run) plus S3 integration tests verified against a
  real MinIO instance — byte-exact round trips, overwrite, `NotFoundError`,
  delete-absent as a no-op, and a presigned URL fetched over HTTP.

**Remaining**

- The additional catalog models (subscription/plan/invoice/payment,
  notification/webhook, cost/usage records, render/queue jobs) and their
  services, built on the same repository/service/event scaffolding.
