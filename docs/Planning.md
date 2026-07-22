# Planning, Reasoning & Execution

The three engines that turn a goal into results. All live under
`app/agents/` and run through the Phase 04 LLM framework.

## Planning engine (`planner/`)

`Planner.plan(goal, context)` decomposes a goal into a `TaskGraph` — a dependency
graph of `AgentTask`s. Planning is a **hybrid**: a robust deterministic
decomposition (so it always yields a valid, acyclic graph, even offline) enriched
by an LLM-generated outline.

- **Decomposition** — an `understand` task, then one work task per success
  criterion (or per outline step, or a single task), then a `synthesize` task
  that depends on the work tasks. Work tasks run in parallel where the graph
  allows.
- **Dependency graph** — `TaskGraph.topological_order()` validates acyclicity and
  yields a safe order; `TaskGraph.ready()` returns tasks whose dependencies have
  all succeeded (enabling parallel execution).
- **Dynamic replanning** — after failures, `Planner.replan()` appends recovery
  tasks rather than aborting. The `BaseAgent` loop calls it between iterations,
  bounded by `config.max_iterations`.
- **Preview** — `PlanningService.preview()` returns the plan (rationale, outline,
  tasks) without executing, backing `POST /plans/preview`.

## Reasoning engine (`reasoning/`)

`Reasoner.reason(task, context)` produces a structured `ReasoningTrace` following
the pipeline:

```
Understand Goal → Gather Context → Plan → Select Tools
→ Execute → Evaluate → Reflect → Improve
```

Each stage is recorded as a `ReasoningStep`. The reasoner gathers relevant
knowledge and policies, lists available tools, then asks the LLM for a concise
approach (`context.complete()`), storing the thought in short-term memory. It
degrades gracefully offline (the trace is still well-formed with the mock
provider). `ReasoningService.reason()` exposes a one-off trace via `POST /reason`.

## Execution engine (`executor/`)

`Executor.execute(task, context)` runs a single task to completion with:

- **Dispatch by kind** — `REASON` (run the reasoner), `LLM` (a completion,
  e.g. synthesis), `TOOL` (a policy-gated tool call), `DELEGATE` (hand to another
  agent), and `WORKFLOW`/`CUSTOM`.
- **Retries + timeout** — up to the task's (policy-clamped) `max_retries`, each
  attempt wrapped in `asyncio.wait_for`. Policy failures are terminal (no retry).
- **Policy enforcement** — `check_step()` (step ceiling), `check_tool()` (allow
  list + approval for mutating tools), and `add_usage()` (cost/token ceilings).
- **Observability** — updates run metrics, appends artifacts (reasoning/LLM/tool),
  writes task logs, and publishes `ToolExecuted` / `TaskFinished` events.

The `BaseAgent` drives the loop: it repeatedly runs the `ready()` batch
concurrently, replans on failure, and stops when the graph is complete or the
iteration budget is exhausted. See [AgentFramework.md](./AgentFramework.md).
