# Roadmap

Phased delivery. Each phase meets a Definition of Done (backend + frontend +
DB + tests + docs + Docker + CI) before the next begins.

| Phase  | Focus                                                                                                                                            | Status     |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- |
| **01** | **Project foundation** — monorepo, tooling, Docker, CI, shared packages, backend skeleton, web apps                                              | ✅ Done    |
| **02** | **Authentication & identity** — users, orgs, teams, RBAC, JWT, sessions, OAuth, API keys, invitations, audit, email                              | ✅ Done    |
| **03** | **Database & core infrastructure** — domain models, enhanced repositories, cache, events, tasks, storage, workflow, feature flags, API framework | ✅ Current |
| 04     | LLM provider layer — Claude integration behind the abstraction (base/claude/factory/prompts/memory/tokenizer/cache)                              | Planned    |
| 05     | Storage providers — S3 / MinIO / R2 / GCS / Azure (behind the existing interface)                                                                | Planned    |
| 06     | AI agent framework — goals, memory, tools, planner, executor, reflection, retries, metrics                                                       | Planned    |
| 07     | Workflow engine (visual) — triggers, conditions, loops, parallel/merge, scheduler on the Phase 03 foundation                                     | Planned    |
| 08     | Video pipeline — research → publish → analytics → learning                                                                                       | Planned    |
| 09     | Observability — OpenTelemetry, Prometheus, Grafana, tracing                                                                                      | Planned    |
| 10     | Billing, plugin ecosystem, public API, mobile                                                                                                    | Planned    |

## Phase 04 — next up

- Implement the LLM provider layer (Claude) behind the Phase 01 abstraction:
  `base` / `claude` / `factory` / `prompts` / `memory` / `tokenizer` / `cache`.
- Store prompts in the database with versioning; track cost/latency/token usage.
- Register real workflow node handlers (LLM calls) on the Phase 03 engine.
- Remaining Phase 03 breadth: the additional catalog models (subscription/plan/
  invoice/payment, notification/webhook, cost/usage records, render/queue jobs)
  and their services, built on the same repository/service/event scaffolding.
