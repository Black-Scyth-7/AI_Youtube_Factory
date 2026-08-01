# Roadmap

Phased delivery. Each phase meets a Definition of Done (backend + frontend +
DB + tests + docs + Docker + CI) before the next begins.

| Phase  | Focus                                                                                                                                                                                                      | Status  |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| **01** | **Project foundation** — monorepo, tooling, Docker, CI, shared packages, backend skeleton, web apps                                                                                                        | ✅ Done |
| **02** | **Authentication & identity** — users, orgs, teams, RBAC, JWT, sessions, OAuth, API keys, invitations, audit, email                                                                                        | ✅ Done |
| **03** | **Database & core infrastructure** — domain models, enhanced repositories, cache, events, tasks, storage, workflow, feature flags, API framework                                                           | ✅ Done |
| **04** | **Claude LLM framework** — provider abstraction, prompt engine, conversation memory, structured output, streaming, tools, retry/circuit-breaker, token accounting, cost tracking, caching, rate limiting   | ✅ Done |
| **05** | **AI agent framework** — BaseAgent, manager, registry, planner, reasoner, executor, reflection, evaluation, memory, knowledge, tools, policies, scheduler, workflows, multi-agent coordination, monitoring | ✅ Done |
| **06** | **Storage providers & catalog domain** — S3/MinIO/R2/GCS/Azure, billing, notifications, jobs                                                                                                               | ✅ Done |
| **07** | **Workflow engine** — triggers, conditions, loops, parallel/merge, scheduler on the Phase 03 foundation                                                                                                    | ✅ Done |
| **08** | **Video pipeline** — research → script → render → publish → analytics → learning                                                                                                                           | ✅ Done |
| **09** | **Observability** — metrics, W3C tracing, OpenTelemetry export, Prometheus, Grafana, alerting                                                                                                              | ✅ Done |
| **10** | **Billing, plugin ecosystem, public API, mobile**                                                                                                                                                          | ✅ Done |

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

## Phase 06 — delivered

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

**Delivered — catalog models and services**

- Billing: `Plan`, `Subscription`, `Invoice`, `Payment`, plus `UsageRecord` and
  `CostRecord`. Money is stored as integer minor units, never floats; overage
  rounds `ROUND_HALF_UP` at the single point a fractional total becomes a
  charge. Closing a period stamps the usage it consumed, so invoicing twice
  cannot bill the same usage again, and `record_payment` is idempotent on the
  provider's payment id so a replayed webhook cannot double-credit an invoice.
- Notifications: `Notification`, `NotificationPreference`, and outbound
  `Webhook`/`WebhookDelivery`. Webhook secrets are returned once and stored
  hashed; deliveries back off on a fixed schedule and are marked exhausted
  rather than retried forever.
- Jobs: `QueueJob` as the durable record of background work — separate from the
  broker that carries it — and `RenderJob` for media. Both success and failure
  publish `RenderFinished`, distinguished by its `success` flag.
- Migration `0005_catalog` adds twelve tables. Verified against PostgreSQL 17:
  `upgrade head` creates them all and `downgrade 0004_agent` removes them.
- 45 service tests covering the quota, invoicing, refund, retry and state
  machine rules, and [Catalog.md](./Catalog.md).

## Phase 07 — delivered

- Edge conditions are now **evaluated**. `WorkflowEdge.condition` existed from
  Phase 03 but was never read, so the executor ran every node regardless and an
  authored condition had no effect. A false condition prunes the branch behind
  it, skipping propagates to nodes reachable only through it, and a merge runs
  if any branch survived.
- Conditions are parsed to an AST and walked rather than `eval`'d. A character
  allow-list around `eval` is not enough: one permitting `*` still admits
  `9**9**9**9`, which passes the filter and then hangs the worker. The evaluator
  bounds the exponent, length and nesting depth. The agent `CalculatorTool` had
  that exact shape and now uses the same evaluator.
- Independent nodes run concurrently by dependency level, loops expand over a
  collection with the loop variables scoped to each pass, and every node writes a
  `WorkflowNodeExecution` row — status, iteration, output, error, skip reason —
  which is what a visual editor replays.
- `WorkflowTrigger` starts runs manually, on a cron schedule, or from an internal
  event, reusing the agent scheduler's cron matcher rather than a second
  implementation.
- Migration `0006_workflow`, 42 engine tests, and
  [WorkflowEngine.md](./WorkflowEngine.md).

## Phase 08 — delivered

- The product path end to end: research → script → voiceover → render → publish
  → analytics → learning, with each stage a separate method so a run resumes at
  the stage that failed rather than repeating an expensive render.
- Four provider Protocols — speech, render, publish, analytics — each with a
  deterministic mock, mirroring the LLM framework. The whole pipeline therefore
  runs offline and CI needs no TTS key, renderer or YouTube account. Mocks write
  real bytes through the storage layer, so that path is exercised rather than
  stubbed.
- One `Publication` per video per platform, enforced by a unique constraint, so
  re-publishing updates rather than duplicates; a provider failure is recorded on
  the publication before being re-raised. Analytics upsert on
  `(publication_id, measured_on)`, so re-fetching a day updates that row while
  separate days stay separate.
- `PerformanceLesson` closes the loop with explainable observations an agent can
  consult when planning the next video.
- Migration `0007_pipeline`, 26 tests, and [VideoPipeline.md](./VideoPipeline.md).

## Phase 09 — delivered

- **Metrics** at `GET /metrics` in the Prometheus text format, covering HTTP,
  LLM spend and tokens, pipeline stages, workflow nodes, and storage. The
  registry is written in process rather than pulled in: `prometheus_client`'s
  global registry does not survive a test suite that builds the application
  twice, since the second definition of a metric aborts the process.
- **Cardinality is bounded by construction.** HTTP metrics are labelled by the
  matched route template, never the request path, so `/agents/{slug}` is one
  series rather than one per agent; unmatched requests share a single series, so
  a 404 probe sweep cannot create one per probed path. Every metric also caps
  itself at 2000 series and logs once on overflow — losing a label value beats
  losing the process.
- **Tracing** follows W3C Trace Context. An inbound `traceparent` continues the
  caller's trace, spans nest through a context variable, and each completed span
  is logged, so traces are usable with no collector running. Installing the
  `[otel]` extra and setting `OTEL_ENABLED` additionally exports over OTLP; a
  missing SDK warns and keeps serving rather than refusing to start.
- **Two bugs found on the way in.** The access log was emitted after a `finally`
  that had already cleared the request context, so every *successful* request
  logged a null request id — the one field that makes an access log searchable;
  failures were unaffected, which is why it went unnoticed. And `X-Trace-ID` was
  generated separately from the span, so the two correlation headers on the same
  response named different traces.
- **Prometheus and Grafana** behind a compose profile, with a provisioned
  datasource, two dashboards, and 8 alert rules — all on symptoms rather than
  causes, and all validated with `promtool`.
- `/metrics` is guarded by `METRICS_TOKEN` (compared in constant time) for
  deployments that cannot restrict it at the network layer.
- 72 tests and [Observability.md](./Observability.md).

## Phase 10 — delivered

**Billing — delivered.** Phase 06 left the models and services with no way to
reach them; there was no billing API at all.

- A `PaymentProvider` Protocol — charge, refund, verify webhook — with a
  registry and a deterministic mock, the same shape as the LLM, storage, and
  pipeline abstractions. Billing runs offline and CI needs no account. The
  mock's ids are derived from the request rather than random, so the
  idempotency downstream is genuinely exercised; its declines are reachable on
  demand, because the interesting billing code is the failure path.
- Eight endpoints: the public plan catalogue, subscribe/cancel, usage against
  quota, invoices, pay, refund, and the provider callback. Split
  `billing.read` from `billing.manage` — seeing the bill is not the same as
  being able to change the plan.
- **A decline answers 200**, not an error: the request was handled correctly and
  the caller needs the reason rather than something to retry against a card that
  will keep failing.
- **Callbacks are verified over the raw body** before anything is read out of
  them; a bad signature is 401 and an empty secret fails closed. A replayed
  event is a no-op that still answers 204, because a provider that gets an error
  for an event already handled retries forever.
- Two bugs caught while wiring the routes: the cancel endpoint passed an
  organization id to a service that cancels by *subscription* id, which would
  have 404'd every time; and the subscription schema spelled `canceled_at` where
  the model spells `cancelled_at` — with `from_attributes` that does not error,
  the field just stays null forever.
- A `/dashboard/billing` console, 35 tests, and [Billing.md](./Billing.md).

**Public API.** `ApiKeyService.authenticate` already existed and nothing called
it — keys could be created and listed but could not authenticate anything.
Adds `/api/public/v1`: a versioned surface with its own payload models,
authenticated by scoped key, with tenancy verified on every object rather than
relying on unguessable ids. A write scope does not imply the matching read
scope, an unknown scope is refused at creation instead of silently dropped, and
another organization's object is a 404 rather than a 403 — confirming an id
exists is itself a disclosure. Two rate-limiter defects fixed on the way: one
transient Redis error permanently disabled rate limiting for the life of the
process, and there was no `Retry-After`, so a limited client's usual guess is
"retry immediately".

**Plugin ecosystem.** Manifest-first, so the host validates before it executes.
A plugin cannot crash the host (exception boundary), hang it (per-plugin
timeout), or reach what it never declared (capabilities). Network and LLM access
are refused unless an operator allow-lists the plugin by name, so a formatter
cannot exfiltrate anything even if hostile. Handlers get a copy of a plain dict,
never an ORM entity — a live entity would let a plugin write through a
relationship, outside the capability model entirely. Three built-ins ship, and
the publish chain is wired into the pipeline.

**Mobile.** Delivered as an installable PWA, not a native app — stated plainly
because there is no store build here and nothing produces one. The actual defect
was that the sidebar is `hidden md:block`, so below that breakpoint the
dashboard had *no navigation at all*. Adds a bottom bar and sheet, a shared
nav-item list (two copies had already drifted — the billing console shipped
unreachable), a web manifest with a maskable icon, and a service worker that
caches the app shell and **never** API responses: Cache Storage is shared across
accounts on a device, so caching them would serve one user's data to the next.

96 tests across billing, the public API, and plugins, plus
[Billing.md](./Billing.md),
[PublicAPI.md](./PublicAPI.md), [Plugins.md](./Plugins.md), and
[Mobile.md](./Mobile.md).
