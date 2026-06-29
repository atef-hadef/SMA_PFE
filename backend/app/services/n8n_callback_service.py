from datetime import datetime, timedelta, timezone
import logging
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    AgentRun,
    CrmEmailDraft,
    CrmEmailMessage,
    CrmInteraction,
    CrmLead,
    CrmTask,
    User,
    WorkflowExecution,
)
from app.schemas.n8n_callbacks import (
    AgentRunCallbackPayload,
    CrmAnalysisResultPayload,
    CrmCollectResultPayload,
    CrmCommunicationResultPayload,
    CrmEmailSentResultPayload,
    CrmRoutingResultPayload,
    CrmScoringResultPayload,
    N8nCallbackResult,
    WorkflowCallbackPayload,
)
from app.services.crm_service import _assign_lead_round_robin

DEFAULT_CRM_OWNER_ID = "user_030"
APPROVED_EMAIL_WORKFLOW_NAME = "FP CRM 04 - Approved Email Sending"
CONVERSION_PENDING_STATUS = "conversion_pending"
CUSTOMER_LIFECYCLE_TIERS = {
    "customer",
    "active_customer",
    "inactive_customer",
    "loyal_customer",
    "vip_customer",
}
SAFE_COMMUNICATION_INTERACTION_TYPES = {
    "communication_draft",
    "communication_result",
}
logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _score_lead_with_ml(lead: CrmLead, db: Session) -> dict | None:
    """
    Score le lead avec le modèle ML et stocke le résultat (ml_score + SHAP).

    Server-side : déclenché après le scoring LLM (handle_scoring_result), quand
    sentiment/urgence/intention/lead_score sont déjà renseignés. Ne bloque JAMAIS
    le process CRM — toute erreur (modèle absent, lib manquante…) est avalée.
    Le score LLM (lead_score) reste intact ; on ajoute ml_* en parallèle.

    Retourne le dict de scoring (pour enrichir la réponse callback) ou None.
    """
    try:
        from app.services.ml_scoring_service import MLScoringService

        service = MLScoringService.get_instance()
        if not service._model_available:
            return None

        # Attributs IA réels déjà calculés par le LLM (interaction_count omis -> neutre)
        known: dict = {}
        if lead.sentiment:
            known["sentiment"] = lead.sentiment
        if lead.urgency:
            known["urgency"] = lead.urgency
        if lead.intention:
            known["intention"] = lead.intention
        if lead.estimated_value is not None:
            known["estimated_value"] = float(lead.estimated_value)
        if lead.product_service:
            known["product_service"] = lead.product_service
        if lead.location:
            known["location"] = lead.location

        result = service.score_lead(
            lead_id=lead.id,
            message=lead.message or "",
            phone=lead.phone,
            company=lead.company_name,
            email=lead.email,
            source=lead.source or "website_form",
            created_at=lead.created_at,
            llm_score=lead.lead_score,
            known=known,
        )

        lead.ml_score = result["ml_score"]
        lead.ml_probability = result["ml_probability"]
        lead.ml_category = result["ml_category"]
        lead.ml_confidence = result["ml_confidence"]
        lead.shap_explanation = {
            "explanation_text": result["explanation_text"],
            "top_factors": result["top_factors"],
            "model_version": result["model_version"],
            "delta": result["delta"],
            "scored_at": utc_now().isoformat(),
        }
        db.add(lead)
        db.commit()
        return result
    except Exception as exc:  # noqa: BLE001 — ne jamais bloquer le process CRM si le ML échoue
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        logger.warning("ML scoring failed for %s: %s", getattr(lead, "id", "?"), exc)
        return None


def handle_collect_result(
    payload: CrmCollectResultPayload,
    db: Session,
) -> N8nCallbackResult:
    now = utc_now()
    lead = _get_or_create_lead(payload, now, db)

    try:
        db.add(lead)
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM collect-result callback failed while saving lead data.")
        raise HTTPException(
            status_code=500,
            detail="CRM collection callback could not be saved.",
        ) from exc

    interaction = _build_interaction(
        lead_id=lead.id,
        interaction_type="lead_collected",
        summary=payload.message or "Lead collected from n8n CRM workflow.",
        channel=payload.source,
        interaction_date=now,
    )

    try:
        db.add(interaction)
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception(
            "CRM collect-result callback failed while saving interaction data.",
        )
        raise HTTPException(
            status_code=500,
            detail="CRM collection callback could not be saved.",
        ) from exc

    workflow_execution_id, agent_run_id = _persist_callback_traces_safely(
        workflow_payload=_get_workflow_payload(payload),
        agent_run_payload=payload.agent_run,
        lead_id=lead.id,
        now=now,
        db=db,
    )

    try:
        db.commit()
        db.refresh(lead)
        db.refresh(interaction)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM collect-result callback failed while committing data.")
        raise HTTPException(
            status_code=500,
            detail="CRM collection callback could not be saved.",
        ) from exc

    assigned_user = db.get(User, lead.assigned_to) if lead.assigned_to else None
    return _callback_result(
        lead_id=lead.id,
        interaction_id=interaction.id,
        status=lead.status,
        workflow_execution_id=workflow_execution_id,
        agent_run_id=agent_run_id,
        assigned_user=assigned_user,
    )


def handle_analysis_result(
    payload: CrmAnalysisResultPayload,
    db: Session,
) -> N8nCallbackResult:
    lead = _get_required_lead(payload.lead_id, db)
    now = utc_now()

    if payload.sentiment is not None:
        lead.sentiment = payload.sentiment
    if payload.intention is not None:
        lead.intention = payload.intention
    if payload.urgency is not None:
        lead.urgency = payload.urgency
    if payload.ai_summary is not None:
        lead.ai_summary = payload.ai_summary

    lead.updated_at = now
    interaction = _build_interaction(
        lead_id=lead.id,
        interaction_type="ai_analysis",
        summary=payload.ai_summary or "AI analysis completed.",
        channel="n8n",
        interaction_date=now,
    )

    return _commit_lead_and_interaction(
        lead=lead,
        interaction=interaction,
        status=lead.status,
        workflow_payload=payload.workflow_execution,
        agent_run_payload=payload.agent_run,
        db=db,
        failure_detail="CRM analysis callback could not be saved.",
    )


def handle_scoring_result(
    payload: CrmScoringResultPayload,
    db: Session,
) -> N8nCallbackResult:
    lead = _get_required_lead(payload.lead_id, db)
    now = utc_now()

    if payload.lead_score is not None:
        lead.lead_score = payload.lead_score
    if payload.status is not None:
        lead.status = payload.status
    if payload.priority is not None:
        lead.priority = payload.priority

    lead.updated_at = now
    interaction = _build_interaction(
        lead_id=lead.id,
        interaction_type="scoring_completed",
        summary=f"Lead scoring completed with score {lead.lead_score}.",
        channel="n8n",
        interaction_date=now,
    )

    callback_result = _commit_lead_and_interaction(
        lead=lead,
        interaction=interaction,
        status=lead.status,
        workflow_payload=payload.workflow_execution,
        agent_run_payload=payload.agent_run,
        db=db,
        failure_detail="CRM scoring callback could not be saved.",
    )

    # Scoring ML automatique (server-side) une fois le score LLM persisté.
    # Silencieux en cas d'échec : ne bloque jamais le callback CRM.
    ml = _score_lead_with_ml(lead, db)
    if ml:
        callback_result.ml_score = ml["ml_score"]
        callback_result.ml_category = ml["ml_category"]
        callback_result.ml_confidence = ml["ml_confidence"]
        callback_result.ml_delta = ml["delta"]
        callback_result.ml_explanation = ml["explanation_text"]
        callback_result.ml_top_factors = ml["top_factors"]

    return callback_result


def handle_routing_result(
    payload: CrmRoutingResultPayload,
    db: Session,
) -> N8nCallbackResult:
    lead = _get_required_lead(payload.lead_id, db)
    now = utc_now()

    if payload.recommended_action is not None:
        lead.recommended_action = payload.recommended_action
    if payload.next_action is not None:
        lead.next_action = payload.next_action
    if payload.customer_status is not None:
        current_status = (lead.customer_status or "").strip().lower()
        incoming_status = payload.customer_status.strip().lower()
        # Safety: do NOT let the routing callback prematurely promote a lead
        # to "customer" while it is still in conversion_pending. The customer
        # transition is owned by handle_communication_result and only fires
        # once the welcome draft is actually persisted in the database.
        if not (
            current_status == CONVERSION_PENDING_STATUS
            and incoming_status in CUSTOMER_LIFECYCLE_TIERS
        ):
            lead.customer_status = payload.customer_status
    if payload.last_contact_at is not None:
        lead.last_contact_at = payload.last_contact_at

    # Apply AI-driven routing: only honor assigned_to / owner_user_id if the
    # target user exists in DB and is active. Silently ignore otherwise so a
    # bad payload from n8n cannot orphan the lead to an inactive owner.
    incoming_owner = payload.assigned_to or payload.owner_user_id
    if incoming_owner:
        candidate = db.get(User, incoming_owner)
        if candidate is not None and (candidate.status or "").strip().lower() == "active":
            lead.assigned_to = candidate.id
            lead.owner_user_id = candidate.id
        else:
            logger.warning(
                "Routing payload requested assigned_to=%s but user is missing or inactive; keeping previous owner %s.",
                incoming_owner,
                lead.assigned_to,
            )

    lead.updated_at = now
    routing_summary = payload.recommended_action or "CRM routing decision completed."
    if payload.assignment_reason:
        routing_summary = f"{routing_summary} Assignment reason: {payload.assignment_reason}"
    interaction = _build_interaction(
        lead_id=lead.id,
        interaction_type="routing_decision",
        summary=routing_summary,
        channel="n8n",
        interaction_date=now,
    )

    return _commit_lead_and_interaction(
        lead=lead,
        interaction=interaction,
        status=lead.status,
        workflow_payload=payload.workflow_execution,
        agent_run_payload=payload.agent_run,
        db=db,
        failure_detail="CRM routing callback could not be saved.",
    )


def handle_communication_result(
    payload: CrmCommunicationResultPayload,
    db: Session,
) -> N8nCallbackResult:
    lead = _get_required_lead(payload.lead_id, db)
    now = utc_now()

    if payload.next_action is not None:
        lead.next_action = payload.next_action
    if payload.sent or payload.status == "sent":
        lead.last_contact_at = now

    lead.updated_at = now
    interaction = _build_interaction(
        lead_id=lead.id,
        interaction_type=_communication_interaction_type(payload),
        summary=_communication_summary(payload),
        channel=_communication_channel(payload),
        interaction_date=now,
    )

    # Idempotent draft handling: if a pending draft of the same type already
    # exists for this lead, update it in place instead of creating a duplicate.
    # This prevents the user from accumulating multiple identical drafts when
    # "Generate draft" is clicked twice or when n8n retries the workflow.
    new_subject = _communication_subject(payload)
    new_body = _communication_body(payload)
    draft_persisted = False
    draft_type = _communication_draft_type(payload)
    if new_subject or new_body:
        existing_pending = _find_pending_draft(db, lead.id, draft_type)

        if existing_pending is not None:
            existing_pending.deal_id = payload.deal_id or existing_pending.deal_id
            existing_pending.subject = new_subject or existing_pending.subject or "Untitled draft"
            existing_pending.body = new_body or existing_pending.body or "No draft body available."
            existing_pending.tone = payload.tone or existing_pending.tone
            existing_pending.cta = payload.cta or existing_pending.cta
            existing_pending.generated_by_agent = (
                _communication_agent_name(payload) or existing_pending.generated_by_agent
            )
            existing_pending.status = "draft_generated"
            existing_pending.updated_at = now
        else:
            db.add(_build_email_draft_from_payload(payload, now))
        draft_persisted = True

    # Finalize the conversion only when the welcome draft is actually available:
    # the lead must transition from conversion_pending to customer only after
    # n8n successfully produced the welcome content. If the workflow fails or
    # returns no draft, the lead stays in conversion_pending and can be retried.
    if (
        draft_persisted
        and draft_type == "welcome"
        and (lead.customer_status or "").strip().lower() == CONVERSION_PENDING_STATUS
    ):
        lead.customer_status = "customer"

    return _commit_lead_and_interaction(
        lead=lead,
        interaction=interaction,
        status=lead.status,
        workflow_payload=payload.workflow_execution,
        agent_run_payload=payload.agent_run,
        db=db,
        failure_detail="CRM communication callback could not be saved.",
    )


def _find_pending_draft(
    db: Session,
    lead_id: str,
    draft_type: str,
) -> CrmEmailDraft | None:
    return db.execute(
        select(CrmEmailDraft)
        .where(
            CrmEmailDraft.lead_id == lead_id,
            CrmEmailDraft.draft_type == draft_type,
            CrmEmailDraft.status.in_(("draft_generated", "edited")),
        )
        .order_by(CrmEmailDraft.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def handle_email_sent_result(
    payload: CrmEmailSentResultPayload,
    db: Session,
) -> N8nCallbackResult:
    draft = _get_required_email_draft(payload.draft_id, db)
    lead = _get_required_lead(payload.lead_id, db)

    if draft.lead_id != lead.id:
        raise HTTPException(
            status_code=422,
            detail="Email sending result does not match the CRM lead.",
        )

    now = utc_now()
    send_mode = (payload.send_mode or "test").strip().lower()
    provider = (payload.provider or ("gmail" if send_mode == "real" else "test_mode")).strip()
    sent_at = payload.sent_at or now
    workflow_execution = _latest_email_send_workflow_execution(draft.id, db)
    message_status = payload.status
    error_message = payload.error_message.strip() if payload.error_message else None

    draft.status = "sent" if message_status == "sent" else "failed"
    draft.updated_at = now
    if message_status == "sent":
        draft.sent_at = sent_at
        lead.last_contact_at = sent_at
        lead.next_action = (
            "Welcome email sent. Continue customer onboarding."
            if draft.draft_type == "welcome"
            else "Email sent. Wait for prospect response or schedule follow-up."
        )
        interaction_type = "email_sent"
        if send_mode == "real":
            interaction_summary = (
                "Approved email sent through the automated CRM email workflow. "
                f"Subject: {draft.subject or 'Untitled draft'}"
            )
            workflow_result_summary = "Approved email sent through Gmail"
        else:
            interaction_summary = (
                "Approved email recorded through the test email workflow. "
                f"Subject: {draft.subject or 'Untitled draft'}"
            )
            workflow_result_summary = "Approved email recorded in test mode"
        workflow_status = "success"
    else:
        lead.next_action = "Check failed email sending workflow"
        interaction_type = "email_failed"
        interaction_summary = (
            "Approved email sending workflow failed."
            f" Reason: {error_message or 'No error message was provided.'}"
        )
        workflow_result_summary = "Approved email sending workflow failed"
        workflow_status = "failed"

    lead.updated_at = now
    interaction = _build_interaction(
        lead_id=lead.id,
        interaction_type=interaction_type,
        summary=interaction_summary,
        channel="email",
        interaction_date=sent_at if message_status == "sent" else now,
    )
    email_message = CrmEmailMessage(
        id=f"email_msg_{uuid4().hex[:8]}",
        draft_id=draft.id,
        lead_id=lead.id,
        to_email=lead.email or "",
        subject=draft.subject,
        body=draft.body,
        status=message_status,
        send_mode=send_mode,
        provider=provider,
        provider_message_id=payload.provider_message_id,
        error_message=error_message,
        sent_at=sent_at if message_status == "sent" else None,
        created_at=now,
    )

    if workflow_execution is not None:
        workflow_execution.status = workflow_status
        workflow_execution.finished_at = now
        workflow_execution.result_summary = workflow_result_summary
        workflow_execution.output_summary = interaction_summary
        workflow_execution.error_message = error_message
        if workflow_execution.started_at is not None:
            workflow_execution.duration_seconds = _duration_seconds(
                workflow_execution.started_at,
                now,
            )
        workflow_execution.updated_at = now

    # Auto-create a follow-up task once a real commercial email was actually
    # sent. Skipped for welcome drafts (onboarding flow, not a reply-watch) and
    # for failures (no reply to wait for). Idempotent via task_type=='follow_up'
    # + status=='pending' guard: a second email send won't pile up duplicates.
    if message_status == "sent" and draft.draft_type != "welcome":
        existing_followup = db.execute(
            select(CrmTask)
            .where(
                CrmTask.lead_id == lead.id,
                CrmTask.task_type == "follow_up",
                CrmTask.status == "pending",
            )
            .limit(1)
        ).scalar_one_or_none()

        if existing_followup is None:
            owner_id = (
                lead.assigned_to or lead.owner_user_id or DEFAULT_CRM_OWNER_ID
            )
            auto_task = CrmTask(
                id=f"task_{uuid4().hex[:8]}",
                lead_id=lead.id,
                owner_user_id=owner_id,
                title=f"Suivi — réponse attendue de {lead.full_name}",
                description=(
                    "Email envoyé — aucune réponse reçue. "
                    "Relancer si pas de retour sous 3 jours."
                ),
                due_date=now + timedelta(days=3),
                status="pending",
                priority="medium",
                task_type="follow_up",
                created_by=DEFAULT_CRM_OWNER_ID,
                created_at=now,
                updated_at=now,
            )
            db.add(auto_task)
            logger.info(
                "Auto-task follow_up created for lead %s after email send.",
                lead.id,
            )

    try:
        db.add(interaction)
        db.add(email_message)
        db.commit()
        db.refresh(interaction)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM email sending callback could not be saved.")
        raise HTTPException(
            status_code=500,
            detail="CRM email sending result could not be saved.",
        ) from exc

    return _callback_result(
        lead_id=lead.id,
        interaction_id=interaction.id,
        status=draft.status,
        workflow_execution_id=workflow_execution.id if workflow_execution else None,
        agent_run_id=None,
    )


def _get_or_create_lead(
    payload: CrmCollectResultPayload,
    now: datetime,
    db: Session,
) -> CrmLead:
    try:
        lead = db.get(CrmLead, payload.lead_id) if payload.lead_id else None
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="CRM lead could not be loaded.",
        ) from exc

    if lead is None:
        assigned_owner = _assign_lead_round_robin(db) or DEFAULT_CRM_OWNER_ID
        lead = CrmLead(
            id=payload.lead_id or f"lead_{uuid4().hex[:8]}",
            full_name=payload.full_name,
            company_name=payload.company_name or payload.full_name,
            email=payload.email,
            phone=payload.phone,
            source=payload.source,
            status="new",
            customer_status="lead",
            lead_score=0,
            message=payload.message,
            location=payload.location,
            product_service=payload.product_service,
            estimated_value=payload.estimated_value,
            notes=payload.notes,
            owner_user_id=assigned_owner,
            assigned_to=assigned_owner,
            created_at=now,
            updated_at=now,
        )
        return lead

    lead.full_name = payload.full_name
    if payload.company_name is not None:
        lead.company_name = payload.company_name
    lead.email = payload.email
    if payload.phone is not None:
        lead.phone = payload.phone
    if payload.source is not None:
        lead.source = payload.source
    if payload.message is not None:
        lead.message = payload.message
    if payload.location is not None:
        lead.location = payload.location
    if payload.product_service is not None:
        lead.product_service = payload.product_service
    if payload.estimated_value is not None:
        lead.estimated_value = payload.estimated_value
    if payload.notes is not None:
        lead.notes = payload.notes
    lead.updated_at = now
    return lead


def _get_required_lead(lead_id: str, db: Session) -> CrmLead:
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


def _get_required_email_draft(draft_id: str, db: Session) -> CrmEmailDraft:
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


def _latest_email_send_workflow_execution(
    draft_id: str,
    db: Session,
) -> WorkflowExecution | None:
    try:
        return db.scalars(
            select(WorkflowExecution)
            .where(WorkflowExecution.related_object_type == "crm_email_draft")
            .where(WorkflowExecution.related_object_id == draft_id)
            .where(WorkflowExecution.workflow_name == APPROVED_EMAIL_WORKFLOW_NAME)
            .order_by(WorkflowExecution.started_at.desc(), WorkflowExecution.created_at.desc())
        ).first()
    except SQLAlchemyError:
        logger.exception("Email sending workflow execution could not be loaded.")
        return None


def _build_interaction(
    lead_id: str,
    interaction_type: str,
    summary: str,
    channel: str | None,
    interaction_date: datetime,
) -> CrmInteraction:
    return CrmInteraction(
        id=f"interaction_{uuid4().hex[:8]}",
        lead_id=lead_id,
        interaction_type=interaction_type,
        channel=channel,
        summary=summary,
        interaction_date=interaction_date,
        created_by=None,
        created_at=interaction_date,
        updated_at=interaction_date,
    )


def _create_workflow_execution_if_present(
    payload: WorkflowCallbackPayload | None,
    lead_id: str,
    now: datetime,
    db: Session,
) -> str | None:
    if payload is None:
        return None

    # Deal-pipeline transitions (WF 07) must keep their traceability anchored on
    # the deal that triggered them, not collapsed onto the lead. The workflow
    # already emits related_object_type='crm_deal'/related_object_id=deal_id; we
    # honour it whenever the trigger came from the FastAPI deal transition.
    related_object_type = "crm_lead"
    related_object_id = lead_id
    if (
        payload.trigger_source == "fastapi_deal_transition"
        and payload.related_object_id
    ):
        related_object_type = payload.related_object_type or "crm_deal"
        related_object_id = payload.related_object_id

    workflow_execution = WorkflowExecution(
        id=payload.id or _generate_trace_id("exec_n8n", now),
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        workflow_name=payload.workflow_name,
        process=payload.process,
        trigger_source=payload.trigger_source,
        status=payload.status,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        duration_seconds=payload.duration_seconds,
        error_message=payload.error_message,
        result_summary=payload.result_summary,
        input_summary=payload.input_summary,
        output_summary=payload.output_summary,
        agent_name=payload.agent_name,
        created_at=now,
        updated_at=now,
    )
    db.add(workflow_execution)
    return workflow_execution.id


def _create_agent_run_if_present(
    payload: AgentRunCallbackPayload | None,
    workflow_execution_id: str | None,
    now: datetime,
    db: Session,
) -> str | None:
    if payload is None:
        return None

    resolved_workflow_execution_id = workflow_execution_id or payload.workflow_execution_id
    agent_run = AgentRun(
        id=payload.id or _generate_trace_id("run_n8n", now),
        agent_id=payload.agent_id,
        agent_name=payload.agent_name,
        process=payload.process,
        workflow_execution_id=resolved_workflow_execution_id,
        requested_by=_resolve_requested_by(payload.requested_by, db),
        requested_at=payload.requested_at,
        status=payload.status,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        input_summary=payload.input_summary,
        output_summary=payload.output_summary,
        error_message=payload.error_message,
        created_at=now,
        updated_at=now,
    )
    db.add(agent_run)
    return agent_run.id


def _get_workflow_payload(payload: CrmCollectResultPayload) -> WorkflowCallbackPayload | None:
    return payload.workflow_execution or payload.workflow


def _commit_lead_and_interaction(
    lead: CrmLead,
    interaction: CrmInteraction,
    status: str,
    workflow_payload: WorkflowCallbackPayload | None,
    agent_run_payload: AgentRunCallbackPayload | None,
    db: Session,
    failure_detail: str,
) -> N8nCallbackResult:
    return _commit_lead_interaction_and_traces(
        lead=lead,
        interaction=interaction,
        status=status,
        workflow_payload=workflow_payload,
        agent_run_payload=agent_run_payload,
        db=db,
        failure_detail=failure_detail,
    )


def _commit_lead_interaction_and_traces(
    lead: CrmLead,
    interaction: CrmInteraction,
    status: str,
    workflow_payload: WorkflowCallbackPayload | None,
    agent_run_payload: AgentRunCallbackPayload | None,
    db: Session,
    failure_detail: str,
) -> N8nCallbackResult:
    try:
        db.add(interaction)
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM callback failed while saving lead/interaction data.")
        raise HTTPException(status_code=500, detail=failure_detail) from exc

    workflow_execution_id, agent_run_id = _persist_callback_traces_safely(
        workflow_payload=workflow_payload,
        agent_run_payload=agent_run_payload,
        lead_id=lead.id,
        now=interaction.interaction_date,
        db=db,
    )

    try:
        db.commit()
        db.refresh(lead)
        db.refresh(interaction)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("CRM callback failed while committing data.")
        raise HTTPException(status_code=500, detail=failure_detail) from exc

    return _callback_result(
        lead_id=lead.id,
        interaction_id=interaction.id,
        status=status,
        workflow_execution_id=workflow_execution_id,
        agent_run_id=agent_run_id,
    )


def _persist_callback_traces_safely(
    workflow_payload: WorkflowCallbackPayload | None,
    agent_run_payload: AgentRunCallbackPayload | None,
    lead_id: str,
    now: datetime,
    db: Session,
) -> tuple[str | None, str | None]:
    if workflow_payload is None and agent_run_payload is None:
        return None, None

    try:
        with db.begin_nested():
            workflow_execution_id = _create_workflow_execution_if_present(
                workflow_payload,
                lead_id,
                now,
                db,
            )
            if workflow_execution_id is not None:
                db.flush()

            agent_run_id = _create_agent_run_if_present(
                agent_run_payload,
                workflow_execution_id,
                now,
                db,
            )
            if agent_run_id is not None:
                db.flush()
    except SQLAlchemyError:
        logger.exception(
            "CRM callback failed while persisting workflow/agent traces for lead %s.",
            lead_id,
        )
        return None, None

    return workflow_execution_id, agent_run_id


def _resolve_requested_by(requested_by: str | None, db: Session) -> str | None:
    if not requested_by:
        return None

    if db.get(User, requested_by) is not None:
        return requested_by

    if db.get(User, DEFAULT_CRM_OWNER_ID) is not None:
        logger.warning(
            "Invalid requested_by %s in n8n agent_run payload; using %s.",
            requested_by,
            DEFAULT_CRM_OWNER_ID,
        )
        return DEFAULT_CRM_OWNER_ID

    logger.warning(
        "Invalid requested_by %s in n8n agent_run payload; storing null.",
        requested_by,
    )
    return None


def _generate_trace_id(prefix: str, now: datetime) -> str:
    return f"{prefix}_{int(now.timestamp())}_{uuid4().hex[:8]}"


def _duration_seconds(started_at: datetime, finished_at: datetime) -> int:
    if started_at.tzinfo is None and finished_at.tzinfo is not None:
        finished_at = finished_at.replace(tzinfo=None)
    elif started_at.tzinfo is not None and finished_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=None)

    return max(0, int((finished_at - started_at).total_seconds()))


def _callback_result(
    lead_id: str,
    interaction_id: str,
    status: str,
    workflow_execution_id: str | None = None,
    agent_run_id: str | None = None,
    assigned_user: User | None = None,
) -> N8nCallbackResult:
    return N8nCallbackResult(
        lead_id=lead_id,
        interaction_id=interaction_id,
        workflow_execution_id=workflow_execution_id,
        agent_run_id=agent_run_id,
        status=status,
        assigned_to=assigned_user.id if assigned_user else None,
        assigned_to_name=assigned_user.full_name if assigned_user else None,
        assigned_to_email=assigned_user.email if assigned_user else None,
    )


def _communication_summary(payload: CrmCommunicationResultPayload) -> str:
    subject = _communication_subject(payload)
    body = _communication_body(payload)
    status = _communication_status(payload)

    if payload.interaction and payload.interaction.summary and not (subject or body):
        return payload.interaction.summary
    if subject or body:
        resolved_subject = subject or "Untitled draft"
        resolved_body = body or "No draft body available."
        return (
            f"Status: {status}\n"
            f"Subject: {resolved_subject}\n"
            f"Body:\n{resolved_body}"
        )
    if payload.summary:
        return payload.summary

    return f"CRM communication {status}."


def _communication_channel(payload: CrmCommunicationResultPayload) -> str | None:
    if payload.interaction and payload.interaction.channel:
        return payload.interaction.channel

    return payload.channel


def _communication_interaction_type(payload: CrmCommunicationResultPayload) -> str:
    status = _communication_status(payload)

    if (
        payload.interaction
        and payload.interaction.interaction_type in SAFE_COMMUNICATION_INTERACTION_TYPES
    ):
        return payload.interaction.interaction_type

    if payload.sent or status in {"sent", "failed"}:
        return "communication_result"

    return "communication_draft"


def _communication_subject(payload: CrmCommunicationResultPayload) -> str | None:
    return payload.email_subject or payload.subject


def _communication_body(payload: CrmCommunicationResultPayload) -> str | None:
    return payload.email_body or payload.body


def _communication_status(payload: CrmCommunicationResultPayload) -> str:
    status = (payload.communication_status or payload.status or "draft").strip().lower()

    return status or "draft"


def _build_email_draft_from_payload(
    payload: CrmCommunicationResultPayload,
    now: datetime,
) -> CrmEmailDraft | None:
    subject = _communication_subject(payload)
    body = _communication_body(payload)

    if not subject and not body:
        return None

    return CrmEmailDraft(
        id=f"draft_{uuid4().hex[:8]}",
        lead_id=payload.lead_id,
        deal_id=payload.deal_id,
        draft_type=_communication_draft_type(payload),
        subject=subject or "Untitled draft",
        body=body or "No draft body available.",
        status="draft_generated",
        tone=payload.tone,
        cta=payload.cta,
        generated_by_agent=_communication_agent_name(payload),
        created_at=now,
        updated_at=now,
    )


def _communication_draft_type(payload: CrmCommunicationResultPayload) -> str:
    explicit_type = (payload.draft_type or "").strip().lower()

    if explicit_type in {"sales", "welcome", "follow_up", "reactivation", "proposal"}:
        return explicit_type

    searchable_text = " ".join(
        value
        for value in [
            payload.summary,
            payload.interaction.summary if payload.interaction else None,
            _communication_subject(payload),
            _communication_body(payload),
        ]
        if value
    ).lower()

    if any(phrase in searchable_text for phrase in ["welcome", "bienvenue", "customer conversion"]):
        return "welcome"

    return "sales"


def _communication_agent_name(payload: CrmCommunicationResultPayload) -> str | None:
    if payload.agent_run and payload.agent_run.agent_name:
        return payload.agent_run.agent_name
    if payload.workflow_execution and payload.workflow_execution.agent_name:
        return payload.workflow_execution.agent_name

    return None
