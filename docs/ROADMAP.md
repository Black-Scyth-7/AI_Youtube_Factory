# Roadmap

Phased delivery. Each phase meets a Definition of Done (backend + frontend +
DB + tests + docs + Docker + CI) before the next begins.

| Phase  | Focus                                                                                                               | Status     |
| ------ | ------------------------------------------------------------------------------------------------------------------- | ---------- |
| **01** | **Project foundation** — monorepo, tooling, Docker, CI, shared packages, backend skeleton, web apps                 | ✅ Done    |
| **02** | **Authentication & identity** — users, orgs, teams, RBAC, JWT, sessions, OAuth, API keys, invitations, audit, email | ✅ Current |
| 03     | Channels & content model — YouTube channels, projects, and the video entity graph                                   | Planned    |
| 04     | LLM provider layer — Claude integration behind the abstraction (base/claude/factory/prompts/memory/tokenizer/cache) | Planned    |
| 05     | Storage providers — S3 / MinIO / R2 / local                                                                         | Planned    |
| 06     | AI agent framework — goals, memory, tools, planner, executor, reflection, retries, metrics                          | Planned    |
| 07     | Workflow engine — nodes, triggers, conditions, loops, parallel/merge, scheduler                                     | Planned    |
| 08     | Video pipeline — research → publish → analytics → learning                                                          | Planned    |
| 09     | Observability — OpenTelemetry, Prometheus, Grafana, tracing                                                         | Planned    |
| 10     | Billing, teams, plugin ecosystem, public API, mobile                                                                | Planned    |

## Phase 03 — next up

- Define the content entity graph (YouTube channel, project, video, asset) on
  the ORM base, org-scoped, with the same UUID/audit/soft-delete conventions.
- Repository + service layers for those entities behind RBAC permissions.
- Frontend: organization selection, member/team management, account settings
  (sessions + API keys) UI, and data-backed dashboard widgets.
- Wire the readiness probe and audit views to the live schema.
