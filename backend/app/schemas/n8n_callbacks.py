from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel


class WorkflowCallbackPayload(BaseModel):
    id: str | None = None
    workflow_name: str
    process: str | None = None
    trigger_source: str | None = None
    related_object_type: str | None = None
    related_object_id: str | None = None
    status: str = "success"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    result_summary: str | None = None
    error_message: str | None = None
    agent_name: str | None = None


class AgentRunCallbackPayload(BaseModel):
    id: str | None = None
    agent_id: str
    agent_name: str
    process: str | None = None
    workflow_execution_id: str | None = None
    requested_by: str | None = None
    requested_at: datetime | None = None
    status: str = "success"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    error_message: str | None = None


class CrmInteractionCallbackPayload(BaseModel):
    interaction_type: str | None = None
    channel: str | None = None
    summary: str | None = None


class CrmCollectResultPayload(BaseModel):
    lead_id: str | None = None
    full_name: str
    email: str
    phone: str | None = None
    company_name: str | None = None
    source: str | None = None
    message: str | None = None
    location: str | None = None
    product_service: str | None = None
    estimated_value: Decimal | None = None
    notes: str | None = None
    workflow_execution: WorkflowCallbackPayload | None = None
    workflow: WorkflowCallbackPayload | None = None
    agent_run: AgentRunCallbackPayload | None = None


class CrmAnalysisResultPayload(BaseModel):
    lead_id: str
    sentiment: str | None = None
    intention: str | None = None
    urgency: str | None = None
    ai_summary: str | None = None
    workflow_execution: WorkflowCallbackPayload | None = None
    agent_run: AgentRunCallbackPayload | None = None


class CrmScoringResultPayload(BaseModel):
    lead_id: str
    lead_score: int | None = None
    status: Literal["new", "hot", "warm", "cold"] | None = None
    priority: Literal["low", "medium", "high"] | None = None
    workflow_execution: WorkflowCallbackPayload | None = None
    agent_run: AgentRunCallbackPayload | None = None


class CrmRoutingResultPayload(BaseModel):
    lead_id: str
    recommended_action: str | None = None
    next_action: str | None = None
    customer_status: Literal[
        "lead",
        "prospect",
        "conversion_pending",
        "customer",
        "active_customer",
        "inactive_customer",
        "loyal_customer",
        "vip_customer",
    ] | None = None
    last_contact_at: datetime | None = None
    assigned_to: str | None = None
    owner_user_id: str | None = None
    assignment_reason: str | None = None
    workflow_execution: WorkflowCallbackPayload | None = None
    agent_run: AgentRunCallbackPayload | None = None


class CrmCommunicationResultPayload(BaseModel):
    lead_id: str
    deal_id: str | None = None
    channel: str = "email"
    email_subject: str | None = None
    email_body: str | None = None
    communication_status: str | None = None
    draft_type: str | None = None
    tone: str | None = None
    cta: str | None = None
    subject: str | None = None
    body: str | None = None
    summary: str | None = None
    next_action: str | None = None
    status: Literal["draft", "sent", "failed"] = "draft"
    sent: bool = False
    metadata: dict[str, Any] | None = None
    interaction: CrmInteractionCallbackPayload | None = None
    workflow_execution: WorkflowCallbackPayload | None = None
    agent_run: AgentRunCallbackPayload | None = None


class CrmEmailSentResultPayload(BaseModel):
    draft_id: str
    lead_id: str
    status: Literal["sent", "failed"]
    send_mode: str = "test"
    provider: str | None = None
    provider_message_id: str | None = None
    sent_at: datetime | None = None
    error_message: str | None = None


class N8nCallbackResult(BaseModel):
    lead_id: str
    interaction_id: str
    workflow_execution_id: str | None = None
    agent_run_id: str | None = None
    status: str
