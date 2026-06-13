from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


AgentStatus = Literal["active", "inactive", "degraded"]


class AgentListItem(BaseModel):
    id: str
    name: str
    process: str
    status: AgentStatus
    type: str
    success_rate: int
    last_execution: datetime
    total_runs: int
    description: str


class AgentRecentRun(BaseModel):
    id: str
    execution_id: str
    status: Literal["success", "failed", "running", "queued"]
    duration: str
    started_at: datetime
    requested_at: datetime | None = None
    input_summary: str | None = None
    output_summary: str | None = None


class AgentDetail(AgentListItem):
    input_description: str
    output_description: str
    tools: list[str]
    related_workflows: list[str]
    recent_runs: list[AgentRecentRun]


class AgentRunRequest(BaseModel):
    payload: dict[str, Any]


class AgentRunResponse(BaseModel):
    agent_id: str
    run_status: Literal["queued"]
    message: str
    requested_at: datetime
