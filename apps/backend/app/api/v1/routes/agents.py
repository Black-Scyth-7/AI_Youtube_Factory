"""AI agent framework API routes.

Agent catalog and discovery, running/controlling agents, goals and tasks, tools,
reflections, evaluations, plan previews, one-off reasoning, knowledge documents,
workflow runs, and metrics. Org-scoped operations enforce RBAC.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.agents.manager.manager import get_agent_manager
from app.agents.monitoring.monitor import get_agent_monitor
from app.dependencies.auth import CurrentUser, DbSession
from app.schemas.agent import (
    AgentOut,
    AgentVersionOut,
    EvaluationOut,
    GoalOut,
    KnowledgeCreateIn,
    KnowledgeOut,
    ManagerHealthOut,
    MetricsReportOut,
    MonitorOut,
    PlanPreviewIn,
    PlanPreviewOut,
    ReasonIn,
    ReasonOut,
    ReflectionOut,
    RegisterToolIn,
    RunAgentIn,
    RunControlIn,
    RunControlOut,
    RunningAgentOut,
    RunSummaryOut,
    TaskExecutionOut,
    TaskOut,
    ToolExecutionOut,
    ToolOut,
    WorkflowRunOut,
)
from app.schemas.auth import MessageResponse
from app.services.agent import (
    AgentService,
    EvaluationService,
    ExecutionService,
    KnowledgeService,
    MetricsService,
    PlanningService,
    ReasoningService,
    ReflectionService,
    ToolService,
)
from app.services.agent.workflow_service import AgentWorkflowService
from app.services.rbac import RBACService

router = APIRouter(tags=["agents"])


# -- Catalog / discovery -------------------------------------------------
@router.get("/agents", response_model=list[AgentOut])
async def list_agents(_: CurrentUser, session: DbSession) -> list[AgentOut]:
    """List the registered agent catalog."""
    return [
        AgentOut(
            slug=r.slug,
            name=r.name,
            description=r.description,
            version=r.version,
            category=r.category,
            capabilities=list(r.capabilities),
            tags=list(r.tags),
            required_permission=r.required_permission,
            provider_independent=r.provider_independent,
        )
        for r in AgentService(session).catalog()
    ]


@router.get("/agents/running", response_model=list[RunningAgentOut])
async def running_agents(_: CurrentUser) -> list[RunningAgentOut]:
    """List currently running agents."""
    return [
        RunningAgentOut(
            run_id=m.run_id,
            slug=m.slug,
            state=m.state.value,
            objective=m.goal.objective,
        )
        for m in get_agent_manager().running()
    ]


@router.get("/agents/health", response_model=ManagerHealthOut)
async def agents_health(_: CurrentUser) -> ManagerHealthOut:
    """Return manager-wide agent health."""
    health = get_agent_manager().health()
    return ManagerHealthOut(active=health.active, by_state=health.by_state)


@router.get("/agents/{slug}", response_model=AgentOut)
async def get_agent(slug: str, _: CurrentUser, session: DbSession) -> AgentOut:
    """Get a single agent registration by slug."""
    r = AgentService(session).get_registration(slug)
    return AgentOut(
        slug=r.slug,
        name=r.name,
        description=r.description,
        version=r.version,
        category=r.category,
        capabilities=list(r.capabilities),
        tags=list(r.tags),
        required_permission=r.required_permission,
        provider_independent=r.provider_independent,
    )


@router.get("/agents/{slug}/versions", response_model=AgentVersionOut)
async def agent_versions(
    slug: str, _: CurrentUser, session: DbSession
) -> AgentVersionOut:
    """List the registered versions of an agent."""
    AgentService(session).get_registration(slug)
    versions = get_agent_manager().registry.versions(slug)
    return AgentVersionOut(slug=slug, versions=versions)


# -- Run + control -------------------------------------------------------
@router.post("/agents/start", response_model=RunSummaryOut, status_code=201)
async def start_agent(
    body: RunAgentIn, user: CurrentUser, session: DbSession
) -> RunSummaryOut:
    """Run an agent for a goal (accounted + persisted)."""
    if body.organization_id is not None and not user.is_superuser:
        await RBACService(session).require_permission(
            user.id, body.organization_id, "agent.run"
        )
    summary = await AgentService(session).run(
        body.slug,
        body.objective,
        organization_id=body.organization_id,
        user_id=user.id,
        priority=body.priority,
        constraints=body.constraints,
        expected_output=body.expected_output,
        success_criteria=body.success_criteria,
        model=body.model,
        max_iterations=body.max_iterations,
    )
    return RunSummaryOut(
        run_id=summary.run_id,
        goal_id=summary.goal_id,
        agent_slug=summary.agent_slug,
        state=summary.state,
        goal_status=summary.goal_status,
        output=summary.output,
    )


@router.post("/agents/pause", response_model=RunControlOut)
async def pause_agent(body: RunControlIn, _: CurrentUser) -> RunControlOut:
    """Request a running agent pause."""
    acted = get_agent_manager().pause(body.run_id)
    return RunControlOut(
        run_id=body.run_id,
        acted=acted,
        message="paused" if acted else "run not active",
    )


@router.post("/agents/resume", response_model=RunControlOut)
async def resume_agent(body: RunControlIn, _: CurrentUser) -> RunControlOut:
    """Resume a paused agent."""
    acted = get_agent_manager().resume(body.run_id)
    return RunControlOut(
        run_id=body.run_id,
        acted=acted,
        message="resumed" if acted else "run not active",
    )


@router.post("/agents/stop", response_model=RunControlOut)
async def stop_agent(body: RunControlIn, _: CurrentUser) -> RunControlOut:
    """Cancel a running agent."""
    acted = get_agent_manager().cancel(body.run_id)
    return RunControlOut(
        run_id=body.run_id,
        acted=acted,
        message="cancelled" if acted else "run not active",
    )


# -- Goals & tasks -------------------------------------------------------
@router.get("/goals", response_model=list[GoalOut])
async def list_goals(
    organization_id: uuid.UUID, _: CurrentUser, session: DbSession
) -> list[GoalOut]:
    """List goals for an organization."""
    goals = await AgentService(session).goals.list_for_org(organization_id)
    return [GoalOut.model_validate(g) for g in goals]


@router.get("/goals/{goal_id}", response_model=GoalOut)
async def get_goal(goal_id: uuid.UUID, _: CurrentUser, session: DbSession) -> GoalOut:
    """Get a single goal."""
    goal = await AgentService(session).get_goal(goal_id)
    return GoalOut.model_validate(goal)


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    run_id: uuid.UUID, _: CurrentUser, session: DbSession
) -> list[TaskOut]:
    """List tasks for a run."""
    tasks = await AgentService(session).run_tasks(run_id)
    return [TaskOut.model_validate(t) for t in tasks]


@router.get("/tasks/{task_id}/executions", response_model=list[TaskExecutionOut])
async def task_executions(
    task_id: uuid.UUID, _: CurrentUser, session: DbSession
) -> list[TaskExecutionOut]:
    """List execution attempts for a task."""
    execs = await ExecutionService(session).executions_for_task(task_id)
    return [TaskExecutionOut.model_validate(e) for e in execs]


# -- Tools ---------------------------------------------------------------
@router.get("/tools", response_model=list[ToolOut])
async def list_tools(
    _: CurrentUser,
    session: DbSession,
    organization_id: uuid.UUID | None = Query(default=None),
) -> list[ToolOut]:
    """List the tool catalog (built-in + organization-defined)."""
    catalog = await ToolService(session).catalog(organization_id)
    return [
        ToolOut(
            name=t.name,
            description=t.description,
            input_schema=t.input_schema,
            mutating=t.mutating,
            builtin=t.builtin,
        )
        for t in catalog
    ]


@router.post("/tools", response_model=ToolOut, status_code=201)
async def register_tool(
    body: RegisterToolIn, user: CurrentUser, session: DbSession
) -> ToolOut:
    """Register an organization-defined tool definition."""
    if not user.is_superuser:
        await RBACService(session).require_permission(
            user.id, body.organization_id, "agent.manage"
        )
    row = await ToolService(session).register(
        name=body.name,
        description=body.description,
        input_schema=body.input_schema,
        actor_id=user.id,
        organization_id=body.organization_id,
        mutating=body.mutating,
        category=body.category,
    )
    return ToolOut(
        name=row.name,
        description=row.description,
        input_schema=row.input_schema,
        mutating=row.mutating,
        builtin=row.is_builtin,
    )


@router.get("/tools/executions", response_model=list[ToolExecutionOut])
async def tool_executions(
    run_id: uuid.UUID, _: CurrentUser, session: DbSession
) -> list[ToolExecutionOut]:
    """List tool executions for a run."""
    execs = await AgentService(session).run_tool_executions(run_id)
    return [ToolExecutionOut.model_validate(e) for e in execs]


# -- Reflection / evaluation / plan / reasoning --------------------------
@router.get("/reflections/{run_id}", response_model=ReflectionOut)
async def get_reflection(
    run_id: uuid.UUID, _: CurrentUser, session: DbSession
) -> ReflectionOut:
    """Get the reflection for a run."""
    from app.exceptions.base import NotFoundError

    reflection = await ReflectionService(session).get_for_run(run_id)
    if reflection is None:
        raise NotFoundError("No reflection for this run.")
    return ReflectionOut.model_validate(reflection)


@router.get("/evaluations/{run_id}", response_model=EvaluationOut)
async def get_evaluation(
    run_id: uuid.UUID, _: CurrentUser, session: DbSession
) -> EvaluationOut:
    """Get the evaluation for a run."""
    from app.exceptions.base import NotFoundError

    evaluation = await EvaluationService(session).get_for_run(run_id)
    if evaluation is None:
        raise NotFoundError("No evaluation for this run.")
    return EvaluationOut.model_validate(evaluation)


@router.post("/plans/preview", response_model=PlanPreviewOut)
async def preview_plan(
    body: PlanPreviewIn, _: CurrentUser, session: DbSession
) -> PlanPreviewOut:
    """Preview how an agent would decompose a goal."""
    preview = await PlanningService(session).preview(
        body.objective, organization_id=body.organization_id
    )
    return PlanPreviewOut(
        objective=preview.objective,
        rationale=preview.rationale,
        outline=preview.outline,
        tasks=preview.tasks,
    )


@router.post("/reason", response_model=ReasonOut)
async def reason(body: ReasonIn, _: CurrentUser, session: DbSession) -> ReasonOut:
    """Produce a one-off reasoning trace for a task."""
    result = await ReasoningService(session).reason(
        body.objective, body.task, organization_id=body.organization_id
    )
    return ReasonOut(task=result.task, thought=result.thought, steps=result.steps)


# -- Workflow runs -------------------------------------------------------
@router.get("/workflows/{workflow_run_id}", response_model=WorkflowRunOut)
async def get_workflow_run(
    workflow_run_id: uuid.UUID, _: CurrentUser, session: DbSession
) -> WorkflowRunOut:
    """Get a persisted agent workflow run."""
    from app.exceptions.base import NotFoundError

    run = await AgentWorkflowService(session).get_or_none(workflow_run_id)
    if run is None:
        raise NotFoundError("Workflow run not found.")
    return WorkflowRunOut.model_validate(run)


# -- Knowledge -----------------------------------------------------------
@router.get("/knowledge", response_model=list[KnowledgeOut])
async def list_knowledge(
    organization_id: uuid.UUID, _: CurrentUser, session: DbSession
) -> list[KnowledgeOut]:
    """List knowledge documents for an organization."""
    docs = await KnowledgeService(session).list_for_org(organization_id)
    return [KnowledgeOut.model_validate(d) for d in docs]


@router.post("/knowledge", response_model=KnowledgeOut, status_code=201)
async def create_knowledge(
    body: KnowledgeCreateIn, user: CurrentUser, session: DbSession
) -> KnowledgeOut:
    """Create a knowledge document."""
    if not user.is_superuser:
        await RBACService(session).require_permission(
            user.id, body.organization_id, "agent.manage"
        )
    doc = await KnowledgeService(session).create(
        organization_id=body.organization_id,
        title=body.title,
        content=body.content,
        actor_id=user.id,
        kind=body.kind,
        tags=body.tags,
        source=body.source,
    )
    return KnowledgeOut.model_validate(doc)


@router.delete("/knowledge/{document_id}", response_model=MessageResponse)
async def delete_knowledge(
    document_id: uuid.UUID, _: CurrentUser, session: DbSession
) -> MessageResponse:
    """Soft-delete a knowledge document."""
    await KnowledgeService(session).delete(document_id)
    return MessageResponse(message="Knowledge document deleted.")


# -- Metrics -------------------------------------------------------------
@router.get("/metrics", response_model=MetricsReportOut)
async def metrics(
    organization_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> MetricsReportOut:
    """Return aggregate agent metrics for an organization."""
    if not user.is_superuser:
        await RBACService(session).require_permission(
            user.id, organization_id, "analytics.read"
        )
    report = await MetricsService(session).report(organization_id)
    running = len(get_agent_manager().running())
    snap = get_agent_monitor().snapshot(running=running)
    return MetricsReportOut(
        runs=report.runs,
        total_tokens=report.total_tokens,
        total_cost_usd=report.total_cost_usd,
        avg_latency_ms=report.avg_latency_ms,
        success_rate=report.success_rate,
        monitor=MonitorOut(
            running=snap.running,
            runs_total=snap.runs_total,
            runs_succeeded=snap.runs_succeeded,
            runs_failed=snap.runs_failed,
            success_rate=snap.success_rate,
            total_tokens=snap.total_tokens,
            total_cost_usd=snap.total_cost_usd,
            avg_latency_ms=snap.avg_latency_ms,
            tool_calls=snap.tool_calls,
        ),
    )
