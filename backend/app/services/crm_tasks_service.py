"""CRM Tasks service (WF 06 - Task & Reminder).

Provides CRUD operations for follow-up tasks tied to a CRM lead (optional)
and an internal endpoint feed for the n8n Cron workflow that emails sales
reps about their pending follow-ups.
"""

from datetime import datetime, timedelta, timezone
import logging
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import CrmLead, CrmTask, User

# Delay after a reminder email is sent before the same task can be re-included
# in the next pending-followup digest. Override with env var if you want WF06
# to repeat reminders sooner or later than the default 48h cadence.
CRM_TASK_REMINDER_REARM_HOURS = 48
from app.schemas.crm_tasks_deals import (
    CrmPendingFollowupOwnerGroup,
    CrmPendingFollowupResponse,
    CrmTaskCreate,
    CrmTaskItem,
    CrmTaskListResponse,
    CrmTaskReminderAck,
    CrmTaskUpdate,
    CrmTeamMember,
    CrmTeamMemberListResponse,
    TASK_PRIORITIES,
    TASK_STATUSES,
)
from app.services.crm_comments_service import count_comments_by_entity

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_item(
    task: CrmTask,
    *,
    lead: CrmLead | None = None,
    owner: User | None = None,
    comments_count: int = 0,
) -> CrmTaskItem:
    now = utc_now()
    due = _aware(task.due_date) or now
    delta_seconds = (due - now).total_seconds()
    days_until_due = int(delta_seconds // 86400)
    is_overdue = task.status == "pending" and delta_seconds < 0
    return CrmTaskItem(
        id=task.id,
        lead_id=task.lead_id,
        lead_full_name=lead.full_name if lead else None,
        lead_company_name=lead.company_name if lead else None,
        owner_user_id=task.owner_user_id,
        owner_full_name=owner.full_name if owner else None,
        owner_email=owner.email if owner else None,
        title=task.title,
        description=task.description,
        due_date=task.due_date,
        status=task.status if task.status in TASK_STATUSES else "pending",
        priority=task.priority if task.priority in TASK_PRIORITIES else "medium",
        task_type=task.task_type,
        reminder_sent_at=task.reminder_sent_at,
        next_reminder_at=task.next_reminder_at,
        completed_at=task.completed_at,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
        days_until_due=days_until_due,
        is_overdue=is_overdue,
        comments_count=comments_count,
    )


def _resolve_task_relations(
    db: Session,
    tasks: list[CrmTask],
) -> tuple[dict[str, CrmLead], dict[str, User], dict[str, int]]:
    """Fetch lead, owner, and comment counts for a list of tasks in 3 queries."""
    lead_ids = {task.lead_id for task in tasks if task.lead_id}
    owner_ids = {task.owner_user_id for task in tasks if task.owner_user_id}
    leads: dict[str, CrmLead] = {}
    owners: dict[str, User] = {}
    if lead_ids:
        leads = {
            lead.id: lead
            for lead in db.scalars(select(CrmLead).where(CrmLead.id.in_(lead_ids))).all()
        }
    if owner_ids:
        owners = {
            user.id: user
            for user in db.scalars(select(User).where(User.id.in_(owner_ids))).all()
        }
    comments = count_comments_by_entity(db, "task", [task.id for task in tasks])
    return leads, owners, comments


def _require_task(db: Session, task_id: str) -> CrmTask:
    try:
        task = db.get(CrmTask, task_id)
    except SQLAlchemyError as exc:
        logger.exception("CRM task could not be loaded.")
        raise HTTPException(status_code=500, detail="CRM task could not be loaded.") from exc

    if task is None:
        raise HTTPException(status_code=404, detail="CRM task not found.")
    return task


def _validate_owner(db: Session, owner_user_id: str) -> None:
    if db.get(User, owner_user_id) is None:
        raise HTTPException(
            status_code=422,
            detail=f"Owner user '{owner_user_id}' does not exist.",
        )


def _validate_lead(db: Session, lead_id: str | None) -> None:
    if lead_id is None:
        return
    if db.get(CrmLead, lead_id) is None:
        raise HTTPException(
            status_code=422,
            detail=f"CRM lead '{lead_id}' does not exist.",
        )


def list_tasks(
    db: Session,
    *,
    status: str | None = None,
    owner_user_id: str | None = None,
    lead_id: str | None = None,
) -> CrmTaskListResponse:
    try:
        statement = select(CrmTask).order_by(CrmTask.due_date.asc())
        if status:
            statement = statement.where(CrmTask.status == status)
        if owner_user_id:
            statement = statement.where(CrmTask.owner_user_id == owner_user_id)
        if lead_id:
            statement = statement.where(CrmTask.lead_id == lead_id)
        tasks = list(db.scalars(statement).all())
    except SQLAlchemyError as exc:
        logger.exception("CRM task listing failed.")
        raise HTTPException(status_code=500, detail="CRM tasks could not be loaded.") from exc

    leads, owners, comments = _resolve_task_relations(db, tasks)
    items = [
        _to_item(
            task,
            lead=leads.get(task.lead_id) if task.lead_id else None,
            owner=owners.get(task.owner_user_id),
            comments_count=comments.get(task.id, 0),
        )
        for task in tasks
    ]
    return CrmTaskListResponse(count=len(items), items=items)


def get_task(db: Session, task_id: str) -> CrmTaskItem:
    task = _require_task(db, task_id)
    leads, owners, comments = _resolve_task_relations(db, [task])
    return _to_item(
        task,
        lead=leads.get(task.lead_id) if task.lead_id else None,
        owner=owners.get(task.owner_user_id),
        comments_count=comments.get(task.id, 0),
    )


def create_task(db: Session, payload: CrmTaskCreate, *, created_by: str | None) -> CrmTaskItem:
    _validate_owner(db, payload.owner_user_id)
    _validate_lead(db, payload.lead_id)

    now = utc_now()
    task = CrmTask(
        id=f"task_{uuid4().hex[:8]}",
        lead_id=payload.lead_id,
        owner_user_id=payload.owner_user_id,
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
        due_date=_aware(payload.due_date) or now,
        priority=payload.priority,
        status="pending",
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(task)
        db.commit()
        db.refresh(task)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM task could not be saved.")
        raise HTTPException(status_code=500, detail="CRM task could not be saved.") from exc

    leads, owners, _ = _resolve_task_relations(db, [task])
    return _to_item(
        task,
        lead=leads.get(task.lead_id) if task.lead_id else None,
        owner=owners.get(task.owner_user_id),
        comments_count=0,
    )


def update_task(db: Session, task_id: str, payload: CrmTaskUpdate) -> CrmTaskItem:
    task = _require_task(db, task_id)

    if payload.owner_user_id is not None:
        _validate_owner(db, payload.owner_user_id)
        task.owner_user_id = payload.owner_user_id
    if payload.title is not None:
        task.title = payload.title.strip()
    if payload.description is not None:
        task.description = payload.description.strip() or None
    if payload.due_date is not None:
        task.due_date = _aware(payload.due_date) or task.due_date
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.status is not None:
        if payload.status not in TASK_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid task status. Allowed: {', '.join(TASK_STATUSES)}.",
            )
        previous_status = task.status
        task.status = payload.status
        if payload.status == "done" and previous_status != "done":
            task.completed_at = utc_now()
        if payload.status != "done":
            task.completed_at = None

    task.updated_at = utc_now()

    try:
        db.commit()
        db.refresh(task)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM task could not be updated.")
        raise HTTPException(status_code=500, detail="CRM task could not be updated.") from exc

    leads, owners, comments = _resolve_task_relations(db, [task])
    return _to_item(
        task,
        lead=leads.get(task.lead_id) if task.lead_id else None,
        owner=owners.get(task.owner_user_id),
        comments_count=comments.get(task.id, 0),
    )


def delete_task(db: Session, task_id: str) -> None:
    task = _require_task(db, task_id)
    try:
        db.delete(task)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM task could not be deleted.")
        raise HTTPException(status_code=500, detail="CRM task could not be deleted.") from exc


def list_pending_followup_tasks(
    db: Session,
    *,
    threshold_hours: int = 48,
) -> CrmPendingFollowupResponse:
    """Tasks due within the next threshold_hours (or already overdue) and still pending.

    Grouped by owner so WF 06 can send one digest email per sales rep.
    """
    threshold_hours = max(1, min(threshold_hours, 24 * 30))
    now = utc_now()
    cutoff = datetime.fromtimestamp(now.timestamp() + threshold_hours * 3600, tz=timezone.utc)

    try:
        # A task qualifies for the next digest if it is pending, due within the
        # window, AND either has never been reminded yet OR its next_reminder_at
        # has already elapsed (= time to re-include in a digest). This keeps the
        # digest fresh without spamming the owner every morning.
        tasks = list(
            db.scalars(
                select(CrmTask)
                .where(CrmTask.status == "pending")
                .where(CrmTask.due_date <= cutoff)
                .where(
                    or_(
                        CrmTask.reminder_sent_at.is_(None),
                        CrmTask.next_reminder_at.is_(None),
                        CrmTask.next_reminder_at <= now,
                    )
                )
                .order_by(CrmTask.due_date.asc())
            ).all()
        )
    except SQLAlchemyError as exc:
        logger.exception("Pending follow-up tasks could not be loaded.")
        raise HTTPException(
            status_code=500,
            detail="Pending follow-up tasks could not be loaded.",
        ) from exc

    leads, owners_map, comments_map = _resolve_task_relations(db, tasks)
    grouped: dict[str, list[CrmTaskItem]] = {}
    for task in tasks:
        grouped.setdefault(task.owner_user_id, []).append(
            _to_item(
                task,
                lead=leads.get(task.lead_id) if task.lead_id else None,
                owner=owners_map.get(task.owner_user_id),
                comments_count=comments_map.get(task.id, 0),
            )
        )

    if not grouped:
        return CrmPendingFollowupResponse(
            threshold_hours=threshold_hours,
            total_tasks=0,
            owners=[],
        )

    owner_ids = list(grouped.keys())
    try:
        owners = {
            user.id: user
            for user in db.scalars(select(User).where(User.id.in_(owner_ids))).all()
        }
    except SQLAlchemyError as exc:
        logger.exception("Owner lookup for pending tasks failed.")
        raise HTTPException(
            status_code=500,
            detail="Owner lookup for pending tasks failed.",
        ) from exc

    owner_groups: list[CrmPendingFollowupOwnerGroup] = []
    total = 0
    for owner_id, owner_tasks in grouped.items():
        owner = owners.get(owner_id)
        if owner is None or not owner.email:
            # Skip dangling owners — they would never receive the email.
            continue
        total += len(owner_tasks)
        owner_groups.append(
            CrmPendingFollowupOwnerGroup(
                owner_user_id=owner.id,
                owner_full_name=owner.full_name,
                owner_email=owner.email,
                tasks=owner_tasks,
            )
        )

    return CrmPendingFollowupResponse(
        threshold_hours=threshold_hours,
        total_tasks=total,
        owners=owner_groups,
    )


def list_team_members(db: Session) -> CrmTeamMemberListResponse:
    """Lightweight active-users roster for CRM owner pickers (tasks/deals)."""
    try:
        users = list(
            db.scalars(
                select(User).where(User.status == "active").order_by(User.full_name.asc())
            ).all()
        )
    except SQLAlchemyError as exc:
        logger.exception("Listing CRM team members failed.")
        raise HTTPException(
            status_code=500,
            detail="CRM team members could not be loaded.",
        ) from exc

    items = [
        CrmTeamMember(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            role_id=user.role_id,
            job_title=user.job_title,
        )
        for user in users
    ]
    return CrmTeamMemberListResponse(count=len(items), items=items)


def mark_tasks_reminded(db: Session, task_ids: list[str]) -> CrmTaskReminderAck:
    """Called by n8n WF 06 after the reminder email was sent successfully."""
    if not task_ids:
        return CrmTaskReminderAck(task_ids=[], reminded_at=utc_now())

    try:
        tasks = list(
            db.scalars(select(CrmTask).where(CrmTask.id.in_(task_ids))).all()
        )
    except SQLAlchemyError as exc:
        logger.exception("Task reminder bulk update failed (load).")
        raise HTTPException(
            status_code=500,
            detail="Task reminder bulk update failed.",
        ) from exc

    now = utc_now()
    next_reminder = now + timedelta(hours=CRM_TASK_REMINDER_REARM_HOURS)
    updated_ids: list[str] = []
    for task in tasks:
        if task.status != "pending":
            continue
        task.reminder_sent_at = now
        task.next_reminder_at = next_reminder
        task.updated_at = now
        updated_ids.append(task.id)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Task reminder bulk update failed (commit).")
        raise HTTPException(
            status_code=500,
            detail="Task reminder bulk update failed.",
        ) from exc

    return CrmTaskReminderAck(task_ids=updated_ids, reminded_at=now)
