"""Comment threads attached to CRM tasks and deals.

The same table backs both entity types so the UI can list them with one
service. Permissions are enforced at the endpoint layer.
"""

from datetime import datetime, timezone
import logging
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import CrmComment, CrmDeal, CrmTask, User
from app.schemas.crm_tasks_deals import (
    CrmCommentCreate,
    CrmCommentItem,
    CrmCommentListResponse,
)

logger = logging.getLogger(__name__)

ENTITY_TYPES = ("task", "deal")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_entity(db: Session, entity_type: str, entity_id: str) -> None:
    if entity_type == "task":
        entity = db.get(CrmTask, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="CRM task not found.")
    elif entity_type == "deal":
        entity = db.get(CrmDeal, entity_id)
        if entity is None or entity.deleted_at is not None:
            raise HTTPException(status_code=404, detail="CRM deal not found.")
    else:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid entity type '{entity_type}'.",
        )


def _to_item(comment: CrmComment, author: User | None) -> CrmCommentItem:
    return CrmCommentItem(
        id=comment.id,
        entity_type=comment.entity_type if comment.entity_type in ENTITY_TYPES else "task",
        entity_id=comment.entity_id,
        author_user_id=comment.author_user_id,
        author_full_name=author.full_name if author else comment.author_user_id,
        author_email=author.email if author else None,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


def list_comments(
    db: Session,
    entity_type: str,
    entity_id: str,
) -> CrmCommentListResponse:
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid entity type '{entity_type}'.",
        )
    _require_entity(db, entity_type, entity_id)

    try:
        rows = list(
            db.scalars(
                select(CrmComment)
                .where(CrmComment.entity_type == entity_type)
                .where(CrmComment.entity_id == entity_id)
                .order_by(CrmComment.created_at.asc())
            ).all()
        )
    except SQLAlchemyError as exc:
        logger.exception("Listing CRM comments failed.")
        raise HTTPException(
            status_code=500,
            detail="CRM comments could not be loaded.",
        ) from exc

    author_ids = {row.author_user_id for row in rows}
    authors: dict[str, User] = {}
    if author_ids:
        try:
            authors = {
                user.id: user
                for user in db.scalars(select(User).where(User.id.in_(author_ids))).all()
            }
        except SQLAlchemyError as exc:
            logger.exception("Resolving comment authors failed.")
            raise HTTPException(
                status_code=500,
                detail="Comment authors could not be resolved.",
            ) from exc

    items = [_to_item(row, authors.get(row.author_user_id)) for row in rows]
    return CrmCommentListResponse(count=len(items), items=items)


def create_comment(
    db: Session,
    entity_type: str,
    entity_id: str,
    payload: CrmCommentCreate,
    *,
    author_user_id: str,
) -> CrmCommentItem:
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid entity type '{entity_type}'.",
        )
    _require_entity(db, entity_type, entity_id)

    author = db.get(User, author_user_id)
    if author is None:
        raise HTTPException(status_code=422, detail="Comment author does not exist.")

    now = utc_now()
    comment = CrmComment(
        id=f"cmt_{uuid4().hex[:10]}",
        entity_type=entity_type,
        entity_id=entity_id,
        author_user_id=author_user_id,
        content=payload.content.strip(),
        created_at=now,
        updated_at=now,
    )
    if not comment.content:
        raise HTTPException(
            status_code=422,
            detail="Comment content cannot be empty.",
        )

    try:
        db.add(comment)
        db.commit()
        db.refresh(comment)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Saving CRM comment failed.")
        raise HTTPException(
            status_code=500,
            detail="Comment could not be saved.",
        ) from exc

    return _to_item(comment, author)


def delete_comment(db: Session, entity_type: str, entity_id: str, comment_id: str) -> None:
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid entity type '{entity_type}'.",
        )
    try:
        comment = db.get(CrmComment, comment_id)
    except SQLAlchemyError as exc:
        logger.exception("Loading CRM comment failed.")
        raise HTTPException(
            status_code=500,
            detail="Comment could not be loaded.",
        ) from exc

    if comment is None or comment.entity_type != entity_type or comment.entity_id != entity_id:
        raise HTTPException(status_code=404, detail="Comment not found.")

    try:
        db.delete(comment)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Deleting CRM comment failed.")
        raise HTTPException(
            status_code=500,
            detail="Comment could not be deleted.",
        ) from exc


def count_comments_by_entity(
    db: Session,
    entity_type: str,
    entity_ids: list[str],
) -> dict[str, int]:
    """Return {entity_id: count} for the provided entity_ids in one query.

    Used by tasks/deals list endpoints to surface comment counts inline.
    """
    if not entity_ids or entity_type not in ENTITY_TYPES:
        return {}
    try:
        rows = list(
            db.execute(
                select(CrmComment.entity_id, func.count(CrmComment.id))
                .where(CrmComment.entity_type == entity_type)
                .where(CrmComment.entity_id.in_(entity_ids))
                .group_by(CrmComment.entity_id)
            ).all()
        )
    except SQLAlchemyError as exc:
        logger.exception("Counting CRM comments failed.")
        raise HTTPException(
            status_code=500,
            detail="Comment counts could not be loaded.",
        ) from exc
    return {row[0]: row[1] for row in rows}
