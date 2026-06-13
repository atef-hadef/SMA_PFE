from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AgentRun, WorkflowExecution
from app.schemas.agents import (
    AgentDetail,
    AgentListItem,
    AgentRecentRun,
    AgentRunResponse,
)
from app.schemas.common import PaginatedResponse, PaginationMeta

DEFAULT_AGENT_RUN_USER_ID = "user_030"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_agents(db: Session) -> PaginatedResponse[AgentListItem]:
    try:
        runs = _load_agent_runs(db)
        items = [
            _to_agent_list_item(agent_id, agent_runs)
            for agent_id, agent_runs in _group_runs_by_agent(runs).items()
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="AI agents could not be loaded.",
        ) from exc

    items.sort(key=lambda item: item.last_execution, reverse=True)

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=1,
            page_size=20,
            total_items=len(items),
            total_pages=1,
        ),
    )


def get_agent_by_id(agent_id: str, db: Session) -> AgentDetail | None:
    try:
        statement = (
            select(AgentRun)
            .where(AgentRun.agent_id == agent_id)
            .order_by(AgentRun.created_at.desc())
        )
        runs = list(db.scalars(statement).all())

        if not runs:
            return None

        related_workflows = _load_related_workflows(runs, db)

        return _to_agent_detail(agent_id, runs, related_workflows)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="AI agent could not be loaded.",
        ) from exc


def run_agent(
    agent_id: str,
    payload: dict[str, Any],
    db: Session,
    requested_by: str = DEFAULT_AGENT_RUN_USER_ID,
) -> AgentRunResponse | None:
    try:
        existing_runs_statement = (
            select(AgentRun)
            .where(AgentRun.agent_id == agent_id)
            .order_by(AgentRun.created_at.desc())
        )
        existing_runs = list(db.scalars(existing_runs_statement).all())

        if not existing_runs:
            return None

        latest_run = existing_runs[0]
        now = utc_now()
        run = AgentRun(
            id=f"run_manual_{now.strftime('%Y%m%d%H%M%S%f')}",
            agent_id=agent_id,
            agent_name=latest_run.agent_name or _readable_agent_name(agent_id),
            process=latest_run.process or "AI Agents",
            requested_by=requested_by,
            requested_at=now,
            status="queued",
            input_summary="Manual test run requested from AI Agent Center",
            output_summary="Awaiting execution",
            created_at=now,
            updated_at=now,
        )

        db.add(run)
        db.commit()
        db.refresh(run)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="AI agent run could not be queued.",
        ) from exc

    return AgentRunResponse(
        agent_id=agent_id,
        run_status="queued",
        message="Agent run queued successfully.",
        requested_at=now,
    )


def _load_agent_runs(db: Session) -> list[AgentRun]:
    statement = select(AgentRun).order_by(AgentRun.created_at.desc())
    return list(db.scalars(statement).all())


def _group_runs_by_agent(runs: list[AgentRun]) -> dict[str, list[AgentRun]]:
    grouped_runs: dict[str, list[AgentRun]] = {}

    for run in runs:
        grouped_runs.setdefault(run.agent_id, []).append(run)

    return grouped_runs


def _to_agent_list_item(
    agent_id: str,
    runs: list[AgentRun],
) -> AgentListItem:
    latest_run = runs[0]

    return AgentListItem(
        id=agent_id,
        name=latest_run.agent_name or _readable_agent_name(agent_id),
        process=latest_run.process or "AI Agents",
        status="active",
        type="automation_agent",
        success_rate=_calculate_success_rate(runs),
        last_execution=_run_timestamp(latest_run),
        total_runs=len(runs),
        description=_agent_description(agent_id),
    )


def _to_agent_detail(
    agent_id: str,
    runs: list[AgentRun],
    related_workflows: list[str],
) -> AgentDetail:
    list_item = _to_agent_list_item(agent_id, runs)

    return AgentDetail(
        **list_item.model_dump(),
        input_description=_agent_input_description(agent_id),
        output_description=_agent_output_description(agent_id),
        tools=_agent_tools(agent_id),
        related_workflows=related_workflows or _default_related_workflows(agent_id),
        recent_runs=[_to_agent_recent_run(run) for run in runs[:5]],
    )


def _to_agent_recent_run(run: AgentRun) -> AgentRecentRun:
    return AgentRecentRun(
        id=run.id,
        execution_id=run.workflow_execution_id or run.id,
        status=_safe_run_status(run.status),
        duration=_format_run_duration(run),
        started_at=run.started_at or run.requested_at or run.created_at,
        requested_at=run.requested_at,
        input_summary=run.input_summary,
        output_summary=run.output_summary,
    )


def _load_related_workflows(
    runs: list[AgentRun],
    db: Session,
) -> list[str]:
    workflow_ids = [
        run.workflow_execution_id for run in runs if run.workflow_execution_id
    ]

    if not workflow_ids:
        return []

    statement = select(WorkflowExecution).where(WorkflowExecution.id.in_(workflow_ids))
    workflows = list(db.scalars(statement).all())

    return sorted({workflow.workflow_name for workflow in workflows})


def _calculate_success_rate(runs: list[AgentRun]) -> int:
    if not runs:
        return 0

    successful_runs = sum(1 for run in runs if run.status == "success")

    return round((successful_runs / len(runs)) * 100)


def _run_timestamp(run: AgentRun) -> datetime:
    return run.requested_at or run.started_at or run.created_at


def _safe_run_status(status: str | None) -> str:
    if status in {"success", "failed", "running", "queued"}:
        return status

    return "queued"


def _format_run_duration(run: AgentRun) -> str:
    if run.started_at and run.finished_at:
        duration_seconds = int((run.finished_at - run.started_at).total_seconds())
        return _format_seconds(duration_seconds)

    if run.status == "running":
        return "running"

    if run.status == "queued":
        return "queued"

    return "not recorded"


def _format_seconds(duration_seconds: int) -> str:
    if duration_seconds < 60:
        return f"{duration_seconds}s"

    minutes, seconds = divmod(duration_seconds, 60)

    if seconds == 0:
        return f"{minutes}m"

    return f"{minutes}m {seconds}s"


def _readable_agent_name(agent_id: str) -> str:
    return " ".join(part.capitalize() for part in agent_id.replace("agent_", "").split("_"))


def _agent_description(agent_id: str) -> str:
    descriptions = {
        "agent_leave_validation": (
            "Validates leave balance, policy constraints, and conflict risk."
        ),
        "agent_lead_scoring": (
            "Scores CRM leads using sentiment, urgency, and business intent."
        ),
    }

    return descriptions.get(
        agent_id,
        "Automation agent derived from recorded PostgreSQL agent runs.",
    )


def _agent_input_description(agent_id: str) -> str:
    descriptions = {
        "agent_leave_validation": (
            "Leave request dates, employee balance, policy rules, and team coverage."
        ),
        "agent_lead_scoring": (
            "CRM lead profile, source, message, sentiment, urgency, and interaction history."
        ),
    }

    return descriptions.get(
        agent_id,
        "Workflow or process data captured by FlowPilot AI.",
    )


def _agent_output_description(agent_id: str) -> str:
    descriptions = {
        "agent_leave_validation": (
            "Validation status, conflict risk, and manager approval recommendation."
        ),
        "agent_lead_scoring": (
            "Lead score, priority level, suggested routing, and recommended action."
        ),
    }

    return descriptions.get(
        agent_id,
        "Queued run status, processing summary, and operational recommendation.",
    )


def _agent_tools(agent_id: str) -> list[str]:
    tools = {
        "agent_leave_validation": [
            "leave_balance_checker",
            "policy_rule_validator",
            "coverage_conflict_detector",
        ],
        "agent_lead_scoring": [
            "sentiment_analyzer",
            "urgency_detector",
            "lead_score_calculator",
        ],
    }

    return tools.get(
        agent_id,
        [
            "workflow_context_reader",
            "process_status_analyzer",
            "recommendation_builder",
        ],
    )


def _default_related_workflows(agent_id: str) -> list[str]:
    workflows = {
        "agent_leave_validation": ["Leave Request Approval Flow"],
        "agent_lead_scoring": ["CRM Lead Scoring Flow"],
    }

    return workflows.get(agent_id, [])
