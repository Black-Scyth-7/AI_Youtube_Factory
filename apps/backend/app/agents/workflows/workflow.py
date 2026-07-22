"""Agent workflow runtime.

A lightweight, in-process step engine agents use to run structured procedures.
Supports the control-flow primitives the spec requires: sequential and parallel
steps, conditionals, loops, per-step retry, delays, human approval gates, and a
merge/collect step. This complements (does not replace) the Phase 03 persisted
workflow engine — it is the ephemeral runtime an agent drives during a task.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

StepAction = Callable[[dict[str, Any]], Awaitable[Any]]
StepCondition = Callable[[dict[str, Any]], bool]


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_APPROVAL = "waiting_approval"


@dataclass(slots=True)
class WorkflowStep:
    """A single workflow step with its control-flow policy."""

    name: str
    action: StepAction
    condition: StepCondition | None = None
    parallel_group: str | None = None
    retries: int = 0
    delay_seconds: float = 0.0
    requires_approval: bool = False
    loop_until: StepCondition | None = None
    max_loops: int = 10
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None


@dataclass(slots=True)
class WorkflowResult:
    """The outcome of running a workflow."""

    completed: bool
    steps: list[WorkflowStep]
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)


class ApprovalPendingError(RuntimeError):
    """Raised when a step needs an approval that has not been granted."""

    def __init__(self, step: str) -> None:
        super().__init__(f"Step '{step}' requires approval.")
        self.step = step


class AgentWorkflow:
    """An ordered set of steps with parallel/conditional/loop/retry semantics."""

    def __init__(self, name: str = "workflow") -> None:
        self.name = name
        self._steps: list[WorkflowStep] = []

    def add(self, step: WorkflowStep) -> AgentWorkflow:
        self._steps.append(step)
        return self

    @property
    def steps(self) -> list[WorkflowStep]:
        return list(self._steps)

    async def run(
        self,
        context: dict[str, Any] | None = None,
        *,
        approvals: set[str] | None = None,
    ) -> WorkflowResult:
        """Execute the workflow, threading a shared context through steps."""
        ctx: dict[str, Any] = dict(context or {})
        granted = approvals or set()
        index = 0
        steps = self._steps
        while index < len(steps):
            group = steps[index].parallel_group
            if group:
                batch = [s for s in steps[index:] if s.parallel_group == group]
                await asyncio.gather(
                    *(self._run_step(step, ctx, granted) for step in batch)
                )
                index += len(batch)
            else:
                await self._run_step(steps[index], ctx, granted)
                index += 1
            if steps[index - 1].status == StepStatus.FAILED:
                break
        completed = all(
            s.status in (StepStatus.SUCCEEDED, StepStatus.SKIPPED) for s in steps
        )
        return WorkflowResult(completed=completed, steps=steps, context=ctx)

    async def _run_step(
        self, step: WorkflowStep, ctx: dict[str, Any], approvals: set[str]
    ) -> None:
        if step.condition is not None and not step.condition(ctx):
            step.status = StepStatus.SKIPPED
            return
        if step.requires_approval and step.name not in approvals:
            step.status = StepStatus.WAITING_APPROVAL
            step.error = "approval required"
            raise ApprovalPendingError(step.name)
        if step.delay_seconds > 0:
            await asyncio.sleep(step.delay_seconds)

        step.status = StepStatus.RUNNING
        attempts = step.retries + 1
        for attempt in range(attempts):
            try:
                result = await self._invoke(step, ctx)
                step.result = result
                ctx[step.name] = result
                step.status = StepStatus.SUCCEEDED
                return
            except Exception as exc:
                step.error = str(exc)
                if attempt == attempts - 1:
                    step.status = StepStatus.FAILED

    async def _invoke(self, step: WorkflowStep, ctx: dict[str, Any]) -> Any:
        """Run the step action, honoring a loop-until condition."""
        if step.loop_until is None:
            return await step.action(ctx)
        result: Any = None
        for _ in range(step.max_loops):
            result = await step.action(ctx)
            ctx[step.name] = result
            if step.loop_until(ctx):
                break
        return result
