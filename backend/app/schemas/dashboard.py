from pydantic import BaseModel, Field


class DashboardBusinessActivity(BaseModel):
    title: str
    description: str
    time: str
    tone: str


class DashboardSummary(BaseModel):
    leave_requests: int
    pending_approvals: int
    crm_leads: int
    active_agents: int
    hot_leads: int | None = None
    prospects: int | None = None
    customers: int | None = None
    drafts_to_review: int | None = None
    automation_successful: int | None = None
    automation_failed: int | None = None
    automation_issues: int | None = None
    automation_pending: int | None = None
    recent_business_activity: list[DashboardBusinessActivity] = Field(default_factory=list)
