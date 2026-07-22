"""Evaluation engine.

Scores an agent run across several dimensions — correctness, completeness, cost,
latency, quality, and confidence — producing an :class:`Evaluation` with a
0..1 score per dimension and an overall score. Scores are computed from the run's
concrete outcomes (task success ratio, spend vs budget, latency) so they are
deterministic and testable offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.agents.base.tasks import TaskGraph, TaskStatus

if TYPE_CHECKING:
    from app.agents.base.context import AgentContext


@dataclass(slots=True)
class Evaluation:
    """Per-dimension scores for a run (each in ``[0, 1]``)."""

    correctness: float = 0.0
    completeness: float = 0.0
    cost: float = 0.0
    latency: float = 0.0
    quality: float = 0.0
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def overall(self) -> float:
        """Weighted overall score."""
        return round(
            0.30 * self.correctness
            + 0.25 * self.completeness
            + 0.15 * self.quality
            + 0.10 * self.cost
            + 0.10 * self.latency
            + 0.10 * self.confidence,
            4,
        )


class Evaluator:
    """Scores a run from its concrete outcomes."""

    async def evaluate(self, graph: TaskGraph, context: AgentContext) -> Evaluation:
        """Score ``graph`` and return an :class:`Evaluation`."""
        tasks = graph.tasks
        total = len(tasks) or 1
        succeeded = sum(1 for t in tasks if t.status == TaskStatus.SUCCEEDED)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)

        correctness = 1.0 - (failed / total)
        completeness = succeeded / total

        budget = context.enforcer.policy.max_cost_usd or 1.0
        cost = max(0.0, 1.0 - min(context.metrics.cost_usd / budget, 1.0))

        # Latency score: fast under 5s -> 1.0, degrading to 0 by 60s.
        seconds = context.metrics.latency_ms / 1000.0
        latency = max(0.0, min(1.0, 1.0 - (seconds - 5.0) / 55.0)) if seconds > 5 else 1.0

        quality = round((correctness + completeness) / 2, 4)
        confidence = round(completeness * (0.5 + 0.5 * correctness), 4)

        evaluation = Evaluation(
            correctness=round(correctness, 4),
            completeness=round(completeness, 4),
            cost=round(cost, 4),
            latency=round(latency, 4),
            quality=quality,
            confidence=confidence,
        )
        if failed:
            evaluation.notes.append(f"{failed} task(s) failed.")
        evaluation.notes.append(
            f"${context.metrics.cost_usd:.4f} spent of ${budget:.2f} budget."
        )
        return evaluation
