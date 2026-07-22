"""Agent monitoring.

Aggregates runtime metrics across agent runs: how many are running, completed
tasks, failures, retries, latency, tokens, cost, and the overall success rate.
The service layer records each finished run; the API and dashboards read the
snapshot.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.base.agent import AgentRunResult


@dataclass(slots=True)
class MonitorSnapshot:
    """A point-in-time view of aggregate agent activity."""

    running: int = 0
    runs_total: int = 0
    runs_succeeded: int = 0
    runs_failed: int = 0
    tasks_total: int = 0
    tasks_failed: int = 0
    retries: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    tool_calls: int = 0

    @property
    def success_rate(self) -> float:
        if not self.runs_total:
            return 0.0
        return round(self.runs_succeeded / self.runs_total, 4)

    @property
    def avg_latency_ms(self) -> float:
        if not self.runs_total:
            return 0.0
        return round(self.total_latency_ms / self.runs_total, 2)

    def as_dict(self) -> dict[str, float | int]:
        data = asdict(self)
        data["success_rate"] = self.success_rate
        data["avg_latency_ms"] = self.avg_latency_ms
        return data


class AgentMonitor:
    """Accumulates metrics from finished agent runs."""

    def __init__(self) -> None:
        self._snapshot = MonitorSnapshot()
        self.running = 0

    def record_run(self, result: AgentRunResult) -> None:
        """Fold a finished run's metrics into the snapshot."""
        from app.agents.base.goals import GoalStatus

        snap = self._snapshot
        metrics = result.metrics
        snap.runs_total += 1
        if result.goal_status == GoalStatus.COMPLETED:
            snap.runs_succeeded += 1
        elif result.goal_status == GoalStatus.FAILED:
            snap.runs_failed += 1
        snap.tasks_total += metrics.tasks_total
        snap.tasks_failed += metrics.tasks_failed
        snap.retries += metrics.retries
        snap.total_tokens += metrics.total_tokens
        snap.total_cost_usd = round(snap.total_cost_usd + metrics.cost_usd, 6)
        snap.total_latency_ms += metrics.latency_ms
        snap.tool_calls += metrics.tool_calls

    def snapshot(self, *, running: int = 0) -> MonitorSnapshot:
        """Return the current snapshot with the live running count filled in."""
        self._snapshot.running = running
        return self._snapshot


_monitor: AgentMonitor | None = None


def get_agent_monitor() -> AgentMonitor:
    """Return the process agent-monitor singleton."""
    global _monitor
    if _monitor is None:
        _monitor = AgentMonitor()
    return _monitor


def set_agent_monitor(monitor: AgentMonitor) -> None:
    """Override the agent-monitor singleton (used in tests)."""
    global _monitor
    _monitor = monitor
