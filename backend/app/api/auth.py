from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.schemas.auth import AuthUser, LoginRequest, LoginResponse, LogoutResponse
from app.schemas.common import ApiResponse
from app.services.auth_service import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[LoginResponse])
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[LoginResponse]:
    return ApiResponse(success=True, data=authenticate_user(payload, db))


@router.get("/me", response_model=ApiResponse[AuthUser])
def read_me(
    current_user: AuthUser = Depends(get_current_user),
) -> ApiResponse[AuthUser]:
    return ApiResponse(success=True, data=current_user)


@router.post("/logout", response_model=ApiResponse[LogoutResponse])
def logout() -> ApiResponse[LogoutResponse]:
    return ApiResponse(
        success=True,
        data=LogoutResponse(message="Logout completed on the client."),
    )
