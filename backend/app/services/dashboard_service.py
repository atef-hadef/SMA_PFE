from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.permissions import crm_scoped_owner_id
from app.models import AgentRun, CrmEmailDraft, CrmInteraction, CrmLead, LeaveRequest, WorkflowExecution
from app.schemas.dashboard import DashboardBusinessActivity, DashboardSummary
from app.services.leave_service import (
    PENDING_MANAGER_STATUSES,
    _ensure_leave_request_integration_columns,
)

FALLBACK_LEAVE_REQUESTS = 24
FALLBACK_PENDING_APPROVALS = 8
FALLBACK_CRM_LEADS = 129
FALLBACK_ACTIVE_AGENTS = 7
FALLBACK_DRAFTS_TO_REVIEW = 2
FALLBACK_AUTOMATION_SUCCESSFUL = 12
FALLBACK_AUTOMATION_FAILED = 1
FALLBACK_AUTOMATION_PENDING = 0


def get_dashboard_summary(db: Session, current_user=None) -> DashboardSummary:
    # Isolation par rôle : un commercial (role_sales) ne voit que SES stats CRM
    # (leads/prospects/clients/brouillons + activité de ses leads). Admin/manager
    # gardent la vue globale. Les compteurs non-CRM (congés, automatisations,
    # agents) restent globaux.
    owner_id = crm_scoped_owner_id(current_user)

    crm_leads = _safe_count(db, lambda d: _count_crm_leads(d, owner_id), FALLBACK_CRM_LEADS)
    leave_requests = _safe_count(db, _count_leave_requests, FALLBACK_LEAVE_REQUESTS)
    pending_approvals = _safe_count(
        db,
        _count_pending_approvals,
        FALLBACK_PENDING_APPROVALS,
    )
    active_agents = _safe_count(db, _count_active_agents, FALLBACK_ACTIVE_AGENTS)
    automation_failed = _safe_count(
        db,
        _count_failed_automation,
        FALLBACK_AUTOMATION_FAILED,
    )

    return DashboardSummary(
        leave_requests=leave_requests,
        pending_approvals=pending_approvals,
        crm_leads=crm_leads,
        active_agents=active_agents,
        hot_leads=_safe_count(db, lambda d: _count_hot_leads(d, owner_id), 0),
        prospects=_safe_count(db, lambda d: _count_prospects(d, owner_id), 0),
        customers=_safe_count(db, lambda d: _count_customers(d, owner_id), 0),
        drafts_to_review=_safe_count(
            db,
            lambda d: _count_drafts_to_review(d, owner_id),
            FALLBACK_DRAFTS_TO_REVIEW,
        ),
        automation_successful=_safe_count(
            db,
            _count_successful_automation,
            FALLBACK_AUTOMATION_SUCCESSFUL,
        ),
        automation_failed=automation_failed,
        automation_issues=automation_failed,
        automation_pending=_safe_count(
            db,
            _count_pending_automation,
            FALLBACK_AUTOMATION_PENDING,
        ),
        recent_business_activity=_safe_recent_business_activity(db, owner_id),
    )


def _safe_count(
    db: Session,
    query_builder: Callable[[Session], int],
    fallback: int,
) -> int:
    try:
        return query_builder(db)
    except SQLAlchemyError:
        db.rollback()
        return fallback


def _safe_recent_business_activity(
    db: Session,
    owner_id: str | None = None,
) -> list[DashboardBusinessActivity]:
    try:
        _ensure_leave_request_integration_columns(db)
        crm_statement = (
            select(CrmInteraction, CrmLead)
            .join(CrmLead, CrmInteraction.lead_id == CrmLead.id)
        )
        if owner_id is not None:
            crm_statement = crm_statement.where(CrmLead.assigned_to == owner_id)
        crm_statement = crm_statement.order_by(
            CrmInteraction.interaction_date.desc()
        ).limit(5)
        crm_rows = db.execute(crm_statement).all()

        # L'activité congés / automatisations est transverse (niveau plateforme) :
        # on ne l'affiche qu'aux rôles à visibilité complète (admin/manager).
        # Un commercial ne voit que l'activité de ses propres leads.
        if owner_id is None:
            leave_statement = (
                select(LeaveRequest)
                .order_by(LeaveRequest.updated_at.desc())
                .limit(5)
            )
            leave_rows = db.scalars(leave_statement).all()

            workflow_statement = (
                select(WorkflowExecution)
                .order_by(WorkflowExecution.updated_at.desc())
                .limit(5)
            )
            workflow_rows = db.scalars(workflow_statement).all()
        else:
            leave_rows = []
            workflow_rows = []
    except SQLAlchemyError:
        db.rollback()
        return []

    activities: list[tuple[datetime, DashboardBusinessActivity]] = []

    activities.extend(
        (
            interaction.interaction_date,
            _to_business_activity(interaction, lead),
        )
        for interaction, lead in crm_rows
    )
    activities.extend(
        (
            _leave_activity_date(leave_request),
            _leave_to_business_activity(leave_request),
        )
        for leave_request in leave_rows
    )
    activities.extend(
        (
            _workflow_activity_date(workflow_execution),
            _workflow_to_business_activity(workflow_execution),
        )
        for workflow_execution in workflow_rows
    )

    return [
        activity
        for _, activity in sorted(
            activities,
            key=lambda item: item[0],
            reverse=True,
        )[:5]
    ]


def _count_crm_leads(db: Session, owner_id: str | None = None) -> int:
    statement = select(func.count()).select_from(CrmLead)
    if owner_id is not None:
        statement = statement.where(CrmLead.assigned_to == owner_id)
    return _scalar_count(db, statement)


def _count_leave_requests(db: Session) -> int:
    _ensure_leave_request_integration_columns(db)
    return _scalar_count(db, select(func.count()).select_from(LeaveRequest))


def _count_pending_approvals(db: Session) -> int:
    _ensure_leave_request_integration_columns(db)
    statement = select(func.count()).select_from(LeaveRequest).where(
        func.lower(LeaveRequest.status).in_(PENDING_MANAGER_STATUSES),
    )
    return _scalar_count(db, statement)


def _count_active_agents(db: Session) -> int:
    active_statement = select(func.count(func.distinct(AgentRun.agent_id))).where(
        func.lower(AgentRun.status).in_(["running", "queued"]),
    )
    active_agents = _scalar_count(db, active_statement)

    if active_agents > 0:
        return active_agents

    known_agents_statement = select(func.count(func.distinct(AgentRun.agent_id)))
    return _scalar_count(db, known_agents_statement)


def _count_hot_leads(db: Session, owner_id: str | None = None) -> int:
    statement = select(func.count()).select_from(CrmLead).where(
        or_(
            func.lower(CrmLead.priority) == "high",
            func.lower(CrmLead.status) == "hot",
            CrmLead.lead_score >= 80,
        ),
    )
    if owner_id is not None:
        statement = statement.where(CrmLead.assigned_to == owner_id)
    return _scalar_count(db, statement)


def _count_prospects(db: Session, owner_id: str | None = None) -> int:
    statement = select(func.count()).select_from(CrmLead).where(
        func.lower(CrmLead.customer_status) == "prospect",
    )
    if owner_id is not None:
        statement = statement.where(CrmLead.assigned_to == owner_id)
    return _scalar_count(db, statement)


def _count_customers(db: Session, owner_id: str | None = None) -> int:
    statement = select(func.count()).select_from(CrmLead).where(
        func.lower(CrmLead.customer_status) == "customer",
    )
    if owner_id is not None:
        statement = statement.where(CrmLead.assigned_to == owner_id)
    return _scalar_count(db, statement)


def _count_drafts_to_review(db: Session, owner_id: str | None = None) -> int:
    statement = select(func.count()).select_from(CrmEmailDraft)
    if owner_id is not None:
        statement = statement.join(
            CrmLead, CrmEmailDraft.lead_id == CrmLead.id
        ).where(CrmLead.assigned_to == owner_id)
    statement = statement.where(
        func.lower(CrmEmailDraft.status).in_(["draft_generated", "edited", "reviewed"]),
    )
    return _scalar_count(db, statement)


def _count_successful_automation(db: Session) -> int:
    today_start = datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    statement = select(func.count()).select_from(WorkflowExecution).where(
        func.lower(WorkflowExecution.status).in_(["success", "completed"]),
        or_(
            WorkflowExecution.started_at >= today_start,
            and_(
                WorkflowExecution.started_at.is_(None),
                WorkflowExecution.created_at >= today_start,
            ),
        ),
    )
    return _scalar_count(db, statement)


def _count_failed_automation(db: Session) -> int:
    statement = select(func.count()).select_from(WorkflowExecution).where(
        func.lower(WorkflowExecution.status).in_(["failed", "error"]),
    )
    return _scalar_count(db, statement)


def _count_pending_automation(db: Session) -> int:
    statement = select(func.count()).select_from(WorkflowExecution).where(
        func.lower(WorkflowExecution.status).in_(["pending", "running", "queued"]),
    )
    return _scalar_count(db, statement)


def _scalar_count(db: Session, statement: object) -> int:
    return int(db.scalar(statement) or 0)


def _to_business_activity(
    interaction: CrmInteraction,
    lead: CrmLead,
) -> DashboardBusinessActivity:
    title = _activity_title(interaction)

    return DashboardBusinessActivity(
        title=title,
        description=_activity_description(title, interaction, lead),
        time=_format_activity_time(interaction.interaction_date),
        tone=_activity_tone(title),
    )


def _leave_activity_date(leave_request: LeaveRequest) -> datetime:
    return leave_request.reviewed_at or leave_request.updated_at or leave_request.created_at


def _leave_to_business_activity(leave_request: LeaveRequest) -> DashboardBusinessActivity:
    status = leave_request.status.lower()
    title = "Leave request submitted"
    description = "Waiting for manager review"
    tone = "orange"

    if status == "approved":
        title = "Leave request approved"
        description = "Manager decision completed"
        tone = "green"
    elif status == "rejected":
        title = "Leave request reviewed"
        description = "Manager decision completed"
        tone = "slate"

    return DashboardBusinessActivity(
        title=title,
        description=description,
        time=_format_activity_time(_leave_activity_date(leave_request)),
        tone=tone,
    )


def _workflow_activity_date(workflow_execution: WorkflowExecution) -> datetime:
    return (
        workflow_execution.finished_at
        or workflow_execution.started_at
        or workflow_execution.updated_at
        or workflow_execution.created_at
    )


def _workflow_to_business_activity(
    workflow_execution: WorkflowExecution,
) -> DashboardBusinessActivity:
    status = workflow_execution.status.lower()

    if status in ["failed", "error"]:
        return DashboardBusinessActivity(
            title="Automation needs attention",
            description=_business_process_label(workflow_execution),
            time=_format_activity_time(_workflow_activity_date(workflow_execution)),
            tone="red",
        )

    if status in ["success", "completed"]:
        return DashboardBusinessActivity(
            title="Automation completed",
            description=_business_process_label(workflow_execution),
            time=_format_activity_time(_workflow_activity_date(workflow_execution)),
            tone="green",
        )

    return DashboardBusinessActivity(
        title="Automation in progress",
        description=_business_process_label(workflow_execution),
        time=_format_activity_time(_workflow_activity_date(workflow_execution)),
        tone="blue",
    )


def _business_process_label(workflow_execution: WorkflowExecution) -> str:
    return workflow_execution.process or "Automation process"


def _activity_title(interaction: CrmInteraction) -> str:
    interaction_type = interaction.interaction_type
    summary = interaction.summary.lower()

    if interaction_type == "routing_decision" and _contains_conversion(summary):
        return "Customer converted"

    if interaction_type == "communication_draft" and _contains_welcome(summary):
        return "Welcome communication draft generated"

    if interaction_type == "communication_draft":
        return "Communication draft generated"

    if interaction_type == "scoring_completed":
        return "Lead scored as high priority"

    if interaction_type == "ai_analysis":
        return "AI analysis completed"

    if interaction_type == "lead_collected":
        return "Lead collected"

    return "CRM activity recorded"


def _activity_description(
    title: str,
    interaction: CrmInteraction,
    lead: CrmLead,
) -> str:
    lead_label = f"{lead.full_name} - {lead.company_name}"

    if title == "Welcome communication draft generated":
        return "Awaiting human review"

    if title == "Communication draft generated":
        return "Communication draft awaiting review"

    if title == "Lead scored as high priority":
        return f"{lead.company_name} - Score {lead.lead_score}"

    if "undefined" in interaction.summary.lower():
        return lead_label

    return lead_label


def _activity_tone(title: str) -> str:
    if title == "Customer converted":
        return "green"

    if "draft" in title.lower() or "AI" in title:
        return "blue"

    if "scored" in title.lower():
        return "orange"

    return "slate"


def _format_activity_time(value: datetime) -> str:
    now = datetime.now(timezone.utc)
    activity_date = value.date()

    if activity_date == now.date():
        return "Today"

    return value.strftime("%b %d")


def _contains_conversion(summary: str) -> bool:
    return any(
        phrase in summary
        for phrase in [
            "customer converted",
            "converted to customer",
            "converted by human validation",
            "prospect converted",
        ]
    )


def _contains_welcome(summary: str) -> bool:
    return any(
        phrase in summary
        for phrase in [
            "welcome",
            "bienvenue",
            "customer conversion",
            "after customer conversion",
        ]
    )
