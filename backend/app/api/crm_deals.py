"""REST endpoints for CRM Deals (WF 07 - Deal Pipeline Update)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.core.database import get_db
from app.schemas.auth import AuthUser
from app.schemas.common import ApiResponse
from app.schemas.crm_tasks_deals import (
    CrmCommentCreate,
    CrmCommentItem,
    CrmCommentListResponse,
    CrmDealCreate,
    CrmDealItem,
    CrmDealListResponse,
    CrmDealStageTransitionRequest,
    CrmDealStageTransitionResponse,
    CrmDealUpdate,
)
from app.services.crm_comments_service import (
    create_comment,
    delete_comment,
    list_comments,
)
from app.services.crm_deals_service import (
    create_deal,
    delete_deal,
    get_deal,
    list_deals,
    transition_deal_stage,
    update_deal,
)

router = APIRouter()


@router.get("/crm/deals", response_model=ApiResponse[CrmDealListResponse])
def read_crm_deals(
    stage: str | None = None,
    owner_user_id: str | None = None,
    lead_id: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.deals.view")),
) -> ApiResponse[CrmDealListResponse]:
    return ApiResponse(
        success=True,
        data=list_deals(db, stage=stage, owner_user_id=owner_user_id, lead_id=lead_id),
    )


@router.get("/crm/deals/{deal_id}", response_model=ApiResponse[CrmDealItem])
def read_crm_deal(
    deal_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.deals.view")),
) -> ApiResponse[CrmDealItem]:
    return ApiResponse(success=True, data=get_deal(db, deal_id))


@router.post("/crm/deals", response_model=ApiResponse[CrmDealItem])
def create_crm_deal(
    payload: CrmDealCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.deals.manage")),
) -> ApiResponse[CrmDealItem]:
    return ApiResponse(
        success=True,
        message="CRM deal created.",
        data=create_deal(db, payload),
    )


@router.patch("/crm/deals/{deal_id}", response_model=ApiResponse[CrmDealItem])
def update_crm_deal(
    deal_id: str,
    payload: CrmDealUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.deals.manage")),
) -> ApiResponse[CrmDealItem]:
    return ApiResponse(
        success=True,
        message="CRM deal updated.",
        data=update_deal(db, deal_id, payload),
    )


@router.post(
    "/crm/deals/{deal_id}/transition",
    response_model=ApiResponse[CrmDealStageTransitionResponse],
)
def transition_crm_deal_stage(
    deal_id: str,
    payload: CrmDealStageTransitionRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.deals.manage")),
) -> ApiResponse[CrmDealStageTransitionResponse]:
    return ApiResponse(
        success=True,
        message="Deal stage transition processed.",
        data=transition_deal_stage(db, deal_id, payload, requested_by=current_user.id),
    )


@router.delete("/crm/deals/{deal_id}", response_model=ApiResponse[None])
def delete_crm_deal(
    deal_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.deals.manage")),
) -> ApiResponse[None]:
    delete_deal(db, deal_id)
    return ApiResponse(success=True, message="CRM deal removed.", data=None)


@router.get(
    "/crm/deals/{deal_id}/comments",
    response_model=ApiResponse[CrmCommentListResponse],
)
def read_crm_deal_comments(
    deal_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.deals.view")),
) -> ApiResponse[CrmCommentListResponse]:
    return ApiResponse(success=True, data=list_comments(db, "deal", deal_id))


@router.post(
    "/crm/deals/{deal_id}/comments",
    response_model=ApiResponse[CrmCommentItem],
)
def create_crm_deal_comment(
    deal_id: str,
    payload: CrmCommentCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.deals.manage")),
) -> ApiResponse[CrmCommentItem]:
    return ApiResponse(
        success=True,
        message="Comment added.",
        data=create_comment(
            db, "deal", deal_id, payload, author_user_id=current_user.id
        ),
    )


@router.delete(
    "/crm/deals/{deal_id}/comments/{comment_id}",
    response_model=ApiResponse[None],
)
def delete_crm_deal_comment(
    deal_id: str,
    comment_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.deals.manage")),
) -> ApiResponse[None]:
    delete_comment(db, "deal", deal_id, comment_id)
    return ApiResponse(success=True, message="Comment removed.", data=None)
