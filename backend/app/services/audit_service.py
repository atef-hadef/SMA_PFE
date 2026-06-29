"""Audit log centralisé (FIX 4).

log_activity est best-effort : toute erreur est avalée (et loggée) pour ne JAMAIS
faire échouer l'action métier déjà committée par l'endpoint appelant.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.schemas.activities import ActivityItem, ActivityListResponse

logger = logging.getLogger(__name__)

HR_ENTITY_TYPES = ("leave_request", "leave_allocation")
FULL_VISIBILITY_ROLE_IDS = ("role_admin", "role_manager")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def log_activity(
    db: Session,
    *,
    entity_type: str,
    entity_id: str | None,
    action: str,
    actor_id: str | None = None,
    actor_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        if actor_name is None and actor_id:
            user = db.get(User, actor_id)
            actor_name = user.full_name if user else None
        db.add(
            AuditLog(
                id=f"audit_{uuid4().hex[:12]}",
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor_id=actor_id,
                actor_name=actor_name,
                details=details,
                created_at=utc_now(),
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.warning(
            "Audit log non enregistré (entity=%s id=%s action=%s).",
            entity_type,
            entity_id,
            action,
            exc_info=True,
        )


def _period_cutoff(period: str | None) -> datetime | None:
    if not period:
        return None
    now = utc_now()
    return {
        "today": now - timedelta(days=1),
        "week": now - timedelta(days=7),
        "month": now - timedelta(days=30),
    }.get(period)


def get_recent_activities(
    db: Session,
    *,
    current_user,
    limit: int = 50,
    entity_type: str | None = None,
    period: str | None = None,
) -> ActivityListResponse:
    limit = max(1, min(limit, 200))
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())

    role_id = getattr(current_user, "role_id", None)
    if role_id in FULL_VISIBILITY_ROLE_IDS:
        scope = "all"
    elif role_id == "role_hr":
        scope = "hr"
        stmt = stmt.where(AuditLog.entity_type.in_(HR_ENTITY_TYPES))
    else:
        scope = "own"
        stmt = stmt.where(AuditLog.actor_id == getattr(current_user, "id", None))

    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    cutoff = _period_cutoff(period)
    if cutoff is not None:
        stmt = stmt.where(AuditLog.created_at >= cutoff)

    try:
        rows = list(db.scalars(stmt.limit(limit)).all())
    except SQLAlchemyError as exc:
        logger.exception("Lecture des activités échouée.")
        raise HTTPException(status_code=500, detail="Activités indisponibles.") from exc

    items = [
        ActivityItem(
            id=row.id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            action=row.action,
            actor_id=row.actor_id,
            actor_name=row.actor_name,
            details=row.details,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return ActivityListResponse(count=len(items), scope=scope, items=items)
