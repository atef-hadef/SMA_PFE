"""CRM Deals service (WF 07 - Deal Pipeline Update).

Manages deals attached to leads and posts a webhook to n8n every time a deal
stage changes, so WF 07 can run conditional automation (proposal email
generation, win/lost notifications, etc.).
"""

from datetime import datetime, timezone
import logging
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CrmDeal, CrmLead, User
from app.schemas.crm_tasks_deals import (
    CrmDealCreate,
    CrmDealItem,
    CrmDealListResponse,
    CrmDealStageTransitionRequest,
    CrmDealStageTransitionResponse,
    CrmDealUpdate,
    DEAL_STAGES,
)
from app.services import webhook_outbox_service
from app.services.crm_comments_service import count_comments_by_entity

logger = logging.getLogger(__name__)

DEAL_STAGE_PIPELINE_WEBHOOK_PATH = "flowpilot-crm-deal-stage-changed"

# Allowed transitions. Closed deals (won/lost) are terminal.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "discovery": {"discovery", "proposal", "lost"},
    "proposal": {"proposal", "negotiation", "lost"},
    "negotiation": {"negotiation", "closing", "lost"},
    "closing": {"closing", "won", "lost"},
    "won": set(),
    "lost": set(),
}

# Default win probability per stage (used when probability is not provided).
DEFAULT_PROBABILITY: dict[str, int] = {
    "discovery": 20,
    "proposal": 40,
    "negotiation": 60,
    "closing": 80,
    "won": 100,
    "lost": 0,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_item(
    deal: CrmDeal,
    *,
    lead: CrmLead | None = None,
    owner: User | None = None,
    comments_count: int = 0,
) -> CrmDealItem:
    return CrmDealItem(
        id=deal.id,
        lead_id=deal.lead_id,
        lead_full_name=lead.full_name if lead else None,
        lead_company_name=lead.company_name if lead else None,
        owner_user_id=deal.owner_user_id,
        owner_full_name=owner.full_name if owner else None,
        owner_email=owner.email if owner else None,
        title=deal.title,
        stage=deal.stage if deal.stage in DEAL_STAGES else "discovery",
        previous_stage=deal.previous_stage,
        amount=deal.amount,
        currency=deal.currency,
        probability_percent=deal.probability_percent,
        expected_close_date=deal.expected_close_date,
        notes=deal.notes,
        won_reason=deal.won_reason,
        lost_reason=deal.lost_reason,
        closed_at=deal.closed_at,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        comments_count=comments_count,
    )


def _resolve_deal_relations(
    db: Session,
    deals: list[CrmDeal],
) -> tuple[dict[str, CrmLead], dict[str, User], dict[str, int]]:
    lead_ids = {deal.lead_id for deal in deals if deal.lead_id}
    owner_ids = {deal.owner_user_id for deal in deals if deal.owner_user_id}
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
    comments = count_comments_by_entity(db, "deal", [deal.id for deal in deals])
    return leads, owners, comments


def _require_deal(db: Session, deal_id: str) -> CrmDeal:
    try:
        deal = db.get(CrmDeal, deal_id)
    except SQLAlchemyError as exc:
        logger.exception("CRM deal could not be loaded.")
        raise HTTPException(status_code=500, detail="CRM deal could not be loaded.") from exc

    if deal is None or deal.deleted_at is not None:
        raise HTTPException(status_code=404, detail="CRM deal not found.")
    return deal


def _validate_owner(db: Session, owner_user_id: str) -> None:
    if db.get(User, owner_user_id) is None:
        raise HTTPException(
            status_code=422,
            detail=f"Owner user '{owner_user_id}' does not exist.",
        )


def _validate_lead(db: Session, lead_id: str) -> CrmLead:
    lead = db.get(CrmLead, lead_id)
    if lead is None:
        raise HTTPException(
            status_code=422,
            detail=f"CRM lead '{lead_id}' does not exist.",
        )
    return lead


def list_deals(
    db: Session,
    *,
    stage: str | None = None,
    owner_user_id: str | None = None,
    lead_id: str | None = None,
) -> CrmDealListResponse:
    try:
        statement = (
            select(CrmDeal)
            .where(CrmDeal.deleted_at.is_(None))
            .order_by(CrmDeal.updated_at.desc())
        )
        if stage:
            statement = statement.where(CrmDeal.stage == stage)
        if owner_user_id:
            statement = statement.where(CrmDeal.owner_user_id == owner_user_id)
        if lead_id:
            statement = statement.where(CrmDeal.lead_id == lead_id)
        deals = list(db.scalars(statement).all())
    except SQLAlchemyError as exc:
        logger.exception("CRM deal listing failed.")
        raise HTTPException(status_code=500, detail="CRM deals could not be loaded.") from exc

    leads, owners, comments = _resolve_deal_relations(db, deals)
    items = [
        _to_item(
            deal,
            lead=leads.get(deal.lead_id),
            owner=owners.get(deal.owner_user_id),
            comments_count=comments.get(deal.id, 0),
        )
        for deal in deals
    ]
    return CrmDealListResponse(count=len(items), items=items)


def get_deal(db: Session, deal_id: str) -> CrmDealItem:
    deal = _require_deal(db, deal_id)
    leads, owners, comments = _resolve_deal_relations(db, [deal])
    return _to_item(
        deal,
        lead=leads.get(deal.lead_id),
        owner=owners.get(deal.owner_user_id),
        comments_count=comments.get(deal.id, 0),
    )


def create_deal(db: Session, payload: CrmDealCreate) -> CrmDealItem:
    _validate_owner(db, payload.owner_user_id)
    _validate_lead(db, payload.lead_id)

    now = utc_now()
    deal = CrmDeal(
        id=f"deal_{uuid4().hex[:8]}",
        lead_id=payload.lead_id,
        owner_user_id=payload.owner_user_id,
        title=payload.title.strip(),
        stage=payload.stage,
        previous_stage=None,
        amount=payload.amount,
        currency=payload.currency,
        probability_percent=payload.probability_percent,
        expected_close_date=payload.expected_close_date,
        notes=(payload.notes or "").strip() or None,
        created_at=now,
        updated_at=now,
    )
    if payload.stage in {"won", "lost"}:
        deal.closed_at = now

    try:
        db.add(deal)
        db.commit()
        db.refresh(deal)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM deal could not be saved.")
        raise HTTPException(status_code=500, detail="CRM deal could not be saved.") from exc

    leads, owners, comments = _resolve_deal_relations(db, [deal])
    return _to_item(
        deal,
        lead=leads.get(deal.lead_id),
        owner=owners.get(deal.owner_user_id),
        comments_count=comments.get(deal.id, 0),
    )


def update_deal(db: Session, deal_id: str, payload: CrmDealUpdate) -> CrmDealItem:
    deal = _require_deal(db, deal_id)

    if payload.owner_user_id is not None:
        _validate_owner(db, payload.owner_user_id)
        deal.owner_user_id = payload.owner_user_id
    if payload.title is not None:
        deal.title = payload.title.strip()
    if payload.amount is not None:
        deal.amount = payload.amount
    if payload.currency is not None:
        deal.currency = payload.currency
    if payload.probability_percent is not None:
        deal.probability_percent = payload.probability_percent
    if payload.expected_close_date is not None:
        deal.expected_close_date = payload.expected_close_date
    if payload.notes is not None:
        deal.notes = payload.notes.strip() or None

    deal.updated_at = utc_now()
    try:
        db.commit()
        db.refresh(deal)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM deal could not be updated.")
        raise HTTPException(status_code=500, detail="CRM deal could not be updated.") from exc

    leads, owners, comments = _resolve_deal_relations(db, [deal])
    return _to_item(
        deal,
        lead=leads.get(deal.lead_id),
        owner=owners.get(deal.owner_user_id),
        comments_count=comments.get(deal.id, 0),
    )


def transition_deal_stage(
    db: Session,
    deal_id: str,
    payload: CrmDealStageTransitionRequest,
    *,
    requested_by: str | None,
) -> CrmDealStageTransitionResponse:
    deal = _require_deal(db, deal_id)
    lead = _validate_lead(db, deal.lead_id)

    new_stage = payload.new_stage
    if new_stage not in DEAL_STAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid deal stage. Allowed: {', '.join(DEAL_STAGES)}.",
        )

    current_stage = deal.stage
    allowed = ALLOWED_TRANSITIONS.get(current_stage, set())
    if new_stage not in allowed and new_stage != current_stage:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Deal cannot transition from '{current_stage}' to '{new_stage}'. "
                f"Allowed: {sorted(allowed) or 'terminal stage'}."
            ),
        )

    if current_stage in {"won", "lost"}:
        raise HTTPException(
            status_code=422,
            detail=f"Deal is already closed ({current_stage}) and cannot transition.",
        )

    if new_stage == current_stage:
        # No-op transition is fine but does not trigger the workflow.
        return CrmDealStageTransitionResponse(
            deal_id=deal.id,
            new_stage=new_stage,
            previous_stage=deal.previous_stage,
            workflow_triggered=False,
            n8n_response=None,
            message="Deal already at requested stage.",
        )

    now = utc_now()
    deal.previous_stage = current_stage
    deal.stage = new_stage
    deal.probability_percent = DEFAULT_PROBABILITY.get(new_stage, deal.probability_percent)
    deal.updated_at = now

    reason = (payload.reason or "").strip() or None
    if new_stage == "won":
        deal.won_reason = reason
        deal.closed_at = now
    elif new_stage == "lost":
        deal.lost_reason = reason
        deal.closed_at = now

    try:
        db.commit()
        db.refresh(deal)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Deal stage transition could not be saved for %s.", deal_id)
        raise HTTPException(
            status_code=500,
            detail="Deal stage transition could not be saved.",
        ) from exc

    workflow_triggered = False
    n8n_response = None
    if payload.trigger_workflow:
        outbox = webhook_outbox_service.enqueue(
            db,
            _deal_stage_webhook_url(),
            {
                "deal_id": deal.id,
                "lead_id": deal.lead_id,
                "owner_user_id": deal.owner_user_id,
                "title": deal.title,
                "new_stage": new_stage,
                "previous_stage": current_stage,
                "amount": float(deal.amount) if deal.amount is not None else None,
                "currency": deal.currency,
                "probability_percent": deal.probability_percent,
                "expected_close_date": (
                    deal.expected_close_date.isoformat()
                    if deal.expected_close_date
                    else None
                ),
                "reason": reason,
                "lead_full_name": lead.full_name,
                "lead_email": lead.email or "",
                "lead_company_name": lead.company_name,
                "lead_product_service": lead.product_service,
                "requested_by": requested_by or "user_030",
                "transitioned_at": now.isoformat(),
            },
            related_object_type="crm_deal",
            related_object_id=deal.id,
            workflow_name="FP_CRM_07_Deal_Pipeline_Update",
        )
        try:
            n8n_response = webhook_outbox_service.sync_attempt(db, outbox)
            workflow_triggered = True
        except HTTPException:
            # Sync attempt failed; outbox row is marked 'failed' with backoff
            # and the cron worker will retry. Keep the existing soft-warning
            # behaviour for the caller — the stage change itself is committed.
            logger.warning(
                "Deal stage workflow sync attempt failed for deal %s; outbox %s will retry.",
                deal.id,
                outbox.id,
            )

    return CrmDealStageTransitionResponse(
        deal_id=deal.id,
        new_stage=new_stage,
        previous_stage=current_stage,
        workflow_triggered=workflow_triggered,
        n8n_response=n8n_response,
        message=(
            f"Deal moved from '{current_stage}' to '{new_stage}'."
            + ("" if workflow_triggered else " Workflow trigger failed; stage change persisted.")
        ),
    )


def delete_deal(db: Session, deal_id: str) -> None:
    # Soft-delete: deals are the anchor for proposal drafts and workflow
    # traceability (WF 07). Physically removing a deal would orphan those
    # records, so we mark it deleted and exclude it from all reads instead.
    deal = _require_deal(db, deal_id)
    now = utc_now()
    deal.deleted_at = now
    deal.updated_at = now
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM deal could not be deleted.")
        raise HTTPException(status_code=500, detail="CRM deal could not be deleted.") from exc


def _deal_stage_webhook_url() -> str:
    return (
        f"{settings.N8N_WEBHOOK_BASE_URL.rstrip('/')}/"
        f"{DEAL_STAGE_PIPELINE_WEBHOOK_PATH}"
    )


