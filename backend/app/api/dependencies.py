import hmac
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User
from app.schemas.auth import AuthUser
from app.services.auth_service import build_auth_user

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthenticated_error()

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise _unauthenticated_error() from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise _unauthenticated_error()

    try:
        user = db.get(User, user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated user could not be loaded.",
        ) from exc

    if user is None or user.status != "active":
        raise _unauthenticated_error()

    return build_auth_user(user, db)


def require_permission(permission_name: str) -> Callable[[AuthUser], AuthUser]:
    def dependency(
        current_user: AuthUser = Depends(get_current_user),
    ) -> AuthUser:
        if permission_name not in current_user.permissions:
            raise _forbidden_error(permission_name)
        return current_user

    return dependency


def require_any_permission(
    permission_names: list[str],
) -> Callable[[AuthUser], AuthUser]:
    required_permissions = set(permission_names)

    def dependency(
        current_user: AuthUser = Depends(get_current_user),
    ) -> AuthUser:
        if required_permissions.isdisjoint(current_user.permissions):
            raise _forbidden_error(", ".join(permission_names))
        return current_user

    return dependency


def require_internal_secret(request: Request) -> None:
    incoming_secret = request.headers.get("X-FlowPilot-Secret", "")
    expected_secret = settings.FLOWPILOT_N8N_SHARED_SECRET

    if not expected_secret or not hmac.compare_digest(incoming_secret, expected_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid FlowPilot integration secret.",
        )


def require_permission_or_internal_secret(
    permission_name: str,
) -> Callable[[Request, HTTPAuthorizationCredentials | None, Session], AuthUser | None]:
    def dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
        db: Session = Depends(get_db),
    ) -> AuthUser | None:
        incoming_secret = request.headers.get("X-FlowPilot-Secret", "")
        expected_secret = settings.FLOWPILOT_N8N_SHARED_SECRET
        if expected_secret and hmac.compare_digest(incoming_secret, expected_secret):
            return None

        current_user = get_current_user(credentials=credentials, db=db)
        if permission_name not in current_user.permissions:
            raise _forbidden_error(permission_name)
        return current_user

    return dependency


def _unauthenticated_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden_error(permission_name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Permission required: {permission_name}.",
    )
