"""Request/response schemas for the AI agent API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# -- Catalog -------------------------------------------------------------
class AgentOut(BaseModel):
    slug: str
    name: str
    description: str
    version: str
    category: str
    capabilities: list[str]
    tags: list[str]
    required_permission: str
    provider_independent: bool


class AgentVersionOut(BaseModel):
    slug: str
    versions: list[str]


# -- Running & control ---------------------------------------------------
class RunAgentIn(BaseModel):
    slug: str
    objective: str = Field(min_length=1)
    organization_id: uuid.UUID | None = None
    priority: int = Field(default=5, ge=0, le=20)
    constraints: list[str] = Field(default_factory=list)
    expected_output: str | None = None
    success_criteria: list[str] = Field(default_factory=list)
    model: str | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=50)


class RunSummaryOut(BaseModel):
    run_id: uuid.UUID
    goal_id: uuid.UUID
    agent_slug: str
    state: str
    goal_status: str
    output: str


class RunControlIn(BaseModel):
    run_id: uuid.UUID


class RunControlOut(BaseModel):
    run_id: uuid.UUID
    acted: bool
    message: str


class RunningAgentOut(BaseModel):
    run_id: uuid.UUID
    slug: str
    state: str
    objective: str


class ManagerHealthOut(BaseModel):
    active: int
    by_state: dict[str, int]


# -- Goals & tasks -------------------------------------------------------
class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    objective: str
    priority: int
    status: str
    run_id: uuid.UUID | None
    expected_output: str | None
    result: str | None
    created_at: datetime


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    description: str
    kind: str
    status: str
    order_index: int
    attempts: int
    depends_on: list[str]
    error: str | None
    result: str | None


class TaskExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    attempt: int
    status: str
    output: str
    error: str | None
    duration_ms: float


# -- Tools ---------------------------------------------------------------
class ToolOut(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    mutating: bool
    builtin: bool


class RegisterToolIn(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    mutating: bool = False
    category: str = "general"


class ToolExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool_name: str
    success: bool
    output: str
    error: str | None
    duration_ms: float


# -- Reflection / evaluation / plan / reasoning --------------------------
class ReflectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    summary: str
    mistakes: list[str]
    lessons: list[str]
    improvements: list[str]


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    correctness: float
    completeness: float
    cost: float
    latency: float
    quality: float
    confidence: float
    overall: float
    notes: list[str]


class PlanPreviewIn(BaseModel):
    objective: str = Field(min_length=1)
    organization_id: uuid.UUID | None = None


class PlanPreviewOut(BaseModel):
    objective: str
    rationale: str
    outline: list[str]
    tasks: list[dict[str, Any]]


class ReasonIn(BaseModel):
    objective: str = Field(min_length=1)
    task: str = Field(min_length=1)
    organization_id: uuid.UUID | None = None


class ReasonOut(BaseModel):
    task: str
    thought: str
    steps: list[dict[str, str]]


# -- Knowledge -----------------------------------------------------------
class KnowledgeCreateIn(BaseModel):
    organization_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    kind: str = "fact"
    tags: list[str] = Field(default_factory=list)
    source: str | None = None


class KnowledgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    content: str
    kind: str
    tags: list[str]
    source: str | None
    created_at: datetime


# -- Workflow & metrics --------------------------------------------------
class WorkflowRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    name: str
    status: str
    completed: bool
    steps: list[dict[str, Any]]


class MonitorOut(BaseModel):
    running: int
    runs_total: int
    runs_succeeded: int
    runs_failed: int
    success_rate: float
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    tool_calls: int


class MetricsReportOut(BaseModel):
    runs: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    success_rate: float
    monitor: MonitorOut
