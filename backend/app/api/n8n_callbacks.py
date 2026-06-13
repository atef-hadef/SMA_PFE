from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_internal_secret
from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.n8n_callbacks import (
    CrmAnalysisResultPayload,
    CrmCollectResultPayload,
    CrmCommunicationResultPayload,
    CrmEmailSentResultPayload,
    CrmRoutingResultPayload,
    CrmScoringResultPayload,
    N8nCallbackResult,
)
from app.services.n8n_callback_service import (
    handle_analysis_result,
    handle_collect_result,
    handle_communication_result,
    handle_email_sent_result,
    handle_routing_result,
    handle_scoring_result,
)

router = APIRouter(dependencies=[Depends(require_internal_secret)])


@router.post("/crm/collect-result", response_model=ApiResponse[N8nCallbackResult])
def receive_crm_collect_result(
    payload: CrmCollectResultPayload,
    db: Session = Depends(get_db),
) -> ApiResponse[N8nCallbackResult]:
    return ApiResponse(
        success=True,
        message="CRM lead collection result saved.",
        data=handle_collect_result(payload, db),
    )


@router.post("/crm/analysis-result", response_model=ApiResponse[N8nCallbackResult])
def receive_crm_analysis_result(
    payload: CrmAnalysisResultPayload,
    db: Session = Depends(get_db),
) -> ApiResponse[N8nCallbackResult]:
    return ApiResponse(
        success=True,
        message="CRM analysis result saved.",
        data=handle_analysis_result(payload, db),
    )


@router.post("/crm/scoring-result", response_model=ApiResponse[N8nCallbackResult])
def receive_crm_scoring_result(
    payload: CrmScoringResultPayload,
    db: Session = Depends(get_db),
) -> ApiResponse[N8nCallbackResult]:
    return ApiResponse(
        success=True,
        message="CRM scoring result saved.",
        data=handle_scoring_result(payload, db),
    )


@router.post("/crm/routing-result", response_model=ApiResponse[N8nCallbackResult])
def receive_crm_routing_result(
    payload: CrmRoutingResultPayload,
    db: Session = Depends(get_db),
) -> ApiResponse[N8nCallbackResult]:
    return ApiResponse(
        success=True,
        message="CRM routing result saved.",
        data=handle_routing_result(payload, db),
    )


@router.post(
    "/crm/communication-result",
    response_model=ApiResponse[N8nCallbackResult],
)
def receive_crm_communication_result(
    payload: CrmCommunicationResultPayload,
    db: Session = Depends(get_db),
) -> ApiResponse[N8nCallbackResult]:
    return ApiResponse(
        success=True,
        message="CRM communication result saved.",
        data=handle_communication_result(payload, db),
    )


@router.post(
    "/crm/email-sent-result",
    response_model=ApiResponse[N8nCallbackResult],
)
def receive_crm_email_sent_result(
    payload: CrmEmailSentResultPayload,
    db: Session = Depends(get_db),
) -> ApiResponse[N8nCallbackResult]:
    return ApiResponse(
        success=True,
        message="CRM email sending result saved.",
        data=handle_email_sent_result(payload, db),
    )
