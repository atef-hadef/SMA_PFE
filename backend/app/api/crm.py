from email import policy
from email.parser import BytesParser

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import (
    require_internal_secret,
    require_permission,
    require_permission_or_internal_secret,
)
from app.core.database import get_db
from app.schemas.auth import AuthUser
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.crm import (
    CrmCommunicationDraftTriggerRequest,
    CrmCommunicationDraftTriggerResponse,
    CrmCustomerConversionRequest,
    CrmCustomerConversionTriggerResponse,
    CrmEmailAttachmentItem,
    CrmEmailDraftItem,
    CrmEmailDraftReject,
    CrmEmailDraftSendResponse,
    CrmEmailDraftUpdate,
    CrmEmailSendPackage,
    CrmInactiveLeadsResponse,
    CrmInteractionHistoryItem,
    CrmLeadInteractionCreate,
    CrmLeadCreate,
    CrmLeadCreatedResponse,
    CrmLeadDetail,
    CrmLeadListItem,
    CrmWebhookOutboxProcessResponse,
    CrmWeeklyStatsResponse,
    CrmWorkflowErrorLogPayload,
    CrmWorkflowErrorLogResponse,
    CrmWorkflowTracePayload,
    CrmWorkflowTraceResponse,
    PublicCrmLeadIntake,
    PublicCrmLeadIntakeResponse,
)
from app.schemas.crm_responses import (
    CrmLeadResponseCreate,
    CrmLeadResponseCreatedResponse,
    CrmLeadResponseListResponse,
)
from app.services import webhook_outbox_service
from app.services.audit_service import log_activity
from app.services.crm_responses_service import list_responses, record_response
from app.services.crm_service import (
    convert_lead_to_customer,
    approve_email_draft,
    create_lead_interaction,
    create_crm_lead,
    delete_email_draft_attachment,
    generate_communication_draft_for_lead,
    get_email_draft_send_package,
    get_lead_email_drafts,
    get_crm_lead_by_id,
    get_crm_leads,
    get_weekly_crm_stats,
    list_inactive_leads,
    log_crm_workflow_error,
    record_crm_workflow_trace,
    reject_email_draft,
    review_email_draft,
    send_approved_email_draft,
    submit_public_lead,
    update_email_draft,
    upload_email_draft_attachment,
)

router = APIRouter()


@router.get("/crm/leads", response_model=ApiResponse[PaginatedResponse[CrmLeadListItem]])
def read_crm_leads(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.leads.view")),
) -> ApiResponse[PaginatedResponse[CrmLeadListItem]]:
    return ApiResponse(
        success=True,
        data=get_crm_leads(db, page=page, page_size=page_size, current_user=current_user),
    )


@router.get("/crm/leads/{lead_id}", response_model=ApiResponse[CrmLeadDetail])
def read_crm_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.leads.view")),
) -> ApiResponse[CrmLeadDetail]:
    lead = get_crm_lead_by_id(lead_id, db, current_user=current_user)

    if lead is None:
        raise HTTPException(status_code=404, detail="CRM lead not found.")

    return ApiResponse(success=True, data=lead)


@router.get(
    "/crm/leads/{lead_id}/drafts",
    response_model=ApiResponse[list[CrmEmailDraftItem]],
)
def read_crm_lead_email_drafts(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.leads.view")),
) -> ApiResponse[list[CrmEmailDraftItem]]:
    return ApiResponse(
        success=True,
        data=get_lead_email_drafts(db, lead_id, current_user=current_user),
    )


@router.post("/crm/leads", response_model=ApiResponse[CrmLeadCreatedResponse])
def submit_crm_lead(
    payload: CrmLeadCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.leads.create")),
) -> ApiResponse[CrmLeadCreatedResponse]:
    created = create_crm_lead(payload, db)
    log_activity(
        db,
        entity_type="lead",
        entity_id=created.id,
        action="created",
        actor_id=current_user.id,
        details={"company": created.company, "name": created.name},
    )
    return ApiResponse(success=True, data=created)


@router.post(
    "/crm/leads/public",
    response_model=ApiResponse[PublicCrmLeadIntakeResponse],
    status_code=202,
)
def submit_public_crm_lead(
    payload: PublicCrmLeadIntake,
    db: Session = Depends(get_db),
) -> ApiResponse[PublicCrmLeadIntakeResponse]:
    """Public, unauthenticated endpoint for the website contact form.

    Server-side relay to CRM_01: adds the FlowPilot secret in the backend
    (browsers cannot safely carry it), enqueues via webhook_outbox so the
    lead is durable even if n8n is momentarily down, and returns 202 Accepted
    immediately so the form UX stays snappy.
    """
    return ApiResponse(success=True, data=submit_public_lead(payload, db))


@router.post(
    "/crm/leads/{lead_id}/generate-communication-draft",
    response_model=ApiResponse[CrmCommunicationDraftTriggerResponse],
)
def trigger_crm_communication_draft(
    lead_id: str,
    payload: CrmCommunicationDraftTriggerRequest | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.drafts.generate")),
) -> ApiResponse[CrmCommunicationDraftTriggerResponse]:
    # Corps optionnel : un ancien client sans body retombe sur 'initial'.
    draft_type = (payload or CrmCommunicationDraftTriggerRequest()).draft_type
    return ApiResponse(
        success=True,
        message="Communication draft workflow triggered successfully.",
        data=generate_communication_draft_for_lead(db, lead_id, draft_type=draft_type),
    )


@router.post(
    "/crm/leads/{lead_id}/interactions",
    response_model=ApiResponse[CrmInteractionHistoryItem],
)
def log_crm_lead_interaction(
    lead_id: str,
    payload: CrmLeadInteractionCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.interactions.create")),
) -> ApiResponse[CrmInteractionHistoryItem]:
    payload = payload.model_copy(update={"created_by": current_user.id})
    return ApiResponse(
        success=True,
        message="Customer interaction logged successfully.",
        data=create_lead_interaction(db, lead_id, payload),
    )


@router.post(
    "/crm/leads/{lead_id}/responses",
    response_model=ApiResponse[CrmLeadResponseCreatedResponse],
)
def record_crm_lead_response(
    lead_id: str,
    payload: CrmLeadResponseCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.interactions.create")),
) -> ApiResponse[CrmLeadResponseCreatedResponse]:
    result = record_response(db, lead_id, payload, recorded_by=current_user.id)
    log_activity(
        db,
        entity_type="response",
        entity_id=result.response.id,
        action="recorded",
        actor_id=current_user.id,
        details={"lead_id": lead_id, "response_type": result.response.response_type},
    )
    return ApiResponse(success=True, message=result.message, data=result)


@router.get(
    "/crm/leads/{lead_id}/responses",
    response_model=ApiResponse[CrmLeadResponseListResponse],
)
def read_crm_lead_responses(
    lead_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.leads.view")),
) -> ApiResponse[CrmLeadResponseListResponse]:
    return ApiResponse(success=True, data=list_responses(db, lead_id))


@router.patch(
    "/crm/email-drafts/{draft_id}",
    response_model=ApiResponse[CrmEmailDraftItem],
)
def edit_crm_email_draft(
    draft_id: str,
    payload: CrmEmailDraftUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.drafts.review")),
) -> ApiResponse[CrmEmailDraftItem]:
    payload = payload.model_copy(update={"edited_by": current_user.id})
    return ApiResponse(
        success=True,
        message="Email draft updated successfully.",
        data=update_email_draft(db, draft_id, payload),
    )


@router.post(
    "/crm/email-drafts/{draft_id}/review",
    response_model=ApiResponse[CrmEmailDraftItem],
)
def mark_crm_email_draft_reviewed(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.drafts.review")),
) -> ApiResponse[CrmEmailDraftItem]:
    return ApiResponse(
        success=True,
        message="Email draft marked as reviewed.",
        data=review_email_draft(db, draft_id, current_user.id),
    )


@router.post(
    "/crm/email-drafts/{draft_id}/approve",
    response_model=ApiResponse[CrmEmailDraftItem],
)
def approve_crm_email_draft(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.email.approve")),
) -> ApiResponse[CrmEmailDraftItem]:
    data = approve_email_draft(db, draft_id, current_user.id)
    log_activity(
        db,
        entity_type="email_draft",
        entity_id=draft_id,
        action="approved",
        actor_id=current_user.id,
        details={"lead_id": data.lead_id, "subject": data.subject},
    )
    return ApiResponse(
        success=True,
        message="Email draft approved. It is ready for future automated sending.",
        data=data,
    )


@router.post(
    "/crm/email-drafts/{draft_id}/reject",
    response_model=ApiResponse[CrmEmailDraftItem],
)
def reject_crm_email_draft(
    draft_id: str,
    payload: CrmEmailDraftReject,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.drafts.review")),
) -> ApiResponse[CrmEmailDraftItem]:
    payload = payload.model_copy(update={"rejected_by": current_user.id})
    data = reject_email_draft(db, draft_id, payload)
    log_activity(
        db,
        entity_type="email_draft",
        entity_id=draft_id,
        action="rejected",
        actor_id=current_user.id,
        details={"lead_id": data.lead_id, "reason": payload.rejection_reason},
    )
    return ApiResponse(
        success=True,
        message="Email draft rejected.",
        data=data,
    )


@router.post(
    "/crm/email-drafts/{draft_id}/send",
    response_model=ApiResponse[CrmEmailDraftSendResponse],
)
def send_crm_approved_email_draft(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.email.send")),
) -> ApiResponse[CrmEmailDraftSendResponse]:
    response = send_approved_email_draft(db, draft_id, requested_by=current_user.id)
    log_activity(
        db,
        entity_type="email_draft",
        entity_id=draft_id,
        action="sent",
        actor_id=current_user.id,
        details={"message": response.message},
    )

    return ApiResponse(
        success=True,
        message=response.message,
        data=response,
    )


@router.get(
    "/crm/email-drafts/{draft_id}/send-package",
    response_model=ApiResponse[CrmEmailSendPackage],
)
def read_crm_email_draft_send_package(
    draft_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission_or_internal_secret("crm.email.send")),
) -> ApiResponse[CrmEmailSendPackage]:
    return ApiResponse(
        success=True,
        data=get_email_draft_send_package(db, draft_id),
    )


@router.post(
    "/crm/email-drafts/{draft_id}/attachments",
    response_model=ApiResponse[CrmEmailAttachmentItem],
)
async def upload_crm_email_draft_attachment(
    draft_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.drafts.review")),
) -> ApiResponse[CrmEmailAttachmentItem]:
    file_name, file_content, mime_type, uploaded_by = await _parse_attachment_upload(request)
    uploaded_by = current_user.id

    return ApiResponse(
        success=True,
        message="Attachment added.",
        data=upload_email_draft_attachment(
            db,
            draft_id,
            file_name,
            file_content,
            mime_type,
            uploaded_by,
        ),
    )


@router.delete(
    "/crm/email-drafts/{draft_id}/attachments/{attachment_id}",
    response_model=ApiResponse[None],
)
def delete_crm_email_draft_attachment(
    draft_id: str,
    attachment_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("crm.drafts.review")),
) -> ApiResponse[None]:
    delete_email_draft_attachment(db, draft_id, attachment_id)

    return ApiResponse(success=True, message="Attachment removed.", data=None)


async def _parse_attachment_upload(request: Request) -> tuple[str, bytes, str | None, str | None]:
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" not in content_type.lower():
        raise HTTPException(status_code=400, detail="Multipart file upload is required.")

    body = await request.body()
    message = BytesParser(policy=policy.default).parsebytes(
        (
            f"Content-Type: {content_type}\r\n"
            "MIME-Version: 1.0\r\n\r\n"
        ).encode("utf-8")
        + body
    )
    uploaded_by: str | None = None
    file_name: str | None = None
    file_content: bytes | None = None
    mime_type: str | None = None

    for part in message.iter_parts():
        field_name = part.get_param("name", header="content-disposition")

        if field_name == "uploaded_by":
            payload = part.get_payload(decode=True) or b""
            uploaded_by = payload.decode("utf-8", errors="replace").strip() or None
        elif field_name == "file":
            file_name = part.get_filename() or "attachment"
            file_content = part.get_payload(decode=True) or b""
            mime_type = part.get_content_type()

    if file_content is None:
        raise HTTPException(status_code=422, detail="Attachment file is required.")

    return file_name or "attachment", file_content, mime_type, uploaded_by


@router.post(
    "/crm/leads/{lead_id}/convert-to-customer",
    response_model=ApiResponse[CrmCustomerConversionTriggerResponse],
)
def trigger_crm_customer_conversion(
    lead_id: str,
    payload: CrmCustomerConversionRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_permission("crm.customer.convert")),
) -> ApiResponse[CrmCustomerConversionTriggerResponse]:
    payload = payload.model_copy(update={"requested_by": current_user.id})
    data = convert_lead_to_customer(db, lead_id, payload)
    log_activity(
        db,
        entity_type="lead",
        entity_id=lead_id,
        action="converted",
        actor_id=current_user.id,
        details={"lead_id": lead_id},
    )
    return ApiResponse(
        success=True,
        message="Customer conversion workflow triggered successfully.",
        data=data,
    )


@router.post(
    "/crm/webhook/error-log",
    response_model=ApiResponse[CrmWorkflowErrorLogResponse],
    dependencies=[Depends(require_internal_secret)],
)
def receive_crm_workflow_error(
    payload: CrmWorkflowErrorLogPayload,
    db: Session = Depends(get_db),
) -> ApiResponse[CrmWorkflowErrorLogResponse]:
    return ApiResponse(
        success=True,
        message="CRM workflow error log captured.",
        data=log_crm_workflow_error(payload, db),
    )


@router.post(
    "/crm/webhook/workflow-trace",
    response_model=ApiResponse[CrmWorkflowTraceResponse],
    dependencies=[Depends(require_internal_secret)],
)
def receive_crm_workflow_trace(
    payload: CrmWorkflowTracePayload,
    db: Session = Depends(get_db),
) -> ApiResponse[CrmWorkflowTraceResponse]:
    return ApiResponse(
        success=True,
        message="CRM workflow trace captured.",
        data=record_crm_workflow_trace(payload, db),
    )


@router.post(
    "/crm/webhook/process-outbox",
    response_model=ApiResponse[CrmWebhookOutboxProcessResponse],
    dependencies=[Depends(require_internal_secret)],
)
def process_crm_webhook_outbox(
    db: Session = Depends(get_db),
) -> ApiResponse[CrmWebhookOutboxProcessResponse]:
    """Drain the webhook outbox: retries pending/failed rows with backoff.

    Intended for periodic invocation (n8n cron or external scheduler). Caller
    must present the internal X-FlowPilot-Secret header.
    """
    stats = webhook_outbox_service.process_pending(db)
    return ApiResponse(
        success=True,
        message=(
            f"Outbox processed: {stats['sent']} sent, "
            f"{stats['failed']} failed, {stats['dead']} dead."
        ),
        data=CrmWebhookOutboxProcessResponse(**stats),
    )


@router.get(
    "/crm/leads/inactive",
    response_model=ApiResponse[CrmInactiveLeadsResponse],
    dependencies=[Depends(require_internal_secret)],
)
def read_crm_inactive_leads(
    days: int = 7,
    db: Session = Depends(get_db),
) -> ApiResponse[CrmInactiveLeadsResponse]:
    return ApiResponse(
        success=True,
        data=list_inactive_leads(db, threshold_days=days),
    )


@router.get(
    "/crm/stats/weekly",
    response_model=ApiResponse[CrmWeeklyStatsResponse],
    dependencies=[Depends(require_internal_secret)],
)
def read_crm_weekly_stats(
    db: Session = Depends(get_db),
) -> ApiResponse[CrmWeeklyStatsResponse]:
    return ApiResponse(
        success=True,
        data=get_weekly_crm_stats(db),
    )
