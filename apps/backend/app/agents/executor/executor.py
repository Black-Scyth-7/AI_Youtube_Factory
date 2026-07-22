"""Execution engine.

Runs a single task to completion: reasoning, LLM calls, tool calls, memory
updates, logging, metrics, retries, and timeouts. Tool calls are gated by the
policy enforcer and captured as artifacts. The executor never talks to a
provider directly — LLM work flows through the agent context's LLM bridge.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from app.agents.base.tasks import AgentTask, TaskKind, TaskStatus
from app.agents.events.events import TaskFinished, ToolExecuted
from app.agents.policies.policies import ApprovalRequiredError, PolicyViolationError
from app.agents.reasoning.reasoner import Reasoner

if TYPE_CHECKING:
    from app.agents.base.context import AgentContext


class ExecutionError(RuntimeError):
    """Raised when a task exhausts its retries."""


class Executor:
    """Runs tasks with retries, timeouts, and policy enforcement."""

    def __init__(self, reasoner: Reasoner | None = None) -> None:
        self._reasoner = reasoner or Reasoner()

    async def execute(self, task: AgentTask, context: AgentContext) -> Any:
        """Run ``task``, retrying on failure up to its (policy-clamped) limit."""
        context.enforcer.check_step()
        retries = context.enforcer.retries_for(task.max_retries)
        timeout = task.timeout_seconds or context.enforcer.policy.task_timeout_seconds

        task.status = TaskStatus.RUNNING
        context.metrics.tasks_total += 1
        last_error: str | None = None

        for attempt in range(retries + 1):
            task.attempts = attempt + 1
            try:
                result = await asyncio.wait_for(
                    self._dispatch(task, context), timeout=timeout
                )
                task.status = TaskStatus.SUCCEEDED
                task.result = result
                task.progress = 1.0
                context.metrics.tasks_succeeded += 1
                await self._publish_finished(task, context)
                return result
            except (PolicyViolationError, ApprovalRequiredError) as exc:
                # Policy failures are terminal — do not retry.
                last_error = str(exc)
                task.log(f"policy blocked: {exc}")
                break
            except (TimeoutError, asyncio.TimeoutError):  # noqa: UP041
                last_error = f"timeout after {timeout}s"
                task.log(last_error)
            except Exception as exc:
                last_error = str(exc)
                task.log(f"attempt {attempt + 1} failed: {exc}")
            if attempt < retries:
                context.metrics.retries += 1

        task.status = TaskStatus.FAILED
        task.error = last_error
        context.metrics.tasks_failed += 1
        await self._publish_finished(task, context)
        return None

    async def _dispatch(self, task: AgentTask, context: AgentContext) -> Any:
        """Route a task to the handler for its kind."""
        if task.kind == TaskKind.TOOL:
            return await self._run_tool(task, context)
        if task.kind == TaskKind.LLM:
            return await self._run_llm(task, context)
        if task.kind in (TaskKind.REASON, TaskKind.CUSTOM):
            return await self._run_reason(task, context)
        if task.kind == TaskKind.DELEGATE:
            return await self._run_delegate(task, context)
        # WORKFLOW and anything else: reason as a safe default.
        return await self._run_reason(task, context)

    async def _run_reason(self, task: AgentTask, context: AgentContext) -> str:
        trace = await self._reasoner.reason(task, context)
        task.artifacts.append({"type": "reasoning", "thought": trace.thought})
        return trace.thought

    async def _run_llm(self, task: AgentTask, context: AgentContext) -> str:
        prompt = task.payload.get("prompt") or self._synthesis_prompt(task, context)
        output = await context.complete(prompt)
        task.artifacts.append({"type": "llm", "output": output})
        context.memory.remember("task", task.key, output)
        return output

    async def _run_tool(self, task: AgentTask, context: AgentContext) -> str:
        name = str(task.payload.get("tool", ""))
        arguments: dict[str, Any] = dict(task.payload.get("arguments", {}))
        tool = context.tools.get(name)
        mutating = bool(tool and tool.mutating)
        context.enforcer.check_tool(name, mutating=mutating)
        outcome = await context.tools.run(name, arguments)
        context.metrics.tool_calls += 1
        task.artifacts.append(
            {
                "type": "tool",
                "tool": name,
                "success": outcome.success,
                "output": outcome.output,
                "error": outcome.error,
            }
        )
        await context.events.publish(
            ToolExecuted(run_id=context.run_id, tool_name=name, success=outcome.success)
        )
        if not outcome.success:
            raise ExecutionError(outcome.error or f"Tool '{name}' failed")
        return outcome.output

    async def _run_delegate(self, task: AgentTask, context: AgentContext) -> str:
        target = str(task.payload.get("agent", "unknown"))
        task.log(f"delegated to {target}")
        return f"delegated:{target}"

    def _synthesis_prompt(self, task: AgentTask, context: AgentContext) -> str:
        notes = context.memory.scope_items("task")
        joined = "\n".join(f"- {k}: {v}" for k, v in notes.items())
        expected = task.payload.get("expected_output") or ""
        prompt = (
            f"Goal: {context.goal.objective}\n"
            f"Work completed:\n{joined or '- (no intermediate notes)'}\n\n"
            f"{task.description}"
        )
        if expected:
            prompt += f"\nExpected output: {expected}"
        return prompt

    async def _publish_finished(self, task: AgentTask, context: AgentContext) -> None:
        await context.events.publish(
            TaskFinished(
                run_id=context.run_id, task_key=task.key, status=task.status.value
            )
        )
