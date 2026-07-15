from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import re
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import crm_scoped_owner_id
from app.models import (
    CrmEmailAttachment,
    CrmEmailDraft,
    CrmEmailMessage,
    CrmInteraction,
    CrmLead,
    User,
    WorkflowExecution,
)
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.services import webhook_outbox_service
from app.schemas.crm import (
    CrmLeadDraft,
    CrmCommunicationDraftTriggerResponse,
    CrmCustomerConversionRequest,
    CrmCustomerConversionTriggerResponse,
    CrmDisplayState,
    CrmEmailAttachmentItem,
    CrmEmailDraftItem,
    CrmEmailDraftReject,
    CrmEmailDraftSendResponse,
    CrmEmailDraftUpdate,
    CrmEmailSendPackage,
    CrmEmailSendPackageAttachment,
    CrmInactiveLeadItem,
    CrmInactiveLeadsResponse,
    CrmLeadInteractionCreate,
    CrmLeadCreate,
    CrmLeadCreatedResponse,
    CrmLeadDetail,
    CrmInteractionHistoryItem,
    CrmLeadListItem,
    CrmWeeklyStatsResponse,
    CrmWorkflowErrorLogPayload,
    CrmWorkflowErrorLogResponse,
    CrmWorkflowTracePayload,
    CrmWorkflowTraceResponse,
    PublicCrmLeadIntake,
    PublicCrmLeadIntakeResponse,
)

DEFAULT_CRM_OWNER_ID = "user_030"
SALES_ROLE_ID = "role_sales"
# Statuts de cycle de vie qui ne comptent plus comme charge active pour le
# round-robin (lead clôturé ou client converti). Comparaison en minuscules.
INACTIVE_WORKLOAD_STATUSES = {
    "converted",
    "customer",
    "vip_customer",
    "lost",
    "archived",
    "unqualified",
}
COMMUNICATION_DRAFT_WEBHOOK_PATH = "flowpilot-crm-communication-draft"
CUSTOMER_CONVERSION_WEBHOOK_PATH = "flowpilot-crm-customer-converted"
APPROVED_EMAIL_SEND_WEBHOOK_PATH = "flowpilot-crm-send-approved-email-real"
PUBLIC_LEAD_INTAKE_WEBHOOK_PATH = "flowpilot-crm-lead-intake"
APPROVED_EMAIL_WORKFLOW_NAME = "FP CRM 04 - Approved Email Sending"
PUBLIC_LEAD_INTAKE_WORKFLOW_NAME = "FP_CRM_01_Lead_Intake_AI_Scoring_Routing"
PUBLIC_EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
logger = logging.getLogger(__name__)

INTERACTION_TYPE_LABELS = {
    "email_reply": "Email reply",
    "phone_call": "Phone call",
    "meeting": "Meeting",
    "whatsapp": "WhatsApp",
    "manual_note": "Manual note",
}
INTERACTION_CHANNELS = {
    "email_reply": "email",
    "phone_call": "phone",
    "meeting": "meeting",
    "whatsapp": "whatsapp",
    "manual_note": "sales note",
}
OUTCOME_LABELS = {
    "confirmed_interest": "Prospect confirmed interest",
    "requested_more_information": "Requested more information",
    "accepted_next_step": "Accepted next step",
    "no_response": "No response",
    "not_interested": "Not interested",
}
DRAFT_STATUSES = {
    "draft_generated",
    "edited",
    "reviewed",
    "approved",
    "sending",
    "rejected",
    "sent",
    "failed",
}
DRAFT_TYPES = {"sales", "welcome", "follow_up", "reactivation", "proposal"}
UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "email_attachments"
POSITIVE_RESPONSE_SIGNALS = {
    "confirmed_interest",
    "prospect_confirmed_interest",
    "accepted_next_step",
    "positive_response",
    "wants_to_continue",
    "wants_to_move_forward",
    "prospect confirmed interest",
    "confirmed interest",
    "accepted next step",
    "positive response",
    "wants to continue",
    "wants to move forward",
}
NEGATIVE_RESPONSE_SIGNALS = {
    "not_interested",
    "not interested",
    "declined",
    "rejected",
    "no interest",
    "not relevant",
    "not a priority",
    "refused",
    "pas intéressé",
    "pas interesse",
    "pas prioritaire",
    "refusé",
    "refuse",
}
NEUTRAL_RESPONSE_SIGNALS = {
    "requested_more_information",
    "need_more_info",
    "asked_question",
    "information_request",
    "neutral_response",
    "needs more information",
    "requested more information",
    "question",
    "demande plus d'informations",
    "demande plus d informations",
}
FOLLOW_UP_SIGNALS = {
    "follow_up",
    "call_again_later",
    "schedule_follow_up",
    "call again later",
    "relancer plus tard",
    "follow-up",
    "follow up",
}
RESPONSE_INTERACTION_TYPES = {
    "email_reply",
    "phone_call",
    "meeting",
    "whatsapp",
    "manual_note",
}
FRENCH_CRM_SIGNALS = {
    "bonjour",
    "nous",
    "voulons",
    "souhaitons",
    "besoin",
    "processus",
    "commercial",
    "relance",
    "automatiser",
    "prioriser",
    "tableau de bord",
}
CUSTOMER_LIFECYCLE_STAGES = {
    "customer",
    "active_customer",
    "inactive_customer",
    "loyal_customer",
    "vip_customer",
}
# Intermediate customer_status used between trigger and welcome-draft callback.
# Lifecycle stays "prospect" until the n8n welcome workflow finalizes the conversion.
CONVERSION_PENDING_STATUS = "conversion_pending"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_crm_lead_access(lead: CrmLead, current_user) -> None:
    """403 si un commercial (role_sales) ouvre un lead qui ne lui est pas assigné."""
    scoped_owner_id = crm_scoped_owner_id(current_user)
    if scoped_owner_id is not None and lead.assigned_to != scoped_owner_id:
        raise HTTPException(
            status_code=403,
            detail="Accès refusé : ce lead n'est pas assigné à votre compte.",
        )


def _assign_lead_round_robin(db: Session) -> str | None:
    """Round-robin pondéré par charge : renvoie l'id du commercial actif
    (role_sales) ayant le moins de leads actifs.

    - Candidats : role_id == 'role_sales' ET status == 'active'
      (HR / AI Supervisor et tout autre rôle sont exclus).
    - Charge = nb de leads dont customer_status NOT IN INACTIVE_WORKLOAD_STATUSES.
    - Égalité : plus petit id (rotation stable).
    - None si aucun commercial actif n'existe.
    """
    sales_users = list(
        db.scalars(
            select(User)
            .where(User.role_id == SALES_ROLE_ID)
            .where(User.status == "active")
            .order_by(User.id.asc())
        ).all()
    )
    if not sales_users:
        return None

    sales_ids = [user.id for user in sales_users]
    workload_rows = db.execute(
        select(CrmLead.assigned_to, func.count())
        .where(CrmLead.assigned_to.in_(sales_ids))
        .where(
            func.lower(func.coalesce(CrmLead.customer_status, "")).notin_(
                INACTIVE_WORKLOAD_STATUSES
            )
        )
        .group_by(CrmLead.assigned_to)
    ).all()
    workload = {owner_id: count for owner_id, count in workload_rows}

    # sales_users est déjà trié par id croissant : min() renvoie donc le plus
    # petit id parmi les ex-aequo de charge minimale.
    chosen = min(sales_users, key=lambda user: workload.get(user.id, 0))
    return chosen.id


def get_crm_leads(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    current_user=None,
) -> PaginatedResponse[CrmLeadListItem]:
    # Clamp before SQL so a hostile or buggy caller can't bypass the limit
    # and try to fetch the whole table again.
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size

    # Isolation par rôle : un commercial (role_sales) ne voit que les leads qui
    # lui sont assignés ; admin/manager (et appels internes) voient tout.
    scoped_owner_id = crm_scoped_owner_id(current_user)

    try:
        count_statement = select(func.count()).select_from(CrmLead)
        statement = select(CrmLead).order_by(CrmLead.created_at.desc())
        if scoped_owner_id is not None:
            count_statement = count_statement.where(CrmLead.assigned_to == scoped_owner_id)
            statement = statement.where(CrmLead.assigned_to == scoped_owner_id)
        total_items = db.scalar(count_statement) or 0
        statement = statement.offset(offset).limit(page_size)
        leads = list(db.scalars(statement).all())
        lead_ids = [lead.id for lead in leads]
        drafts_by_lead = _email_drafts_by_lead_id(db, lead_ids)
        interactions_by_lead = _interactions_by_lead_id(db, lead_ids)
        messages_by_lead = _email_messages_by_lead_id(db, lead_ids)
        owner_names_by_id = _owner_full_names_for_leads(db, leads)
        items = [
            _to_crm_lead_list_item(
                lead,
                db,
                drafts_by_lead.get(lead.id, []),
                interactions_by_lead.get(lead.id, []),
                messages_by_lead.get(lead.id, []),
                owner_names_by_id=owner_names_by_id,
            )
            for lead in leads
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="CRM leads could not be loaded.",
        ) from exc

    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


def get_crm_lead_by_id(
    lead_id: str,
    db: Session,
    current_user=None,
) -> CrmLeadDetail | None:
    try:
        lead = db.get(CrmLead, lead_id)
        if lead is None:
            return None

        _ensure_crm_lead_access(lead, current_user)

        interaction_statement = (
            select(CrmInteraction)
            .where(CrmInteraction.lead_id == lead.id)
            .order_by(CrmInteraction.interaction_date.desc())
        )
        interactions = list(db.scalars(interaction_statement).all())
        drafts = _email_drafts_by_lead_id(db, [lead.id]).get(lead.id, [])
        email_messages = _email_messages_by_lead_id(db, [lead.id]).get(lead.id, [])

        return _to_crm_lead_detail(lead, interactions, db, drafts, email_messages)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="CRM lead could not be loaded.",
        ) from exc


def get_lead_email_drafts(
    db: Session,
    lead_id: str,
    current_user=None,
) -> list[CrmEmailDraftItem]:
    try:
        lead = db.get(CrmLead, lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="CRM lead not found.")

        _ensure_crm_lead_access(lead, current_user)

        drafts = list(
            db.scalars(
                select(CrmEmailDraft)
                .where(CrmEmailDraft.lead_id == lead_id)
                .order_by(CrmEmailDraft.updated_at.desc())
            ).all()
        )
        attachments = _attachments_by_draft_id(db, [draft.id for draft in drafts])
        user_names = _user_names_for_drafts(db, drafts)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="CRM email drafts could not be loaded.",
        ) from exc

    return [
        _to_email_draft_item(draft, attachments.get(draft.id, []), user_names)
        for draft in drafts
    ]


def create_crm_lead(
    payload: CrmLeadCreate,
    db: Session,
) -> CrmLeadCreatedResponse:
    now = utc_now()
    assigned_owner = _assign_lead_round_robin(db) or DEFAULT_CRM_OWNER_ID
    lead = CrmLead(
        id=f"lead_{uuid4().hex[:8]}",
        full_name=payload.name,
        company_name=payload.company,
        email=payload.email,
        source=payload.source,
        status="new",
        lead_score=0,
        sentiment="neutral",
        urgency="low",
        intention="new-inquiry",
        message=payload.message,
        ai_summary="Lead captured and awaiting AI analysis.",
        recommended_action="Review lead details and assign next follow-up.",
        owner_user_id=assigned_owner,
        assigned_to=assigned_owner,
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(lead)
        db.commit()
        db.refresh(lead)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="CRM lead could not be saved.",
        ) from exc

    return CrmLeadCreatedResponse(
        id=lead.id,
        name=lead.full_name,
        company=lead.company_name,
        email=lead.email or "",
        source=lead.source or "",
        status="new",
        score=lead.lead_score,
        created_at=lead.created_at,
    )


def update_email_draft(
    db: Session,
    draft_id: str,
    payload: CrmEmailDraftUpdate,
) -> CrmEmailDraftItem:
    draft = _get_required_email_draft(db, draft_id)
    if draft.status in {"approved", "sending", "sent"}:
        raise HTTPException(
            status_code=422,
            detail="Approved, sending, or sent drafts cannot be edited directly.",
        )

    subject = _clean_optional_text(payload.subject)
    body = _clean_optional_text(payload.body)

    if subject is None and body is None:
        raise HTTPException(
            status_code=422,
            detail="Draft subject or body is required.",
        )

    now = utc_now()
    if subject is not None:
        draft.subject = subject
    if body is not None:
        draft.body = body
    draft.status = "edited"
    draft.edited_by = _resolve_user_id(payload.edited_by, db)
    draft.updated_at = now

    return _commit_email_draft_with_activity(
        db,
        draft,
        "Draft edited by human and requires review.",
        "Review edited draft",
        "Email draft could not be updated.",
        actor_user_id=draft.edited_by,
    )


def review_email_draft(
    db: Session,
    draft_id: str,
    current_user_id: str,
) -> CrmEmailDraftItem:
    draft = _get_required_email_draft(db, draft_id)
    if draft.status not in {"draft_generated", "edited"}:
        raise HTTPException(
            status_code=422,
            detail="Only generated or edited drafts can be marked as reviewed.",
        )

    now = utc_now()
    draft.status = "reviewed"
    draft.reviewed_by = _resolve_user_id(current_user_id, db)
    draft.reviewed_at = now
    draft.updated_at = now

    return _commit_email_draft_with_activity(
        db,
        draft,
        "Draft reviewed by human.",
        "Approve or reject reviewed draft",
        "Email draft could not be marked as reviewed.",
        actor_user_id=draft.reviewed_by,
    )


def approve_email_draft(
    db: Session,
    draft_id: str,
    current_user_id: str,
) -> CrmEmailDraftItem:
    draft = _get_required_email_draft(db, draft_id)

    # Enforce double-control: only drafts explicitly marked as reviewed can be
    # approved. A rejected draft must be edited (-> "edited"), then reviewed
    # (-> "reviewed"), before reaching this endpoint.
    if draft.status != "reviewed":
        raise HTTPException(
            status_code=422,
            detail="Draft must be marked as reviewed before approval.",
        )

    now = utc_now()
    draft.status = "approved"
    draft.approved_by = _resolve_user_id(current_user_id, db)
    draft.approved_at = now
    draft.updated_at = now

    return _commit_email_draft_with_activity(
        db,
        draft,
        "Draft approved and ready for automated sending.",
        "Approved draft ready for automated sending",
        "Email draft could not be approved.",
        actor_user_id=draft.approved_by,
    )


def reject_email_draft(
    db: Session,
    draft_id: str,
    payload: CrmEmailDraftReject,
) -> CrmEmailDraftItem:
    draft = _get_required_email_draft(db, draft_id)
    reason = payload.rejection_reason.strip()

    if draft.status not in {"draft_generated", "edited", "reviewed"}:
        raise HTTPException(
            status_code=422,
            detail="Only generated, edited, or reviewed drafts can be rejected.",
        )

    if not reason:
        raise HTTPException(status_code=422, detail="Rejection reason is required.")

    now = utc_now()
    draft.status = "rejected"
    draft.rejected_by = _resolve_user_id(payload.rejected_by, db)
    draft.rejected_at = now
    draft.rejection_reason = reason
    draft.updated_at = now

    return _commit_email_draft_with_activity(
        db,
        draft,
        f"Draft rejected. Reason: {reason}",
        "Revise rejected draft",
        "Email draft could not be rejected.",
        actor_user_id=draft.rejected_by,
    )


def upload_email_draft_attachment(
    db: Session,
    draft_id: str,
    file_name: str,
    file_content: bytes,
    mime_type: str | None,
    uploaded_by: str | None,
) -> CrmEmailAttachmentItem:
    draft = _get_required_email_draft(db, draft_id)
    if draft.status in {"approved", "sending", "sent"}:
        raise HTTPException(
            status_code=422,
            detail="Approved, sending, or sent drafts cannot be changed.",
        )

    safe_file_name = _safe_file_name(file_name)
    attachment_id = f"attachment_{uuid4().hex[:8]}"
    target_dir = UPLOAD_ROOT / draft_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{attachment_id}_{safe_file_name}"

    try:
        with target_path.open("wb") as output_file:
            output_file.write(file_content)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Attachment could not be stored.",
        ) from exc

    attachment = CrmEmailAttachment(
        id=attachment_id,
        draft_id=draft_id,
        file_name=safe_file_name,
        file_path=str(target_path),
        mime_type=mime_type,
        file_size_bytes=len(file_content),
        uploaded_by=_resolve_user_id(uploaded_by, db),
        created_at=utc_now(),
    )

    try:
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
    except SQLAlchemyError as exc:
        db.rollback()
        _delete_file_if_safe(target_path)
        raise HTTPException(
            status_code=500,
            detail="Attachment metadata could not be saved.",
        ) from exc

    return _to_email_attachment_item(attachment)


def delete_email_draft_attachment(
    db: Session,
    draft_id: str,
    attachment_id: str,
) -> None:
    attachment = _get_required_email_attachment(db, draft_id, attachment_id)
    draft = _get_required_email_draft(db, draft_id)
    if draft.status in {"approved", "sending", "sent"}:
        raise HTTPException(
            status_code=422,
            detail="Approved, sending, or sent draft attachments cannot be deleted.",
        )

    attachment_path = Path(attachment.file_path)

    try:
        db.delete(attachment)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Attachment could not be deleted.",
        ) from exc

    _delete_file_if_safe(attachment_path)


def send_approved_email_draft(
    db: Session,
    draft_id: str,
    requested_by: str | None = DEFAULT_CRM_OWNER_ID,
) -> CrmEmailDraftSendResponse:
    draft = _get_required_email_draft(db, draft_id)
    # Idempotence: refuse double-send while the previous run is still in
    # flight or already finished. The Gmail worker has no idempotency key, so
    # this is the only place we can prevent a duplicate customer email.
    if draft.status in {"sending", "sent"}:
        raise HTTPException(
            status_code=409,
            detail=(
                "Email is already being sent or has been sent. "
                "Wait for the current workflow to finish before retrying."
            ),
        )
    if draft.status not in {"approved", "failed"}:
        raise HTTPException(
            status_code=422,
            detail="Only approved drafts can start the automated sending workflow.",
        )

    lead = _get_required_lead_for_email_draft(db, draft.lead_id)
    if not (lead.email or "").strip():
        raise HTTPException(
            status_code=422,
            detail="Lead email is required before automated sending can start.",
        )
    if not (draft.subject or "").strip():
        raise HTTPException(
            status_code=422,
            detail="Draft subject is required before automated sending can start.",
        )
    if not (draft.body or "").strip():
        raise HTTPException(
            status_code=422,
            detail="Draft body is required before automated sending can start.",
        )

    now = utc_now()
    draft.status = "sending"
    draft.updated_at = now
    lead.next_action = "Automated email sending in progress"
    lead.updated_at = now
    workflow_execution = WorkflowExecution(
        id=_generate_trace_id("exec_crm_send", now),
        related_object_type="crm_email_draft",
        related_object_id=draft.id,
        workflow_name=APPROVED_EMAIL_WORKFLOW_NAME,
        process="CRM",
        trigger_source="CRM Draft Approval",
        status="running",
        started_at=now,
        input_summary="Approved email draft queued for real Gmail automated sending.",
        result_summary="Approved email sending workflow started.",
        created_at=now,
        updated_at=now,
    )
    db.add(workflow_execution)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Approved email sending workflow could not be prepared.",
        ) from exc

    payload = {
        "draft_id": draft.id,
        "lead_id": lead.id,
        "requested_by": requested_by or DEFAULT_CRM_OWNER_ID,
        "send_mode": "real",
    }

    outbox = webhook_outbox_service.enqueue(
        db,
        _approved_email_send_webhook_url(),
        payload,
        related_object_type="crm_email_draft",
        related_object_id=draft.id,
        workflow_name=APPROVED_EMAIL_WORKFLOW_NAME,
    )
    try:
        webhook_outbox_service.sync_attempt(db, outbox)
    except HTTPException:
        _mark_email_send_trigger_failed(db, draft.id, workflow_execution.id)
        # Opt out of cron retry: a retry would re-fire the Gmail send and we
        # have no idempotency key. Operator must reset the draft manually.
        webhook_outbox_service.mark_dead(
            db,
            outbox,
            "Send trigger failed; draft marked failed. No auto-retry to avoid duplicate Gmail send.",
        )
        raise

    return CrmEmailDraftSendResponse(
        ok=True,
        message="Approved email sending workflow started.",
    )


def get_email_draft_send_package(
    db: Session,
    draft_id: str,
) -> CrmEmailSendPackage:
    draft = _get_required_email_draft(db, draft_id)
    if draft.status not in {"approved", "sending"}:
        raise HTTPException(
            status_code=422,
            detail="Only approved drafts can be prepared for automated sending.",
        )

    lead = _get_required_lead_for_email_draft(db, draft.lead_id)
    to_email = (lead.email or "").strip()
    if not to_email:
        raise HTTPException(
            status_code=422,
            detail="Lead email is required before automated sending can start.",
        )

    attachments = _attachments_by_draft_id(db, [draft.id]).get(draft.id, [])

    return CrmEmailSendPackage(
        draft_id=draft.id,
        lead_id=lead.id,
        draft_type=_safe_draft_type(draft.draft_type),
        to_email=to_email,
        to_name=lead.full_name,
        company_name=lead.company_name,
        subject=draft.subject or "Untitled draft",
        body=draft.body or "No draft body available.",
        status="sending" if draft.status == "sending" else "approved",
        attachments=[
            CrmEmailSendPackageAttachment(
                attachment_id=attachment.id,
                file_name=attachment.file_name,
                mime_type=attachment.mime_type,
                file_size_bytes=attachment.file_size_bytes,
            )
            for attachment in attachments
        ],
    )


def generate_communication_draft_for_lead(
    db: Session,
    lead_id: str,
    draft_type: str = "initial",
) -> CrmCommunicationDraftTriggerResponse:
    try:
        lead = db.get(CrmLead, lead_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="CRM lead could not be loaded.",
        ) from exc

    if lead is None:
        raise HTTPException(status_code=404, detail="CRM lead not found.")

    payload = _build_communication_draft_payload(lead, db, draft_type=draft_type)
    outbox = webhook_outbox_service.enqueue(
        db,
        _communication_draft_webhook_url(),
        payload,
        related_object_type="crm_lead",
        related_object_id=lead.id,
        workflow_name="FP_CRM_02_Communication_Draft",
    )
    n8n_response = webhook_outbox_service.sync_attempt(db, outbox)
    _raise_if_draft_generation_failed(n8n_response)

    return CrmCommunicationDraftTriggerResponse(
        lead_id=lead.id,
        draft_type=draft_type,  # type: ignore[arg-type]
        n8n_response=n8n_response,
    )


def _raise_if_draft_generation_failed(n8n_response: object) -> None:
    """Fait remonter un échec de génération IA à l'UI.

    Le workflow CRM_02 répond désormais `{ok: false, error: 'llm_generation_failed'}`
    quand le modèle n'a rien pu rédiger. Sans ce contrôle, l'appel HTTP réussissait
    (2xx) et l'UI affichait un message de succès alors qu'aucun brouillon n'était
    créé — c'est exactement ce qui a masqué le modèle LLM mort pendant des semaines.
    """
    if not isinstance(n8n_response, dict):
        return
    if n8n_response.get("ok") is not False:
        return

    detail = str(
        n8n_response.get("message")
        or n8n_response.get("error")
        or "AI draft generation failed."
    )
    raise HTTPException(
        status_code=502,
        detail=f"La génération IA du brouillon a échoué : {detail}",
    )


def create_lead_interaction(
    db: Session,
    lead_id: str,
    payload: CrmLeadInteractionCreate,
) -> CrmInteractionHistoryItem:
    try:
        lead = db.get(CrmLead, lead_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="CRM lead could not be loaded.",
        ) from exc

    if lead is None:
        raise HTTPException(status_code=404, detail="CRM lead not found.")

    note = payload.note.strip()
    if not note:
        raise HTTPException(status_code=422, detail="Interaction note is required.")

    now = utc_now()
    next_action = _clean_optional_text(payload.next_action)
    follow_up_date = _clean_optional_text(payload.follow_up_date)
    created_by = _resolve_user_id(payload.created_by, db)
    interaction = CrmInteraction(
        id=f"interaction_{uuid4().hex[:8]}",
        lead_id=lead.id,
        interaction_type=payload.interaction_type,
        channel=INTERACTION_CHANNELS.get(payload.interaction_type, "sales"),
        summary=_build_interaction_summary(
            interaction_type=payload.interaction_type,
            outcome=payload.outcome,
            note=note,
            next_action=next_action,
            follow_up_date=follow_up_date,
        ),
        interaction_date=now,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )

    lead.last_contact_at = now
    if next_action is not None:
        lead.next_action = next_action
    if (
        payload.outcome in {"confirmed_interest", "accepted_next_step"}
        and (lead.customer_status or "").lower() == "lead"
    ):
        lead.customer_status = "prospect"
    lead.updated_at = now

    try:
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM interaction could not be saved for lead %s.", lead_id)
        raise HTTPException(
            status_code=500,
            detail="Customer interaction could not be saved.",
        ) from exc

    return _to_interaction_history_item(interaction)


def convert_lead_to_customer(
    db: Session,
    lead_id: str,
    payload: CrmCustomerConversionRequest,
) -> CrmCustomerConversionTriggerResponse:
    _validate_customer_conversion_payload(payload)

    try:
        lead = db.get(CrmLead, lead_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="CRM lead could not be loaded.",
        ) from exc

    if lead is None:
        raise HTTPException(status_code=404, detail="CRM lead not found.")

    current_status = (lead.customer_status or "").strip().lower()
    if _crm_lifecycle_stage(current_status) in CUSTOMER_LIFECYCLE_STAGES:
        raise HTTPException(
            status_code=422,
            detail="Lead is already a customer. Conversion cannot be triggered again.",
        )

    # Snapshot for rollback if the webhook fails. The conversion_pending state
    # MUST be committed BEFORE calling the n8n webhook, otherwise the routing
    # and communication callbacks (which fire while n8n's respondToWebhook is
    # still holding the request) would race with this transaction and see a
    # stale customer_status, then get overwritten when this function commits.
    previous_customer_status = lead.customer_status
    previous_next_action = lead.next_action
    previous_last_contact_at = lead.last_contact_at

    now = utc_now()
    lead.customer_status = CONVERSION_PENDING_STATUS
    lead.next_action = (
        "Conversion in progress — awaiting welcome draft from CRM workflow 03."
    )
    lead.last_contact_at = now
    lead.updated_at = now

    interaction = CrmInteraction(
        id=f"interaction_{uuid4().hex[:8]}",
        lead_id=lead.id,
        interaction_type="customer_conversion",
        channel="sales review",
        summary=_build_conversion_summary(payload),
        interaction_date=now,
        created_by=_resolve_user_id(payload.requested_by, db),
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(interaction)
        db.commit()
        db.refresh(lead)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Customer conversion evidence could not be saved for lead %s.", lead_id)
        raise HTTPException(
            status_code=500,
            detail="Customer conversion evidence could not be saved.",
        ) from exc

    webhook_payload = _build_customer_conversion_payload(lead, payload)
    outbox = webhook_outbox_service.enqueue(
        db,
        _customer_conversion_webhook_url(),
        webhook_payload,
        related_object_type="crm_lead",
        related_object_id=lead.id,
        workflow_name="FP_CRM_03_Human_Conversion_Customer_Welcome",
    )
    try:
        n8n_response = webhook_outbox_service.sync_attempt(db, outbox)
    except HTTPException:
        # n8n is unreachable: revert the lead to its previous state so it does
        # not stay stuck in conversion_pending. Compensation already applied,
        # so mark the outbox dead — letting cron retry would re-fire CRM_03
        # against a reverted lead and re-set conversion_pending in a loop.
        lead.customer_status = previous_customer_status
        lead.next_action = previous_next_action
        lead.last_contact_at = previous_last_contact_at
        lead.updated_at = utc_now()
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception(
                "Failed to revert conversion_pending after webhook failure for lead %s.",
                lead_id,
            )
        webhook_outbox_service.mark_dead(
            db,
            outbox,
            "Conversion reverted; auto-retry disabled to avoid re-firing CRM_03.",
        )
        raise

    return CrmCustomerConversionTriggerResponse(
        lead_id=lead.id,
        message=(
            "Customer conversion workflow triggered. "
            "Lead marked as conversion_pending; status will become customer "
            "once the welcome draft callback succeeds."
        ),
        n8n_response=n8n_response,
    )


def list_inactive_leads(db: Session, threshold_days: int) -> CrmInactiveLeadsResponse:
    threshold_days = max(1, min(threshold_days, 365))
    now = utc_now()
    cutoff = now.timestamp() - threshold_days * 86400

    try:
        statement = (
            select(CrmLead)
            .where(CrmLead.is_active.is_(True))
            .order_by(CrmLead.last_contact_at.asc().nullsfirst())
        )
        leads = list(db.scalars(statement).all())
    except SQLAlchemyError as exc:
        logger.exception("Inactive leads listing failed.")
        raise HTTPException(
            status_code=500,
            detail="Inactive leads could not be loaded.",
        ) from exc

    items: list[CrmInactiveLeadItem] = []
    for lead in leads:
        lifecycle = _crm_lifecycle_stage(lead.customer_status)
        if lifecycle in CUSTOMER_LIFECYCLE_STAGES:
            continue
        if (lead.customer_status or "").strip().lower() == CONVERSION_PENDING_STATUS:
            continue

        reference = lead.last_contact_at or lead.created_at
        if reference is None:
            continue
        if reference.tzinfo is None:
            reference_ts = reference.replace(tzinfo=timezone.utc).timestamp()
        else:
            reference_ts = reference.timestamp()
        if reference_ts > cutoff:
            continue

        days_inactive = max(threshold_days, int((now.timestamp() - reference_ts) // 86400))
        items.append(
            CrmInactiveLeadItem(
                lead_id=lead.id,
                full_name=lead.full_name,
                email=lead.email or "",
                company_name=lead.company_name,
                product_service=lead.product_service,
                customer_status=lead.customer_status,
                priority=lead.priority,
                last_contact_at=lead.last_contact_at,
                days_inactive=days_inactive,
            )
        )

    return CrmInactiveLeadsResponse(
        threshold_days=threshold_days,
        count=len(items),
        items=items,
    )


def get_weekly_crm_stats(db: Session) -> CrmWeeklyStatsResponse:
    now = utc_now()
    period_start_ts = now.timestamp() - 7 * 86400
    period_start = datetime.fromtimestamp(period_start_ts, tz=timezone.utc)

    try:
        all_leads = list(db.scalars(select(CrmLead)).all())
        all_drafts = list(db.scalars(select(CrmEmailDraft)).all())
        all_interactions = list(db.scalars(select(CrmInteraction)).all())
    except SQLAlchemyError as exc:
        logger.exception("Weekly stats query failed.")
        raise HTTPException(
            status_code=500,
            detail="Weekly CRM stats could not be loaded.",
        ) from exc

    def _within_week(value: datetime | None) -> bool:
        if value is None:
            return False
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value >= period_start

    leads_incoming = sum(1 for lead in all_leads if _within_week(lead.created_at))
    leads_qualified = sum(
        1
        for lead in all_leads
        if _within_week(lead.updated_at)
        and _crm_lifecycle_stage(lead.customer_status) == "prospect"
    )
    customers_converted = sum(
        1
        for lead in all_leads
        if _within_week(lead.updated_at)
        and _crm_lifecycle_stage(lead.customer_status) in CUSTOMER_LIFECYCLE_STAGES
    )
    emails_sent = sum(
        1
        for draft in all_drafts
        if _safe_draft_status(draft.status) == "sent" and _within_week(draft.sent_at)
    )
    drafts_pending_review = sum(
        1
        for draft in all_drafts
        if _safe_draft_status(draft.status) in {"draft_generated", "edited", "reviewed"}
    )
    positive_responses = sum(
        1
        for interaction in all_interactions
        if _within_week(interaction.interaction_date)
        and (interaction.summary or "").lower().find("confirmed interest") != -1
    )
    negative_responses = sum(
        1
        for interaction in all_interactions
        if _within_week(interaction.interaction_date)
        and (interaction.summary or "").lower().find("not interested") != -1
    )
    pipeline_open = sum(
        1
        for lead in all_leads
        if _crm_lifecycle_stage(lead.customer_status) == "prospect"
        and (lead.is_active is True)
    )

    if leads_incoming + customers_converted == 0:
        conversion_rate = 0.0
    else:
        denominator = max(1, leads_incoming + customers_converted)
        conversion_rate = round((customers_converted / denominator) * 100.0, 2)

    return CrmWeeklyStatsResponse(
        period_start=period_start,
        period_end=now,
        leads_incoming=leads_incoming,
        leads_qualified_to_prospect=leads_qualified,
        customers_converted=customers_converted,
        emails_sent=emails_sent,
        drafts_pending_review=drafts_pending_review,
        positive_responses=positive_responses,
        negative_responses=negative_responses,
        conversion_rate_percent=conversion_rate,
        pipeline_open_count=pipeline_open,
    )


def _to_crm_lead_list_item(
    lead: CrmLead,
    db: Session,
    drafts: list[CrmEmailDraft] | None = None,
    interactions: list[CrmInteraction] | None = None,
    email_messages: list[CrmEmailMessage] | None = None,
    owner_names_by_id: dict[str, str] | None = None,
) -> CrmLeadListItem:
    return CrmLeadListItem(
        id=lead.id,
        name=lead.full_name,
        company=lead.company_name,
        email=lead.email or "",
        source=lead.source or "",
        customer_status=lead.customer_status,
        status=_safe_status(lead.status),
        score=lead.lead_score,
        phone=lead.phone,
        priority=lead.priority,
        customer_category=lead.customer_category,
        product_service=lead.product_service,
        estimated_value=lead.estimated_value,
        location=lead.location,
        is_active=lead.is_active if lead.is_active is not None else True,
        next_action=lead.next_action,
        sentiment=_safe_sentiment(lead.sentiment),
        urgency=_safe_urgency(lead.urgency),
        assigned_to=_resolve_owner_label(lead.assigned_to, owner_names_by_id, db),
        created_at=lead.created_at,
        last_contact_at=lead.last_contact_at,
        crm_display_state=compute_crm_display_state(
            lead,
            drafts or [],
            interactions or [],
            email_messages or [],
        ),
    )


def compute_crm_display_state(
    lead: CrmLead,
    drafts: list[CrmEmailDraft],
    interactions: list[CrmInteraction],
    email_messages: list[CrmEmailMessage],
) -> CrmDisplayState:
    lifecycle_stage = _crm_lifecycle_stage(lead.customer_status)
    language = _crm_display_language(lead)
    communication_drafts = [
        draft for draft in drafts if _display_draft_type(draft.draft_type) == "communication"
    ]
    welcome_drafts = [
        draft for draft in drafts if _display_draft_type(draft.draft_type) == "welcome"
    ]
    relevant_draft = _latest_draft(welcome_drafts if lifecycle_stage == "customer" else communication_drafts)
    latest_draft_type = _display_draft_type(relevant_draft.draft_type) if relevant_draft else None
    latest_draft_status = _safe_draft_status(relevant_draft.status) if relevant_draft else None
    latest_email_status = _latest_email_status(relevant_draft, email_messages)
    communication_email_sent = any(
        _safe_draft_status(draft.status) == "sent" for draft in communication_drafts
    )
    welcome_email_sent = (
        lifecycle_stage in CUSTOMER_LIFECYCLE_STAGES
        and any(_safe_draft_status(draft.status) == "sent" for draft in welcome_drafts)
    )
    response_state, follow_up_required = _crm_response_state(
        interactions,
        communication_email_sent=communication_email_sent,
    )
    positive_response_recorded = response_state == "positive_response"
    negative_response_recorded = response_state in {"negative_response", "not_interested", "unqualified"}
    neutral_response_recorded = response_state == "neutral_response"
    customer_converted = lifecycle_stage in CUSTOMER_LIFECYCLE_STAGES
    conversion_pending = (
        (lead.customer_status or "").strip().lower() == CONVERSION_PENDING_STATUS
    )
    conversion_ready = (
        lifecycle_stage in {"lead", "prospect"}
        and positive_response_recorded
        and not customer_converted
        and not conversion_pending
    )
    waiting_for_response = (
        communication_email_sent
        and response_state == "waiting_response"
        and lifecycle_stage in {"lead", "prospect"}
    )
    current_state = _crm_current_state(
        lifecycle_stage=lifecycle_stage,
        latest_draft_type=latest_draft_type,
        latest_draft_status=latest_draft_status,
        communication_email_sent=communication_email_sent,
        welcome_email_sent=welcome_email_sent,
        response_state=response_state,
    )
    computed_next_action = _computed_next_action(current_state)
    primary_action = _primary_action_for_state(current_state)
    secondary_actions = _secondary_actions_for_state(
        current_state,
        has_sent_communication=communication_email_sent,
        has_draft=relevant_draft is not None,
    )
    needs_human_review = current_state in {
        "draft_generated",
        "draft_reviewed",
        "welcome_draft_generated",
    }
    needs_human_action = current_state in {
        "draft_generated",
        "draft_reviewed",
        "draft_approved",
        "positive_response_recorded",
        "negative_response_recorded",
        "neutral_response_recorded",
        "follow_up_required",
        "conversion_ready",
        "welcome_draft_generated",
        "welcome_draft_approved",
    }
    warnings = _crm_display_warnings(
        lifecycle_stage=lifecycle_stage,
        communication_email_sent=communication_email_sent,
        positive_response_recorded=positive_response_recorded,
        welcome_email_sent=welcome_email_sent,
    )
    display_stage = _crm_display_stage(
        lifecycle_stage,
        communication_email_sent=communication_email_sent,
        positive_response_recorded=positive_response_recorded,
    )
    ai_insight_text, business_summary_text = _crm_display_texts(current_state, language)

    return CrmDisplayState(
        lifecycle_stage=lifecycle_stage,
        display_stage=display_stage,
        current_state=current_state,
        latest_draft_id=relevant_draft.id if relevant_draft else None,
        latest_draft_type=latest_draft_type,
        latest_draft_status=latest_draft_status,
        response_state=response_state,
        latest_email_status=latest_email_status,
        communication_email_sent=communication_email_sent,
        welcome_email_sent=welcome_email_sent,
        waiting_for_response=waiting_for_response,
        positive_response_recorded=positive_response_recorded,
        negative_response_recorded=negative_response_recorded,
        neutral_response_recorded=neutral_response_recorded,
        follow_up_required=follow_up_required,
        conversion_ready=conversion_ready,
        conversion_pending=conversion_pending,
        customer_converted=customer_converted,
        needs_human_review=needs_human_review,
        needs_human_action=needs_human_action,
        primary_action=primary_action,
        secondary_actions=secondary_actions,
        computed_next_action=computed_next_action,
        ai_insight_text=ai_insight_text,
        business_summary_text=business_summary_text,
        language=language,
        warnings=warnings,
    )


def _crm_lifecycle_stage(customer_status: str | None) -> str:
    normalized_status = (customer_status or "").strip().lower()

    # conversion_pending is an in-flight state between prospect and customer:
    # the lifecycle stays "prospect" so the lead does not appear as a customer
    # until the welcome workflow callback confirms the transition.
    if normalized_status == CONVERSION_PENDING_STATUS:
        return "prospect"
    if "vip" in normalized_status:
        return "vip_customer"
    if "loyal" in normalized_status:
        return "loyal_customer"
    if "inactive" in normalized_status and "customer" in normalized_status:
        return "inactive_customer"
    if "active" in normalized_status and "customer" in normalized_status:
        return "active_customer"
    if "customer" in normalized_status:
        return "customer"
    if "prospect" in normalized_status:
        return "prospect"

    return "lead"


def _crm_display_language(lead: CrmLead) -> str:
    text = " ".join(
        value or ""
        for value in [
            lead.message,
            lead.ai_summary,
            lead.recommended_action,
        ]
    ).lower()

    return "fr" if any(signal in text for signal in FRENCH_CRM_SIGNALS) else "en"


def _display_draft_type(draft_type: str | None) -> str | None:
    normalized_type = (draft_type or "").strip().lower()

    if normalized_type == "welcome":
        return "welcome"
    if normalized_type in {"sales", "communication"}:
        return "communication"

    return None


def _latest_draft(drafts: list[CrmEmailDraft]) -> CrmEmailDraft | None:
    if not drafts:
        return None

    return max(drafts, key=lambda draft: draft.updated_at or draft.created_at)


def _latest_email_status(
    latest_draft: CrmEmailDraft | None,
    email_messages: list[CrmEmailMessage],
) -> str:
    if latest_draft is not None:
        draft_status = _safe_draft_status(latest_draft.status)
        if draft_status in {"sending", "sent", "failed"}:
            return draft_status

    if not email_messages:
        return "none"

    latest_message = max(
        email_messages,
        key=lambda message: message.sent_at or message.created_at,
    )
    message_status = (latest_message.status or "").strip().lower()

    if message_status in {"sending", "sent", "failed"}:
        return message_status

    return "none"


def _crm_current_state(
    *,
    lifecycle_stage: str,
    latest_draft_type: str | None,
    latest_draft_status: str | None,
    communication_email_sent: bool,
    welcome_email_sent: bool,
    response_state: str,
) -> str:
    if lifecycle_stage in CUSTOMER_LIFECYCLE_STAGES:
        if welcome_email_sent:
            return "welcome_email_sent"
        if latest_draft_type == "welcome" and latest_draft_status == "approved":
            return "welcome_draft_approved"
        if latest_draft_type == "welcome" and latest_draft_status in {
            "draft_generated",
            "edited",
            "reviewed",
        }:
            return "welcome_draft_generated"

        return "customer_converted"

    if response_state == "positive_response":
        return "positive_response_recorded"
    if response_state in {"negative_response", "not_interested", "unqualified"}:
        return "negative_response_recorded"
    if response_state == "neutral_response":
        return "neutral_response_recorded"
    if response_state == "follow_up_required":
        return "follow_up_required"
    if communication_email_sent:
        return "email_sent_waiting_response"
    if latest_draft_status == "failed":
        return "failed"
    if latest_draft_status == "sending":
        return "email_sending"
    if latest_draft_status == "approved":
        return "draft_approved"
    if latest_draft_status == "reviewed":
        return "draft_reviewed"
    if latest_draft_status in {"draft_generated", "edited", "generated"}:
        return "draft_generated"
    if lifecycle_stage == "prospect":
        return "draft_missing"

    return "lead_analyzed"


def _computed_next_action(current_state: str) -> str:
    return {
        "lead_collected": "Review AI recommendation and qualify the lead",
        "lead_analyzed": "Review AI recommendation and qualify the lead",
        "prospect_qualified": "Generate first communication draft",
        "draft_missing": "Generate first communication draft",
        "draft_generated": "Review communication draft",
        "draft_reviewed": "Approve or reject reviewed draft",
        "draft_approved": "Send approved email",
        "email_sending": "Wait for email sending result",
        "email_sent_waiting_response": "Wait for response or record the result",
        "positive_response_recorded": "Review conversion evidence",
        "negative_response_recorded": "Schedule follow-up or mark as not interested",
        "neutral_response_recorded": "Prepare follow-up response",
        "follow_up_required": "Schedule follow-up",
        "conversion_ready": "Review conversion evidence",
        "customer_converted": "Prepare onboarding and welcome communication",
        "welcome_draft_generated": "Review welcome communication draft",
        "welcome_draft_approved": "Send approved welcome email",
        "welcome_email_sent": "No urgent welcome action",
        "failed": "Retry sending workflow",
    }.get(current_state, "Review CRM status")


def _primary_action_for_state(current_state: str) -> str:
    return {
        "lead_collected": "Review Lead",
        "lead_analyzed": "Review Lead",
        "prospect_qualified": "Generate Communication Draft",
        "draft_missing": "Generate Communication Draft",
        "draft_generated": "View Draft",
        "draft_reviewed": "Approve Draft",
        "draft_approved": "Send Approved Email",
        "email_sending": "View Draft",
        "email_sent_waiting_response": "Record Response",
        "positive_response_recorded": "Confirm as Customer",
        "negative_response_recorded": "Schedule Follow-up",
        "neutral_response_recorded": "Prepare Follow-up",
        "follow_up_required": "Log Interaction",
        "conversion_ready": "Confirm as Customer",
        "customer_converted": "Review Welcome Communication",
        "welcome_draft_generated": "View Welcome Draft",
        "welcome_draft_approved": "Send Welcome Email",
        "welcome_email_sent": "View Sent Welcome Email",
        "failed": "Retry Sending Workflow",
    }.get(current_state, "Review Lead")


def _secondary_actions_for_state(
    current_state: str,
    *,
    has_sent_communication: bool,
    has_draft: bool,
) -> list[str]:
    if current_state == "email_sent_waiting_response":
        return ["View Sent Email", "Log Interaction"]
    if current_state in {"positive_response_recorded", "conversion_ready"}:
        actions = ["Record Another Response", "View Activity"]
        if has_sent_communication:
            actions.insert(0, "View Sent Email")
        return actions
    if current_state in {"negative_response_recorded", "neutral_response_recorded", "follow_up_required"}:
        actions = ["Record Another Response", "View Activity"]
        if has_sent_communication:
            actions.insert(0, "View Sent Email")
        return actions
    if current_state in {"draft_generated", "draft_reviewed", "draft_approved", "email_sending", "failed"}:
        return ["View Draft", "Log Interaction"] if has_draft else ["Log Interaction"]
    if current_state in {"welcome_draft_generated", "welcome_draft_approved"}:
        return ["View Draft", "View Activity"]
    if current_state == "welcome_email_sent":
        return ["View Activity"]

    return ["Log Interaction", "View Activity"]


def _crm_display_stage(
    lifecycle_stage: str,
    *,
    communication_email_sent: bool,
    positive_response_recorded: bool,
) -> str:
    if lifecycle_stage == "lead" and (communication_email_sent or positive_response_recorded):
        return "Prospect"

    return {
        "lead": "Lead",
        "prospect": "Prospect",
        "customer": "Customer",
        "active_customer": "Active Customer",
        "inactive_customer": "Inactive Customer",
        "loyal_customer": "Loyal Customer",
        "vip_customer": "VIP Customer",
    }.get(lifecycle_stage, "Lead")


def _crm_display_warnings(
    *,
    lifecycle_stage: str,
    communication_email_sent: bool,
    positive_response_recorded: bool,
    welcome_email_sent: bool,
) -> list[str]:
    warnings: list[str] = []

    if lifecycle_stage == "lead" and communication_email_sent:
        warnings.append(
            "Persisted customer_status is lead, but a communication email has already been sent.",
        )
    if lifecycle_stage == "lead" and positive_response_recorded:
        warnings.append(
            "Persisted customer_status is lead, but positive response evidence was recorded.",
        )
    if lifecycle_stage not in CUSTOMER_LIFECYCLE_STAGES and welcome_email_sent:
        warnings.append(
            "Welcome email state was ignored because the record is not in the customer lifecycle.",
        )

    return warnings


def _has_positive_response_evidence(interactions: list[CrmInteraction]) -> bool:
    return any(_is_positive_response_interaction(interaction) for interaction in interactions)


def _crm_response_state(
    interactions: list[CrmInteraction],
    *,
    communication_email_sent: bool,
) -> tuple[str, bool]:
    response_interactions = [
        interaction
        for interaction in interactions
        if (interaction.interaction_type or "").strip().lower() in RESPONSE_INTERACTION_TYPES
    ]
    sorted_interactions = sorted(
        response_interactions,
        key=lambda interaction: interaction.interaction_date or interaction.created_at,
        reverse=True,
    )

    for interaction in sorted_interactions:
        response_state = _classify_response_interaction(interaction)
        follow_up_required = _interaction_requires_follow_up(interaction)

        if response_state != "unknown":
            return response_state, follow_up_required
        if follow_up_required:
            return "follow_up_required", True

    if communication_email_sent:
        return "waiting_response", False

    return "none", False


def _classify_response_interaction(interaction: CrmInteraction) -> str:
    summary = interaction.summary or ""
    outcome = _extract_labeled_value(summary, "outcome").lower()
    normalized_summary = summary.lower()

    if _contains_signal(outcome, POSITIVE_RESPONSE_SIGNALS) or _contains_signal(
        normalized_summary,
        POSITIVE_RESPONSE_SIGNALS,
    ):
        return "positive_response"
    if "not_interested" in outcome or "not interested" in outcome:
        return "not_interested"
    if _contains_signal(outcome, NEGATIVE_RESPONSE_SIGNALS) or _contains_signal(
        normalized_summary,
        NEGATIVE_RESPONSE_SIGNALS,
    ):
        return "negative_response"
    if _contains_signal(outcome, NEUTRAL_RESPONSE_SIGNALS) or _contains_signal(
        normalized_summary,
        NEUTRAL_RESPONSE_SIGNALS,
    ):
        return "neutral_response"

    return "unknown"


def _contains_signal(text: str, signals: set[str]) -> bool:
    return any(signal in text for signal in signals)


def _interaction_requires_follow_up(interaction: CrmInteraction) -> bool:
    summary = interaction.summary or ""
    follow_up_date = _extract_labeled_value(summary, "follow-up date")
    next_action = _extract_labeled_value(summary, "next action").lower()
    normalized_summary = summary.lower()

    return bool(
        follow_up_date
        or _contains_signal(next_action, FOLLOW_UP_SIGNALS)
        or _contains_signal(normalized_summary, FOLLOW_UP_SIGNALS)
    )


def _is_positive_response_interaction(interaction: CrmInteraction) -> bool:
    interaction_type = (interaction.interaction_type or "").strip().lower()
    if interaction_type not in RESPONSE_INTERACTION_TYPES:
        return False

    summary = interaction.summary or ""
    outcome = _extract_labeled_value(summary, "outcome").lower()
    normalized_summary = summary.lower()

    return any(
        signal in outcome or signal in normalized_summary
        for signal in POSITIVE_RESPONSE_SIGNALS
    )


def _extract_labeled_value(summary: str, label: str) -> str:
    label_pattern = re.escape(label)
    known_labels = "interaction|outcome|next action|follow-up date|note|status|subject|body"
    inline_match = re.search(
        rf"(?:^|\s){label_pattern}\s*:\s*([\s\S]*?)(?=\s+(?:{known_labels})\s*:|$)",
        summary,
        flags=re.IGNORECASE,
    )

    if inline_match and inline_match.group(1):
        return inline_match.group(1).strip()

    label_prefix = f"{label.lower()}:"
    for line in summary.splitlines():
        stripped_line = line.strip()
        if stripped_line.lower().startswith(label_prefix):
            return stripped_line.split(":", 1)[1].strip()

    return ""


def _crm_display_texts(current_state: str, language: str) -> tuple[str, str]:
    if language == "fr":
        return _crm_display_texts_fr(current_state)

    return _crm_display_texts_en(current_state)


def _crm_display_texts_fr(current_state: str) -> tuple[str, str]:
    texts = {
        "email_sent_waiting_response": (
            "L'email commercial a été envoyé. La prochaine étape consiste à surveiller la réponse du prospect et à enregistrer le résultat dans le CRM.",
            "Ce prospect est en attente de réponse. L'email commercial a été envoyé et l'équipe doit surveiller la réponse, enregistrer le résultat dans le CRM ou planifier une relance.",
        ),
        "positive_response_recorded": (
            "Une réponse positive a été enregistrée. Le prospect a confirmé son intérêt et accepte d'avancer vers une prochaine étape commerciale. La prochaine décision consiste à valider la conversion en client si les preuves sont suffisantes.",
            "Le prospect a confirmé son intérêt après l'email commercial. L'équipe doit maintenant vérifier les éléments de preuve, planifier la prochaine étape commerciale et décider si le prospect peut être converti en client.",
        ),
        "negative_response_recorded": (
            "Une réponse négative a été enregistrée. Le prospect n'a pas exprimé d'intérêt immédiat.",
            "Le prospect n'est pas intéressé pour le moment. L'équipe doit décider s'il faut planifier une relance, conserver le contact en suivi ou le marquer comme non qualifié.",
        ),
        "neutral_response_recorded": (
            "Une réponse a été enregistrée, mais elle ne suffit pas encore pour confirmer une conversion.",
            "Le prospect a répondu, mais l'opportunité nécessite encore une clarification avant décision commerciale.",
        ),
        "follow_up_required": (
            "Une relance est nécessaire. La prochaine étape consiste à planifier un suivi clair.",
            "Le prospect nécessite une relance ou une clarification avant la prochaine décision commerciale.",
        ),
        "draft_generated": (
            "Un brouillon de communication a été généré. La prochaine étape consiste à le relire, l'ajuster si nécessaire, puis l'approuver avant tout envoi.",
            "Ce prospect dispose d'un brouillon de communication prêt pour validation humaine. Aucun email ne doit être envoyé avant approbation.",
        ),
        "lead_analyzed": (
            "L'IA a analysé le lead. La prochaine étape consiste à vérifier la recommandation et décider s'il doit être qualifié comme prospect.",
            "Ce lead a été collecté et analysé. Il doit être vérifié avant d'être traité comme une opportunité commerciale.",
        ),
        "draft_missing": (
            "Le prospect est qualifié. La prochaine étape consiste à préparer une première communication commerciale.",
            "Ce prospect est prêt pour un suivi commercial et attend un brouillon de communication.",
        ),
        "draft_reviewed": (
            "Le brouillon de communication a été relu. La prochaine étape consiste à l'approuver ou à le rejeter.",
            "Un brouillon relu attend une décision humaine avant envoi.",
        ),
        "draft_approved": (
            "Le brouillon de communication est approuvé. La prochaine étape consiste à lancer l'envoi automatisé.",
            "L'email commercial est prêt à être envoyé via le workflow automatisé.",
        ),
        "email_sending": (
            "L'email approuvé est en cours d'envoi par le workflow automatisé.",
            "Le workflow d'envoi est en cours. L'équipe doit attendre le résultat avant toute action suivante.",
        ),
        "failed": (
            "Le workflow d'envoi a échoué. Vérifiez le suivi d'automatisation ou relancez l'envoi après correction.",
            "Une erreur d'envoi bloque la prochaine étape commerciale.",
        ),
        "customer_converted": (
            "Le prospect a été converti en client après validation humaine. La prochaine étape consiste à préparer l'accueil client.",
            "Ce client vient d'être converti. L'équipe doit préparer l'onboarding et la communication de bienvenue.",
        ),
        "welcome_draft_generated": (
            "Un brouillon de bienvenue a été généré pour ce client. Il doit être relu avant tout envoi.",
            "Le client dispose d'une communication de bienvenue prête pour validation humaine.",
        ),
        "welcome_draft_approved": (
            "Le brouillon de bienvenue est approuvé. La prochaine étape consiste à envoyer l'email de bienvenue.",
            "La communication de bienvenue est prête pour envoi automatisé.",
        ),
        "welcome_email_sent": (
            "L'email de bienvenue a été envoyé. Aucune action urgente de bienvenue n'est requise.",
            "Le client a reçu l'email de bienvenue. L'équipe peut poursuivre l'onboarding.",
        ),
    }

    return texts.get(current_state, texts["lead_analyzed"])


def _crm_display_texts_en(current_state: str) -> tuple[str, str]:
    texts = {
        "email_sent_waiting_response": (
            "The communication email was sent. The next step is to monitor the prospect response and record the result in the CRM.",
            "This prospect is waiting for a response. The commercial email was sent, and the team should monitor the reply, record the result in CRM, or schedule a follow-up.",
        ),
        "positive_response_recorded": (
            "A positive response was recorded. The prospect confirmed interest and is ready for a next commercial step. The next decision is to validate the evidence and decide whether to convert the prospect to customer.",
            "The prospect confirmed interest after the commercial email. The team should now review the evidence, plan the next commercial step, and decide whether this prospect can be converted to customer.",
        ),
        "negative_response_recorded": (
            "A negative response was recorded. The prospect has not expressed immediate interest.",
            "The prospect is not interested for now. The team should decide whether to schedule a follow-up, keep the contact in monitoring, or mark it as not qualified.",
        ),
        "neutral_response_recorded": (
            "A response was recorded, but it is not enough yet to confirm a conversion.",
            "The prospect replied, but the opportunity still needs clarification before a commercial decision.",
        ),
        "follow_up_required": (
            "A follow-up is required. The next step is to plan a clear follow-up action.",
            "This prospect requires follow-up or clarification before the next commercial decision.",
        ),
        "draft_generated": (
            "A communication draft has been generated. The next step is to review it, adjust it if needed, and approve it before any email is sent.",
            "This prospect has a communication draft ready for human validation. No email should be sent before approval.",
        ),
        "lead_analyzed": (
            "AI analyzed the lead. The next step is to review the recommendation and decide whether the lead should be qualified as a prospect.",
            "This lead has been collected and analyzed. It should be reviewed before it is treated as a commercial opportunity.",
        ),
        "draft_missing": (
            "This prospect is qualified. The next step is to prepare the first commercial communication.",
            "This prospect is ready for commercial follow-up and is waiting for a communication draft.",
        ),
        "draft_reviewed": (
            "The communication draft has been reviewed. The next step is to approve it or reject it for revision.",
            "A reviewed draft is waiting for a human decision before sending.",
        ),
        "draft_approved": (
            "The communication draft is approved. The next step is to start the automated sending workflow.",
            "The commercial email is ready to be sent through automation.",
        ),
        "email_sending": (
            "The approved email is being processed by the automated sending workflow.",
            "Email sending is in progress. The team should wait for the workflow result before taking the next step.",
        ),
        "failed": (
            "The sending workflow failed. Check workflow monitoring or retry after correction.",
            "An email sending issue is blocking the next commercial step.",
        ),
        "customer_converted": (
            "The prospect was converted to customer after human validation. The next step is to prepare onboarding and welcome communication.",
            "This customer was just converted. The team should prepare onboarding and welcome communication.",
        ),
        "welcome_draft_generated": (
            "A welcome draft was generated for this customer. It should be reviewed before sending.",
            "This customer has a welcome communication ready for human validation.",
        ),
        "welcome_draft_approved": (
            "The welcome draft is approved. The next step is to send the welcome email.",
            "The welcome communication is ready for automated sending.",
        ),
        "welcome_email_sent": (
            "The welcome email was sent. No urgent welcome action is required.",
            "The customer received the welcome email. The team can continue onboarding.",
        ),
    }

    return texts.get(current_state, texts["lead_analyzed"])


def _to_crm_lead_detail(
    lead: CrmLead,
    interactions: list[CrmInteraction],
    db: Session,
    drafts: list[CrmEmailDraft] | None = None,
    email_messages: list[CrmEmailMessage] | None = None,
) -> CrmLeadDetail:
    interaction_history = [
        _to_interaction_history_item(interaction)
        for interaction in interactions
    ]

    return CrmLeadDetail(
        id=lead.id,
        name=lead.full_name,
        company=lead.company_name,
        email=lead.email or "",
        phone=lead.phone or "",
        source=lead.source or "",
        customer_status=lead.customer_status,
        status=_safe_status(lead.status),
        score=lead.lead_score,
        priority=lead.priority,
        customer_category=lead.customer_category,
        product_service=lead.product_service,
        estimated_value=lead.estimated_value,
        location=lead.location,
        is_active=lead.is_active if lead.is_active is not None else True,
        next_action=lead.next_action,
        sentiment=_safe_sentiment(lead.sentiment),
        intention=lead.intention or "not-classified",
        urgency=_safe_urgency(lead.urgency),
        message=lead.message or "",
        ai_summary=lead.ai_summary or "AI summary not generated yet.",
        recommended_action=lead.recommended_action or "Review lead and choose next action.",
        assigned_to=_assigned_to_label(lead.assigned_to, db),
        created_at=lead.created_at,
        last_contact_at=lead.last_contact_at,
        notes=lead.notes,
        ml_score=lead.ml_score,
        ml_probability=lead.ml_probability,
        ml_category=lead.ml_category,
        ml_confidence=lead.ml_confidence,
        shap_explanation=lead.shap_explanation,
        drafts=[
            draft
            for interaction in interactions
            if (draft := _to_lead_draft(interaction)) is not None
        ],
        interaction_history=interaction_history,
        crm_display_state=compute_crm_display_state(
            lead,
            drafts or [],
            interactions,
            email_messages or [],
        ),
    )


def _to_interaction_history_item(
    interaction: CrmInteraction,
) -> CrmInteractionHistoryItem:
    draft_type = _draft_type(interaction)

    return CrmInteractionHistoryItem(
        id=interaction.id,
        interaction_type=interaction.interaction_type,
        channel=interaction.channel,
        summary=interaction.summary,
        interaction_date=interaction.interaction_date,
        created_by=interaction.created_by,
        created_at=interaction.created_at,
        business_label=_interaction_business_label(interaction),
        draft_subject=_draft_subject(interaction.summary, draft_type),
        draft_body=_draft_body(interaction.summary) if draft_type is not None else None,
        draft_status=_draft_status(interaction.summary, interaction.interaction_type),
        draft_type=draft_type,
    )


def _to_lead_draft(interaction: CrmInteraction) -> CrmLeadDraft | None:
    draft_type = _draft_type(interaction)
    if draft_type is None:
        return None

    return CrmLeadDraft(
        draft_type="welcome" if draft_type == "welcome" else "sales",
        subject=_draft_subject(interaction.summary, draft_type),
        body=_draft_body(interaction.summary),
        status=_draft_status(interaction.summary, interaction.interaction_type),
        generated_at=interaction.interaction_date,
        summary=interaction.summary,
        channel=interaction.channel,
    )


def _to_email_draft_item(
    draft: CrmEmailDraft,
    attachments: list[CrmEmailAttachment],
    user_names_by_id: dict[str, str] | None = None,
) -> CrmEmailDraftItem:
    def _resolve(user_id: str | None) -> str | None:
        if not user_id or user_names_by_id is None:
            return None
        return user_names_by_id.get(user_id)

    return CrmEmailDraftItem(
        id=draft.id,
        lead_id=draft.lead_id,
        draft_type=_safe_draft_type(draft.draft_type),
        subject=draft.subject,
        body=draft.body,
        status=_safe_draft_status(draft.status),
        tone=draft.tone,
        cta=draft.cta,
        generated_by_agent=draft.generated_by_agent,
        rejection_reason=draft.rejection_reason,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        reviewed_at=draft.reviewed_at,
        approved_at=draft.approved_at,
        rejected_at=draft.rejected_at,
        sent_at=draft.sent_at,
        edited_by=draft.edited_by,
        edited_by_name=_resolve(draft.edited_by),
        reviewed_by=draft.reviewed_by,
        reviewed_by_name=_resolve(draft.reviewed_by),
        approved_by=draft.approved_by,
        approved_by_name=_resolve(draft.approved_by),
        rejected_by=draft.rejected_by,
        rejected_by_name=_resolve(draft.rejected_by),
        attachments=[_to_email_attachment_item(attachment) for attachment in attachments],
    )


def _user_names_for_drafts(
    db: Session,
    drafts: list[CrmEmailDraft],
) -> dict[str, str]:
    """Bulk-load full_name for every actor referenced by a list of drafts."""
    actor_ids: set[str] = set()
    for draft in drafts:
        for actor_id in (
            draft.edited_by,
            draft.reviewed_by,
            draft.approved_by,
            draft.rejected_by,
        ):
            if actor_id:
                actor_ids.add(actor_id)
    if not actor_ids:
        return {}
    rows = db.execute(
        select(User.id, User.full_name).where(User.id.in_(actor_ids))
    ).all()
    return {row[0]: row[1] for row in rows}


def _to_email_attachment_item(attachment: CrmEmailAttachment) -> CrmEmailAttachmentItem:
    return CrmEmailAttachmentItem(
        id=attachment.id,
        draft_id=attachment.draft_id,
        file_name=attachment.file_name,
        mime_type=attachment.mime_type,
        file_size_bytes=attachment.file_size_bytes,
        uploaded_by=attachment.uploaded_by,
        created_at=attachment.created_at,
    )


def _attachments_by_draft_id(
    db: Session,
    draft_ids: list[str],
) -> dict[str, list[CrmEmailAttachment]]:
    if not draft_ids:
        return {}

    attachments = list(
        db.scalars(
            select(CrmEmailAttachment)
            .where(CrmEmailAttachment.draft_id.in_(draft_ids))
            .order_by(CrmEmailAttachment.created_at.asc())
        ).all()
    )
    grouped_attachments: dict[str, list[CrmEmailAttachment]] = {}

    for attachment in attachments:
        grouped_attachments.setdefault(attachment.draft_id, []).append(attachment)

    return grouped_attachments


def _email_drafts_by_lead_id(
    db: Session,
    lead_ids: list[str],
) -> dict[str, list[CrmEmailDraft]]:
    if not lead_ids:
        return {}

    drafts = list(
        db.scalars(
            select(CrmEmailDraft)
            .where(CrmEmailDraft.lead_id.in_(lead_ids))
            .order_by(CrmEmailDraft.updated_at.desc())
        ).all()
    )
    grouped_drafts: dict[str, list[CrmEmailDraft]] = {}

    for draft in drafts:
        grouped_drafts.setdefault(draft.lead_id, []).append(draft)

    return grouped_drafts


def _interactions_by_lead_id(
    db: Session,
    lead_ids: list[str],
) -> dict[str, list[CrmInteraction]]:
    if not lead_ids:
        return {}

    interactions = list(
        db.scalars(
            select(CrmInteraction)
            .where(CrmInteraction.lead_id.in_(lead_ids))
            .order_by(CrmInteraction.interaction_date.desc())
        ).all()
    )
    grouped_interactions: dict[str, list[CrmInteraction]] = {}

    for interaction in interactions:
        grouped_interactions.setdefault(interaction.lead_id, []).append(interaction)

    return grouped_interactions


def _email_messages_by_lead_id(
    db: Session,
    lead_ids: list[str],
) -> dict[str, list[CrmEmailMessage]]:
    if not lead_ids:
        return {}

    messages = list(
        db.scalars(
            select(CrmEmailMessage)
            .where(CrmEmailMessage.lead_id.in_(lead_ids))
            .order_by(CrmEmailMessage.created_at.desc())
        ).all()
    )
    grouped_messages: dict[str, list[CrmEmailMessage]] = {}

    for message in messages:
        grouped_messages.setdefault(message.lead_id, []).append(message)

    return grouped_messages


def _assigned_to_label(assigned_to: str | None, db: Session) -> str:
    if assigned_to is None:
        return "Unassigned"

    user = db.get(User, assigned_to)

    if user is None:
        return assigned_to

    return user.full_name


def _owner_full_names_for_leads(
    db: Session,
    leads: list[CrmLead],
) -> dict[str, str]:
    """Bulk-load owner full names for every lead in one query.

    Eliminates the N+1 that used to happen when _to_crm_lead_list_item ran a
    db.get(User, ...) per row during list rendering.
    """
    owner_ids = {lead.assigned_to for lead in leads if lead.assigned_to}
    if not owner_ids:
        return {}

    rows = db.execute(
        select(User.id, User.full_name).where(User.id.in_(owner_ids))
    ).all()
    return {row[0]: row[1] for row in rows}


def _resolve_owner_label(
    assigned_to: str | None,
    owner_map: dict[str, str] | None,
    db: Session,
) -> str:
    if assigned_to is None:
        return "Unassigned"
    if owner_map is not None:
        return owner_map.get(assigned_to, assigned_to)
    return _assigned_to_label(assigned_to, db)


def _safe_status(status: str | None) -> str:
    if status in {"new", "hot", "warm", "cold"}:
        return status

    return "new"


def _safe_sentiment(sentiment: str | None) -> str:
    if sentiment in {"positive", "neutral", "negative"}:
        return sentiment

    return "neutral"


def _safe_urgency(urgency: str | None) -> str:
    if urgency in {"low", "medium", "high"}:
        return urgency

    return "low"


def _safe_draft_type(draft_type: str | None) -> str:
    if draft_type in DRAFT_TYPES:
        return draft_type

    return "sales"


def _safe_draft_status(status: str | None) -> str:
    if status in DRAFT_STATUSES:
        return status

    return "draft_generated"


def _interaction_business_label(interaction: CrmInteraction) -> str:
    interaction_type = interaction.interaction_type
    summary = interaction.summary.lower()

    if interaction_type in INTERACTION_TYPE_LABELS:
        return INTERACTION_TYPE_LABELS[interaction_type]
    if interaction_type == "email_sent":
        return "Email sent"
    if interaction_type == "email_failed":
        return "Email sending failed"
    if interaction_type == "customer_conversion":
        return "Customer converted"
    if interaction_type == "draft_lifecycle":
        if "approved" in summary:
            return "Draft approved"
        if "reviewed" in summary:
            return "Draft reviewed"
        if "rejected" in summary:
            return "Draft rejected"
        if "edited" in summary:
            return "Draft edited"
        return "Draft updated"
    if interaction_type == "lead_collected":
        return "Lead collected"
    if interaction_type == "ai_analysis":
        return "AI analysis completed"
    if interaction_type == "scoring_completed":
        return "Lead scored"
    if interaction_type == "routing_decision" and _contains_any(
        summary,
        [
            "customer converted",
            "converted to customer",
            "converted by human validation",
            "prospect converted",
        ],
    ):
        return "Customer converted"
    if interaction_type == "routing_decision":
        return "Routing decision made"
    if interaction_type == "communication_draft" and _is_welcome_summary(summary):
        return "Welcome draft generated"
    if interaction_type == "communication_draft":
        return "Communication draft generated"
    if interaction_type == "communication_result":
        return "Communication reviewed"

    return "CRM activity recorded"


def _draft_type(interaction: CrmInteraction) -> str | None:
    if interaction.interaction_type != "communication_draft":
        return None

    if _is_welcome_summary(interaction.summary.lower()):
        return "welcome"

    return "communication"


def _draft_subject(summary: str, draft_type: str | None) -> str | None:
    if draft_type is None:
        return None

    subject = _extract_labeled_value(summary, "subject")
    if subject:
        return subject

    first_line = summary.strip().splitlines()[0] if summary.strip() else ""
    if first_line.lower().startswith("draft communication:"):
        return first_line.split(":", 1)[1].strip() or "Communication draft"

    return "Welcome communication draft" if draft_type == "welcome" else "Communication draft"


def _draft_body(summary: str) -> str | None:
    body = _extract_labeled_block(summary, "body")

    return body or summary


def _draft_status(summary: str, interaction_type: str) -> str | None:
    if interaction_type != "communication_draft":
        return None

    status = _extract_labeled_value(summary, "status")
    return status or "draft"


def _extract_labeled_block(summary: str, label: str) -> str | None:
    lines = summary.splitlines()
    label_prefix = f"{label.lower()}:"

    for index, line in enumerate(lines):
        if line.strip().lower().startswith(label_prefix):
            first_line_value = line.split(":", 1)[1].strip()
            remaining_lines = [first_line_value] if first_line_value else []
            remaining_lines.extend(lines[index + 1 :])
            value = "\n".join(remaining_lines).strip()
            return value or None

    return None


def _contains_any(value: str, phrases: list[str]) -> bool:
    return any(phrase in value for phrase in phrases)


def _is_welcome_summary(summary: str) -> bool:
    return _contains_any(
        summary,
        [
            "welcome",
            "bienvenue",
            "customer conversion",
            "after customer conversion",
        ],
    )


def _to_title_case_name(value: str | None) -> str | None:
    """Capitalise chaque mot d'un nom (ex. "atef ben hadef" -> "Atef Ben Hadef").

    Le nom du lead arrive parfois en minuscules ; on le normalise avant de
    l'envoyer au workflow n8n CRM_02 pour que l'IA l'emploie tel quel.
    """
    if not value:
        return value
    return re.sub(
        r"(^|[\s'-])(\w)",
        lambda match: match.group(1) + match.group(2).upper(),
        value.lower(),
    )


# Métadonnées par type de génération, exploitées par le workflow n8n CRM_02 pour
# adapter le prompt LLM. 'initial' garde le comportement historique (email de vente).
COMMUNICATION_DRAFT_PURPOSES: dict[str, dict[str, str]] = {
    "initial": {
        "email_purpose": "Premier email commercial de prise de contact",
        "response_context": "first_touch",
        "instruction": (
            "Rédige un premier email commercial personnalisé qui présente notre "
            "offre à partir du besoin exprimé par le prospect."
        ),
    },
    "follow_up": {
        "email_purpose": "Relance après absence de réponse au premier email",
        "response_context": "no_response",
        "instruction": (
            "Le prospect n'a pas répondu à notre premier email. Rédige une relance "
            "courtoise et concise qui rappelle le message précédent, apporte un "
            "élément de valeur supplémentaire et propose un prochain pas simple. "
            "Ne réécris pas le premier email à l'identique."
        ),
    },
    "reactivation": {
        "email_purpose": "Réactivation d'un lead ayant décliné",
        "response_context": "not_interested",
        "instruction": (
            "Le prospect s'était montré non intéressé. Rédige un email de "
            "réactivation à faible pression qui reprend contact sous un angle "
            "nouveau (nouveauté, cas d'usage, offre) sans insister sur le refus."
        ),
    },
    "information": {
        "email_purpose": "Email d'information / clarification demandée",
        "response_context": "requested_more_information",
        "instruction": (
            "Le prospect a demandé plus d'informations. Rédige un email de "
            "clarification qui répond précisément à sa demande et lève les "
            "objections potentielles, en s'appuyant sur l'échange précédent."
        ),
    },
}


def _latest_communication_draft(db: Session, lead_id: str) -> CrmEmailDraft | None:
    """Dernier brouillon de communication (email de vente) pour un lead, en
    privilégiant un email réellement envoyé, sinon le plus récent. Sert de
    référence pour les relances afin que n8n ne reparte pas du message initial."""
    try:
        drafts = list(
            db.scalars(
                select(CrmEmailDraft).where(CrmEmailDraft.lead_id == lead_id)
            ).all()
        )
    except SQLAlchemyError:
        logger.exception("Previous communication draft could not be loaded for lead %s.", lead_id)
        return None

    communication = [
        d for d in drafts if _display_draft_type(d.draft_type) == "communication"
    ]
    if not communication:
        return None

    sent = [d for d in communication if _safe_draft_status(d.status) == "sent"]
    pool = sent or communication
    return max(pool, key=lambda d: d.sent_at or d.updated_at or d.created_at)


def _build_communication_draft_payload(
    lead: CrmLead,
    db: Session,
    draft_type: str = "initial",
) -> dict[str, object | None]:
    # Nom complet du commercial assigné, normalisé, pour la signature de l'email
    # généré par le workflow CRM_02. Chaîne vide si le lead n'est pas assigné.
    assigned_user = db.get(User, lead.assigned_to) if lead.assigned_to else None
    assigned_to_name = (
        _to_title_case_name(assigned_user.full_name)
        if assigned_user and assigned_user.full_name
        else ""
    )
    normalized_type = draft_type if draft_type in COMMUNICATION_DRAFT_PURPOSES else "initial"
    purpose = COMMUNICATION_DRAFT_PURPOSES[normalized_type]

    payload: dict[str, object | None] = {
        "lead_id": lead.id,
        "draft_type": normalized_type,
        "is_follow_up": normalized_type != "initial",
        "email_purpose": purpose["email_purpose"],
        "response_context": purpose["response_context"],
        "generation_instruction": purpose["instruction"],
        "full_name": _to_title_case_name(lead.full_name),
        "assigned_to_name": assigned_to_name,
        "email": lead.email,
        "phone": lead.phone,
        "company_name": lead.company_name,
        "source": lead.source,
        "message": lead.message,
        "product_service": lead.product_service,
        "intention": lead.intention,
        "urgency": lead.urgency,
        "priority": lead.priority,
        "ai_summary": lead.ai_summary,
        "recommended_action": lead.recommended_action,
        "requested_by": DEFAULT_CRM_OWNER_ID,
        # Champs de contexte "email précédent" : null pour un premier email.
        "previous_email_subject": None,
        "previous_email_body": None,
        "previous_email_sent_at": None,
    }

    # Pour toute génération autre que l'email initial, on joint le contenu du
    # dernier email de communication afin que le workflow rédige une VRAIE suite
    # (relance / réactivation / clarification) plutôt que de recopier le message
    # initial du lead.
    if normalized_type != "initial":
        previous = _latest_communication_draft(db, lead.id)
        if previous is not None:
            payload["previous_email_subject"] = previous.subject
            payload["previous_email_body"] = previous.body
            payload["previous_email_sent_at"] = (
                previous.sent_at.isoformat() if previous.sent_at else None
            )

    return payload


def _build_customer_conversion_payload(
    lead: CrmLead,
    payload: CrmCustomerConversionRequest,
) -> dict[str, str | bool | int | float | None]:
    return {
        "lead_id": lead.id,
        "full_name": lead.full_name,
        "email": lead.email,
        "phone": lead.phone,
        "company_name": lead.company_name,
        "customer_status": lead.customer_status or "prospect",
        "new_customer_status": "customer",
        "conversion_status": "converted",
        "human_validated": True,
        "validation_reason": payload.validation_reason.strip(),
        "evidence_source": payload.evidence_source.strip(),
        "validated_by": payload.requested_by or DEFAULT_CRM_OWNER_ID,
        "requested_by": payload.requested_by or DEFAULT_CRM_OWNER_ID,
        "product_service": lead.product_service,
        "estimated_value": float(lead.estimated_value) if lead.estimated_value is not None else None,
        "priority": lead.priority,
        "source": "crm_ui",
        "customer_category": lead.customer_category or "new",
        "conversion_note": payload.conversion_note.strip(),
        "next_action": payload.next_action.strip(),
        "send_welcome_email": False,
    }


def _build_interaction_summary(
    interaction_type: str,
    outcome: str,
    note: str,
    next_action: str | None,
    follow_up_date: str | None,
) -> str:
    lines = [
        f"Interaction: {INTERACTION_TYPE_LABELS.get(interaction_type, 'Customer interaction')}",
        f"Outcome: {OUTCOME_LABELS.get(outcome, format_business_label(outcome))}",
    ]

    if next_action:
        lines.append(f"Next action: {next_action}")
    if follow_up_date:
        lines.append(f"Follow-up date: {follow_up_date}")

    lines.append(f"Note: {note}")
    return "\n".join(lines)


def _build_conversion_summary(payload: CrmCustomerConversionRequest) -> str:
    return "\n".join(
        [
            "Customer converted after human review.",
            f"Validation reason: {payload.validation_reason.strip()}",
            f"Evidence source: {payload.evidence_source.strip()}",
            f"Next action: {payload.next_action.strip()}",
            f"Conversion note: {payload.conversion_note.strip()}",
        ]
    )


def _validate_customer_conversion_payload(payload: CrmCustomerConversionRequest) -> None:
    if payload.human_validated is not True:
        raise HTTPException(
            status_code=422,
            detail="Human validation is required before customer conversion.",
        )

    required_fields = {
        "validation_reason": payload.validation_reason,
        "evidence_source": payload.evidence_source,
        "next_action": payload.next_action,
        "conversion_note": payload.conversion_note,
    }
    missing_fields = [
        field_name
        for field_name, value in required_fields.items()
        if not value or not value.strip()
    ]

    if missing_fields:
        raise HTTPException(
            status_code=422,
            detail="Conversion reason, evidence, next action, and note are required.",
        )


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    stripped_value = value.strip()
    return stripped_value or None


def _resolve_user_id(user_id: str | None, db: Session) -> str | None:
    if user_id and db.get(User, user_id) is not None:
        return user_id

    if db.get(User, DEFAULT_CRM_OWNER_ID) is not None:
        return DEFAULT_CRM_OWNER_ID

    return None


def _get_required_lead_for_email_draft(db: Session, lead_id: str) -> CrmLead:
    try:
        lead = db.get(CrmLead, lead_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="CRM lead could not be loaded.",
        ) from exc

    if lead is None:
        raise HTTPException(status_code=404, detail="CRM lead not found.")

    return lead


def _get_required_email_draft(db: Session, draft_id: str) -> CrmEmailDraft:
    try:
        draft = db.get(CrmEmailDraft, draft_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="CRM email draft could not be loaded.",
        ) from exc

    if draft is None:
        raise HTTPException(status_code=404, detail="CRM email draft not found.")

    return draft


def _get_required_email_attachment(
    db: Session,
    draft_id: str,
    attachment_id: str,
) -> CrmEmailAttachment:
    try:
        attachment = db.get(CrmEmailAttachment, attachment_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="CRM email attachment could not be loaded.",
        ) from exc

    if attachment is None or attachment.draft_id != draft_id:
        raise HTTPException(status_code=404, detail="CRM email attachment not found.")

    return attachment


def _commit_email_draft(
    db: Session,
    draft: CrmEmailDraft,
    failure_detail: str,
) -> CrmEmailDraftItem:
    try:
        db.commit()
        db.refresh(draft)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=failure_detail) from exc

    attachments = _attachments_by_draft_id(db, [draft.id])
    user_names = _user_names_for_drafts(db, [draft])
    return _to_email_draft_item(draft, attachments.get(draft.id, []), user_names)


def _commit_email_draft_with_activity(
    db: Session,
    draft: CrmEmailDraft,
    summary: str,
    next_action: str,
    failure_detail: str,
    actor_user_id: str | None = None,
) -> CrmEmailDraftItem:
    now = utc_now()
    lead = db.get(CrmLead, draft.lead_id)

    if lead is not None:
        lead.next_action = next_action
        lead.updated_at = now

    db.add(
        CrmInteraction(
            id=f"interaction_{uuid4().hex[:8]}",
            lead_id=draft.lead_id,
            interaction_type="draft_lifecycle",
            channel="sales review",
            summary=summary,
            interaction_date=now,
            created_by=_resolve_user_id(actor_user_id, db),
            created_at=now,
            updated_at=now,
        )
    )

    return _commit_email_draft(db, draft, failure_detail)


def _safe_file_name(file_name: str) -> str:
    normalized_name = Path(file_name).name
    normalized_name = re.sub(r"[^A-Za-z0-9._ -]", "_", normalized_name).strip(" .")

    return normalized_name or "attachment"


def _delete_file_if_safe(file_path: Path) -> None:
    try:
        resolved_upload_root = UPLOAD_ROOT.resolve()
        resolved_file_path = file_path.resolve()
    except OSError:
        return

    if resolved_upload_root not in resolved_file_path.parents:
        return

    try:
        resolved_file_path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Attachment file could not be deleted: %s", resolved_file_path)
        return

    try:
        if resolved_file_path.parent != resolved_upload_root:
            resolved_file_path.parent.rmdir()
    except OSError:
        return


def _mark_email_send_trigger_failed(
    db: Session,
    draft_id: str,
    workflow_execution_id: str,
) -> None:
    now = utc_now()

    try:
        draft = db.get(CrmEmailDraft, draft_id)
        if draft is not None:
            draft.status = "failed"
            draft.updated_at = now
            lead = db.get(CrmLead, draft.lead_id)
            if lead is not None:
                lead.next_action = "Check failed email sending workflow"
                lead.updated_at = now

        workflow_execution = db.get(WorkflowExecution, workflow_execution_id)
        if workflow_execution is not None:
            workflow_execution.status = "failed"
            workflow_execution.finished_at = now
            workflow_execution.error_message = "Approved email sending workflow could not be triggered."
            workflow_execution.result_summary = "Approved email sending workflow failed to start."
            if workflow_execution.started_at is not None:
                workflow_execution.duration_seconds = _duration_seconds(
                    workflow_execution.started_at,
                    now,
                )
            workflow_execution.updated_at = now

        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Email sending trigger failure state could not be saved.")


def _generate_trace_id(prefix: str, now: datetime) -> str:
    return f"{prefix}_{int(now.timestamp())}_{uuid4().hex[:8]}"


def log_crm_workflow_error(
    payload: CrmWorkflowErrorLogPayload,
    db: Session,
) -> CrmWorkflowErrorLogResponse:
    now = utc_now()

    raw_payload_summary: str | None = None
    if payload.raw_payload is not None:
        try:
            raw_payload_summary = json.dumps(payload.raw_payload, default=str)[:4000]
        except (TypeError, ValueError):
            raw_payload_summary = str(payload.raw_payload)[:4000]

    error_message = payload.error_message or "Unknown workflow error reported by n8n."
    if payload.failed_node:
        error_message = f"[{payload.failed_node}] {error_message}"

    workflow_execution = WorkflowExecution(
        id=_generate_trace_id("exec_crm_error", now),
        related_object_type=payload.related_object_type,
        related_object_id=payload.related_object_id,
        workflow_name=payload.workflow_name[:160],
        process=payload.process or "CRM",
        trigger_source=(payload.trigger_source or "n8n_error_trigger")[:120],
        status="failed",
        started_at=now,
        finished_at=now,
        duration_seconds=0,
        error_message=error_message[:8000],
        result_summary=f"Workflow error captured by CRM_00 Error Handler "
        f"(execution_id={payload.execution_id or 'n/a'}).",
        input_summary=(payload.input_summary or raw_payload_summary or "")[:4000] or None,
        output_summary=None,
        agent_name="CRM Error Handler",
        created_at=now,
        updated_at=now,
    )
    db.add(workflow_execution)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to persist CRM workflow error log.")
        raise HTTPException(
            status_code=500,
            detail="Could not persist workflow error log.",
        )

    logger.warning(
        "CRM workflow error captured: workflow=%s execution_id=%s message=%s",
        payload.workflow_name,
        payload.execution_id,
        error_message[:500],
    )

    return CrmWorkflowErrorLogResponse(
        workflow_execution_id=workflow_execution.id,
        logged_at=now,
    )


def record_crm_workflow_trace(
    payload: CrmWorkflowTracePayload,
    db: Session,
) -> CrmWorkflowTraceResponse:
    """Persist a workflow_executions row for ANY status (success/failed).

    Unlike log_crm_workflow_error which is hardcoded to status='failed', this
    endpoint lets cron-style workflows (CRM_08 weekly report, etc.) record a
    success trace too. Without it, successful runs leave no audit trail.
    """
    if payload.status == "failed" and not (payload.error_message or "").strip():
        raise HTTPException(
            status_code=422,
            detail="error_message is required when status is failed.",
        )

    now = utc_now()
    summary = (payload.summary or "").strip() or None
    error_message = (payload.error_message or "").strip() or None

    workflow_execution = WorkflowExecution(
        id=_generate_trace_id("exec_crm_trace", now),
        related_object_type=payload.related_object_type,
        related_object_id=payload.related_object_id,
        workflow_name=payload.workflow_name[:160],
        process=(payload.process or "CRM")[:120],
        trigger_source=(payload.trigger_source or "n8n_workflow_trace")[:120],
        status=payload.status,
        started_at=now,
        finished_at=now,
        duration_seconds=0,
        error_message=error_message[:8000] if error_message else None,
        result_summary=(
            summary
            or (
                f"Workflow {payload.status} captured "
                f"(execution_id={payload.execution_id or 'n/a'})."
            )
        )[:4000],
        input_summary=None,
        output_summary=summary[:4000] if summary else None,
        agent_name="CRM Workflow Trace",
        created_at=now,
        updated_at=now,
    )
    db.add(workflow_execution)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to persist CRM workflow trace.")
        raise HTTPException(
            status_code=500,
            detail="Could not persist workflow trace.",
        ) from exc

    log_method = logger.info if payload.status == "success" else logger.warning
    log_method(
        "CRM workflow trace: workflow=%s status=%s execution_id=%s",
        payload.workflow_name,
        payload.status,
        payload.execution_id,
    )

    return CrmWorkflowTraceResponse(
        workflow_execution_id=workflow_execution.id,
        logged_at=now,
        status=payload.status,
    )


def _duration_seconds(started_at: datetime, finished_at: datetime) -> int:
    if started_at.tzinfo is None and finished_at.tzinfo is not None:
        finished_at = finished_at.replace(tzinfo=None)
    elif started_at.tzinfo is not None and finished_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=None)

    return max(0, int((finished_at - started_at).total_seconds()))


def format_business_label(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _communication_draft_webhook_url() -> str:
    return (
        f"{settings.N8N_WEBHOOK_BASE_URL.rstrip('/')}/"
        f"{COMMUNICATION_DRAFT_WEBHOOK_PATH}"
    )


def _customer_conversion_webhook_url() -> str:
    return (
        f"{settings.N8N_WEBHOOK_BASE_URL.rstrip('/')}/"
        f"{CUSTOMER_CONVERSION_WEBHOOK_PATH}"
    )


def _approved_email_send_webhook_url() -> str:
    return (
        f"{settings.N8N_WEBHOOK_BASE_URL.rstrip('/')}/"
        f"{APPROVED_EMAIL_SEND_WEBHOOK_PATH}"
    )


def _public_lead_intake_webhook_url() -> str:
    return (
        f"{settings.N8N_WEBHOOK_BASE_URL.rstrip('/')}/"
        f"{PUBLIC_LEAD_INTAKE_WEBHOOK_PATH}"
    )


def submit_public_lead(
    payload: PublicCrmLeadIntake,
    db: Session,
) -> PublicCrmLeadIntakeResponse:
    """Server-side relay for the public website form.

    Adds the X-FlowPilot-Secret header (held only by the backend) before
    forwarding to CRM_01, so the browser never carries the secret. The lead
    is enqueued in webhook_outbox first — even if n8n is momentarily down,
    the cron drain (FP_CRM_99_Outbox_Drain) will retry.
    """
    # Honeypot: bots fill every field. A legit human never touches the hidden
    # 'website' input. Silently accept (so bots can't tell they were detected)
    # and skip persisting / forwarding anything.
    if payload.website and payload.website.strip():
        logger.warning(
            "Public lead form honeypot triggered (email=%s, ip=server-side).",
            payload.email,
        )
        return PublicCrmLeadIntakeResponse(
            accepted=True,
            message="Demande reçue.",
        )

    if not payload.consent_to_contact:
        raise HTTPException(
            status_code=422,
            detail="Le consentement de contact est requis.",
        )

    email = payload.email.strip().lower()
    if not PUBLIC_EMAIL_REGEX.match(email):
        raise HTTPException(
            status_code=422,
            detail="Email invalide.",
        )

    webhook_payload = {
        "full_name": payload.full_name.strip(),
        "email": email,
        "phone": (payload.phone or "").strip(),
        "company_name": (payload.company_name or "").strip(),
        "location": (payload.location or "").strip(),
        "product_service": (payload.product_service or "").strip(),
        "source": (payload.source or "website_form").strip(),
        "message": payload.message.strip(),
        "consent_to_contact": True,
        "requested_by": (payload.requested_by or "website_visitor").strip(),
    }

    outbox = webhook_outbox_service.enqueue(
        db,
        _public_lead_intake_webhook_url(),
        webhook_payload,
        related_object_type="public_lead_form",
        related_object_id=None,
        workflow_name=PUBLIC_LEAD_INTAKE_WORKFLOW_NAME,
    )
    try:
        webhook_outbox_service.sync_attempt(db, outbox)
    except HTTPException:
        # Best-effort: the cron drain will retry. We must NOT surface the
        # failure to the public form — the lead is durably enqueued and the
        # user shouldn't see internal infrastructure errors.
        logger.warning(
            "Public lead enqueue: sync attempt failed; outbox %s will retry asynchronously.",
            outbox.id,
        )

    return PublicCrmLeadIntakeResponse(
        accepted=True,
        message="Demande reçue. Notre équipe vous contacte sous 24h.",
    )


