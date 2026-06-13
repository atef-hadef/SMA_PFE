from datetime import date, datetime, timezone
import json
import logging
from decimal import Decimal
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AgentRun, LeaveRequest, User, WorkflowExecution
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.leave_requests import (
    LeaveAutomationAnalysisCallback,
    LeaveBalancePrecheckResponse,
    LeaveCallbackResponse,
    LeaveDecisionResponse,
    LeaveDecisionSyncCallback,
    LeaveRequestCreate,
    LeaveRequestHistoryResponse,
    LeaveRequestResponse,
    PendingLeaveRequestResponse,
)

DEFAULT_EMPLOYEE_ID = "user_010"
DEFAULT_MANAGER_ID = "user_020"
LEAVE_REQUEST_PROCESS = "leave_request"
LEAVE_ANALYSIS_WORKFLOW_NAME = "FP_LEAVE_01_REQUEST_ANALYSIS"
LEAVE_DECISION_SYNC_WORKFLOW_NAME = "FP_LEAVE_02_DECISION_SYNC"
LEAVE_ANALYSIS_AGENT_ID = "hr_leave_request_analysis"
LEAVE_ANALYSIS_AGENT_NAME = "HR Leave Request Analysis"
LEAVE_DECISION_SYNC_AGENT_ID = "hr_leave_decision_sync"
LEAVE_DECISION_SYNC_AGENT_NAME = "HR Leave Decision Sync"
LEAVE_REQUEST_ANALYSIS_WEBHOOK_PATH = "flowpilot/leave/request-analysis"
LEAVE_DECISION_SYNC_WEBHOOK_PATH = "flowpilot/leave/decision-sync"
MVP_ODOO_EMPLOYEE_IDS = {"user_010": 3}
MVP_ODOO_DEPARTMENT_ID = 2
MVP_ODOO_ANNUAL_LEAVE_TYPE_ID = 5
MVP_MANAGER_ID = "manager_001"
MVP_MANAGER_NAME = "Manager RH"
MVP_MANAGER_EMAIL = "manager.rh@flowpilot.ai"
PENDING_MANAGER_STATUSES = ("pending", "manager_review_required")
CANONICAL_DECISION_STATUSES = {"approved", "rejected"}
LEAVE_REQUEST_INTEGRATION_COLUMNS = {
    "odoo_leave_id": "ALTER TABLE leave_requests ADD COLUMN odoo_leave_id VARCHAR(64)",
    "odoo_state": "ALTER TABLE leave_requests ADD COLUMN odoo_state VARCHAR(40)",
    "odoo_sync_status": (
        "ALTER TABLE leave_requests ADD COLUMN odoo_sync_status VARCHAR(40) DEFAULT 'pending'"
    ),
    "automation_recommendation": (
        "ALTER TABLE leave_requests ADD COLUMN automation_recommendation VARCHAR(120)"
    ),
    "automation_summary": "ALTER TABLE leave_requests ADD COLUMN automation_summary TEXT",
    "score": "ALTER TABLE leave_requests ADD COLUMN score INTEGER",
    "available_days": "ALTER TABLE leave_requests ADD COLUMN available_days NUMERIC(8, 2)",
    "requested_days": "ALTER TABLE leave_requests ADD COLUMN requested_days NUMERIC(8, 2)",
}
logger = logging.getLogger(__name__)


class LeaveBalanceValidationError(Exception):
    def __init__(self, data: LeaveBalancePrecheckResponse) -> None:
        self.data = data
        super().__init__(
            data.message
            or data.ai_explanation
            or "Le solde disponible est insuffisant."
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_leave_request(
    payload: LeaveRequestCreate,
    db: Session,
    user_id: str = DEFAULT_EMPLOYEE_ID,
) -> LeaveRequestResponse:
    _ensure_leave_request_integration_columns(db)
    requested_days = _requested_days(payload.start_date, payload.end_date)
    _prevalidate_leave_balance(
        user_id=user_id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        requested_days=Decimal(requested_days),
    )

    now = utc_now()
    leave_request = LeaveRequest(
        id=f"leave_{uuid4().hex[:8]}",
        user_id=user_id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        status="pending",
        odoo_sync_status="pending",
        requested_days=requested_days,
        created_at=now,
        updated_at=now,
    )
    workflow_execution, agent_run = _prepare_leave_workflow_trace(
        leave_request=leave_request,
        workflow_name=LEAVE_ANALYSIS_WORKFLOW_NAME,
        trigger_source="Leave Request Submission",
        status="running",
        input_summary="Leave request queued for n8n Odoo analysis.",
        result_summary="Workflow 1 request analysis trigger prepared.",
        agent_id=LEAVE_ANALYSIS_AGENT_ID,
        agent_name=LEAVE_ANALYSIS_AGENT_NAME,
        requested_by=leave_request.user_id,
        now=now,
    )

    try:
        db.add(leave_request)
        db.add(workflow_execution)
        db.flush()
        db.add(agent_run)
        db.commit()
        db.refresh(leave_request)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Leave request could not be saved.",
        ) from exc

    try:
        _post_leave_request_analysis_webhook(
            _build_leave_request_analysis_payload(
                leave_request=leave_request,
                workflow_execution_id=workflow_execution.id,
                db=db,
            ),
        )
    except HTTPException:
        _mark_leave_trigger_failed(
            db=db,
            leave_request_id=leave_request.id,
            workflow_execution_id=workflow_execution.id,
            agent_run_id=agent_run.id,
            preserve_decision_status=False,
            error_message="Leave request analysis workflow could not be triggered.",
        )
        raise

    return LeaveRequestResponse(
        id=leave_request.id,
        employee_id=leave_request.user_id,
        leave_type=leave_request.leave_type,
        start_date=leave_request.start_date,
        end_date=leave_request.end_date,
        reason=leave_request.reason,
        status=leave_request.status,
        created_at=leave_request.created_at,
    )


def get_pending_leave_requests(
    db: Session,
) -> PaginatedResponse[PendingLeaveRequestResponse]:
    _ensure_leave_request_integration_columns(db)
    statement = (
        select(LeaveRequest)
        .where(LeaveRequest.status.in_(PENDING_MANAGER_STATUSES))
        .order_by(LeaveRequest.created_at.desc())
    )

    try:
        leave_requests = list(db.scalars(statement).all())
        items = [
            _to_pending_leave_request_response(leave_request, db)
            for leave_request in leave_requests
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Pending leave requests could not be loaded.",
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


def get_leave_requests_history(
    db: Session,
    status: str | None = None,
    user_id: str | None = None,
) -> PaginatedResponse[LeaveRequestHistoryResponse]:
    _ensure_leave_request_integration_columns(db)
    statement = select(LeaveRequest).order_by(LeaveRequest.updated_at.desc())
    if status:
        statement = statement.where(LeaveRequest.status == status)
    if user_id:
        statement = statement.where(LeaveRequest.user_id == user_id)

    try:
        leave_requests = list(db.scalars(statement).all())
        items = [
            _to_leave_request_history_response(leave_request, db)
            for leave_request in leave_requests
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Leave request history could not be loaded.",
        ) from exc

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=1,
            page_size=len(items),
            total_items=len(items),
            total_pages=1,
        ),
    )


def approve_leave_request(
    request_id: str,
    comment: str,
    db: Session,
) -> LeaveDecisionResponse:
    return _update_leave_decision(
        request_id=request_id,
        status="approved",
        comment=comment,
        db=db,
    )


def reject_leave_request(
    request_id: str,
    comment: str,
    db: Session,
) -> LeaveDecisionResponse:
    return _update_leave_decision(
        request_id=request_id,
        status="rejected",
        comment=comment,
        db=db,
    )


def save_leave_automation_analysis(
    request_id: str,
    payload: LeaveAutomationAnalysisCallback,
    db: Session,
) -> LeaveCallbackResponse:
    _ensure_leave_request_integration_columns(db)
    leave_request = _get_required_leave_request(request_id, db)
    now = utc_now()

    if payload.odoo_leave_id is not None:
        leave_request.odoo_leave_id = str(payload.odoo_leave_id)
    if payload.odoo_state is not None:
        leave_request.odoo_state = payload.odoo_state

    odoo_created = _odoo_creation_succeeded(payload)
    if odoo_created:
        leave_request.odoo_sync_status = "synced"
    elif payload.ok is False or _normalize(payload.odoo_sync_status) == "failed":
        leave_request.odoo_sync_status = "failed"

    recommendation = _analysis_recommendation(payload)
    if recommendation is not None:
        leave_request.automation_recommendation = recommendation

    leave_request.automation_summary = _analysis_summary(payload)

    if payload.score is not None:
        leave_request.score = payload.score
    available_days = _payload_available_days(payload)
    requested_days = _payload_requested_days(payload)
    if available_days is not None:
        leave_request.available_days = available_days
    if requested_days is not None:
        leave_request.requested_days = requested_days

    if _is_policy_rejection(payload):
        leave_request.status = "rejected_by_policy"
    elif _normalize(payload.odoo_state) == "confirm":
        leave_request.status = "manager_review_required"
    elif leave_request.status not in PENDING_MANAGER_STATUSES:
        leave_request.status = "pending"

    leave_request.updated_at = now

    workflow_execution_id, _agent_run_id = _persist_leave_traces_safely(
        request_id=leave_request.id,
        requested_by=leave_request.user_id,
        workflow_name=payload.workflow or LEAVE_ANALYSIS_WORKFLOW_NAME,
        workflow_status="success" if payload.ok is not False else "failed",
        workflow_summary=leave_request.automation_summary,
        agent_id=LEAVE_ANALYSIS_AGENT_ID,
        agent_name=LEAVE_ANALYSIS_AGENT_NAME,
        agent_status="success" if payload.ok is not False else "failed",
        agent_output=leave_request.automation_summary,
        now=now,
        db=db,
        workflow_payload=payload.workflow_execution,
        agent_run_payload=payload.agent_run,
        workflow_execution_id=payload.workflow_execution_id,
        agent_run_id=payload.agent_run_id,
    )

    try:
        db.commit()
        db.refresh(leave_request)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Leave automation analysis callback could not be saved.")
        raise HTTPException(
            status_code=500,
            detail="Leave request automation analysis could not be saved.",
        ) from exc

    if workflow_execution_id is None:
        logger.info("Leave analysis callback saved without workflow trace for %s.", request_id)

    return LeaveCallbackResponse(
        ok=True,
        request_id=leave_request.id,
        message="Leave request automation analysis saved",
    )


def save_leave_decision_sync_result(
    request_id: str,
    payload: LeaveDecisionSyncCallback,
    db: Session,
) -> LeaveCallbackResponse:
    _ensure_leave_request_integration_columns(db)
    leave_request = _get_required_leave_request(request_id, db)
    now = utc_now()
    decision = _normalize(payload.decision)
    odoo_state = _normalize(payload.odoo_state)
    sync_succeeded = (
        decision in CANONICAL_DECISION_STATUSES
        and payload.ok is not False
        and (
            (decision == "approved" and odoo_state == "validate")
            or (decision == "rejected" and odoo_state == "refuse")
            or _normalize(payload.odoo_sync_status) == "synced"
        )
    )

    if payload.odoo_leave_id is not None:
        leave_request.odoo_leave_id = str(payload.odoo_leave_id)
    if payload.odoo_state is not None:
        leave_request.odoo_state = payload.odoo_state

    if sync_succeeded:
        leave_request.status = decision
        leave_request.odoo_sync_status = "synced"
        leave_request.automation_summary = (
            f"Manager decision '{decision}' was synchronized with Odoo."
        )
    else:
        if decision in CANONICAL_DECISION_STATUSES:
            leave_request.status = decision
        leave_request.odoo_sync_status = "failed"
        leave_request.automation_summary = _decision_sync_failure_summary(payload)

    comment = payload.manager_comment or payload.comment
    if comment is not None:
        leave_request.decision_comment = comment

    leave_request.reviewed_at = (
        payload.decided_at
        or payload.approved_at
        or leave_request.reviewed_at
        or now
    )
    leave_request.updated_at = now

    _persist_leave_traces_safely(
        request_id=leave_request.id,
        requested_by=leave_request.reviewed_by or DEFAULT_MANAGER_ID,
        workflow_name=payload.workflow or LEAVE_DECISION_SYNC_WORKFLOW_NAME,
        workflow_status="success" if sync_succeeded else "failed",
        workflow_summary=leave_request.automation_summary,
        agent_id=LEAVE_DECISION_SYNC_AGENT_ID,
        agent_name=LEAVE_DECISION_SYNC_AGENT_NAME,
        agent_status="success" if sync_succeeded else "failed",
        agent_output=leave_request.automation_summary,
        now=now,
        db=db,
        workflow_payload=payload.workflow_execution,
        agent_run_payload=payload.agent_run,
        workflow_execution_id=payload.workflow_execution_id,
        agent_run_id=payload.agent_run_id,
    )

    try:
        db.commit()
        db.refresh(leave_request)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Leave decision sync callback could not be saved.")
        raise HTTPException(
            status_code=500,
            detail="Leave request decision sync could not be saved.",
        ) from exc

    return LeaveCallbackResponse(
        ok=True,
        request_id=leave_request.id,
        message="Leave request decision sync saved",
    )


def _to_leave_request_history_response(
    leave_request: LeaveRequest,
    db: Session,
) -> LeaveRequestHistoryResponse:
    employee = db.get(User, leave_request.user_id)
    requested_days = (
        float(leave_request.requested_days)
        if leave_request.requested_days is not None
        else None
    )
    return LeaveRequestHistoryResponse(
        id=leave_request.id,
        employee_id=leave_request.user_id,
        employee_name=employee.full_name if employee else "Employé inconnu",
        department=employee.department if employee and employee.department else "Non renseigné",
        leave_type=leave_request.leave_type,
        start_date=leave_request.start_date,
        end_date=leave_request.end_date,
        requested_days=requested_days,
        reason=leave_request.reason,
        status=leave_request.status,
        manager_comment=leave_request.decision_comment,
        decided_at=leave_request.reviewed_at,
        created_at=leave_request.created_at,
        odoo_sync_status=leave_request.odoo_sync_status,
    )


def _to_pending_leave_request_response(
    leave_request: LeaveRequest,
    db: Session,
) -> PendingLeaveRequestResponse:
    employee = db.get(User, leave_request.user_id)
    analysis_details = _pending_analysis_details(leave_request)
    requested_days = (
        leave_request.requested_days
        if leave_request.requested_days is not None
        else Decimal(_requested_days(leave_request.start_date, leave_request.end_date))
    )
    available_days = leave_request.available_days
    balance_gap_days = _analysis_decimal(analysis_details, "balance_gap_days")
    if balance_gap_days is None and available_days is not None:
        gap = requested_days - available_days
        balance_gap_days = gap if gap > 0 else Decimal("0")
    analysis_details = _with_balance_explanation_fallback(
        analysis_details=analysis_details,
        available_days=available_days,
        requested_days=requested_days,
        recommendation=_pending_ai_recommendation(leave_request),
    )

    return PendingLeaveRequestResponse(
        id=leave_request.id,
        employee_id=leave_request.user_id,
        employee_name=employee.full_name if employee else "Unknown Employee",
        department=employee.department if employee and employee.department else "Unassigned",
        leave_type=leave_request.leave_type,
        start_date=leave_request.start_date,
        end_date=leave_request.end_date,
        reason=leave_request.reason,
        status=leave_request.status,
        created_at=leave_request.created_at,
        ai_recommendation=_pending_ai_recommendation(leave_request),
        risk_level=_pending_risk_level(leave_request, analysis_details),
        conflict_detected=_pending_conflict_detected(analysis_details),
        automation_summary=_analysis_text(leave_request.automation_summary),
        available_days=available_days,
        requested_days=requested_days,
        balance_gap_days=balance_gap_days,
        ai_explanation=_analysis_string(analysis_details, "ai_explanation"),
        decision_reasons=_analysis_string_list(analysis_details, "decision_reasons"),
        blocking_reasons=_analysis_string_list(analysis_details, "blocking_reasons"),
        approval_factors=_analysis_string_list(analysis_details, "approval_factors"),
        rejection_factors=_analysis_string_list(analysis_details, "rejection_factors"),
        score_reasons=_analysis_string_list(analysis_details, "score_reasons"),
        manager_guidance=_analysis_string(analysis_details, "manager_guidance"),
        can_manager_override=_analysis_bool(analysis_details, "can_manager_override"),
        can_sync_with_odoo=bool(leave_request.odoo_leave_id),
    )


def _update_leave_decision(
    request_id: str,
    status: str,
    comment: str,
    db: Session,
) -> LeaveDecisionResponse:
    _ensure_leave_request_integration_columns(db)
    leave_request = _get_required_leave_request(request_id, db)

    now = utc_now()
    leave_request.status = status
    leave_request.reviewed_by = DEFAULT_MANAGER_ID
    leave_request.reviewed_at = now
    leave_request.decision_comment = comment
    leave_request.odoo_sync_status = "pending"
    leave_request.automation_summary = (
        f"Manager decision '{status}' saved locally. Odoo synchronization is pending."
    )
    leave_request.updated_at = now
    workflow_execution, agent_run = _prepare_leave_workflow_trace(
        leave_request=leave_request,
        workflow_name=LEAVE_DECISION_SYNC_WORKFLOW_NAME,
        trigger_source="Manager Approval",
        status="running",
        input_summary=f"Manager decision '{status}' queued for Odoo synchronization.",
        result_summary="Workflow 2 decision synchronization trigger prepared.",
        agent_id=LEAVE_DECISION_SYNC_AGENT_ID,
        agent_name=LEAVE_DECISION_SYNC_AGENT_NAME,
        requested_by=DEFAULT_MANAGER_ID,
        now=now,
    )

    try:
        db.add(workflow_execution)
        db.flush()
        db.add(agent_run)
        db.commit()
        db.refresh(leave_request)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Leave request decision could not be saved.",
        ) from exc

    if not leave_request.odoo_leave_id:
        _mark_leave_trigger_failed(
            db=db,
            leave_request_id=leave_request.id,
            workflow_execution_id=workflow_execution.id,
            agent_run_id=agent_run.id,
            preserve_decision_status=True,
            error_message="Odoo leave id is missing; decision sync was not triggered.",
        )
        raise HTTPException(
            status_code=422,
            detail=(
                "Manager decision was saved locally, but Odoo sync cannot start "
                "because the leave request has no Odoo leave id yet."
            ),
        )

    try:
        _post_leave_decision_sync_webhook(
            _build_leave_decision_sync_payload(
                leave_request=leave_request,
                workflow_execution_id=workflow_execution.id,
                decision=status,
                manager_comment=comment,
                db=db,
            ),
        )
    except HTTPException:
        _mark_leave_trigger_failed(
            db=db,
            leave_request_id=leave_request.id,
            workflow_execution_id=workflow_execution.id,
            agent_run_id=agent_run.id,
            preserve_decision_status=True,
            error_message="Leave decision synchronization workflow could not be triggered.",
        )
        raise

    return LeaveDecisionResponse(
        id=leave_request.id,
        status=leave_request.status,
        manager_comment=leave_request.decision_comment or "",
        updated_at=leave_request.updated_at,
    )


def _get_required_leave_request(request_id: str, db: Session) -> LeaveRequest:
    try:
        leave_request = db.get(LeaveRequest, request_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Leave request could not be loaded.",
        ) from exc

    if leave_request is None:
        raise HTTPException(status_code=404, detail="Leave request not found.")

    return leave_request


def _ensure_leave_request_integration_columns(db: Session) -> None:
    try:
        existing_columns = {
            column["name"]
            for column in inspect(db.get_bind()).get_columns(LeaveRequest.__tablename__)
        }
    except SQLAlchemyError:
        logger.exception("Leave request table columns could not be inspected.")
        return

    missing_columns = [
        column
        for column in LEAVE_REQUEST_INTEGRATION_COLUMNS
        if column not in existing_columns
    ]
    if not missing_columns:
        return

    try:
        for column in missing_columns:
            db.execute(text(LEAVE_REQUEST_INTEGRATION_COLUMNS[column]))
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Leave request integration columns could not be added.")
        raise HTTPException(
            status_code=500,
            detail="Leave request integration schema could not be prepared.",
        ) from exc


def _prepare_leave_workflow_trace(
    leave_request: LeaveRequest,
    workflow_name: str,
    trigger_source: str,
    status: str,
    input_summary: str,
    result_summary: str,
    agent_id: str,
    agent_name: str,
    requested_by: str | None,
    now: datetime,
) -> tuple[WorkflowExecution, AgentRun]:
    workflow_execution = WorkflowExecution(
        id=_generate_trace_id("exec_leave", now),
        related_object_type="leave_request",
        related_object_id=leave_request.id,
        workflow_name=workflow_name,
        process=LEAVE_REQUEST_PROCESS,
        trigger_source=trigger_source,
        status=status,
        started_at=now,
        input_summary=input_summary,
        result_summary=result_summary,
        agent_name=agent_name,
        created_at=now,
        updated_at=now,
    )
    agent_run = AgentRun(
        id=_generate_trace_id("run_leave", now),
        agent_id=agent_id,
        agent_name=agent_name,
        process=LEAVE_REQUEST_PROCESS,
        workflow_execution_id=workflow_execution.id,
        requested_by=requested_by,
        requested_at=now,
        status=status,
        started_at=now,
        input_summary=input_summary,
        created_at=now,
        updated_at=now,
    )
    return workflow_execution, agent_run


def _build_leave_request_analysis_payload(
    leave_request: LeaveRequest,
    workflow_execution_id: str,
    db: Session,
) -> dict[str, object | None]:
    employee = db.get(User, leave_request.user_id)
    employee_name = employee.full_name if employee else "Sarah N."
    employee_email = employee.email if employee else "sarah@flowpilot.ai"
    department = employee.department if employee and employee.department else "Operations"
    requested_days = float(leave_request.requested_days or 0) or _requested_days(
        leave_request.start_date,
        leave_request.end_date,
    )

    return {
        "flowpilot_request_id": leave_request.id,
        "workflow_execution_id": workflow_execution_id,
        "flowpilot_api_base_url": settings.FLOWPILOT_API_BASE_URL_FOR_N8N,
        "odoo_base_url": settings.ODOO_BASE_URL,
        "odoo_db": settings.ODOO_DB,
        "odoo_uid": settings.ODOO_UID,
        "odoo_password": settings.ODOO_PASSWORD,
        "employee_id": leave_request.user_id,
        "odoo_employee_id": _odoo_employee_id(leave_request.user_id),
        "employee_name": employee_name,
        "employee_email": employee_email,
        "manager_id": MVP_MANAGER_ID,
        "manager_name": MVP_MANAGER_NAME,
        "manager_email": MVP_MANAGER_EMAIL,
        "department_id": department,
        "odoo_department_id": _odoo_department_id(department),
        "date_from": leave_request.start_date.isoformat(),
        "date_to": leave_request.end_date.isoformat(),
        "requested_days": requested_days,
        "leave_type": leave_request.leave_type,
        "odoo_leave_type_id": _odoo_leave_type_id(leave_request.leave_type),
        "reason": leave_request.reason,
    }


def _build_leave_decision_sync_payload(
    leave_request: LeaveRequest,
    workflow_execution_id: str,
    decision: str,
    manager_comment: str,
    db: Session,
) -> dict[str, object | None]:
    employee = db.get(User, leave_request.user_id)
    employee_name = employee.full_name if employee else "Sarah N."
    employee_email = employee.email if employee else "sarah@flowpilot.ai"

    return {
        "flowpilot_request_id": leave_request.id,
        "workflow_execution_id": workflow_execution_id,
        "flowpilot_api_base_url": settings.FLOWPILOT_API_BASE_URL_FOR_N8N,
        "odoo_base_url": settings.ODOO_BASE_URL,
        "odoo_db": settings.ODOO_DB,
        "odoo_uid": settings.ODOO_UID,
        "odoo_password": settings.ODOO_PASSWORD,
        "odoo_leave_id": leave_request.odoo_leave_id,
        "decision": decision,
        "manager_id": MVP_MANAGER_ID,
        "manager_name": MVP_MANAGER_NAME,
        "manager_email": MVP_MANAGER_EMAIL,
        "manager_comment": manager_comment,
        "employee_id": leave_request.user_id,
        "employee_name": employee_name,
        "employee_email": employee_email,
        "date_from": leave_request.start_date.isoformat(),
        "date_to": leave_request.end_date.isoformat(),
        "leave_type": leave_request.leave_type,
        "reason": leave_request.reason,
    }


def _post_leave_request_analysis_webhook(payload: dict[str, object | None]) -> object:
    return _post_leave_webhook(
        webhook_url=_leave_request_analysis_webhook_url(),
        payload=payload,
        unavailable_detail=(
            "Leave request was saved locally, but the n8n request analysis "
            "workflow could not be triggered. Confirm Workflow 1 is active."
        ),
        log_label="leave request analysis",
    )


def _fetch_leave_balance_from_odoo(
    user_id: str,
    leave_type: str,
) -> dict[str, Decimal] | None:
    odoo_employee_id = _odoo_employee_id(user_id)
    odoo_leave_type_id = _odoo_leave_type_id(leave_type)

    try:
        allocations = _odoo_execute_kw(
            model="hr.leave.allocation",
            method="search_read",
            args=[
                [
                    ["employee_id", "=", odoo_employee_id],
                    ["work_entry_type_id", "=", odoo_leave_type_id],
                    ["state", "=", "validate"],
                ],
            ],
            kwargs={
                "fields": [
                    "number_of_days",
                    "number_of_days_display",
                    "virtual_remaining_leaves",
                    "leaves_taken",
                    "work_entry_type_id",
                ],
                "limit": 1,
            },
        )
        taken_leaves = _odoo_execute_kw(
            model="hr.leave",
            method="search_read",
            args=[
                [
                    ["employee_id", "=", odoo_employee_id],
                    ["work_entry_type_id", "=", odoo_leave_type_id],
                    ["state", "in", ["validate", "validate1"]],
                ],
            ],
            kwargs={
                "fields": ["number_of_days", "request_date_from", "request_date_to"],
                "limit": 100,
            },
        )
    except (HTTPError, TimeoutError, URLError, ValueError) as exc:
        logger.warning("Odoo leave balance pre-validation failed: %s", exc)
        return None

    if not isinstance(allocations, list) or not allocations:
        return None
    if not isinstance(taken_leaves, list):
        taken_leaves = []

    allocation = allocations[0]
    if not isinstance(allocation, dict):
        return None

    total_days = _decimal_from_odoo_number(allocation.get("number_of_days"))
    leaves_taken = sum(
        (
            _decimal_from_odoo_number(leave.get("number_of_days"))
            for leave in taken_leaves
            if isinstance(leave, dict)
        ),
        Decimal("0"),
    )
    return {"available_days": total_days - leaves_taken}


def _odoo_execute_kw(
    model: str,
    method: str,
    args: list[object],
    kwargs: dict[str, object],
) -> object:
    request_payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": [
                settings.ODOO_DB,
                settings.ODOO_UID,
                settings.ODOO_PASSWORD,
                model,
                method,
                args,
                kwargs,
            ],
        },
        "id": 1,
    }
    request = Request(
        _odoo_jsonrpc_url(),
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request, timeout=30) as response:
        response_text = response.read().decode("utf-8")

    response_payload = json.loads(response_text)
    if not isinstance(response_payload, dict):
        raise ValueError("Odoo returned an invalid JSON-RPC response.")
    if response_payload.get("error"):
        raise ValueError(f"Odoo JSON-RPC error: {response_payload['error']}")
    if "result" not in response_payload:
        raise ValueError("Odoo JSON-RPC response did not include a result.")
    return response_payload["result"]


def _odoo_jsonrpc_url() -> str:
    base_url = settings.ODOO_BASE_URL.rstrip("/")
    if base_url.endswith("/jsonrpc"):
        return base_url
    return f"{base_url}/jsonrpc"


def _decimal_from_odoo_number(value: object) -> Decimal:
    if value is None or value is False:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _prevalidate_leave_balance(
    user_id: str,
    leave_type: str,
    start_date: date,
    end_date: date,
    requested_days: Decimal,
) -> None:
    precheck_payload = _build_leave_balance_precheck_payload(
        user_id=user_id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        requested_days=requested_days,
    )
    precheck_result = _normalize_leave_balance_precheck_result(
        _post_leave_balance_precheck_webhook(precheck_payload),
    )
    precheck_result.setdefault("date_from", start_date.isoformat())
    precheck_result.setdefault("date_to", end_date.isoformat())
    precheck_result.setdefault("requested_days", float(requested_days))

    if _is_leave_balance_precheck_success(precheck_result):
        return

    if _is_leave_balance_precheck_blocked(precheck_result):
        raise LeaveBalanceValidationError(
            _to_leave_balance_precheck_response(
                precheck_result,
                requested_days=requested_days,
            )
        )

    logger.warning("Workflow 0 returned an unusable balance precheck result: %s", precheck_result)
    raise HTTPException(
        status_code=502,
        detail=(
            "La verification du solde de conge est temporairement indisponible. "
            "Veuillez reessayer."
        ),
    )


def _build_leave_balance_precheck_payload(
    user_id: str,
    leave_type: str,
    start_date: date,
    end_date: date,
    requested_days: Decimal,
) -> dict[str, object | None]:
    return {
        "employee_id": user_id,
        "odoo_employee_id": _odoo_employee_id(user_id),
        "leave_type": leave_type,
        "odoo_leave_type_id": _odoo_leave_type_id(leave_type),
        "date_from": start_date.isoformat(),
        "date_to": end_date.isoformat(),
        "requested_days": float(requested_days),
        "odoo_base_url": settings.ODOO_BASE_URL,
        "odoo_db": settings.ODOO_DB,
        "odoo_uid": settings.ODOO_UID,
        "odoo_password": settings.ODOO_PASSWORD,
    }


def _post_leave_balance_precheck_webhook(payload: dict[str, object | None]) -> object:
    return _post_leave_webhook(
        webhook_url=settings.LEAVE_BALANCE_PRECHECK_WEBHOOK_URL,
        payload=payload,
        unavailable_detail=(
            "La verification du solde de conge est temporairement indisponible. "
            "Veuillez reessayer."
        ),
        log_label="leave balance precheck",
    )


def _normalize_leave_balance_precheck_result(value: object) -> dict[str, Any]:
    if isinstance(value, list):
        first_item = value[0] if value else {}
        return first_item if isinstance(first_item, dict) else {}
    return value if isinstance(value, dict) else {}


def _is_leave_balance_precheck_success(result: dict[str, Any]) -> bool:
    return result.get("ok") is True and result.get("has_enough_balance") is not False


def _is_leave_balance_precheck_blocked(result: dict[str, Any]) -> bool:
    return (
        result.get("ok") is False
        or result.get("error_code") == "INSUFFICIENT_LEAVE_BALANCE"
        or result.get("error_code") == "LEAVE_PERIOD_OVERLAP"
        or result.get("status") == "insufficient_balance"
        or result.get("status") in {"period_overlap", "leave_period_overlap"}
        or result.get("has_enough_balance") is False
    )


def _to_leave_balance_precheck_response(
    result: dict[str, Any],
    requested_days: Decimal,
) -> LeaveBalancePrecheckResponse:
    error_code = _precheck_error_code(result)
    is_overlap = error_code == "LEAVE_PERIOD_OVERLAP"
    available_days = _decimal_or_none(result.get("available_days"))
    resolved_requested_days = _decimal_or_none(result.get("requested_days")) or requested_days
    balance_gap_days = _decimal_or_none(result.get("balance_gap_days"))
    if balance_gap_days is None and available_days is not None:
        gap = resolved_requested_days - available_days
        balance_gap_days = gap if gap > 0 else Decimal("0")

    employee_guidance = _string_or_none(result.get("employee_guidance"))
    manager_guidance = _string_or_none(result.get("manager_guidance"))
    fallback_guidance = (
        "Veuillez choisir une autre periode."
        if is_overlap
        else (
            "Veuillez reduire la periode demandee ou contacter le service RH "
            "pour une exception."
        )
    )
    explanation = (
        _string_or_none(result.get("ai_explanation"))
        or (
            "La periode demandee chevauche deja un conge valide pour cet employe."
            if is_overlap
            else "La demande depasse le solde disponible."
        )
    )

    return LeaveBalancePrecheckResponse(
        ok=result.get("ok") if isinstance(result.get("ok"), bool) else False,
        status=_string_or_none(result.get("status"))
        or ("period_overlap" if is_overlap else "insufficient_balance"),
        error_code=error_code,
        available_days=available_days,
        requested_days=resolved_requested_days,
        balance_gap_days=balance_gap_days,
        has_enough_balance=_bool_or_none(result.get("has_enough_balance")),
        recommendation=_string_or_none(result.get("recommendation"))
        or ("change_dates" if is_overlap else "rejected_by_policy"),
        recommendation_label=_string_or_none(result.get("recommendation_label"))
        or ("Modifier la periode" if is_overlap else "Refus recommande"),
        risk_level=_string_or_none(result.get("risk_level")) or "high",
        ai_explanation=explanation,
        employee_guidance=employee_guidance or fallback_guidance,
        manager_guidance=manager_guidance or employee_guidance or fallback_guidance,
        message=_string_or_none(result.get("message")),
        conflict_detected=_bool_or_none(result.get("conflict_detected")),
        conflict_type=_string_or_none(result.get("conflict_type")),
        overlapping_leave_count=_int_or_none(result.get("overlapping_leave_count")),
        overlapping_leaves=_dict_list_or_empty(result.get("overlapping_leaves")),
        date_from=_date_or_none(result.get("date_from")),
        date_to=_date_or_none(result.get("date_to")),
    )


def _precheck_error_code(result: dict[str, Any]) -> str:
    explicit_error_code = _string_or_none(result.get("error_code"))
    if explicit_error_code:
        return explicit_error_code
    if result.get("status") in {"period_overlap", "leave_period_overlap"}:
        return "LEAVE_PERIOD_OVERLAP"
    return "INSUFFICIENT_LEAVE_BALANCE"


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _string_or_none(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _bool_or_none(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dict_list_or_empty(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _date_or_none(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _post_leave_decision_sync_webhook(payload: dict[str, object | None]) -> object:
    return _post_leave_webhook(
        webhook_url=_leave_decision_sync_webhook_url(),
        payload=payload,
        unavailable_detail=(
            "Manager decision was saved locally, but the n8n Odoo decision "
            "sync workflow could not be triggered. Confirm Workflow 2 is active."
        ),
        log_label="leave decision sync",
    )


def _post_leave_webhook(
    webhook_url: str,
    payload: dict[str, object | None],
    unavailable_detail: str,
    log_label: str,
) -> object:
    request = Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-FlowPilot-Secret": settings.FLOWPILOT_N8N_SHARED_SECRET,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            response_text = response.read().decode("utf-8")
    except HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        logger.warning("n8n %s webhook returned %s: %s", log_label, exc.code, error_text)
        raise HTTPException(status_code=502, detail=unavailable_detail) from exc
    except (TimeoutError, URLError) as exc:
        logger.warning("n8n %s webhook is unavailable: %s", log_label, exc)
        raise HTTPException(status_code=502, detail=unavailable_detail) from exc

    return _parse_n8n_response(response_text)


def _mark_leave_trigger_failed(
    db: Session,
    leave_request_id: str,
    workflow_execution_id: str,
    agent_run_id: str,
    preserve_decision_status: bool,
    error_message: str,
) -> None:
    now = utc_now()

    try:
        leave_request = db.get(LeaveRequest, leave_request_id)
        if leave_request is not None:
            leave_request.odoo_sync_status = "failed"
            if not preserve_decision_status:
                leave_request.status = "odoo_sync_failed"
            leave_request.automation_summary = error_message
            leave_request.updated_at = now

        workflow_execution = db.get(WorkflowExecution, workflow_execution_id)
        if workflow_execution is not None:
            workflow_execution.status = "failed"
            workflow_execution.finished_at = now
            workflow_execution.error_message = error_message
            workflow_execution.result_summary = error_message
            workflow_execution.output_summary = error_message
            workflow_execution.updated_at = now

        agent_run = db.get(AgentRun, agent_run_id)
        if agent_run is not None:
            agent_run.status = "failed"
            agent_run.finished_at = now
            agent_run.error_message = error_message
            agent_run.output_summary = error_message
            agent_run.updated_at = now

        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Leave workflow trigger failure could not be persisted.")


def _leave_request_analysis_webhook_url() -> str:
    return (
        f"{settings.LEAVE_N8N_WEBHOOK_BASE_URL.rstrip('/')}/"
        f"{LEAVE_REQUEST_ANALYSIS_WEBHOOK_PATH}"
    )


def _leave_decision_sync_webhook_url() -> str:
    return (
        f"{settings.LEAVE_N8N_WEBHOOK_BASE_URL.rstrip('/')}/"
        f"{LEAVE_DECISION_SYNC_WEBHOOK_PATH}"
    )


def _parse_n8n_response(response_text: str) -> object:
    if not response_text:
        return {}

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {"raw": response_text}


def _requested_days(start_date: date, end_date: date) -> int:
    return max(1, (end_date - start_date).days + 1)


def _odoo_employee_id(user_id: str) -> int:
    return MVP_ODOO_EMPLOYEE_IDS.get(user_id, 3)


def _odoo_department_id(department: str | None) -> int:
    normalized_department = _normalize(department)
    if normalized_department in {"operations", "tac-tic", "it"}:
        return MVP_ODOO_DEPARTMENT_ID
    return MVP_ODOO_DEPARTMENT_ID


def _odoo_leave_type_id(leave_type: str | None) -> int:
    normalized_leave_type = _normalize(leave_type)
    if any(value in normalized_leave_type for value in ["annual", "annuel", "conge"]):
        return MVP_ODOO_ANNUAL_LEAVE_TYPE_ID
    return MVP_ODOO_ANNUAL_LEAVE_TYPE_ID


def _odoo_creation_succeeded(payload: LeaveAutomationAnalysisCallback) -> bool:
    return payload.ok is not False and payload.odoo_leave_id is not None


def _analysis_recommendation(payload: LeaveAutomationAnalysisCallback) -> str | None:
    return (
        payload.automation_recommendation
        or payload.recommendation
        or payload.recommendation_label
    )


def _analysis_summary(payload: LeaveAutomationAnalysisCallback) -> str:
    analysis_details = _build_analysis_details(payload)
    if analysis_details:
        summary = _analysis_readable_summary(payload, analysis_details)
        return json.dumps(
            {
                "summary": summary,
                **analysis_details,
            },
            ensure_ascii=False,
        )

    if payload.automation_summary:
        return payload.automation_summary
    if payload.summary:
        return payload.summary
    if payload.error_message:
        return f"Leave automation analysis failed: {payload.error_message}"

    recommendation = _analysis_recommendation(payload) or "No recommendation provided"
    score = f" Score: {payload.score}." if payload.score is not None else ""
    branch = f" Branch: {payload.branch}." if payload.branch else ""
    odoo_state = f" Odoo state: {payload.odoo_state}." if payload.odoo_state else ""

    return f"{recommendation}.{score}{branch}{odoo_state}".strip()


def _build_analysis_details(payload: LeaveAutomationAnalysisCallback) -> dict[str, Any]:
    available_days = _payload_available_days(payload)
    requested_days = _payload_requested_days(payload)
    balance_gap_days = payload.balance_gap_days
    if balance_gap_days is None and available_days is not None and requested_days is not None:
        gap = requested_days - available_days
        balance_gap_days = gap if gap > 0 else Decimal("0")

    has_enough_balance = payload.has_enough_balance
    if has_enough_balance is None:
        has_enough_balance = payload.hasEnoughBalance
    if has_enough_balance is None and available_days is not None and requested_days is not None:
        has_enough_balance = available_days >= requested_days

    score_reasons = payload.score_reasons or payload.scoreReasons
    details: dict[str, Any] = {
        "ai_explanation": payload.ai_explanation,
        "decision_reasons": payload.decision_reasons,
        "blocking_reasons": payload.blocking_reasons,
        "approval_factors": payload.approval_factors,
        "rejection_factors": payload.rejection_factors,
        "score_reasons": score_reasons,
        "manager_guidance": payload.manager_guidance,
        "balance_gap_days": balance_gap_days,
        "can_manager_override": payload.can_manager_override,
        "available_days": available_days,
        "requested_days": requested_days,
        "has_enough_balance": has_enough_balance,
        "balance_status": payload.balance_status,
        "balance_label": payload.balance_label,
        "conflict_count": payload.conflict_count,
        "risk_level": payload.risk_level,
        "recommendation": _analysis_recommendation(payload),
        "recommendation_label": payload.recommendation_label,
        "score": payload.score,
    }

    if details["ai_explanation"] is None and has_enough_balance is False:
        details["ai_explanation"] = _insufficient_balance_explanation(
            available_days=available_days,
            requested_days=requested_days,
        )
    if details["decision_reasons"] is None and has_enough_balance is False:
        details["decision_reasons"] = _insufficient_balance_decision_reasons(
            balance_gap_days,
        )
    if details["blocking_reasons"] is None and has_enough_balance is False:
        details["blocking_reasons"] = [
            "Le solde disponible ne couvre pas la période demandée",
        ]
    if details["approval_factors"] is None and has_enough_balance is False:
        details["approval_factors"] = [
            "Le manager peut accepter uniquement en cas d'exception RH validée",
        ]
    if details["rejection_factors"] is None and has_enough_balance is False:
        details["rejection_factors"] = [
            "Demande supérieure au solde disponible",
            "Risque RH élevé",
        ]
    if details["manager_guidance"] is None and has_enough_balance is False:
        details["manager_guidance"] = (
            "Refuser la demande ou demander au collaborateur de réduire la période. "
            "Une validation RH exceptionnelle est nécessaire si le manager souhaite "
            "l'approuver malgré le solde insuffisant."
        )
    if details["can_manager_override"] is None and has_enough_balance is False:
        details["can_manager_override"] = True
    if details["risk_level"] is None and has_enough_balance is False:
        details["risk_level"] = "high"

    return {
        key: _json_safe_analysis_value(value)
        for key, value in details.items()
        if _has_analysis_value(value)
    }


def _analysis_readable_summary(
    payload: LeaveAutomationAnalysisCallback,
    analysis_details: dict[str, Any],
) -> str:
    if payload.automation_summary:
        return payload.automation_summary
    if payload.summary:
        return payload.summary
    explanation = _analysis_string(analysis_details, "ai_explanation")
    if explanation:
        return explanation
    recommendation = _analysis_recommendation(payload) or "Analyse IA enregistrée"
    guidance = _analysis_string(analysis_details, "manager_guidance")
    return f"{recommendation}. {guidance}".strip()


def _json_safe_analysis_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_json_safe_analysis_value(item) for item in value]
    return value


def _has_analysis_value(value: Any) -> bool:
    if value is None:
        return False
    if value == "":
        return False
    if isinstance(value, list) and len(value) == 0:
        return False
    return True


def _payload_available_days(payload: LeaveAutomationAnalysisCallback) -> Decimal | None:
    return payload.available_days if payload.available_days is not None else payload.availableDays


def _payload_requested_days(payload: LeaveAutomationAnalysisCallback) -> Decimal | None:
    return payload.requested_days if payload.requested_days is not None else payload.requestedDays


def _insufficient_balance_explanation(
    available_days: Decimal | None,
    requested_days: Decimal | None,
) -> str:
    if available_days is not None and requested_days is not None:
        return (
            "La demande dépasse le solde disponible. Le collaborateur demande "
            f"{_format_days(requested_days)} alors que seulement "
            f"{_format_days(available_days)} sont disponibles."
        )
    return "La demande dépasse le solde disponible."


def _insufficient_balance_decision_reasons(
    balance_gap_days: Decimal | None,
) -> list[str]:
    reasons = [
        "Solde disponible insuffisant",
        "Durée demandée supérieure au solde",
    ]
    if balance_gap_days is not None and balance_gap_days > 0:
        reasons.append(f"Écart de {_format_days(balance_gap_days)}")
    return reasons


def _format_days(value: Decimal | int | float) -> str:
    decimal_value = Decimal(str(value))
    normalized = decimal_value.quantize(Decimal("1")) if decimal_value == decimal_value.to_integral() else decimal_value.normalize()
    suffix = "jour" if normalized == 1 else "jours"
    return f"{normalized} {suffix}"


def _pending_analysis_details(leave_request: LeaveRequest) -> dict[str, Any]:
    if not leave_request.automation_summary:
        return {}
    try:
        parsed = json.loads(leave_request.automation_summary)
    except (TypeError, json.JSONDecodeError):
        return {"summary": leave_request.automation_summary}
    if isinstance(parsed, dict):
        return parsed
    return {"summary": leave_request.automation_summary}


def _analysis_text(summary: str | None) -> str | None:
    if not summary:
        return None
    details = _pending_analysis_details_from_text(summary)
    return _analysis_string(details, "summary") or summary


def _pending_analysis_details_from_text(summary: str) -> dict[str, Any]:
    try:
        parsed = json.loads(summary)
    except (TypeError, json.JSONDecodeError):
        return {"summary": summary}
    return parsed if isinstance(parsed, dict) else {"summary": summary}


def _with_balance_explanation_fallback(
    analysis_details: dict[str, Any],
    available_days: Decimal | None,
    requested_days: Decimal | None,
    recommendation: Literal["approve", "reject", "review"],
) -> dict[str, Any]:
    if available_days is None or requested_days is None or available_days >= requested_days:
        return analysis_details

    updated = dict(analysis_details)
    balance_gap_days = requested_days - available_days
    updated.setdefault(
        "ai_explanation",
        _insufficient_balance_explanation(available_days, requested_days),
    )
    updated.setdefault(
        "decision_reasons",
        _insufficient_balance_decision_reasons(balance_gap_days),
    )
    updated.setdefault(
        "blocking_reasons",
        ["Le solde disponible ne couvre pas la période demandée"],
    )
    updated.setdefault(
        "approval_factors",
        ["Le manager peut accepter uniquement en cas d'exception RH validée"],
    )
    updated.setdefault(
        "rejection_factors",
        ["Demande supérieure au solde disponible", "Risque RH élevé"],
    )
    updated.setdefault(
        "manager_guidance",
        (
            "Refuser la demande ou demander au collaborateur de réduire la période. "
            "Une validation RH exceptionnelle est nécessaire si le manager souhaite "
            "l'approuver malgré le solde insuffisant."
        ),
    )
    updated.setdefault("balance_gap_days", float(balance_gap_days))
    updated.setdefault("can_manager_override", recommendation != "approve")
    updated.setdefault("risk_level", "high")
    return updated


def _analysis_string(details: dict[str, Any], key: str) -> str | None:
    value = details.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _analysis_string_list(details: dict[str, Any], key: str) -> list[str]:
    value = details.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _analysis_decimal(details: dict[str, Any], key: str) -> Decimal | None:
    value = details.get(key)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _analysis_bool(details: dict[str, Any], key: str) -> bool | None:
    value = details.get(key)
    return value if isinstance(value, bool) else None


def _decision_sync_failure_summary(payload: LeaveDecisionSyncCallback) -> str:
    detail = payload.error_message or "Odoo did not confirm the expected decision state."
    return (
        "Odoo decision synchronization failed. "
        f"Local manager decision was preserved. {detail}"
    )


def _is_policy_rejection_branch(branch: str | None) -> bool:
    normalized_branch = _normalize(branch)
    return "policy" in normalized_branch and "reject" in normalized_branch


def _is_policy_rejection(payload: LeaveAutomationAnalysisCallback) -> bool:
    recommendation = _normalize(_analysis_recommendation(payload))
    return (
        _is_policy_rejection_branch(payload.branch)
        or "rejected_by_policy" in recommendation
        or "policy_rejection" in recommendation
    )


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _pending_ai_recommendation(
    leave_request: LeaveRequest,
) -> Literal["approve", "reject", "review"]:
    recommendation = _normalize(leave_request.automation_recommendation)
    if "reject" in recommendation or "refus" in recommendation:
        return "reject"
    if (
        "approv" in recommendation
        or "approval" in recommendation
        or "accord" in recommendation
    ):
        return "approve"
    return "review"


def _pending_risk_level(
    leave_request: LeaveRequest,
    analysis_details: dict[str, Any] | None = None,
) -> Literal["low", "medium", "high"]:
    risk_level = _normalize(
        _analysis_string(analysis_details or {}, "risk_level"),
    )
    if risk_level in {"low", "medium", "high"}:
        return risk_level  # type: ignore[return-value]
    if leave_request.score is None:
        return "low"
    if leave_request.score >= 80:
        return "low"
    if leave_request.score >= 50:
        return "medium"
    return "high"


def _pending_conflict_detected(analysis_details: dict[str, Any]) -> bool:
    conflict_count = analysis_details.get("conflict_count")
    if isinstance(conflict_count, int):
        return conflict_count > 0
    if isinstance(conflict_count, float):
        return conflict_count > 0
    return False


def _persist_leave_traces_safely(
    request_id: str,
    requested_by: str | None,
    workflow_name: str,
    workflow_status: str,
    workflow_summary: str | None,
    agent_id: str,
    agent_name: str,
    agent_status: str,
    agent_output: str | None,
    now: datetime,
    db: Session,
    workflow_payload: object | None = None,
    agent_run_payload: object | None = None,
    workflow_execution_id: str | None = None,
    agent_run_id: str | None = None,
) -> tuple[str | None, str | None]:
    try:
        with db.begin_nested():
            workflow_execution = _upsert_leave_workflow_execution(
                request_id=request_id,
                workflow_name=workflow_name,
                status=workflow_status,
                summary=workflow_summary,
                now=now,
                payload=workflow_payload,
                workflow_execution_id=workflow_execution_id,
                db=db,
            )
            db.flush()

            agent_run = _upsert_leave_agent_run(
                workflow_execution_id=workflow_execution.id,
                requested_by=requested_by,
                agent_id=agent_id,
                agent_name=agent_name,
                status=agent_status,
                output_summary=agent_output,
                now=now,
                payload=agent_run_payload,
                agent_run_id=agent_run_id,
                db=db,
            )
            db.flush()
    except SQLAlchemyError:
        logger.exception(
            "Leave callback trace persistence failed for request %s.",
            request_id,
        )
        return None, None

    return workflow_execution.id, agent_run.id


def _upsert_leave_workflow_execution(
    request_id: str,
    workflow_name: str,
    status: str,
    summary: str | None,
    now: datetime,
    payload: object | None,
    workflow_execution_id: str | None,
    db: Session,
) -> WorkflowExecution:
    resolved_id = (
        getattr(payload, "id", None)
        or workflow_execution_id
        or _generate_trace_id("exec_leave", now)
    )
    workflow_execution = db.get(WorkflowExecution, resolved_id)
    if workflow_execution is None:
        workflow_execution = WorkflowExecution(
            id=resolved_id,
            related_object_type="leave_request",
            related_object_id=request_id,
            workflow_name=getattr(payload, "workflow_name", None) or workflow_name,
            process=getattr(payload, "process", None) or LEAVE_REQUEST_PROCESS,
            trigger_source=getattr(payload, "trigger_source", None) or "n8n_callback",
            status=getattr(payload, "status", None) or status,
            started_at=getattr(payload, "started_at", None) or now,
            finished_at=getattr(payload, "finished_at", None) or now,
            duration_seconds=getattr(payload, "duration_seconds", None),
            error_message=getattr(payload, "error_message", None),
            result_summary=getattr(payload, "result_summary", None) or summary,
            input_summary=getattr(payload, "input_summary", None),
            output_summary=getattr(payload, "output_summary", None) or summary,
            agent_name=getattr(payload, "agent_name", None),
            created_at=now,
            updated_at=now,
        )
        db.add(workflow_execution)
        return workflow_execution

    workflow_execution.related_object_type = "leave_request"
    workflow_execution.related_object_id = request_id
    workflow_execution.workflow_name = (
        getattr(payload, "workflow_name", None)
        or workflow_execution.workflow_name
        or workflow_name
    )
    workflow_execution.process = getattr(payload, "process", None) or LEAVE_REQUEST_PROCESS
    workflow_execution.trigger_source = (
        getattr(payload, "trigger_source", None)
        or workflow_execution.trigger_source
        or "n8n_callback"
    )
    workflow_execution.status = getattr(payload, "status", None) or status
    workflow_execution.started_at = (
        getattr(payload, "started_at", None) or workflow_execution.started_at or now
    )
    workflow_execution.finished_at = getattr(payload, "finished_at", None) or now
    workflow_execution.duration_seconds = getattr(payload, "duration_seconds", None)
    workflow_execution.error_message = getattr(payload, "error_message", None)
    workflow_execution.result_summary = getattr(payload, "result_summary", None) or summary
    workflow_execution.output_summary = getattr(payload, "output_summary", None) or summary
    workflow_execution.agent_name = getattr(payload, "agent_name", None) or workflow_execution.agent_name
    workflow_execution.updated_at = now
    return workflow_execution


def _upsert_leave_agent_run(
    workflow_execution_id: str,
    requested_by: str | None,
    agent_id: str,
    agent_name: str,
    status: str,
    output_summary: str | None,
    now: datetime,
    payload: object | None,
    agent_run_id: str | None,
    db: Session,
) -> AgentRun:
    resolved_agent_id = getattr(payload, "agent_id", None) or agent_id
    resolved_id = getattr(payload, "id", None) or agent_run_id
    agent_run = db.get(AgentRun, resolved_id) if resolved_id else None
    if agent_run is None and resolved_id is None:
        agent_run = db.scalars(
            select(AgentRun)
            .where(AgentRun.workflow_execution_id == workflow_execution_id)
            .where(AgentRun.agent_id == resolved_agent_id)
            .order_by(AgentRun.created_at.desc())
        ).first()

    if agent_run is None:
        agent_run = AgentRun(
            id=resolved_id or _generate_trace_id("run_leave", now),
            agent_id=resolved_agent_id,
            agent_name=getattr(payload, "agent_name", None) or agent_name,
            process=getattr(payload, "process", None) or LEAVE_REQUEST_PROCESS,
            workflow_execution_id=getattr(payload, "workflow_execution_id", None)
            or workflow_execution_id,
            requested_by=_resolve_requested_by(
                getattr(payload, "requested_by", None) or requested_by,
                db,
            ),
            requested_at=getattr(payload, "requested_at", None) or now,
            status=getattr(payload, "status", None) or status,
            started_at=getattr(payload, "started_at", None) or now,
            finished_at=getattr(payload, "finished_at", None) or now,
            input_summary=getattr(payload, "input_summary", None),
            output_summary=getattr(payload, "output_summary", None) or output_summary,
            error_message=getattr(payload, "error_message", None),
            created_at=now,
            updated_at=now,
        )
        db.add(agent_run)
        return agent_run

    agent_run.agent_id = resolved_agent_id
    agent_run.agent_name = getattr(payload, "agent_name", None) or agent_run.agent_name
    agent_run.process = getattr(payload, "process", None) or LEAVE_REQUEST_PROCESS
    agent_run.workflow_execution_id = (
        getattr(payload, "workflow_execution_id", None) or workflow_execution_id
    )
    agent_run.requested_by = _resolve_requested_by(
        getattr(payload, "requested_by", None) or requested_by,
        db,
    )
    agent_run.requested_at = getattr(payload, "requested_at", None) or agent_run.requested_at or now
    agent_run.status = getattr(payload, "status", None) or status
    agent_run.started_at = getattr(payload, "started_at", None) or agent_run.started_at or now
    agent_run.finished_at = getattr(payload, "finished_at", None) or now
    agent_run.input_summary = getattr(payload, "input_summary", None) or agent_run.input_summary
    agent_run.output_summary = getattr(payload, "output_summary", None) or output_summary
    agent_run.error_message = getattr(payload, "error_message", None)
    agent_run.updated_at = now
    return agent_run


def _resolve_requested_by(requested_by: str | None, db: Session) -> str | None:
    if not requested_by:
        return None
    if db.get(User, requested_by) is not None:
        return requested_by
    if db.get(User, DEFAULT_MANAGER_ID) is not None:
        return DEFAULT_MANAGER_ID
    return None


def _generate_trace_id(prefix: str, now: datetime) -> str:
    return f"{prefix}_{int(now.timestamp())}_{uuid4().hex[:8]}"
