"""Schemas pour le journal d'activité / audit log (FIX 4)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ActivityItem(BaseModel):
    id: str
    entity_type: str
    entity_id: str | None
    action: str
    actor_id: str | None
    actor_name: str | None
    details: dict[str, Any] | None = None
    created_at: datetime


class ActivityListResponse(BaseModel):
    count: int
    scope: str  # all | hr | own
    items: list[ActivityItem] = Field(default_factory=list)
