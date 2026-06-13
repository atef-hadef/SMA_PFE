from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


WorkflowStatus = Literal["success", "failed", "running", "queued"]


class WorkflowExecutionListItem(BaseModel):
    id: str
    workflow_name: str
    process: str
    status: WorkflowStatus
    related_object_type: str | None = None
    related_object_id: str | None = None
    trigger_source: str
    duration_seconds: int | None = None
    agent_name: str
    related_object: str
    started_at: datetime
    finished_at: datetime | None
    created_at: datetime
    duration: str
    triggered_by: str
    agent: str


class WorkflowStep(BaseModel):
    name: str
    status: WorkflowStatus
    duration: str


class WorkflowRelatedAgentRun(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    status: WorkflowStatus
    requested_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    error_message: str | None = None


class WorkflowExecutionDetail(WorkflowExecutionListItem):
    input_summary: str
    output_summary: str
    result_summary: str | None = None
    steps: list[WorkflowStep]
    error_message: str | None = None
    updated_at: datetime
    related_agent_runs: list[WorkflowRelatedAgentRun] = Field(default_factory=list)


class RetryWorkflowExecutionRequest(BaseModel):
    reason: str


class RetryWorkflowExecutionResponse(BaseModel):
    id: str
    status: Literal["queued"]
    execution_id: str
    retry_status: Literal["queued"]
    message: str
    requested_at: datetime
