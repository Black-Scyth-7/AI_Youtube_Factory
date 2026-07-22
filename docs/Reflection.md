# Reflection & Evaluation

After a run, agents analyze what happened (reflection) and score how well they did
(evaluation). Both are best-effort, deterministic offline, and persisted.

## Reflection engine (`reflection/`)

`Reflector.reflect(graph, context)` produces a `Reflection`:

- **summary** — succeeded/failed task counts.
- **mistakes** — one entry per failed task, with its error.
- **lessons** — LLM-generated, concise takeaways (falls back silently if the LLM
  is unavailable — reflection never fails the run).
- **improvements** — concrete suggestions when tasks failed.

Lessons are written to agent memory (`scope="agent"`, key `lessons`) so **future
runs benefit** — the essence of the "self-improvement" requirement. Reflections
are persisted to `agent_reflection` and read via `GET /reflections/{run_id}`.

## Evaluation engine (`evaluation/`)

`Evaluator.evaluate(graph, context)` scores the run across six dimensions, each in
`[0, 1]`, from concrete outcomes (so scores are deterministic and testable):

| Dimension | Derived from |
| --- | --- |
| correctness | `1 − failed/total` tasks |
| completeness | `succeeded/total` tasks |
| cost | spend vs the policy budget |
| latency | wall-clock time (fast ⇒ high) |
| quality | mean of correctness + completeness |
| confidence | completeness weighted by correctness |

`Evaluation.overall` is a weighted blend (correctness 0.30, completeness 0.25,
quality 0.15, cost/latency/confidence 0.10 each). Evaluations persist to
`agent_evaluation` and are read via `GET /evaluations/{run_id}`; the frontend
renders them as bars on the agent console and the metrics dashboard.

## Monitoring (`monitoring/`)

`AgentMonitor` folds each finished run into an aggregate `MonitorSnapshot`
(runs, success rate, tokens, cost, latency, tool calls). `MetricsService.report()`
combines the persisted per-run `agent_metric` rows with the live snapshot for
`GET /metrics`.
