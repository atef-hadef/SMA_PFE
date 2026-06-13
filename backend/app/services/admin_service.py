from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.permissions import ALL_PERMISSIONS
from app.core.security import hash_password
from app.models import Role, RolePermission, User
from app.schemas.admin import (
    DeactivateUserResponse,
    RoleListItem,
    RolePermissionsUpdatedResponse,
    UserCreate,
    UserCreatedResponse,
    UserListItem,
    UserUpdate,
    UserUpdatedResponse,
)
from app.schemas.common import PaginatedResponse, PaginationMeta


def get_users(db: Session) -> PaginatedResponse[UserListItem]:
    statement = select(User).order_by(User.created_at.desc())
    users = list(db.scalars(statement).all())
    roles_by_id = _roles_by_id(db)

    items = [
        UserListItem(
            id=user.id,
            name=user.full_name,
            email=user.email,
            role=roles_by_id.get(user.role_id, user.role_id),
            department=user.department or "Unassigned",
            status="inactive" if user.status == "inactive" else "active",
            last_login=user.last_login_at,
        )
        for user in users
    ]
    return _paginated(items)


def create_user(payload: UserCreate, db: Session) -> UserCreatedResponse:
    password = (payload.password or "").strip()
    if not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A temporary password is required when creating a user.",
        )

    role = _resolve_role(payload.role, db)
    now = datetime.now(timezone.utc)
    user = User(
        id=f"user_{uuid4().hex[:8]}",
        full_name=payload.name.strip(),
        email=payload.email.strip().lower(),
        password_hash=hash_password(password),
        role_id=role.id,
        status="active",
        department=payload.department.strip() or None,
        job_title=payload.job_title.strip() if payload.job_title else None,
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User could not be created.",
        ) from exc

    return UserCreatedResponse(
        id=user.id,
        name=user.full_name,
        email=user.email,
        role=role.name,
        department=user.department or "Unassigned",
        status="active",
        created_at=user.created_at,
    )


def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session,
) -> UserUpdatedResponse | None:
    user = db.get(User, user_id)
    if user is None:
        return None

    role = _resolve_role(payload.role, db)
    user.full_name = payload.name.strip()
    user.role_id = role.id
    user.department = payload.department.strip() or None
    if payload.job_title is not None:
        user.job_title = payload.job_title.strip() or None
    user.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User could not be updated.",
        ) from exc

    return UserUpdatedResponse(
        id=user.id,
        name=user.full_name,
        role=role.name,
        department=user.department or "Unassigned",
        updated_at=user.updated_at,
    )


def deactivate_user(
    user_id: str,
    reason: str,
    db: Session,
) -> DeactivateUserResponse | None:
    user = db.get(User, user_id)
    if user is None:
        return None

    user.status = "inactive"
    user.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User could not be deactivated.",
        ) from exc

    return DeactivateUserResponse(
        id=user.id,
        status="inactive",
        deactivated_at=user.updated_at,
        reason=reason,
    )


def get_roles(db: Session) -> PaginatedResponse[RoleListItem]:
    roles = list(db.scalars(select(Role).order_by(Role.name.asc())).all())
    permissions_by_role = _permissions_by_role_id(db)
    user_counts = _user_counts_by_role_id(db)

    items = [
        RoleListItem(
            id=role.id,
            name=role.name,
            description=role.description or "",
            user_count=user_counts.get(role.id, 0),
            permissions=permissions_by_role.get(role.id, []),
        )
        for role in roles
    ]
    return _paginated(items)


def update_role_permissions(
    role_id: str,
    permissions: list[str],
    db: Session,
) -> RolePermissionsUpdatedResponse | None:
    role = db.get(Role, role_id)
    if role is None:
        return None

    clean_permissions = sorted(set(permissions))
    unknown_permissions = sorted(set(clean_permissions).difference(ALL_PERMISSIONS))
    if unknown_permissions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown permissions: {', '.join(unknown_permissions)}",
        )

    now = datetime.now(timezone.utc)
    try:
        db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        for permission_code in clean_permissions:
            db.add(
                RolePermission(
                    id=_role_permission_id(role_id, permission_code),
                    role_id=role_id,
                    permission_code=permission_code,
                    created_at=now,
                    updated_at=now,
                )
            )
        role.updated_at = now
        db.commit()
        db.refresh(role)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role permissions could not be updated.",
        ) from exc

    return RolePermissionsUpdatedResponse(
        id=role.id,
        name=role.name,
        permissions=clean_permissions,
        updated_at=role.updated_at,
    )


def _resolve_role(role_identifier: str, db: Session) -> Role:
    normalized = role_identifier.strip()
    role = db.get(Role, normalized)
    if role is None:
        role = db.scalars(
            select(Role).where(func.lower(Role.name) == normalized.lower()),
        ).first()

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role not found.",
        )
    return role


def _roles_by_id(db: Session) -> dict[str, str]:
    roles = list(db.scalars(select(Role)).all())
    return {role.id: role.name for role in roles}


def _permissions_by_role_id(db: Session) -> dict[str, list[str]]:
    rows = list(
        db.execute(
            select(RolePermission.role_id, RolePermission.permission_code).order_by(
                RolePermission.permission_code.asc(),
            )
        ).all()
    )
    permissions_by_role: dict[str, list[str]] = {}
    for role_id, permission_code in rows:
        permissions_by_role.setdefault(role_id, []).append(permission_code)
    return permissions_by_role


def _user_counts_by_role_id(db: Session) -> dict[str, int]:
    rows = list(
        db.execute(
            select(User.role_id, func.count(User.id)).group_by(User.role_id),
        ).all()
    )
    return {role_id: int(count) for role_id, count in rows}


def _paginated(items: list) -> PaginatedResponse:
    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=1,
            page_size=20,
            total_items=len(items),
            total_pages=1,
        ),
    )


def _role_permission_id(role_id: str, permission_code: str) -> str:
    safe_permission = permission_code.replace(".", "_")
    return f"{role_id}_{safe_permission}"
