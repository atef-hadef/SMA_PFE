ALL_PERMISSIONS = [
    "dashboard.view",
    "admin.users.manage",
    "admin.roles.manage",
    "crm.leads.view",
    "crm.leads.create",
    "crm.leads.update",
    "crm.interactions.create",
    "crm.drafts.generate",
    "crm.drafts.review",
    "crm.email.approve",
    "crm.email.send",
    "crm.customer.convert",
    "crm.vip.manage",
    "crm.tasks.view",
    "crm.tasks.manage",
    "crm.deals.view",
    "crm.deals.manage",
    "leave.request.create",
    "leave.request.view_own",
    "leave.request.view_all",
    "leave.request.approve",
    "leave.request.reject",
    "leave.request.hr_validate",
    "workflow.monitor.view",
    "workflow.executions.view",
    "workflow.executions.retry",
    "agents.view",
    "agents.run",
]


ROLE_DEFINITIONS = [
    {
        "id": "role_admin",
        "name": "Admin",
        "description": "Full platform administration access.",
        "is_system_role": True,
    },
    {
        "id": "role_manager",
        "name": "Manager",
        "description": "Manager access for CRM review, leave approvals, and monitoring.",
        "is_system_role": True,
    },
    {
        "id": "role_sales",
        "name": "Sales",
        "description": "Sales access for CRM lead and communication workflows.",
        "is_system_role": True,
    },
    {
        "id": "role_hr",
        "name": "HR",
        "description": "HR access for leave request validation and approvals.",
        "is_system_role": True,
    },
    {
        "id": "role_employee",
        "name": "Employee",
        "description": "Employee access for dashboard and own leave requests.",
        "is_system_role": True,
    },
    {
        "id": "role_ai_supervisor",
        "name": "AI Supervisor",
        "description": "AI and workflow supervision access.",
        "is_system_role": True,
    },
]


ROLE_PERMISSIONS = {
    "role_admin": ALL_PERMISSIONS,
    "role_manager": [
        "dashboard.view",
        "crm.leads.view",
        "crm.interactions.create",
        "crm.drafts.review",
        "crm.email.approve",
        "crm.customer.convert",
        "crm.tasks.view",
        "crm.tasks.manage",
        "crm.deals.view",
        "crm.deals.manage",
        "leave.request.view_all",
        "leave.request.approve",
        "leave.request.reject",
        "workflow.monitor.view",
        "workflow.executions.view",
        "agents.view",
    ],
    "role_sales": [
        "dashboard.view",
        "crm.leads.view",
        "crm.leads.create",
        "crm.leads.update",
        "crm.interactions.create",
        "crm.drafts.generate",
        "crm.drafts.review",
        "crm.email.send",
        "crm.tasks.view",
        "crm.tasks.manage",
        "crm.deals.view",
        "crm.deals.manage",
        "leave.request.create",
        "leave.request.view_own",
    ],
    "role_hr": [
        "dashboard.view",
        "leave.request.view_all",
        "leave.request.approve",
        "leave.request.reject",
        "leave.request.hr_validate",
    ],
    "role_employee": [
        "dashboard.view",
        "leave.request.create",
        "leave.request.view_own",
    ],
    "role_ai_supervisor": [
        "dashboard.view",
        "workflow.monitor.view",
        "workflow.executions.view",
        "workflow.executions.retry",
        "agents.view",
        "agents.run",
    ],
}


# Rôles avec visibilité CRM complète (pas d'isolation par propriétaire).
CRM_FULL_VISIBILITY_ROLE_IDS = {"role_admin", "role_manager"}


def crm_scoped_owner_id(current_user) -> str | None:
    """Id propriétaire auquel un commercial (role_sales) est restreint.

    Renvoie None pour les rôles à visibilité complète (admin/manager) et pour
    les appelants internes/non authentifiés (current_user=None) -> accès complet.
    Sert à appliquer l'isolation par commercial sur leads, tâches et deals.
    """
    if current_user is None:
        return None
    if getattr(current_user, "role_id", None) in CRM_FULL_VISIBILITY_ROLE_IDS:
        return None
    return getattr(current_user, "id", None)
