# AI Agent Framework

The agent framework (Phase 05) is the generic, provider-independent platform every
future AI capability is built on — research, scripting, SEO, analytics, video
generation, and enterprise workflows. It lives under `apps/backend/app/agents/`
(runtime), with persistence in `app/models/agent.py`, services in
`app/services/agent/`, and the API under `/api/v1` (`/agents`, `/goals`, `/tasks`,
`/tools`, `/reflections`, `/evaluations`, `/workflows`, `/metrics`).

> **Provider independence:** agents reason, plan, and reflect **only** through the
> Phase 04 LLM framework (`app.core.llm`). No agent touches a provider or the
> Anthropic SDK directly, so the whole engine runs offline against the mock
> provider and swaps models via config.

## Architecture

```
                         ┌──────────────── AgentManager ───────────────┐
   AgentRegistry ──────▶ │  create / run / pause / resume / cancel      │
   (discover agents)     │  health · tracks running agents              │
                         └──────────────────────┬───────────────────────┘
                                                │ run(goal)
                                                ▼
        ┌──────────────────────────  BaseAgent  ──────────────────────────┐
        │ initialize → plan → (reason → execute)* → reflect → learn        │
        │            → evaluate → finish   (pause/resume/cancel/health)    │
        └───┬─────────┬──────────┬───────────┬───────────┬──────────┬──────┘
            ▼         ▼          ▼           ▼           ▼          ▼
        Planner   Reasoner   Executor    Reflector   Evaluator   (events)
            │         │          │           │           │
            │         │          ▼           │           │
            │         │   Tools · Policies · Sandbox     │
            ▼         ▼          ▼           ▼           ▼
        ┌──────────────────  AgentContext  ───────────────────┐
        │ identity · goal · config · Memory · Knowledge ·      │
        │ ToolRegistry · PolicyEnforcer · AgentLLM · metrics   │
        └───────────────────────┬──────────────────────────────┘
                                ▼
                    LLM framework (Phase 04)  ──▶ Claude / Mock
```

## Anatomy of an agent

Every agent carries: **identity**, **goal**, **instructions**, **prompt**,
**memory**, **knowledge**, **context**, **planner**, **executor**, **reasoner**,
**reflection**, **tools**, **policies**, **scheduler**, **metrics**, **logs**,
**evaluation**, **configuration**, and a **lifecycle**. The runtime bundles the
mutable pieces into an `AgentContext` threaded through a run.

### BaseAgent lifecycle

`initialize()` → `plan()` → `reason()` + `execute()` (looped) → `reflect()` →
`learn()` → `evaluate()` → `finish()`, plus `cancel()` / `pause()` / `resume()` /
`health()`. Concrete agents subclass `BaseAgent` and override `configure()`
(register tools/knowledge) and optionally `final_output()`. See the three example
agents in `app/agents/examples/` (`echo`, `assistant`, `research`).

## Subsystems

| Package          | Responsibility                                                              | Doc                                                  |
| ---------------- | --------------------------------------------------------------------------- | ---------------------------------------------------- |
| `base/`          | identity, goals, tasks, lifecycle, context, config, LLM bridge, `BaseAgent` | —                                                    |
| `manager/`       | `AgentManager` — create/run/pause/resume/cancel, health, tracking           | —                                                    |
| `registry/`      | `AgentRegistry` — versioning, discovery, capabilities, tags                 | —                                                    |
| `planner/`       | goal decomposition, dependency graph, replanning                            | [Planning.md](./Planning.md)                         |
| `reasoning/`     | structured reasoning pipeline                                               | [Planning.md](./Planning.md)                         |
| `executor/`      | run tasks: LLM/tool calls, retries, timeouts, metrics                       | [Planning.md](./Planning.md)                         |
| `reflection/`    | post-run analysis + lessons                                                 | [Reflection.md](./Reflection.md)                     |
| `evaluation/`    | scored quality dimensions                                                   | [Reflection.md](./Reflection.md)                     |
| `memory/`        | scoped working memory + Phase 04 window/summary                             | [Memory.md](./Memory.md)                             |
| `knowledge/`     | policies/docs/facts/preferences, searchable                                 | [Knowledge.md](./Knowledge.md)                       |
| `tools/`         | `AgentTool` interface + built-in tools                                      | [Tools.md](./Tools.md)                               |
| `policies/`      | allowed/forbidden tools, cost/token/step limits, approval                   | [Tools.md](./Tools.md)                               |
| `scheduler/`     | immediate/delayed/recurring/cron scheduling                                 | —                                                    |
| `workflows/`     | sequential/parallel/conditional/loop/retry/approval steps                   | [Workflow.md](./Workflow.md)                         |
| `coordination/`  | multi-agent supervisor/worker/observer + delegation                         | [AgentFramework.md](./AgentFramework.md#multi-agent) |
| `communication/` | inter-agent message bus + mailboxes                                         | —                                                    |
| `monitoring/`    | aggregate run metrics + snapshot                                            | —                                                    |
| `sandbox/`       | per-action timeout + concurrency limits                                     | —                                                    |
| `events/`        | agent domain events on the Phase 03 event bus                               | —                                                    |

## Multi-agent

`MultiAgentCoordinator` (`coordination/`) assigns subgoals to worker agents,
shares memory and a message bus (`communication/`), and has a supervisor agent
synthesize the workers' results. Roles: supervisor, worker, coordinator, observer.

## Events

Runs publish `AgentStarted`, `TaskCreated`, `TaskFinished`, `ToolExecuted`,
`ReflectionFinished`, `GoalCompleted`, `GoalFailed`, and `AgentStopped` on the
shared event bus, so monitoring and future subscribers can react without coupling
to the runtime.

## Persistence

15 tables (`app/models/agent.py`, migration `0004_agent_framework`): `agent`,
`agent_version`, `agent_configuration`, `agent_goal`, `agent_task`,
`agent_task_execution`, `agent_memory`, `knowledge_document`, `agent_tool`,
`agent_tool_execution`, `agent_reflection`, `agent_evaluation`, `agent_plan`,
`agent_workflow_run`, `agent_metric`. `AgentService.run()` persists the whole
run: goal, plan, tasks + executions, tool executions, reflection, evaluation, and
a per-run metric snapshot.

## Security

Agents inherit the caller's permissions. Running an org-scoped agent requires
`agent.run`; creating tools/knowledge requires `agent.manage`; metrics require
`analytics.read`. Every tool call is validated against its schema and gated by the
policy enforcer (mutating tools require approval); executions are audited in
`agent_tool_execution`.

## API

See [API.md](./API.md) for the full endpoint list. Highlights: `POST
/agents/start`, `POST /agents/{pause,resume,stop}`, `GET /agents`,
`GET /tasks?run_id=`, `GET /reflections/{run_id}`, `GET /evaluations/{run_id}`,
`POST /plans/preview`, `POST /reason`, knowledge CRUD, and `GET /metrics`.

## Testing

The entire framework runs offline: `LLM_DEFAULT_PROVIDER=mock` + in-memory SQLite.
See `tests/unit/test_agents_core.py` and `tests/integration/test_agents_api.py`.
