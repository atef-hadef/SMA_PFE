from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.core.database import get_db
from app.schemas.auth import AuthUser
from app.schemas.common import ApiResponse
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import get_dashboard_summary

router = APIRouter()


@router.get("/dashboard/summary", response_model=ApiResponse[DashboardSummary])
def read_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("dashboard.view")),
) -> ApiResponse[DashboardSummary]:
    return ApiResponse(success=True, data=get_dashboard_summary(db, current_user=current_user))
