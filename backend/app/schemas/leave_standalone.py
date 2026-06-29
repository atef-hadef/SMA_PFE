from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class LeaveBalanceItemResponse(BaseModel):
    leave_type: str
    leave_type_label: str
    allocated: float
    used: float
    pending: float
    available: float
    year: int


class LeaveTypeResponse(BaseModel):
    id: str
    code: str
    label_fr: str
    label_en: str | None = None
    default_days: int
    requires_document: bool


class LeaveStandaloneCreateRequest(BaseModel):
    leave_type: str
    start_date: date
    end_date: date
    reason: str


class StandaloneLeaveRequestResponse(BaseModel):
    id: str
    employee_id: str
    leave_type: str
    start_date: date
    end_date: date
    reason: str
    status: str
    requested_days: float | None = None
    available_days: float | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    decision_comment: str | None = None
    created_at: datetime


class AllocationDetailResponse(BaseModel):
    leave_type: str
    leave_type_label: str
    allocated_days: float
    used_days: float
    available_days: float


class AllocationGroupResponse(BaseModel):
    employee_id: str
    employee_name: str
    year: int
    allocations: list[AllocationDetailResponse]


class AllocationUpsertRequest(BaseModel):
    employee_id: str
    year: int
    leave_type: str
    allocated_days: Decimal


class AllocationUpsertResponse(BaseModel):
    id: str
    employee_id: str
    year: int
    leave_type: str
    allocated_days: float


class LeaveAnalyticsResponse(BaseModel):
    total_this_year: int
    approved: int
    rejected: int
    pending: int
    by_type: dict[str, Any]
    by_employee: list[dict[str, Any]]
    burnout_alerts: list[dict[str, Any]]
    pending_over_48h: list[dict[str, Any]]


class LeaveAnalysisCompleteCallback(BaseModel):
    leave_request_id: str
    llm_recommendation: str | None = None
    llm_explanation: str | None = None
    risk_assessment: str | None = None


class LeaveDecisionCompleteCallback(BaseModel):
    leave_request_id: str
    notification_sent: bool | None = None


class StandaloneCallbackResponse(BaseModel):
    success: bool
    message: str | None = None
