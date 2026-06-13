"""Schemas for the CRM Tasks (WF 06) and CRM Deals (WF 07) features."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Comments (shared by tasks and deals)
# ---------------------------------------------------------------------------


class CrmCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class CrmCommentItem(BaseModel):
    id: str
    entity_type: Literal["task", "deal"]
    entity_id: str
    author_user_id: str
    author_full_name: str
    author_email: str | None = None
    content: str
    created_at: datetime
    updated_at: datetime


class CrmCommentListResponse(BaseModel):
    count: int
    items: list[CrmCommentItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Team member picker (read-only roster for owner selects)
# ---------------------------------------------------------------------------


class CrmTeamMember(BaseModel):
    id: str
    full_name: str
    email: str
    role_id: str
    job_title: str | None = None


class CrmTeamMemberListResponse(BaseModel):
    count: int
    items: list[CrmTeamMember] = Field(default_factory=list)

# Allowed enum values, kept centralized so schemas/services stay aligned.
TASK_STATUSES = ("pending", "done", "cancelled")
TASK_PRIORITIES = ("low", "medium", "high")
DEAL_STAGES = ("discovery", "proposal", "negotiation", "closing", "won", "lost")


class CrmTaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    due_date: datetime
    priority: Literal["low", "medium", "high"] = "medium"
    lead_id: str | None = None
    owner_user_id: str


class CrmTaskCreate(CrmTaskBase):
    pass


class CrmTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    due_date: datetime | None = None
    priority: Literal["low", "medium", "high"] | None = None
    status: Literal["pending", "done", "cancelled"] | None = None
    owner_user_id: str | None = None


class CrmTaskItem(BaseModel):
    id: str
    lead_id: str | None
    lead_full_name: str | None = None
    lead_company_name: str | None = None
    owner_user_id: str
    owner_full_name: str | None = None
    owner_email: str | None = None
    title: str
    description: str | None
    due_date: datetime
    status: Literal["pending", "done", "cancelled"]
    priority: Literal["low", "medium", "high"]
    task_type: str | None = None
    reminder_sent_at: datetime | None
    next_reminder_at: datetime | None = None
    completed_at: datetime | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    days_until_due: int
    is_overdue: bool
    comments_count: int = 0


class CrmTaskListResponse(BaseModel):
    count: int
    items: list[CrmTaskItem] = Field(default_factory=list)


class CrmPendingFollowupOwnerGroup(BaseModel):
    owner_user_id: str
    owner_full_name: str
    owner_email: str
    tasks: list[CrmTaskItem]


class CrmPendingFollowupResponse(BaseModel):
    threshold_hours: int
    total_tasks: int
    owners: list[CrmPendingFollowupOwnerGroup] = Field(default_factory=list)


class CrmTaskReminderAck(BaseModel):
    task_ids: list[str] = Field(default_factory=list)
    reminded_at: datetime


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------


class CrmDealBase(BaseModel):
    lead_id: str
    owner_user_id: str
    title: str = Field(min_length=1, max_length=255)
    amount: Decimal | None = None
    currency: str = Field(default="TND", min_length=3, max_length=8)
    probability_percent: int = Field(default=20, ge=0, le=100)
    expected_close_date: datetime | None = None
    notes: str | None = None


class CrmDealCreate(CrmDealBase):
    stage: Literal["discovery", "proposal", "negotiation", "closing", "won", "lost"] = "discovery"


class CrmDealUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    amount: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    probability_percent: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: datetime | None = None
    notes: str | None = None
    owner_user_id: str | None = None


class CrmDealStageTransitionRequest(BaseModel):
    new_stage: Literal["discovery", "proposal", "negotiation", "closing", "won", "lost"]
    reason: str | None = None
    trigger_workflow: bool = True


class CrmDealItem(BaseModel):
    id: str
    lead_id: str
    lead_full_name: str | None = None
    lead_company_name: str | None = None
    owner_user_id: str
    owner_full_name: str | None = None
    owner_email: str | None = None
    title: str
    stage: Literal["discovery", "proposal", "negotiation", "closing", "won", "lost"]
    previous_stage: str | None
    amount: Decimal | None
    currency: str
    probability_percent: int
    expected_close_date: datetime | None
    notes: str | None
    won_reason: str | None
    lost_reason: str | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    comments_count: int = 0


class CrmDealListResponse(BaseModel):
    count: int
    items: list[CrmDealItem] = Field(default_factory=list)


class CrmDealStageTransitionResponse(BaseModel):
    deal_id: str
    new_stage: str
    previous_stage: str | None
    workflow_triggered: bool
    n8n_response: Any | None = None
    message: str
