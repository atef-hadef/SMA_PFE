from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.n8n_callbacks import AgentRunCallbackPayload, WorkflowCallbackPayload


class LeaveRequestHistoryResponse(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    department: str
    leave_type: str
    start_date: date
    end_date: date
    requested_days: float | None
    reason: str
    status: str
    manager_comment: str | None
    decided_at: datetime | None
    created_at: datetime
    odoo_sync_status: str | None


class LeaveRequestCreate(BaseModel):
    leave_type: str
    start_date: date
    end_date: date
    reason: str


class LeaveRequestResponse(BaseModel):
    id: str
    employee_id: str
    leave_type: str
    start_date: date
    end_date: date
    reason: str
    status: str
    created_at: datetime


class LeaveBalancePrecheckResponse(BaseModel):
    ok: bool | None = None
    status: str | None = None
    error_code: str | None = None
    available_days: Decimal | None = None
    requested_days: Decimal | None = None
    balance_gap_days: Decimal | None = None
    has_enough_balance: bool | None = None
    recommendation: str | None = None
    recommendation_label: str | None = None
    risk_level: str | None = None
    ai_explanation: str | None = None
    employee_guidance: str | None = None
    manager_guidance: str | None = None
    message: str | None = None
    conflict_detected: bool | None = None
    conflict_type: str | None = None
    overlapping_leave_count: int | None = None
    overlapping_leaves: list[dict[str, object]] = Field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None


class PendingLeaveRequestResponse(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    department: str
    leave_type: str
    start_date: date
    end_date: date
    reason: str
    status: Literal["pending", "manager_review_required"]
    created_at: datetime
    ai_recommendation: Literal["approve", "reject", "review"]
    risk_level: Literal["low", "medium", "high"]
    conflict_detected: bool
    automation_summary: str | None = None
    available_days: Decimal | None = None
    requested_days: Decimal | None = None
    balance_gap_days: Decimal | None = None
    ai_explanation: str | None = None
    decision_reasons: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    approval_factors: list[str] = Field(default_factory=list)
    rejection_factors: list[str] = Field(default_factory=list)
    score_reasons: list[str] = Field(default_factory=list)
    manager_guidance: str | None = None
    can_manager_override: bool | None = None
    can_sync_with_odoo: bool = False


class LeaveDecisionRequest(BaseModel):
    comment: str


class LeaveDecisionResponse(BaseModel):
    id: str
    status: Literal["approved", "rejected"]
    manager_comment: str
    updated_at: datetime


class LeaveAutomationAnalysisCallback(BaseModel):
    ok: bool | None = None
    workflow: str | None = None
    branch: str | None = None
    flowpilot_request_id: str | None = None
    workflow_execution_id: str | None = None
    agent_run_id: str | None = None
    odoo_leave_id: int | str | None = None
    odoo_state: str | None = None
    odoo_sync_status: str | None = None
    recommendation: str | None = None
    recommendation_label: str | None = None
    automation_recommendation: str | None = None
    automation_summary: str | None = None
    summary: str | None = None
    score: int | None = None
    available_days: Decimal | None = None
    availableDays: Decimal | None = None
    requested_days: Decimal | None = None
    requestedDays: Decimal | None = None
    has_enough_balance: bool | None = None
    hasEnoughBalance: bool | None = None
    balance_status: str | None = None
    balance_label: str | None = None
    conflict_count: int | None = None
    risk_level: str | None = None
    ai_explanation: str | None = None
    decision_reasons: list[str] | None = None
    blocking_reasons: list[str] | None = None
    approval_factors: list[str] | None = None
    rejection_factors: list[str] | None = None
    score_reasons: list[str] | None = None
    scoreReasons: list[str] | None = None
    manager_guidance: str | None = None
    balance_gap_days: Decimal | None = None
    can_manager_override: bool | None = None
    error_message: str | None = None
    workflow_execution: WorkflowCallbackPayload | None = None
    agent_run: AgentRunCallbackPayload | None = None


class LeaveDecisionSyncCallback(BaseModel):
    ok: bool | None = None
    workflow: str | None = None
    branch: str | None = None
    flowpilot_request_id: str | None = None
    workflow_execution_id: str | None = None
    agent_run_id: str | None = None
    decision: str
    odoo_leave_id: int | str | None = None
    odoo_state: str | None = None
    odoo_sync_status: str | None = None
    manager_comment: str | None = None
    comment: str | None = None
    decided_at: datetime | None = None
    approved_at: datetime | None = None
    error_message: str | None = None
    workflow_execution: WorkflowCallbackPayload | None = None
    agent_run: AgentRunCallbackPayload | None = None


class LeaveCallbackResponse(BaseModel):
    ok: bool
    request_id: str
    message: str
