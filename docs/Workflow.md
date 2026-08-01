# Agent Workflows

Two complementary workflow systems exist in the platform:

1. **Phase 03 persisted workflow engine** (`app/services/workflow.py`) — a durable
   graph of nodes/edges executed by a topological walk, aimed at a future visual
   editor.
2. **Phase 05 agent workflow runtime** (`app/agents/workflows/`) — an ephemeral,
   in-process step engine an agent drives during a task.

This document covers the agent workflow runtime.

## `AgentWorkflow`

An ordered set of `WorkflowStep`s executed with a shared, threaded context dict.
Each step supports the full set of control-flow primitives:

| Primitive       | How                                                              |
| --------------- | ---------------------------------------------------------------- |
| **Sequential**  | Default — steps run in order.                                    |
| **Parallel**    | Steps sharing a `parallel_group` run via `asyncio.gather`.       |
| **Conditional** | `condition(ctx)` returning `False` skips the step.               |
| **Loop**        | `loop_until(ctx)` repeats the action up to `max_loops`.          |
| **Retry**       | `retries` re-attempts on failure.                                |
| **Delay**       | `delay_seconds` waits before running.                            |
| **Approval**    | `requires_approval` raises `ApprovalPendingError` until granted. |
| **Merge**       | Downstream steps read prior results from the shared context.     |

`run(context, approvals)` returns a `WorkflowResult` (`completed`, per-step
statuses, final context). Execution stops early on a failed step.

## Persistence

`AgentWorkflowService.record()` persists a finished run to `agent_workflow_run`
(steps + status + context), read via `GET /workflows/{workflow_run_id}` for the
workflow viewer.

## Example

```python
wf = AgentWorkflow("research")
wf.add(WorkflowStep("gather", gather_fn, parallel_group="g"))
wf.add(WorkflowStep("verify", verify_fn, parallel_group="g"))
wf.add(WorkflowStep("write", write_fn))            # runs after the parallel batch
result = await wf.run({"topic": "SSR"})
```
