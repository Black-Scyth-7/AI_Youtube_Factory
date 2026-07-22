"""Agent execution policies.

Policies bound what an agent may do: which tools are permitted, spend/token
ceilings, per-task timeouts, retry and step limits, and whether mutating tools
require human approval. The :class:`PolicyEnforcer` is consulted by the executor
before every tool call and after each step.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class PolicyViolationError(RuntimeError):
    """Raised when an action would violate the active policy."""


class ApprovalRequiredError(RuntimeError):
    """Raised when a mutating tool needs human approval before running."""


@dataclass(slots=True)
class AgentPolicy:
    """Declarative limits for an agent run."""

    allowed_tools: frozenset[str] | None = None  # None = allow all not forbidden
    forbidden_tools: frozenset[str] = frozenset()
    max_cost_usd: float = 1.0
    max_tokens: int = 100_000
    max_steps: int = 50
    max_retries: int = 3
    task_timeout_seconds: float = 120.0
    require_approval_for_mutations: bool = True

    def tool_allowed(self, name: str, *, mutating: bool = False) -> bool:
        """Return whether ``name`` may be called under this policy."""
        if name in self.forbidden_tools:
            return False
        return not (self.allowed_tools is not None and name not in self.allowed_tools)


@dataclass(slots=True)
class PolicyState:
    """Mutable accounting tracked against a policy during a run."""

    cost_usd: float = 0.0
    tokens: int = 0
    steps: int = 0
    approvals: set[str] = field(default_factory=set)


class PolicyEnforcer:
    """Checks actions against a policy and tracks cumulative usage."""

    def __init__(self, policy: AgentPolicy | None = None) -> None:
        self.policy = policy or AgentPolicy()
        self.state = PolicyState()

    def check_tool(self, name: str, *, mutating: bool = False) -> None:
        """Raise if a tool call is forbidden or needs approval."""
        if not self.policy.tool_allowed(name, mutating=mutating):
            raise PolicyViolationError(f"Tool '{name}' is not permitted by policy.")
        if (
            mutating
            and self.policy.require_approval_for_mutations
            and name not in self.state.approvals
        ):
            raise ApprovalRequiredError(
                f"Tool '{name}' mutates state and requires approval."
            )

    def grant_approval(self, name: str) -> None:
        """Record a human approval for a mutating tool."""
        self.state.approvals.add(name)

    def check_step(self) -> None:
        """Increment the step counter and enforce the step ceiling."""
        self.state.steps += 1
        if self.state.steps > self.policy.max_steps:
            raise PolicyViolationError(f"Step limit exceeded ({self.policy.max_steps}).")

    def add_usage(self, *, cost_usd: float, tokens: int) -> None:
        """Accumulate spend/token usage and enforce ceilings."""
        self.state.cost_usd += cost_usd
        self.state.tokens += tokens
        if self.state.cost_usd > self.policy.max_cost_usd:
            raise PolicyViolationError(
                f"Cost limit exceeded (${self.policy.max_cost_usd:.4f})."
            )
        if self.state.tokens > self.policy.max_tokens:
            raise PolicyViolationError(
                f"Token limit exceeded ({self.policy.max_tokens})."
            )

    def retries_for(self, requested: int) -> int:
        """Clamp a task's requested retries to the policy ceiling."""
        return min(requested, self.policy.max_retries)
