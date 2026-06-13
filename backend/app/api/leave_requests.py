from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import require_any_permission, require_permission
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


@router.post("/leave-requests", response_model=ApiResponse[LeaveRequestResponse])
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
