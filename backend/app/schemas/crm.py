from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class CrmLeadCreate(BaseModel):
    name: str
    company: str
    email: str
    source: str
    message: str


class CrmDisplayState(BaseModel):
    lifecycle_stage: Literal[
        "lead",
        "prospect",
        "customer",
        "active_customer",
        "inactive_customer",
        "loyal_customer",
        "vip_customer",
    ]
    display_stage: str
    current_state: Literal[
        "lead_collected",
        "lead_analyzed",
        "prospect_qualified",
        "draft_missing",
        "draft_generated",
        "draft_reviewed",
        "draft_approved",
        "email_sending",
        "email_sent_waiting_response",
        "positive_response_recorded",
        "negative_response_recorded",
        "neutral_response_recorded",
        "follow_up_required",
        "conversion_ready",
        "customer_converted",
        "welcome_draft_generated",
        "welcome_draft_approved",
        "welcome_email_sent",
        "failed",
    ]
    latest_draft_id: str | None = None
    latest_draft_type: Literal["communication", "welcome"] | None = None
    latest_draft_status: str | None = None
    response_state: Literal[
        "none",
        "waiting_response",
        "positive_response",
        "negative_response",
        "neutral_response",
        "follow_up_required",
        "not_interested",
        "unqualified",
        "unknown",
    ]
    latest_email_status: Literal["none", "sending", "sent", "failed"]
    communication_email_sent: bool
    welcome_email_sent: bool
    waiting_for_response: bool
    positive_response_recorded: bool
    negative_response_recorded: bool
    neutral_response_recorded: bool
    follow_up_required: bool
    conversion_ready: bool
    conversion_pending: bool = False
    customer_converted: bool
    needs_human_review: bool
    needs_human_action: bool
    primary_action: str
    secondary_actions: list[str] = Field(default_factory=list)
    computed_next_action: str
    ai_insight_text: str
    business_summary_text: str
    language: Literal["fr", "en"]
    warnings: list[str] = Field(default_factory=list)


class CrmLeadListItem(BaseModel):
    id: str
    name: str
    company: str
    email: str
    phone: str | None = None
    source: str
    customer_status: str | None = None
    status: Literal["new", "hot", "warm", "cold"]
    score: int
    priority: str | None = None
    customer_category: str | None = None
    product_service: str | None = None
    estimated_value: Decimal | None = None
    location: str | None = None
    is_active: bool = True
    next_action: str | None = None
    sentiment: Literal["positive", "neutral", "negative"]
    urgency: Literal["low", "medium", "high"]
    assigned_to: str
    created_at: datetime
    last_contact_at: datetime | None = None
    crm_display_state: CrmDisplayState | None = None


class CrmInteractionHistoryItem(BaseModel):
    id: str
    interaction_type: str
    channel: str | None = None
    summary: str
    interaction_date: datetime
    created_by: str | None = None
    created_at: datetime
    business_label: str | None = None
    draft_subject: str | None = None
    draft_body: str | None = None
    draft_status: str | None = None
    draft_type: str | None = None


class CrmLeadInteractionCreate(BaseModel):
    interaction_type: Literal[
        "email_reply",
        "phone_call",
        "meeting",
        "whatsapp",
        "manual_note",
    ]
    outcome: Literal[
        "confirmed_interest",
        "requested_more_information",
        "accepted_next_step",
        "no_response",
        "not_interested",
    ]
    note: str = Field(min_length=1)
    next_action: str | None = None
    follow_up_date: str | None = None
    created_by: str | None = None


class CrmEmailAttachmentItem(BaseModel):
    id: str
    draft_id: str
    file_name: str
    mime_type: str | None = None
    file_size_bytes: int
    uploaded_by: str | None = None
    created_at: datetime


class CrmEmailDraftItem(BaseModel):
    id: str
    lead_id: str
    draft_type: Literal["sales", "welcome", "follow_up", "reactivation", "proposal"]
    subject: str | None = None
    body: str | None = None
    status: Literal[
        "draft_generated",
        "edited",
        "reviewed",
        "approved",
        "sending",
        "rejected",
        "sent",
        "failed",
    ]
    tone: str | None = None
    cta: str | None = None
    generated_by_agent: str | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    sent_at: datetime | None = None
    edited_by: str | None = None
    edited_by_name: str | None = None
    reviewed_by: str | None = None
    reviewed_by_name: str | None = None
    approved_by: str | None = None
    approved_by_name: str | None = None
    rejected_by: str | None = None
    rejected_by_name: str | None = None
    attachments: list[CrmEmailAttachmentItem] = Field(default_factory=list)


class CrmEmailDraftUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None
    edited_by: str | None = None


class CrmEmailDraftReject(BaseModel):
    rejection_reason: str = Field(min_length=1)
    rejected_by: str | None = None


class CrmEmailDraftSendResponse(BaseModel):
    ok: bool
    message: str


class CrmEmailSendPackageAttachment(BaseModel):
    attachment_id: str
    file_name: str
    mime_type: str | None = None
    file_size_bytes: int


class CrmEmailSendPackage(BaseModel):
    draft_id: str
    lead_id: str
    draft_type: Literal["sales", "welcome", "follow_up", "reactivation", "proposal"]
    to_email: str
    to_name: str
    company_name: str | None = None
    subject: str
    body: str
    status: Literal["approved", "sending"]
    attachments: list[CrmEmailSendPackageAttachment] = Field(default_factory=list)


class CrmLeadDraft(BaseModel):
    draft_type: Literal["sales", "welcome"]
    subject: str | None = None
    body: str | None = None
    status: str | None = None
    generated_at: datetime
    summary: str | None = None
    channel: str | None = None


class CrmLeadDetail(CrmLeadListItem):
    phone: str
    intention: str
    message: str
    ai_summary: str
    recommended_action: str
    notes: str | None = None
    drafts: list[CrmLeadDraft] = Field(default_factory=list)
    interaction_history: list[CrmInteractionHistoryItem] = Field(default_factory=list)


class CrmLeadCreatedResponse(BaseModel):
    id: str
    name: str
    company: str
    email: str
    source: str
    status: Literal["new"]
    score: int
    created_at: datetime


class CrmCommunicationDraftTriggerResponse(BaseModel):
    lead_id: str
    n8n_response: Any


class CrmCustomerConversionRequest(BaseModel):
    human_validated: bool
    validation_reason: str = Field(min_length=1)
    evidence_source: str = Field(min_length=1)
    next_action: str = Field(min_length=1)
    conversion_note: str = Field(min_length=1)
    requested_by: str | None = None


class CrmCustomerConversionTriggerResponse(BaseModel):
    lead_id: str
    message: str
    n8n_response: Any


class CrmWorkflowErrorLogPayload(BaseModel):
    workflow_name: str
    error_message: str | None = None
    process: str | None = "CRM"
    trigger_source: str | None = None
    related_object_type: str | None = None
    related_object_id: str | None = None
    failed_node: str | None = None
    execution_id: str | None = None
    input_summary: str | None = None
    raw_payload: dict[str, Any] | None = None


class CrmWorkflowErrorLogResponse(BaseModel):
    workflow_execution_id: str
    logged_at: datetime


class CrmWorkflowTracePayload(BaseModel):
    workflow_name: str = Field(min_length=1, max_length=160)
    status: Literal["success", "failed"]
    execution_id: str | None = None
    summary: str | None = None
    error_message: str | None = None
    related_object_type: str | None = None
    related_object_id: str | None = None
    process: str | None = "CRM"
    trigger_source: str | None = None


class CrmWorkflowTraceResponse(BaseModel):
    workflow_execution_id: str
    logged_at: datetime
    status: Literal["success", "failed"]


class CrmWebhookOutboxProcessResponse(BaseModel):
    sent: int
    failed: int
    dead: int


class PublicCrmLeadIntake(BaseModel):
    """Payload of the public website form (test-form.html and equivalents).

    No authentication is required at this endpoint, so each field is validated
    aggressively. The honeypot 'website' must stay empty — bots fill every
    field they see; a legit human never touches a hidden input.

    Min lengths mirror CRM_01 normalize/validate node so a payload accepted
    here is also accepted by n8n (no double-validation surprises).
    """

    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=5, max_length=255)
    phone: str | None = Field(default=None, max_length=80)
    company_name: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    product_service: str | None = Field(default=None, max_length=200)
    source: str = Field(default="website_form", max_length=80)
    message: str = Field(min_length=10, max_length=5000)
    consent_to_contact: bool
    requested_by: str | None = Field(default=None, max_length=80)
    # Honeypot — keep last and DO NOT expose visually in the form.
    website: str | None = Field(default=None, max_length=200)


class PublicCrmLeadIntakeResponse(BaseModel):
    accepted: bool
    message: str


class CrmInactiveLeadItem(BaseModel):
    lead_id: str
    full_name: str
    email: str
    company_name: str | None = None
    product_service: str | None = None
    customer_status: str | None = None
    priority: str | None = None
    last_contact_at: datetime | None = None
    days_inactive: int


class CrmInactiveLeadsResponse(BaseModel):
    threshold_days: int
    count: int
    items: list[CrmInactiveLeadItem] = Field(default_factory=list)


class CrmWeeklyStatsResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    leads_incoming: int
    leads_qualified_to_prospect: int
    customers_converted: int
    emails_sent: int
    drafts_pending_review: int
    positive_responses: int
    negative_responses: int
    conversion_rate_percent: float
    pipeline_open_count: int
