# Workflow engine

Phase 03 persisted workflow graphs and walked them in topological order. Phase 07
makes them actually branch: edge conditions are evaluated, independent nodes run
concurrently, loops expand, and triggers start runs without a person.

## What changed

`WorkflowEdge.condition` existed from Phase 03 but **was never read** — the
executor ran every node regardless, so an authored condition had no effect. It
is now evaluated, and a false condition prunes the branch behind it.

Graph logic lives in `app/core/workflow/engine.py`, free of the database, so it
can be tested on plain dataclasses. The service maps ORM rows onto `GraphNode`
and `GraphEdge` and persists the outcomes.

## Conditions

Conditions are expressions evaluated against the run context. Each node's return
value is stored under its key, so downstream conditions can read it:

```python
edges=[
    {"source": "score", "target": "publish", "condition": "score['value'] > 80"},
    {"source": "score", "target": "revise",  "condition": "score['value'] <= 80"},
]
```

A blank or absent condition is always true, so an unconditional edge needs no
expression. An unknown name evaluates to `None` rather than raising, so a
condition may reference a value an earlier node did not set.

### Why not `eval`

Conditions are author-supplied, so `app/core/workflow/expressions.py` parses to
an AST and walks it, permitting only literals, names, subscripts, boolean and
comparison operators, and arithmetic. Calls, attribute access, comprehensions
and imports all raise.

`eval(expr, {"__builtins__": {}})` is not an adequate substitute. It is only as
safe as the filter in front of it, and a character allow-list that permits `*`
still admits `9**9**9**9` — which passes the filter and then hangs the worker
computing an astronomically large integer. The evaluator bounds the exponent
(`MAX_EXPONENT`), the expression length, and the nesting depth instead.

The agent `CalculatorTool` had exactly that eval-plus-allow-list shape and now
uses this evaluator.

## Branching and merging

A node runs when **at least one** incoming edge is satisfied and that edge's
source actually ran. Two consequences worth knowing:

- Skipping propagates. If a node is skipped, nodes reachable only through it are
  skipped too, with `skip_reason` naming what excluded them.
- A merge node runs if _any_ branch reaching it survived. Requiring all branches
  would deadlock the common "do A or B, then continue" shape.

## Parallelism

`WorkflowGraph.levels()` groups nodes into dependency levels; everything in a
level is independent, so the engine runs a level with `asyncio.gather`. Two
100 ms nodes on one level take ~100 ms, not 200 ms. The first failure stops the
run and the outcomes gathered so far are attached to the error.

## Loops

A node of type `loop` runs once per item in the collection named by
`config.over`:

```python
{"key": "each_clip", "type": "loop", "config": {"over": "clips"}}
```

Each pass sees `item` and the zero-based `index` in a **copy** of the context, so
loop variables cannot leak into the surrounding run. The node's final output is
the list of every pass's result. Iterations are capped at `MAX_LOOP_ITERATIONS`
so a mis-authored loop cannot run away.

## Triggers

`WorkflowTrigger` records what starts a workflow:

| Kind       | Fires when                           |
| ---------- | ------------------------------------ |
| `manual`   | Someone calls `execute`              |
| `schedule` | A five-field cron expression matches |
| `event`    | A named internal event is dispatched |

`WorkflowTriggerService.fire_due()` runs everything due now. Cron has minute
resolution and `last_fired_at` is compared to the minute, so a poller running
several times within the same minute fires a trigger once.

The cron matcher is the one the agent scheduler already uses, not a second
implementation, so both subsystems agree on what an expression means.

## Per-node records

Each run writes a `WorkflowNodeExecution` per node — status, iteration, output,
error and skip reason. That is what a visual editor renders when replaying a run,
and it is why a skipped node is recorded rather than simply absent.

## Schema

Migration `0006_workflow` adds `workflow_trigger` and `workflow_node_execution`.
Verified against PostgreSQL 17: `upgrade head` creates both, `downgrade
0005_catalog` removes them.
