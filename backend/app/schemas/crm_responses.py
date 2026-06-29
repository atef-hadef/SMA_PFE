"""Schemas pour les réponses client CRM (FIX 3)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RESPONSE_TYPES = (
    "interested",
    "not_interested",
    "needs_more_info",
    "callback_requested",
    "no_response",
)
CrmResponseType = Literal[
    "interested",
    "not_interested",
    "needs_more_info",
    "callback_requested",
    "no_response",
]


class CrmLeadResponseCreate(BaseModel):
    response_type: CrmResponseType
    notes: str | None = Field(default=None, max_length=4000)
    next_action: str | None = Field(default=None, max_length=255)
    next_action_date: datetime | None = None


class CrmLeadResponseItem(BaseModel):
    id: str
    lead_id: str
    response_type: CrmResponseType
    notes: str | None
    next_action: str | None
    next_action_date: datetime | None
    recorded_by: str | None
    recorded_by_name: str | None = None
    recorded_at: datetime


class CrmLeadResponseListResponse(BaseModel):
    count: int
    items: list[CrmLeadResponseItem] = Field(default_factory=list)


class CrmLeadResponseCreatedResponse(BaseModel):
    response: CrmLeadResponseItem
    lead_status: str | None = None
    lead_customer_status: str | None = None
    created_task_id: str | None = None
    message: str
