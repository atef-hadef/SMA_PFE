from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models import Role, RolePermission, User
from app.schemas.auth import AuthUser, LoginRequest, LoginResponse


def authenticate_user(payload: LoginRequest, db: Session) -> LoginResponse:
    user = get_user_by_email(payload.email, db)
    if user is None or user.status != "active":
        raise _invalid_credentials_error()

    if not verify_password(payload.password, user.password_hash):
        raise _invalid_credentials_error()

    user.last_login_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login could not be completed.",
        )

    auth_user = build_auth_user(user, db)
    token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": auth_user.role_name},
    )
    return LoginResponse(access_token=token, user=auth_user)


def get_user_by_email(email: str, db: Session) -> User | None:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return None

    statement = select(User).where(func.lower(User.email) == normalized_email)
    return db.scalars(statement).first()


def build_auth_user(user: User, db: Session) -> AuthUser:
    role = db.get(Role, user.role_id)
    return AuthUser(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role_id=user.role_id,
        role_name=role.name if role else user.role_id,
        permissions=get_user_permissions(user, db),
        status=user.status,
        job_title=user.job_title,
        department=user.department,
    )


def get_user_permissions(user: User, db: Session) -> list[str]:
    statement = (
        select(RolePermission.permission_code)
        .where(RolePermission.role_id == user.role_id)
        .order_by(RolePermission.permission_code)
    )
    return list(db.scalars(statement).all())


def _invalid_credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )
