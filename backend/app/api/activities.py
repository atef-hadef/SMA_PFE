from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.schemas.activities import ActivityListResponse
from app.schemas.auth import AuthUser
from app.schemas.common import ApiResponse
from app.services.audit_service import get_recent_activities

router = APIRouter()


@router.get("/activities/recent", response_model=ApiResponse[ActivityListResponse])
def read_recent_activities(
    limit: int = 50,
    entity_type: str | None = None,
    period: str | None = None,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> ApiResponse[ActivityListResponse]:
    return ApiResponse(
        success=True,
        data=get_recent_activities(
            db,
            current_user=current_user,
            limit=limit,
            entity_type=entity_type,
            period=period,
        ),
    )
