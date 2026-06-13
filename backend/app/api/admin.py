from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.core.database import get_db
from app.schemas.admin import (
    DeactivateUserRequest,
    DeactivateUserResponse,
    RoleListItem,
    RolePermissionsUpdatedResponse,
    UpdateRolePermissionsRequest,
    UserCreate,
    UserCreatedResponse,
    UserListItem,
    UserUpdate,
    UserUpdatedResponse,
)
from app.schemas.common import ApiResponse, PaginatedResponse
from app.services.admin_service import (
    create_user,
    deactivate_user,
    get_roles,
    get_users,
    update_role_permissions,
    update_user,
)

router = APIRouter()


@router.get("/users", response_model=ApiResponse[PaginatedResponse[UserListItem]])
def read_users(
    db: Session = Depends(get_db),
    _user=Depends(require_permission("admin.users.manage")),
) -> ApiResponse[PaginatedResponse[UserListItem]]:
    return ApiResponse(success=True, data=get_users(db))


@router.post("/users", response_model=ApiResponse[UserCreatedResponse])
def submit_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("admin.users.manage")),
) -> ApiResponse[UserCreatedResponse]:
    return ApiResponse(success=True, data=create_user(payload, db))


@router.put("/users/{user_id}", response_model=ApiResponse[UserUpdatedResponse])
def modify_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("admin.users.manage")),
) -> ApiResponse[UserUpdatedResponse]:
    updated_user = update_user(user_id=user_id, payload=payload, db=db)

    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    return ApiResponse(success=True, data=updated_user)


@router.post(
    "/users/{user_id}/deactivate",
    response_model=ApiResponse[DeactivateUserResponse],
)
def deactivate_existing_user(
    user_id: str,
    payload: DeactivateUserRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("admin.users.manage")),
) -> ApiResponse[DeactivateUserResponse]:
    deactivated_user = deactivate_user(user_id=user_id, reason=payload.reason, db=db)

    if deactivated_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    return ApiResponse(success=True, data=deactivated_user)


@router.get("/roles", response_model=ApiResponse[PaginatedResponse[RoleListItem]])
def read_roles(
    db: Session = Depends(get_db),
    _user=Depends(require_permission("admin.roles.manage")),
) -> ApiResponse[PaginatedResponse[RoleListItem]]:
    return ApiResponse(success=True, data=get_roles(db))


@router.put(
    "/roles/{role_id}/permissions",
    response_model=ApiResponse[RolePermissionsUpdatedResponse],
)
def modify_role_permissions(
    role_id: str,
    payload: UpdateRolePermissionsRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("admin.roles.manage")),
) -> ApiResponse[RolePermissionsUpdatedResponse]:
    updated_role = update_role_permissions(
        role_id=role_id,
        permissions=payload.permissions,
        db=db,
    )

    if updated_role is None:
        raise HTTPException(status_code=404, detail="Role not found.")

    return ApiResponse(success=True, data=updated_role)
