# API Reference

All endpoints are under `/api/v1` and return the standard error envelope
(`{ "error": { code, message, details, request_id } }`). Auth is a Bearer access
token (see [AUTHENTICATION.md](./AUTHENTICATION.md)). Org-scoped operations enforce
RBAC. This page covers the AI surfaces; identity/content endpoints are documented
in their respective guides.

## Agents (`/api/v1`)

### Catalog & control

| Method & path                 | Purpose                              | Permission           |
| ----------------------------- | ------------------------------------ | -------------------- |
| `GET /agents`                 | List the agent catalog.              | authenticated        |
| `GET /agents/{slug}`          | Get one agent registration.          | authenticated        |
| `GET /agents/{slug}/versions` | List an agent's versions.            | authenticated        |
| `GET /agents/running`         | List running agents.                 | authenticated        |
| `GET /agents/health`          | Manager-wide health.                 | authenticated        |
| `POST /agents/start`          | Run an agent for a goal (persisted). | `agent.run` (if org) |
| `POST /agents/pause`          | Request a run pause.                 | authenticated        |
| `POST /agents/resume`         | Resume a paused run.                 | authenticated        |
| `POST /agents/stop`           | Cancel a run.                        | authenticated        |

`POST /agents/start` body: `{ slug, objective, organization_id?, priority?,
constraints?, expected_output?, success_criteria?, model?, max_iterations? }`
→ `{ run_id, goal_id, agent_slug, state, goal_status, output }`.

### Goals, tasks, tools

| Method & path                     | Purpose                                      |
| --------------------------------- | -------------------------------------------- |
| `GET /goals?organization_id=`     | List goals for an org.                       |
| `GET /goals/{goal_id}`            | Get a goal.                                  |
| `GET /tasks?run_id=`              | Tasks for a run.                             |
| `GET /tasks/{task_id}/executions` | Execution attempts for a task.               |
| `GET /tools?organization_id=`     | Tool catalog (built-in + org-defined).       |
| `POST /tools`                     | Register a tool definition (`agent.manage`). |
| `GET /tools/executions?run_id=`   | Tool executions for a run.                   |

### Reasoning, plans, reflection, evaluation

| Method & path                      | Purpose                             |
| ---------------------------------- | ----------------------------------- |
| `POST /plans/preview`              | Preview a plan without running.     |
| `POST /reason`                     | One-off reasoning trace for a task. |
| `GET /reflections/{run_id}`        | Reflection for a run.               |
| `GET /evaluations/{run_id}`        | Evaluation for a run.               |
| `GET /workflows/{workflow_run_id}` | A persisted agent workflow run.     |

### Knowledge & metrics

| Method & path                     | Purpose                                 | Permission       |
| --------------------------------- | --------------------------------------- | ---------------- |
| `GET /knowledge?organization_id=` | List knowledge documents.               | authenticated    |
| `POST /knowledge`                 | Create a document.                      | `agent.manage`   |
| `DELETE /knowledge/{document_id}` | Remove a document.                      | authenticated    |
| `GET /metrics?organization_id=`   | Aggregate agent metrics + live monitor. | `analytics.read` |

## LLM framework (`/api/v1/llm`)

See [LLM.md](./LLM.md) for detail. Summary: `POST /llm/chat`, `POST /llm/stream`
(SSE), `GET /llm/models`, `GET /llm/health`, `GET /llm/tools`, prompt CRUD
(`/llm/prompts…`), conversations (`/llm/conversations…`), and `GET /llm/usage` /
`GET /llm/costs`.

## Interactive docs

The full, always-current schema is served by the app: Swagger UI at `/docs`,
ReDoc at `/redoc`, and the OpenAPI document at `/api/v1/openapi.json`.
