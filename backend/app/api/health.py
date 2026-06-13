from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import ApiResponse

router = APIRouter()


@router.get("/health", response_model=ApiResponse[dict[str, str]])
def get_health() -> ApiResponse[dict[str, str]]:
    return ApiResponse(
        success=True,
        data={
            "status": "ok",
            "service": settings.APP_NAME,
        },
    )
