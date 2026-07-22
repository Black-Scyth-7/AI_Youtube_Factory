"""Agent scheduler.

Schedules agent runs: immediate, delayed, recurring (fixed interval), or cron,
each with a priority. The scheduler computes due jobs for a given moment; a
worker (or the service layer) polls :meth:`due` and dispatches runs. Cron support
covers the standard five fields with ``*``, ``*/n``, lists, and ranges.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import IntEnum, StrEnum


class ScheduleKind(StrEnum):
    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    RECURRING = "recurring"
    CRON = "cron"


class SchedulePriority(IntEnum):
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


def _matches_field(expr: str, value: int) -> bool:
    """Return whether a single cron field ``expr`` matches ``value``."""
    for part in expr.split(","):
        if part == "*":
            return True
        if part.startswith("*/"):
            step = int(part[2:])
            if step > 0 and value % step == 0:
                return True
        elif "-" in part:
            low, high = part.split("-", 1)
            if int(low) <= value <= int(high):
                return True
        elif part.isdigit() and int(part) == value:
            return True
    return False


def cron_matches(expression: str, moment: datetime) -> bool:
    """Return whether a 5-field cron ``expression`` fires at ``moment``."""
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("Cron expression must have 5 fields.")
    minute, hour, dom, month, dow = fields
    return (
        _matches_field(minute, moment.minute)
        and _matches_field(hour, moment.hour)
        and _matches_field(dom, moment.day)
        and _matches_field(month, moment.month)
        and _matches_field(dow, moment.isoweekday() % 7)
    )


@dataclass(slots=True)
class ScheduledJob:
    """A scheduled agent run."""

    agent_slug: str
    objective: str
    kind: ScheduleKind = ScheduleKind.IMMEDIATE
    priority: SchedulePriority = SchedulePriority.NORMAL
    run_at: datetime | None = None
    interval_seconds: float | None = None
    cron: str | None = None
    enabled: bool = True
    last_run: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    def is_due(self, now: datetime) -> bool:
        """Return whether this job should run at ``now``."""
        if not self.enabled:
            return False
        if self.kind == ScheduleKind.IMMEDIATE:
            return self.last_run is None
        if self.kind in (ScheduleKind.DELAYED,) and self.run_at is not None:
            return self.last_run is None and now >= self.run_at
        if self.kind == ScheduleKind.RECURRING and self.interval_seconds is not None:
            if self.last_run is None:
                return True
            return now >= self.last_run + timedelta(seconds=self.interval_seconds)
        if self.kind == ScheduleKind.CRON and self.cron is not None:
            if self.last_run is not None and (now - self.last_run).total_seconds() < 60:
                return False
            return cron_matches(self.cron, now)
        return False


class AgentScheduler:
    """Holds scheduled jobs and reports which are due."""

    def __init__(self) -> None:
        self._jobs: dict[uuid.UUID, ScheduledJob] = {}

    def schedule(self, job: ScheduledJob) -> ScheduledJob:
        self._jobs[job.id] = job
        return job

    def cancel(self, job_id: uuid.UUID) -> bool:
        return self._jobs.pop(job_id, None) is not None

    def jobs(self) -> list[ScheduledJob]:
        return list(self._jobs.values())

    def due(self, now: datetime | None = None) -> list[ScheduledJob]:
        """Return jobs due at ``now``, highest priority first."""
        moment = now or datetime.now(UTC)
        ready = [job for job in self._jobs.values() if job.is_due(moment)]
        return sorted(ready, key=lambda j: j.priority, reverse=True)

    def mark_run(self, job_id: uuid.UUID, now: datetime | None = None) -> None:
        """Record that a job ran (advances recurring/cron scheduling)."""
        job = self._jobs.get(job_id)
        if job is not None:
            job.last_run = now or datetime.now(UTC)


_scheduler: AgentScheduler | None = None


def get_agent_scheduler() -> AgentScheduler:
    """Return the process agent-scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AgentScheduler()
    return _scheduler


def set_agent_scheduler(scheduler: AgentScheduler) -> None:
    """Override the agent-scheduler singleton (used in tests)."""
    global _scheduler
    _scheduler = scheduler
