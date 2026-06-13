from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AgentRun, WorkflowExecution
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.workflow_monitoring import (
    RetryWorkflowExecutionResponse,
    WorkflowExecutionDetail,
    WorkflowExecutionListItem,
    WorkflowRelatedAgentRun,
    WorkflowStep,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_workflow_executions(
    db: Session,
) -> PaginatedResponse[WorkflowExecutionListItem]:
    statement = select(WorkflowExecution).order_by(
        WorkflowExecution.created_at.desc(),
    )

    try:
        executions = list(db.scalars(statement).all())
        items = [_to_workflow_execution_list_item(execution) for execution in executions]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Workflow executions could not be loaded.",
        ) from exc

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=1,
            page_size=20,
            total_items=len(items),
            total_pages=1,
        ),
    )


def get_workflow_execution_by_id(
    execution_id: str,
    db: Session,
) -> WorkflowExecutionDetail | None:
    try:
        execution = db.get(WorkflowExecution, execution_id)

        if execution is None:
            return None

        related_runs_statement = (
            select(AgentRun)
            .where(AgentRun.workflow_execution_id == execution_id)
            .order_by(AgentRun.created_at.desc())
        )
        related_agent_runs = list(db.scalars(related_runs_statement).all())

        return _to_workflow_execution_detail(execution, related_agent_runs)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Workflow execution could not be loaded.",
        ) from exc


def retry_workflow_execution(
    execution_id: str,
    reason: str,
    db: Session,
) -> RetryWorkflowExecutionResponse | None:
    try:
        original_execution = db.get(WorkflowExecution, execution_id)

        if original_execution is None:
            return None

        now = utc_now()
        retry_execution = WorkflowExecution(
            id=f"exec_retry_{now.strftime('%Y%m%d%H%M%S%f')}",
            workflow_name=original_execution.workflow_name,
            process=original_execution.process,
            related_object_type=original_execution.related_object_type,
            related_object_id=original_execution.related_object_id,
            trigger_source="Manual Retry",
            status="queued",
            input_summary="Manual retry requested from Workflow Monitoring UI",
            output_summary="Awaiting retry execution.",
            result_summary="Retry queued",
            agent_name=original_execution.agent_name,
            created_at=now,
            updated_at=now,
        )

        db.add(retry_execution)
        db.commit()
        db.refresh(retry_execution)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Workflow retry could not be queued.",
        ) from exc

    return RetryWorkflowExecutionResponse(
        id=retry_execution.id,
        status="queued",
        execution_id=retry_execution.id,
        retry_status="queued",
        message="Workflow retry queued successfully.",
        requested_at=now,
    )


def _to_workflow_execution_list_item(
    execution: WorkflowExecution,
) -> WorkflowExecutionListItem:
    started_at = execution.started_at or execution.created_at
    related_object = execution.related_object_id or "unassigned"
    trigger_source = execution.trigger_source or "Unknown"
    agent_name = execution.agent_name or "Unassigned"

    return WorkflowExecutionListItem(
        id=execution.id,
        workflow_name=execution.workflow_name,
        process=execution.process or "Monitoring",
        status=_safe_workflow_status(execution.status),
        related_object_type=execution.related_object_type,
        related_object_id=execution.related_object_id,
        trigger_source=trigger_source,
        duration_seconds=execution.duration_seconds,
        agent_name=agent_name,
        related_object=related_object,
        started_at=started_at,
        finished_at=execution.finished_at,
        created_at=execution.created_at,
        duration=_format_duration(execution),
        triggered_by=trigger_source,
        agent=agent_name,
    )


def _to_workflow_execution_detail(
    execution: WorkflowExecution,
    related_agent_runs: list[AgentRun],
) -> WorkflowExecutionDetail:
    list_item = _to_workflow_execution_list_item(execution)

    return WorkflowExecutionDetail(
        **list_item.model_dump(),
        input_summary=execution.input_summary or "No input summary recorded.",
        output_summary=execution.output_summary or "No output summary recorded.",
        result_summary=execution.result_summary,
        steps=_build_workflow_steps(execution),
        error_message=execution.error_message,
        updated_at=execution.updated_at,
        related_agent_runs=[
            _to_related_agent_run(run) for run in related_agent_runs
        ],
    )


def _to_related_agent_run(run: AgentRun) -> WorkflowRelatedAgentRun:
    return WorkflowRelatedAgentRun(
        id=run.id,
        agent_id=run.agent_id,
        agent_name=run.agent_name,
        status=_safe_workflow_status(run.status),
        requested_at=run.requested_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        input_summary=run.input_summary,
        output_summary=run.output_summary,
        error_message=run.error_message,
    )


def _build_workflow_steps(execution: WorkflowExecution) -> list[WorkflowStep]:
    duration = _format_duration(execution)

    steps = [
        WorkflowStep(
            name="Input captured",
            status="success",
            duration="recorded",
        ),
        WorkflowStep(
            name="Agent processing",
            status=_safe_workflow_status(execution.status),
            duration=duration,
        ),
    ]

    if execution.result_summary:
        steps.append(
            WorkflowStep(
                name="Result stored",
                status=_safe_workflow_status(execution.status),
                duration="recorded",
            )
        )

    return steps


def _safe_workflow_status(status: str | None) -> str:
    if status in {"success", "failed", "running", "queued"}:
        return status

    return "queued"


def _format_duration(execution: WorkflowExecution) -> str:
    if execution.duration_seconds is not None:
        return _format_seconds(execution.duration_seconds)

    if execution.status == "running":
        return "running"

    if execution.status == "queued":
        return "queued"

    return "not recorded"


def _format_seconds(duration_seconds: int) -> str:
    if duration_seconds < 60:
        return f"{duration_seconds}s"

    minutes, seconds = divmod(duration_seconds, 60)

    if seconds == 0:
        return f"{minutes}m"

    return f"{minutes}m {seconds}s"
