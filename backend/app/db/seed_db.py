from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.permissions import ROLE_DEFINITIONS, ROLE_PERMISSIONS
from app.core.security import hash_password
from app.models import (
    AgentRun,
    CrmDeal,
    CrmInteraction,
    CrmLead,
    CrmTask,
    LeaveAllocation,
    LeaveRequest,
    Role,
    RolePermission,
    User,
    WorkflowExecution,
)
from app.services.leave_service import _ensure_leave_request_integration_columns


ROLES = ROLE_DEFINITIONS
DEV_TEST_PASSWORD = "TacTic2026!"

USERS = [
    {
        "id": "user_001",
        "full_name": "Admin",
        "email": "admin@tac-tic.tn",
        "role_id": "role_admin",
        "status": "active",
        "job_title": "Directeur Général",
        "department": "Direction",
    },
    {
        "id": "user_002",
        "full_name": "Manager Commercial",
        "email": "hadefatef1@gmail.com",
        "role_id": "role_manager",
        "status": "active",
        "job_title": "Manager Commercial",
        "department": "Commercial",
    },
    {
        "id": "user_010",
        "full_name": "Commercial 1",
        "email": "benhadefatef@gmail.com",
        "role_id": "role_sales",
        "status": "active",
        "job_title": "Conseiller Commercial",
        "department": "Commercial",
    },
    {
        "id": "user_020",
        "full_name": "Commercial 2",
        "email": "commercial2@tac-tic.tn",
        "role_id": "role_sales",
        "status": "active",
        "job_title": "Conseillère Commerciale",
        "department": "Commercial",
    },
    {
        "id": "user_030",
        "full_name": "Commercial 3",
        "email": "commercial3@tac-tic.tn",
        "role_id": "role_sales",
        "status": "active",
        "job_title": "Conseiller Commercial",
        "department": "Commercial",
    },
    {
        "id": "user_040",
        "full_name": "HR",
        "email": "hr@tac-tic.tn",
        "role_id": "role_hr",
        "status": "active",
        "job_title": "HR Officer",
        "department": "Human Resources",
    },
    {
        "id": "user_050",
        "full_name": "AI Supervisor",
        "email": "ai.supervisor@tac-tic.tn",
        "role_id": "role_ai_supervisor",
        "status": "active",
        "job_title": "AI Supervisor",
        "department": "Automation",
    },
]

# Module Congés STANDALONE — allocations annuelles par employé.
EMPLOYEES_TO_SEED = [
    "user_010",  # Commercial 1
    "user_020",  # Commercial 2
    "user_030",  # Commercial 3
    "user_040",  # FlowPilot HR
    "user_050",  # AI Supervisor
]

DEFAULT_LEAVE_ALLOCATIONS = {
    "vacation": 25,
    "sick": 15,
    "personal": 5,
    "rtt": 10,
}

ALLOCATION_YEAR = 2026
ALLOCATION_CREATED_BY = "user_001"

LEAVE_REQUESTS = [
    {
        "id": "leave_001",
        "user_id": "user_010",
        "leave_type": "Annual Leave",
        "start_date": date(2026, 5, 3),
        "end_date": date(2026, 5, 5),
        "reason": "Family event",
        "status": "pending",
    },
    {
        "id": "leave_002",
        "user_id": "user_010",
        "leave_type": "Sick Leave",
        "start_date": date(2026, 4, 20),
        "end_date": date(2026, 4, 21),
        "reason": "Medical appointment",
        "status": "approved",
        "reviewed_by": "user_020",
        "reviewed_at": datetime(2026, 4, 22, 9, 0, tzinfo=timezone.utc),
        "decision_comment": "Approved by manager",
    },
]

CRM_LEADS = [
    {
        "id": "lead_001",
        "full_name": "Northwind Logistics",
        "company_name": "Northwind Group",
        "email": "ops@northwind.com",
        "phone": "+216 00 000 000",
        "source": "web",
        "status": "hot",
        "lead_score": 94,
        "sentiment": "positive",
        "urgency": "high",
        "intention": "purchase-ready",
        "message": "We are interested in an automation solution for our sales process.",
        "ai_summary": "High-value lead with strong buying intent and positive sentiment.",
        "recommended_action": (
            "Assign to senior sales representative and send personalized follow-up."
        ),
        "customer_status": "prospect",
        "last_contact_at": datetime(2026, 4, 27, 11, 15, tzinfo=timezone.utc),
        "next_action": "Schedule discovery call",
        "product_service": "AI CRM Automation",
        "estimated_value": 15000,
        "priority": "high",
        "customer_category": "VIP",
        "location": "Tunis, Tunisia",
        "is_active": True,
        "owner_user_id": "user_010",
        "assigned_to": "user_010",
        "notes": "Supervisor-aligned CRM sample for a high-value automation prospect.",
    },
    {
        "id": "lead_002",
        "full_name": "Atlas Retail",
        "company_name": "Atlas Retail Group",
        "email": "contact@atlas-retail.com",
        "phone": "+216 11 111 111",
        "source": "referral",
        "status": "warm",
        "lead_score": 72,
        "sentiment": "neutral",
        "urgency": "medium",
        "intention": "evaluation",
        "message": "We are comparing automation tools for CRM and customer support.",
        "ai_summary": "Medium-priority lead currently evaluating options.",
        "recommended_action": "Send product comparison and schedule discovery call.",
        "customer_status": "lead",
        "last_contact_at": datetime(2026, 4, 26, 14, 30, tzinfo=timezone.utc),
        "next_action": "Send product comparison",
        "product_service": "CRM Workflow Automation",
        "estimated_value": 8000,
        "priority": "medium",
        "customer_category": "standard",
        "location": "Sfax, Tunisia",
        "is_active": True,
        "owner_user_id": "user_020",
        "assigned_to": "user_020",
        "notes": "Needs comparison material before a formal discovery call.",
    },
    {
        "id": "lead_003",
        "full_name": "Medina Services",
        "company_name": "Medina Services",
        "email": "hello@medina-services.com",
        "phone": "+216 22 222 222",
        "source": "email",
        "status": "cold",
        "lead_score": 38,
        "sentiment": "neutral",
        "urgency": "low",
        "intention": "information-gathering",
        "message": "Please send information about your automation platform.",
        "ai_summary": "Early-stage lead with low urgency.",
        "recommended_action": "Add to nurture campaign.",
        "customer_status": "lead",
        "last_contact_at": datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc),
        "next_action": "Add to nurturing campaign",
        "product_service": "Automation Consulting",
        "estimated_value": 2500,
        "priority": "low",
        "customer_category": "new",
        "location": "Sousse, Tunisia",
        "is_active": True,
        "owner_user_id": "user_030",
        "assigned_to": "user_030",
        "notes": "Early-stage lead suitable for automated nurturing.",
    },
]

CRM_INTERACTIONS = [
    {
        "id": "interaction_001",
        "lead_id": "lead_001",
        "interaction_type": "email_received",
        "channel": "email",
        "summary": "Prospect requested information about sales automation.",
        "interaction_date": datetime(2026, 4, 27, 11, 15, tzinfo=timezone.utc),
        "created_by": "user_010",
    },
    {
        "id": "interaction_002",
        "lead_id": "lead_001",
        "interaction_type": "ai_analysis",
        "channel": "n8n",
        "summary": "Lead analyzed as positive sentiment, high urgency, purchase-ready.",
        "interaction_date": datetime(2026, 4, 27, 11, 20, tzinfo=timezone.utc),
        "created_by": "user_010",
    },
    {
        "id": "interaction_003",
        "lead_id": "lead_002",
        "interaction_type": "follow_up_planned",
        "channel": "sales",
        "summary": (
            "Product comparison should be sent before scheduling a discovery call."
        ),
        "interaction_date": datetime(2026, 4, 27, 9, 0, tzinfo=timezone.utc),
        "created_by": "user_020",
    },
]

CRM_SUPERVISOR_FIELDS = [
    "phone",
    "customer_status",
    "last_contact_at",
    "next_action",
    "product_service",
    "estimated_value",
    "priority",
    "customer_category",
    "location",
    "is_active",
    "notes",
]

WORKFLOW_EXECUTIONS = [
    {
        "id": "exec_001",
        "workflow_name": "Leave Request Approval Flow",
        "process": "Leave Management",
        "related_object_type": "leave_request",
        "related_object_id": "leave_001",
        "trigger_source": "Employee Portal",
        "status": "success",
        "started_at": datetime(2026, 4, 27, 9, 30, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 4, 27, 9, 31, 15, tzinfo=timezone.utc),
        "duration_seconds": 75,
        "agent_name": "Leave Validation Agent",
        "input_summary": "Employee submitted annual leave request.",
        "output_summary": "Leave request validated and sent for manager approval.",
        "result_summary": "Leave request validation completed successfully.",
        "error_message": None,
    },
    {
        "id": "exec_002",
        "workflow_name": "CRM Lead Scoring Flow",
        "process": "CRM",
        "related_object_type": "crm_lead",
        "related_object_id": "lead_001",
        "trigger_source": "CRM Lead Intake",
        "status": "failed",
        "started_at": datetime(2026, 4, 27, 9, 40, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 4, 27, 9, 40, 45, tzinfo=timezone.utc),
        "duration_seconds": 45,
        "agent_name": "Lead Scoring Agent",
        "input_summary": "CRM lead message submitted for scoring.",
        "output_summary": "Lead scoring failed before final routing.",
        "result_summary": "Workflow failed during scoring validation.",
        "error_message": "Scoring confidence threshold was not reached.",
    },
    {
        "id": "exec_003",
        "workflow_name": "Agent Manual Run Flow",
        "process": "AI Agents",
        "related_object_type": "agent_run",
        "related_object_id": "run_001",
        "trigger_source": "AI Agent Center",
        "status": "queued",
        "duration_seconds": None,
        "agent_name": "Lead Scoring Agent",
        "input_summary": "Manual test run requested from AI Agent Center.",
        "output_summary": "Awaiting execution.",
        "result_summary": "Agent run queued.",
        "error_message": None,
    },
]

AGENT_RUNS = [
    {
        "id": "run_001",
        "agent_id": "agent_lead_scoring",
        "agent_name": "Lead Scoring Agent",
        "process": "CRM",
        "workflow_execution_id": "exec_002",
        "requested_by": "user_030",
        "requested_at": datetime(2026, 4, 27, 9, 40, tzinfo=timezone.utc),
        "status": "failed",
        "started_at": datetime(2026, 4, 27, 9, 40, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 4, 27, 9, 40, 45, tzinfo=timezone.utc),
        "input_summary": "Lead profile and message analyzed.",
        "output_summary": "Scoring failed because confidence was too low.",
        "error_message": "Scoring confidence threshold was not reached.",
    },
    {
        "id": "run_002",
        "agent_id": "agent_leave_validation",
        "agent_name": "Leave Validation Agent",
        "process": "Leave Management",
        "workflow_execution_id": "exec_001",
        "requested_by": "user_020",
        "requested_at": datetime(2026, 4, 27, 9, 30, tzinfo=timezone.utc),
        "status": "success",
        "started_at": datetime(2026, 4, 27, 9, 30, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 4, 27, 9, 31, 15, tzinfo=timezone.utc),
        "input_summary": "Leave request balance and conflict data checked.",
        "output_summary": "Request validation completed successfully.",
        "error_message": None,
    },
    {
        "id": "run_003",
        "agent_id": "agent_lead_scoring",
        "agent_name": "Lead Scoring Agent",
        "process": "CRM",
        "workflow_execution_id": "exec_003",
        "requested_by": "user_030",
        "requested_at": datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc),
        "status": "queued",
        "input_summary": "Manual scoring test requested.",
        "output_summary": "Awaiting execution.",
        "error_message": None,
    },
]


def seed_roles(db: Session) -> None:
    for role_data in ROLES:
        role = db.get(Role, role_data["id"])
        if role:
            role.name = role_data["name"]
            role.description = role_data["description"]
            role.is_system_role = role_data["is_system_role"]
            continue

        db.add(Role(**role_data))


def seed_role_permissions(db: Session) -> None:
    for role_id, permissions in ROLE_PERMISSIONS.items():
        for permission_code in permissions:
            permission_id = f"{role_id}_{permission_code}".replace(".", "_")

            if db.get(RolePermission, permission_id):
                continue

            db.add(
                RolePermission(
                    id=permission_id,
                    role_id=role_id,
                    permission_code=permission_code,
                )
            )


def seed_users(db: Session) -> None:
    for user_data in USERS:
        user = db.get(User, user_data["id"])
        if user:
            user.full_name = user_data["full_name"]
            user.email = user_data["email"]
            user.role_id = user_data["role_id"]
            user.status = user_data["status"]
            user.job_title = user_data["job_title"]
            user.department = user_data["department"]
            # Force the rehash so existing databases pick up the TacTic2026!
            # test password (the previous "only if missing" guard kept the old
            # FlowPilot@123 hash on already-seeded rows).
            user.password_hash = hash_password(DEV_TEST_PASSWORD)
            continue

        db.add(User(**user_data, password_hash=hash_password(DEV_TEST_PASSWORD)))


def seed_leave_allocations(db: Session) -> None:
    for employee_id in EMPLOYEES_TO_SEED:
        for leave_type, allocated_days in DEFAULT_LEAVE_ALLOCATIONS.items():
            allocation_id = f"alloc_{employee_id}_{leave_type}_{ALLOCATION_YEAR}"
            if db.get(LeaveAllocation, allocation_id):
                continue

            db.add(
                LeaveAllocation(
                    id=allocation_id,
                    employee_id=employee_id,
                    year=ALLOCATION_YEAR,
                    leave_type=leave_type,
                    allocated_days=allocated_days,
                    created_by=ALLOCATION_CREATED_BY,
                )
            )


def seed_leave_requests(db: Session) -> None:
    _ensure_leave_request_integration_columns(db)
    for leave_request_data in LEAVE_REQUESTS:
        if db.get(LeaveRequest, leave_request_data["id"]):
            continue

        db.add(LeaveRequest(**leave_request_data))


def seed_crm_leads(db: Session) -> None:
    for lead_data in CRM_LEADS:
        lead = db.get(CrmLead, lead_data["id"])

        if lead:
            for field_name in CRM_SUPERVISOR_FIELDS:
                setattr(lead, field_name, lead_data[field_name])

            continue

        db.add(CrmLead(**lead_data))


def seed_crm_interactions(db: Session) -> None:
    for interaction_data in CRM_INTERACTIONS:
        if db.get(CrmInteraction, interaction_data["id"]):
            continue

        db.add(CrmInteraction(**interaction_data))


CRM_TASKS = [
    {
        "id": "task_001",
        "lead_id": "lead_002",
        "owner_user_id": "user_020",
        "title": "Envoyer la comparaison produit à Atlas Retail",
        "description": "Préparer un PDF comparatif avant la prochaine réunion.",
        "due_date": datetime(2026, 5, 22, 9, 0, tzinfo=timezone.utc),
        "status": "pending",
        "priority": "high",
        "created_by": "user_020",
    },
    {
        "id": "task_002",
        "lead_id": "lead_003",
        "owner_user_id": "user_030",
        "title": "Planifier un appel de découverte avec Medina Services",
        "description": "Lead froid, premier contact à organiser cette semaine.",
        "due_date": datetime(2026, 5, 25, 14, 0, tzinfo=timezone.utc),
        "status": "pending",
        "priority": "medium",
        "created_by": "user_030",
    },
    {
        "id": "task_003",
        "lead_id": "lead_001",
        "owner_user_id": "user_010",
        "title": "Préparer la proposition commerciale pour Northwind",
        "description": "Demande validée — préparer offre cadrée pour la semaine.",
        "due_date": datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
        "status": "pending",
        "priority": "high",
        "created_by": "user_010",
    },
]


CRM_DEALS = [
    {
        "id": "deal_001",
        "lead_id": "lead_001",
        "owner_user_id": "user_010",
        "title": "Northwind Logistics — AI CRM Automation",
        "stage": "negotiation",
        "previous_stage": "proposal",
        "amount": 15000,
        "currency": "EUR",
        "probability_percent": 60,
        "expected_close_date": datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        "notes": "Négociation finale sur le périmètre et le calendrier de mise en route.",
    },
    {
        "id": "deal_002",
        "lead_id": "lead_002",
        "owner_user_id": "user_020",
        "title": "Atlas Retail — CRM Workflow Automation",
        "stage": "discovery",
        "previous_stage": None,
        "amount": 8000,
        "currency": "EUR",
        "probability_percent": 20,
        "expected_close_date": datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
        "notes": "Premier diagnostic en cours, comparatif produit attendu.",
    },
]


def seed_crm_tasks(db: Session) -> None:
    for task_data in CRM_TASKS:
        if db.get(CrmTask, task_data["id"]):
            continue
        db.add(CrmTask(**task_data))


def seed_crm_deals(db: Session) -> None:
    for deal_data in CRM_DEALS:
        if db.get(CrmDeal, deal_data["id"]):
            continue
        db.add(CrmDeal(**deal_data))


def seed_workflow_executions(db: Session) -> None:
    for execution_data in WORKFLOW_EXECUTIONS:
        if db.get(WorkflowExecution, execution_data["id"]):
            continue

        db.add(WorkflowExecution(**execution_data))


def seed_agent_runs(db: Session) -> None:
    for run_data in AGENT_RUNS:
        if db.get(AgentRun, run_data["id"]):
            continue

        db.add(AgentRun(**run_data))


def seed_database() -> None:
    db = SessionLocal()

    try:
        seed_roles(db)
        db.flush()
        seed_role_permissions(db)
        seed_users(db)
        db.flush()
        seed_leave_allocations(db)
        seed_leave_requests(db)
        seed_crm_leads(db)
        db.flush()
        seed_crm_interactions(db)
        seed_crm_tasks(db)
        seed_crm_deals(db)
        seed_workflow_executions(db)
        db.flush()
        seed_agent_runs(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
