"""CRM lead responses (FIX 3) — enregistre la réponse d'un prospect et déclenche
les suites métier (qualification, perte, ou création d'une tâche de relance)."""

from datetime import datetime, timedelta, timezone
import logging
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import CrmLead, CrmLeadResponse, CrmTask, User
from app.schemas.crm_responses import (
    CrmLeadResponseCreate,
    CrmLeadResponseCreatedResponse,
    CrmLeadResponseItem,
    CrmLeadResponseListResponse,
)

logger = logging.getLogger(__name__)

# Horizon de relance par défaut quand l'utilisateur n'a pas choisi de date explicite.
NEEDS_MORE_INFO_DELAY_DAYS = 2
CALLBACK_DEFAULT_DELAY_DAYS = 1


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _require_lead(db: Session, lead_id: str) -> CrmLead:
    try:
        lead = db.get(CrmLead, lead_id)
    except SQLAlchemyError as exc:
        logger.exception("CRM lead could not be loaded.")
        raise HTTPException(status_code=500, detail="CRM lead could not be loaded.") from exc
    if lead is None:
        raise HTTPException(status_code=404, detail="CRM lead not found.")
    return lead


def _name_for(db: Session, user_id: str | None) -> str | None:
    if not user_id:
        return None
    user = db.get(User, user_id)
    return user.full_name if user else None


def _to_item(
    response: CrmLeadResponse,
    *,
    recorded_by_name: str | None = None,
) -> CrmLeadResponseItem:
    return CrmLeadResponseItem(
        id=response.id,
        lead_id=response.lead_id,
        response_type=response.response_type,
        notes=response.notes,
        next_action=response.next_action,
        next_action_date=response.next_action_date,
        recorded_by=response.recorded_by,
        recorded_by_name=recorded_by_name,
        recorded_at=response.recorded_at,
    )


def record_response(
    db: Session,
    lead_id: str,
    payload: CrmLeadResponseCreate,
    *,
    recorded_by: str,
) -> CrmLeadResponseCreatedResponse:
    lead = _require_lead(db, lead_id)
    now = utc_now()
    notes = (payload.notes or "").strip() or None
    next_action = (payload.next_action or "").strip() or None
    next_action_date = _aware(payload.next_action_date)

    response = CrmLeadResponse(
        id=f"resp_{uuid4().hex[:8]}",
        lead_id=lead.id,
        response_type=payload.response_type,
        notes=notes,
        next_action=next_action,
        next_action_date=next_action_date,
        recorded_by=recorded_by,
        recorded_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(response)

    # Le cycle de vie est porté par customer_status (lu par tout le CRM), pas par
    # status qui est un bucket de scoring coercé à new/hot/warm/cold. Cf. AUDIT_REPORT FIX 5.
    created_task: CrmTask | None = None
    message = "Réponse enregistrée."
    if payload.response_type == "interested":
        lead.customer_status = "prospect"
        message = "Réponse enregistrée — lead qualifié (prospect)."
    elif payload.response_type == "not_interested":
        lead.customer_status = "lost"
        message = "Réponse enregistrée — lead marqué perdu."
    elif payload.response_type in ("needs_more_info", "callback_requested"):
        delay = (
            NEEDS_MORE_INFO_DELAY_DAYS
            if payload.response_type == "needs_more_info"
            else CALLBACK_DEFAULT_DELAY_DAYS
        )
        due = next_action_date or (now + timedelta(days=delay))
        owner_id = (
            lead.assigned_to
            if (lead.assigned_to and db.get(User, lead.assigned_to))
            else recorded_by
        )
        title = (
            "Relance — informations demandées"
            if payload.response_type == "needs_more_info"
            else "Rappel client demandé"
        )
        created_task = CrmTask(
            id=f"task_{uuid4().hex[:8]}",
            lead_id=lead.id,
            owner_user_id=owner_id,
            title=title,
            description=notes,
            due_date=due,
            status="pending",
            priority="high" if payload.response_type == "callback_requested" else "medium",
            task_type="follow_up",
            created_by=recorded_by,
            created_at=now,
            updated_at=now,
        )
        db.add(created_task)
        message = "Réponse enregistrée — tâche de relance créée."

    lead.last_contact_at = now
    if next_action is not None:
        lead.next_action = next_action
    lead.updated_at = now

    try:
        db.commit()
        db.refresh(response)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM lead response could not be saved for lead %s.", lead_id)
        raise HTTPException(status_code=500, detail="Lead response could not be saved.") from exc

    return CrmLeadResponseCreatedResponse(
        response=_to_item(response, recorded_by_name=_name_for(db, recorded_by)),
        lead_status=lead.status,
        lead_customer_status=lead.customer_status,
        created_task_id=created_task.id if created_task else None,
        message=message,
    )


def list_responses(db: Session, lead_id: str) -> CrmLeadResponseListResponse:
    _require_lead(db, lead_id)
    try:
        rows = list(
            db.scalars(
                select(CrmLeadResponse)
                .where(CrmLeadResponse.lead_id == lead_id)
                .order_by(CrmLeadResponse.recorded_at.desc())
            ).all()
        )
    except SQLAlchemyError as exc:
        logger.exception("CRM lead responses could not be loaded.")
        raise HTTPException(status_code=500, detail="Lead responses could not be loaded.") from exc

    names: dict[str, str | None] = {}
    items: list[CrmLeadResponseItem] = []
    for row in rows:
        if row.recorded_by and row.recorded_by not in names:
            names[row.recorded_by] = _name_for(db, row.recorded_by)
        items.append(_to_item(row, recorded_by_name=names.get(row.recorded_by)))
    return CrmLeadResponseListResponse(count=len(items), items=items)
