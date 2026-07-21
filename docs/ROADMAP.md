# Roadmap

Phased delivery. Each phase meets a Definition of Done (backend + frontend +
DB + tests + docs + Docker + CI) before the next begins.

| Phase  | Focus                                                                                                               | Status     |
| ------ | ------------------------------------------------------------------------------------------------------------------- | ---------- |
| **01** | **Project foundation** — monorepo, tooling, Docker, CI, shared packages, backend skeleton, web apps                 | ✅ Current |
| 02     | Data model & persistence — organizations, users, channels, videos; repositories; migrations                         | Planned    |
| 03     | AuthN/AuthZ — JWT, OAuth (Google/YouTube), RBAC, sessions, rate limiting                                            | Planned    |
| 04     | LLM provider layer — Claude integration behind the abstraction (base/claude/factory/prompts/memory/tokenizer/cache) | Planned    |
| 05     | Storage providers — S3 / MinIO / R2 / local                                                                         | Planned    |
| 06     | AI agent framework — goals, memory, tools, planner, executor, reflection, retries, metrics                          | Planned    |
| 07     | Workflow engine — nodes, triggers, conditions, loops, parallel/merge, scheduler                                     | Planned    |
| 08     | Video pipeline — research → publish → analytics → learning                                                          | Planned    |
| 09     | Observability — OpenTelemetry, Prometheus, Grafana, tracing                                                         | Planned    |
| 10     | Billing, teams, plugin ecosystem, public API, mobile                                                                | Planned    |

## Phase 02 — next up

- Define core entities (organization, user, channel, video, job) on the ORM base
  with UUID PKs, audit timestamps, and soft delete.
- Implement the repository layer and service layer for those entities.
- First Alembic migration(s); wire the readiness probe to real schema.
- Frontend: data-backed dashboard widgets via the typed API client.
