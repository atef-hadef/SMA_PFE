import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
    require_any_permission,
    require_internal_secret,
    require_permission,
)
from app.core.database import get_db
from app.schemas.auth import AuthUser
from app.schemas.common import ApiError, ApiResponse, PaginatedResponse
from app.schemas.leave_requests import (
    LeaveAutomationAnalysisCallback,
    LeaveBalancePrecheckResponse,
    LeaveCallbackResponse,
    LeaveDecisionRequest,
    LeaveDecisionResponse,
    LeaveDecisionSyncCallback,
    LeaveRequestCreate,
    LeaveRequestHistoryResponse,
    LeaveRequestResponse,
    PendingLeaveRequestResponse,
)
from app.services.leave_service import (
    DEFAULT_EMPLOYEE_ID,
    LeaveBalanceValidationError,
    approve_leave_request,
    create_leave_request,
    get_leave_requests_history,
    get_pending_leave_requests,
    reject_leave_request,
    save_leave_automation_analysis,
    save_leave_decision_sync_result,
)
from app.models import LeaveAllocation, LeaveRequest, LeaveType, User
from app.schemas.leave_standalone import (
    AllocationDetailResponse,
    AllocationGroupResponse,
    AllocationUpsertRequest,
    AllocationUpsertResponse,
    LeaveAnalysisCompleteCallback,
    LeaveAnalyticsResponse,
    LeaveBalanceItemResponse,
    LeaveDecisionCompleteCallback,
    LeaveStandaloneCreateRequest,
    LeaveTypeResponse,
    StandaloneCallbackResponse,
    StandaloneLeaveRequestResponse,
)
from app.services.leave_standalone_service import (
    approve_leave_standalone,
    create_leave_request_standalone,
    get_all_balances,
    get_analytics,
    get_leave_balance,
    reject_leave_standalone,
)
from app.services.audit_service import log_activity

logger = logging.getLogger(__name__)

router = APIRouter()


def _format_days(value: Decimal | None) -> str:
    if value is None:
        return "Non renseigne"
    normalized = value.quantize(Decimal("1")) if value == value.to_integral() else value.normalize()
    suffix = "jour" if normalized == 1 else "jours"
    return f"{normalized} {suffix}"


def _precheck_error_code(data: LeaveBalancePrecheckResponse) -> str:
    return data.error_code or "INSUFFICIENT_LEAVE_BALANCE"


def _precheck_error_message(data: LeaveBalancePrecheckResponse) -> str:
    if data.message:
        return data.message
    if _precheck_error_code(data) == "LEAVE_PERIOD_OVERLAP":
        return (
            "La periode demandee chevauche deja un conge valide. "
            "Veuillez choisir d'autres dates."
        )
    return (
        "Votre solde disponible est insuffisant. Vous disposez de "
        f"{_format_days(data.available_days)}, mais vous demandez "
        f"{_format_days(data.requested_days)}. Veuillez reduire la "
        "periode demandee ou contacter le service RH."
    )


@router.post(
    "/leave-requests",
    response_model=ApiResponse[LeaveRequestResponse],
    deprecated=True,  # Use /leave-requests/standalone instead (Odoo flow deprecated)
)
def submit_leave_request(
    payload: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("leave.request.create")),
) -> ApiResponse[LeaveRequestResponse] | JSONResponse:
    try:
        user_id = getattr(current_user, "id", DEFAULT_EMPLOYEE_ID)
        return ApiResponse(
            success=True,
            data=create_leave_request(payload, db, user_id=user_id),
        )
    except LeaveBalanceValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=ApiResponse[LeaveBalancePrecheckResponse](
                success=False,
                error=ApiError(
                    code=_precheck_error_code(exc.data),
                    message=_precheck_error_message(exc.data),
                ),
                data=exc.data,
            ).model_dump(mode="json"),
        )


@router.get(
    "/leave-requests",
    response_model=ApiResponse[PaginatedResponse[LeaveRequestHistoryResponse]],
)
def read_leave_requests_history(
    status: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("leave.request.view_all")),
) -> ApiResponse[PaginatedResponse[LeaveRequestHistoryResponse]]:
    return ApiResponse(success=True, data=get_leave_requests_history(db, status=status))


@router.get(
    "/leave-requests/my",
    response_model=ApiResponse[PaginatedResponse[LeaveRequestHistoryResponse]],
)
def read_my_leave_requests(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("leave.request.view_own")),
) -> ApiResponse[PaginatedResponse[LeaveRequestHistoryResponse]]:
    return ApiResponse(
        success=True,
        data=get_leave_requests_history(db, status=status, user_id=current_user.id),
    )


@router.get(
    "/leave-requests/mine",
    response_model=ApiResponse[PaginatedResponse[LeaveRequestHistoryResponse]],
)
def read_mine_leave_requests(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("leave.request.view_own")),
) -> ApiResponse[PaginatedResponse[LeaveRequestHistoryResponse]]:
    return read_my_leave_requests(status=status, db=db, current_user=current_user)


@router.get(
    "/leave-requests/pending",
    response_model=ApiResponse[PaginatedResponse[PendingLeaveRequestResponse]],
)
def read_pending_leave_requests(
    db: Session = Depends(get_db),
    _user=Depends(
        require_any_permission(["leave.request.view_all", "leave.request.approve"]),
    ),
) -> ApiResponse[PaginatedResponse[PendingLeaveRequestResponse]]:
    return ApiResponse(success=True, data=get_pending_leave_requests(db))


@router.post(
    "/leave-requests/{request_id}/approve",
    response_model=ApiResponse[LeaveDecisionResponse],
    deprecated=True,  # Use /{request_id}/approve-standalone instead (Odoo flow deprecated)
)
def approve_pending_leave_request(
    request_id: str,
    payload: LeaveDecisionRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("leave.request.approve")),
) -> ApiResponse[LeaveDecisionResponse]:
    return ApiResponse(
        success=True,
        data=approve_leave_request(
            request_id=request_id,
            comment=payload.comment,
            db=db,
        ),
    )


@router.post(
    "/leave-requests/{request_id}/reject",
    response_model=ApiResponse[LeaveDecisionResponse],
    deprecated=True,  # Use /{request_id}/reject-standalone instead (Odoo flow deprecated)
)
def reject_pending_leave_request(
    request_id: str,
    payload: LeaveDecisionRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("leave.request.reject")),
) -> ApiResponse[LeaveDecisionResponse]:
    return ApiResponse(
        success=True,
        data=reject_leave_request(
            request_id=request_id,
            comment=payload.comment,
            db=db,
        ),
    )


@router.post(
    "/leave-requests/{request_id}/automation-analysis",
    response_model=LeaveCallbackResponse,
    deprecated=True,  # Odoo callback — replaced by /n8n/leave-standalone/analysis-complete
)
def receive_leave_automation_analysis(
    request_id: str,
    payload: LeaveAutomationAnalysisCallback,
    db: Session = Depends(get_db),
) -> LeaveCallbackResponse:
    return save_leave_automation_analysis(
        request_id=request_id,
        payload=payload,
        db=db,
    )


@router.post(
    "/leave-requests/{request_id}/decision-sync-result",
    response_model=LeaveCallbackResponse,
    deprecated=True,  # Odoo callback — replaced by /n8n/leave-standalone/decision-complete
)
def receive_leave_decision_sync_result(
    request_id: str,
    payload: LeaveDecisionSyncCallback,
    db: Session = Depends(get_db),
) -> LeaveCallbackResponse:
    return save_leave_decision_sync_result(
        request_id=request_id,
        payload=payload,
        db=db,
    )


# ---------------------------------------------------------------------------
# Module Congés STANDALONE (sans Odoo) — endpoints additionnels.
# Les endpoints ci-dessus (intégration Odoo) restent inchangés.
# ---------------------------------------------------------------------------


def _leave_type_labels(db: Session) -> dict[str, str]:
    rows = db.execute(select(LeaveType.code, LeaveType.label_fr)).all()
    return {code: label for code, label in rows}


def _to_standalone_response(
    leave_request: LeaveRequest,
) -> StandaloneLeaveRequestResponse:
    return StandaloneLeaveRequestResponse(
        id=leave_request.id,
        employee_id=leave_request.user_id,
        leave_type=leave_request.leave_type,
        start_date=leave_request.start_date,
        end_date=leave_request.end_date,
        reason=leave_request.reason,
        status=leave_request.status,
        requested_days=(
            float(leave_request.requested_days)
            if leave_request.requested_days is not None
            else None
        ),
        available_days=(
            float(leave_request.available_days)
            if leave_request.available_days is not None
            else None
        ),
        reviewed_by=leave_request.reviewed_by,
        reviewed_at=leave_request.reviewed_at,
        decision_comment=leave_request.decision_comment,
        created_at=leave_request.created_at,
    )


@router.get(
    "/leave-requests/my-balance",
    response_model=ApiResponse[list[LeaveBalanceItemResponse]],
)
def read_my_leave_balance(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> ApiResponse[list[LeaveBalanceItemResponse]]:
    labels = _leave_type_labels(db)
    balances = get_all_balances(current_user.id, 2026, db)
    items = [
        LeaveBalanceItemResponse(
            leave_type=balance["leave_type"],
            leave_type_label=labels.get(balance["leave_type"], balance["leave_type"]),
            allocated=balance["allocated"],
            used=balance["used"],
            pending=balance["pending"],
            available=balance["available"],
            year=balance["year"],
        )
        for balance in balances
    ]
    return ApiResponse(success=True, data=items)


@router.get(
    "/leave-requests/leave-types",
    response_model=ApiResponse[list[LeaveTypeResponse]],
)
def read_leave_types(
    db: Session = Depends(get_db),
    _user: AuthUser = Depends(get_current_user),
) -> ApiResponse[list[LeaveTypeResponse]]:
    leave_types = db.scalars(
        select(LeaveType)
        .where(LeaveType.is_active.is_(True))
        .order_by(LeaveType.default_days.desc())
    ).all()
    items = [
        LeaveTypeResponse(
            id=leave_type.id,
            code=leave_type.code,
            label_fr=leave_type.label_fr,
            label_en=leave_type.label_en,
            default_days=leave_type.default_days,
            requires_document=leave_type.requires_document,
        )
        for leave_type in leave_types
    ]
    return ApiResponse(success=True, data=items)


@router.post(
    "/leave-requests/standalone",
    response_model=ApiResponse[StandaloneLeaveRequestResponse],
)
def submit_standalone_leave_request(
    payload: LeaveStandaloneCreateRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("leave.request.create")),
) -> ApiResponse[StandaloneLeaveRequestResponse]:
    leave_request, _context = create_leave_request_standalone(
        employee_id=current_user.id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        db=db,
    )
    log_activity(
        db,
        entity_type="leave_request",
        entity_id=leave_request.id,
        action="created",
        actor_id=current_user.id,
        details={"leave_type": leave_request.leave_type},
    )
    return ApiResponse(success=True, data=_to_standalone_response(leave_request))


@router.post(
    "/leave-requests/{request_id}/approve-standalone",
    response_model=ApiResponse[StandaloneLeaveRequestResponse],
)
def approve_standalone_leave_request(
    request_id: str,
    payload: LeaveDecisionRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("leave.request.approve")),
) -> ApiResponse[StandaloneLeaveRequestResponse]:
    leave_request = approve_leave_standalone(
        request_id=request_id,
        manager_id=current_user.id,
        comment=payload.comment,
        db=db,
    )
    log_activity(
        db,
        entity_type="leave_request",
        entity_id=request_id,
        action="approved",
        actor_id=current_user.id,
        details={"employee_id": leave_request.user_id},
    )
    return ApiResponse(success=True, data=_to_standalone_response(leave_request))


@router.post(
    "/leave-requests/{request_id}/reject-standalone",
    response_model=ApiResponse[StandaloneLeaveRequestResponse],
)
def reject_standalone_leave_request(
    request_id: str,
    payload: LeaveDecisionRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("leave.request.approve")),
) -> ApiResponse[StandaloneLeaveRequestResponse]:
    leave_request = reject_leave_standalone(
        request_id=request_id,
        manager_id=current_user.id,
        comment=payload.comment,
        db=db,
    )
    log_activity(
        db,
        entity_type="leave_request",
        entity_id=request_id,
        action="rejected",
        actor_id=current_user.id,
        details={"employee_id": leave_request.user_id},
    )
    return ApiResponse(success=True, data=_to_standalone_response(leave_request))


@router.get(
    "/leave-requests/allocations",
    response_model=ApiResponse[list[AllocationGroupResponse]],
)
def read_leave_allocations(
    year: int = 2026,
    employee_id: str | None = None,
    db: Session = Depends(get_db),
    _user: AuthUser = Depends(require_permission("leave.request.view_all")),
) -> ApiResponse[list[AllocationGroupResponse]]:
    labels = _leave_type_labels(db)
    statement = select(LeaveAllocation).where(LeaveAllocation.year == year)
    if employee_id:
        statement = statement.where(LeaveAllocation.employee_id == employee_id)
    statement = statement.order_by(
        LeaveAllocation.employee_id,
        LeaveAllocation.leave_type,
    )
    allocations = db.scalars(statement).all()

    grouped: dict[str, AllocationGroupResponse] = {}
    for allocation in allocations:
        group = grouped.get(allocation.employee_id)
        if group is None:
            employee = db.get(User, allocation.employee_id)
            group = AllocationGroupResponse(
                employee_id=allocation.employee_id,
                employee_name=employee.full_name if employee else allocation.employee_id,
                year=year,
                allocations=[],
            )
            grouped[allocation.employee_id] = group
        balance = get_leave_balance(
            allocation.employee_id,
            allocation.leave_type,
            year,
            db,
        )
        group.allocations.append(
            AllocationDetailResponse(
                leave_type=allocation.leave_type,
                leave_type_label=labels.get(
                    allocation.leave_type,
                    allocation.leave_type,
                ),
                allocated_days=float(allocation.allocated_days),
                used_days=balance["used"],
                available_days=balance["available"],
            )
        )
    return ApiResponse(success=True, data=list(grouped.values()))


@router.post(
    "/leave-requests/allocations",
    response_model=ApiResponse[AllocationUpsertResponse],
)
def upsert_leave_allocation(
    payload: AllocationUpsertRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("leave.request.hr_validate")),
) -> ApiResponse[AllocationUpsertResponse]:
    employee = db.get(User, payload.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employé introuvable.")

    leave_type_exists = db.scalar(
        select(LeaveType.id).where(LeaveType.code == payload.leave_type),
    )
    if leave_type_exists is None:
        raise HTTPException(status_code=422, detail="Type de congé invalide.")

    now = datetime.now(timezone.utc)
    allocation = db.scalar(
        select(LeaveAllocation)
        .where(LeaveAllocation.employee_id == payload.employee_id)
        .where(LeaveAllocation.year == payload.year)
        .where(LeaveAllocation.leave_type == payload.leave_type)
    )
    if allocation is None:
        allocation = LeaveAllocation(
            id=f"alloc_{uuid4().hex[:8]}",
            employee_id=payload.employee_id,
            year=payload.year,
            leave_type=payload.leave_type,
            allocated_days=payload.allocated_days,
            created_by=current_user.id,
            created_at=now,
            updated_at=now,
        )
        db.add(allocation)
    else:
        allocation.allocated_days = payload.allocated_days
        allocation.updated_at = now

    db.commit()
    db.refresh(allocation)
    log_activity(
        db,
        entity_type="leave_allocation",
        entity_id=allocation.id,
        action="updated",
        actor_id=current_user.id,
        details={
            "employee_id": allocation.employee_id,
            "leave_type": allocation.leave_type,
            "allocated_days": float(allocation.allocated_days),
        },
    )
    return ApiResponse(
        success=True,
        data=AllocationUpsertResponse(
            id=allocation.id,
            employee_id=allocation.employee_id,
            year=allocation.year,
            leave_type=allocation.leave_type,
            allocated_days=float(allocation.allocated_days),
        ),
    )


@router.get(
    "/leave-requests/analytics",
    response_model=ApiResponse[LeaveAnalyticsResponse],
)
def read_leave_analytics(
    db: Session = Depends(get_db),
    _user: AuthUser = Depends(require_permission("leave.request.view_all")),
) -> ApiResponse[LeaveAnalyticsResponse]:
    return ApiResponse(success=True, data=LeaveAnalyticsResponse(**get_analytics(db)))


@router.post(
    "/n8n/leave-standalone/analysis-complete",
    response_model=StandaloneCallbackResponse,
)
def receive_leave_standalone_analysis_complete(
    payload: LeaveAnalysisCompleteCallback,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_secret),
) -> StandaloneCallbackResponse:
    leave_request = db.get(LeaveRequest, payload.leave_request_id)
    if leave_request is None:
        logger.warning(
            "Standalone analysis callback for unknown leave request %s.",
            payload.leave_request_id,
        )
        return StandaloneCallbackResponse(
            success=True,
            message="Leave request not found",
        )

    if payload.llm_recommendation:
        leave_request.automation_recommendation = payload.llm_recommendation
    summary = {
        "summary": payload.llm_explanation,
        "ai_explanation": payload.llm_explanation,
        "recommendation": payload.llm_recommendation,
        "risk_level": payload.risk_assessment,
    }
    summary = {key: value for key, value in summary.items() if value is not None}
    if summary:
        leave_request.automation_summary = json.dumps(summary, ensure_ascii=False)
    leave_request.updated_at = datetime.now(timezone.utc)
    db.commit()
    return StandaloneCallbackResponse(success=True, message="Analysis saved")


@router.post(
    "/n8n/leave-standalone/decision-complete",
    response_model=StandaloneCallbackResponse,
)
def receive_leave_standalone_decision_complete(
    payload: LeaveDecisionCompleteCallback,
    _: None = Depends(require_internal_secret),
) -> StandaloneCallbackResponse:
    logger.info(
        "Standalone decision notification for %s sent=%s.",
        payload.leave_request_id,
        payload.notification_sent,
    )
    return StandaloneCallbackResponse(success=True, message="Notification logged")
