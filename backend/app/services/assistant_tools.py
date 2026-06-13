"""
assistant_tools.py — Read-only analytics tools for the FlowPilot AI assistant.

V1 MVP scope: CRM process + Leave Request process only.

Internal tools for workflow/agent analytics are kept as private helpers
(_get_workflow_analytics / _get_agent_analytics) so the Workflow Monitoring
and AI Agent Center pages are not affected. They are simply not called from
the user-facing assistant in V1.

Rules:
  - Read-only: no INSERT / UPDATE / DELETE.
  - No n8n calls, no OpenRouter calls.
  - Graceful degradation: every query is wrapped in try/except.
  - All user-facing text is in French.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    AgentRun,
    CrmEmailDraft,
    CrmLead,
    LeaveRequest,
    WorkflowExecution,
)
from app.schemas.assistant import AssistantSource, SuggestedAction, VisualizationData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared return type
# ---------------------------------------------------------------------------
class ToolResult(TypedDict):
    summary: str
    metrics: dict[str, Any]
    visualizations: list[VisualizationData]
    sources: list[AssistantSource]
    suggested_actions: list[SuggestedAction]


# ---------------------------------------------------------------------------
# Low-level DB helpers
# ---------------------------------------------------------------------------

def _safe_scalar(db: Session, statement: Any, fallback: int = 0) -> int:
    try:
        return int(db.scalar(statement) or fallback)
    except SQLAlchemyError:
        db.rollback()
        return fallback


def _safe_scalars(db: Session, statement: Any) -> list[Any]:
    try:
        return list(db.scalars(statement).all())
    except SQLAlchemyError:
        db.rollback()
        return []


def _count_by_field(
    db: Session,
    model: Any,
    field: Any,
) -> list[tuple[str, int]]:
    """Return [(label, count), ...] grouped by field, ordered by count desc."""
    try:
        stmt = (
            select(field, func.count().label("cnt"))
            .select_from(model)
            .group_by(field)
            .order_by(func.count().desc())
        )
        rows = db.execute(stmt).all()
        return [(str(r[0]) if r[0] is not None else "Inconnu", int(r[1])) for r in rows]
    except SQLAlchemyError:
        db.rollback()
        return []


# ---------------------------------------------------------------------------
# Suggested-action builder — only emit actions when count > 0
# ---------------------------------------------------------------------------

def _crm_actions(hot_leads: int, drafts_pending: int) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []
    if hot_leads > 0:
        actions.append(
            SuggestedAction(
                label="Voir les leads haute priorité",
                action_type="navigate",
                payload={"route": "/crm-leads"},
            )
        )
    if drafts_pending > 0:
        actions.append(
            SuggestedAction(
                label="Valider les brouillons d'e-mail",
                action_type="navigate",
                payload={"route": "/crm-leads"},
            )
        )
    # Always offer the pipeline view
    actions.append(
        SuggestedAction(
            label="Ouvrir le pipeline CRM",
            action_type="navigate",
            payload={"route": "/crm-leads"},
        )
    )
    return actions


def _leave_actions(pending: int) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []
    if pending > 0:
        actions.append(
            SuggestedAction(
                label="Approuver les congés en attente",
                action_type="navigate",
                payload={"route": "/manager-approvals"},
            )
        )
    actions.append(
        SuggestedAction(
            label="Voir toutes les demandes de congé",
            action_type="navigate",
            payload={"route": "/leave-request"},
        )
    )
    return actions


# ---------------------------------------------------------------------------
# 1. CRM analytics  (user-facing)
# ---------------------------------------------------------------------------

def get_crm_analytics(db: Session) -> ToolResult:
    """Leads by status, by priority, conversion rate, top-priority leads table."""

    total = _safe_scalar(db, select(func.count()).select_from(CrmLead))
    hot = _safe_scalar(
        db,
        select(func.count()).select_from(CrmLead).where(
            func.lower(CrmLead.priority) == "high"
        ),
    )
    customers = _safe_scalar(
        db,
        select(func.count()).select_from(CrmLead).where(
            func.lower(CrmLead.customer_status) == "customer"
        ),
    )
    prospects = _safe_scalar(
        db,
        select(func.count()).select_from(CrmLead).where(
            func.lower(CrmLead.customer_status) == "prospect"
        ),
    )
    leads_only = _safe_scalar(
        db,
        select(func.count()).select_from(CrmLead).where(
            func.lower(CrmLead.customer_status) == "lead"
        ),
    )
    drafts_pending = _safe_scalar(
        db,
        select(func.count()).select_from(CrmEmailDraft).where(
            func.lower(CrmEmailDraft.status).in_(
                ["draft_generated", "edited", "reviewed"]
            )
        ),
    )

    conversion_rate = round((customers / total * 100), 1) if total > 0 else 0.0

    by_status = _count_by_field(db, CrmLead, CrmLead.status)
    by_priority = _count_by_field(db, CrmLead, CrmLead.priority)

    top_leads_rows = _safe_scalars(
        db,
        select(CrmLead)
        .where(func.lower(CrmLead.priority) == "high")
        .order_by(CrmLead.lead_score.desc())
        .limit(5),
    )
    top_leads_data = [
        {
            "Nom": lead.full_name,
            "Entreprise": lead.company_name,
            "Statut": lead.status,
            "Score": lead.lead_score,
            "Priorité": lead.priority or "—",
        }
        for lead in top_leads_rows
    ]

    # --- summary (natural French, avoids "0/0" patterns) ---
    if total == 0:
        summary = "Aucun lead enregistré dans le CRM pour le moment."
    else:
        parts = [f"Pipeline CRM : {total} lead(s) au total."]
        if hot > 0:
            parts.append(f"{hot} lead(s) haute priorité.")
        if prospects > 0:
            parts.append(f"{prospects} prospect(s).")
        if customers > 0:
            parts.append(f"{customers} client(s) — taux de conversion : {conversion_rate} %.")
        if drafts_pending > 0:
            parts.append(f"{drafts_pending} brouillon(s) d'e-mail en attente de validation.")
        summary = " ".join(parts)

    visualizations: list[VisualizationData] = []

    if by_status:
        visualizations.append(
            VisualizationData(
                type="bar_chart",
                title="Leads par statut",
                description="Répartition des leads selon leur statut actuel.",
                data={
                    "xKey": "statut",
                    "yKey": "nombre",
                    "data": [{"statut": s, "nombre": c} for s, c in by_status],
                },
            )
        )

    if by_priority:
        visualizations.append(
            VisualizationData(
                type="pie_chart",
                title="Leads par priorité",
                description="Distribution des leads selon leur niveau de priorité.",
                data={
                    "data": [{"name": p, "value": c} for p, c in by_priority],
                },
            )
        )

    if top_leads_data:
        visualizations.append(
            VisualizationData(
                type="table",
                title="Top leads haute priorité",
                description="Les 5 leads les mieux scorés parmi les priorités hautes.",
                data={"rows": top_leads_data},
            )
        )

    return ToolResult(
        summary=summary,
        metrics={
            "total_leads": total,
            "hot_leads": hot,
            "prospects": prospects,
            "customers": customers,
            "leads_only": leads_only,
            "conversion_rate_pct": conversion_rate,
            "drafts_pending_review": drafts_pending,
        },
        visualizations=visualizations,
        sources=[
            AssistantSource(
                title="Table crm_leads",
                source_type="database",
                reference="/api/crm/leads",
            ),
            AssistantSource(
                title="Table crm_email_drafts",
                source_type="database",
                reference="/api/crm/email-drafts",
            ),
        ],
        suggested_actions=_crm_actions(hot, drafts_pending),
    )


# ---------------------------------------------------------------------------
# 2. Leave request analytics  (user-facing)
# ---------------------------------------------------------------------------

def get_leave_analytics(db: Session) -> ToolResult:
    """Requests by status, pending count, approval/refusal counts, blocked reasons."""

    total = _safe_scalar(db, select(func.count()).select_from(LeaveRequest))
    pending = _safe_scalar(
        db,
        select(func.count()).select_from(LeaveRequest).where(
            func.lower(LeaveRequest.status).in_(["pending", "manager_review_required"])
        ),
    )
    approved = _safe_scalar(
        db,
        select(func.count()).select_from(LeaveRequest).where(
            func.lower(LeaveRequest.status) == "approved"
        ),
    )
    rejected = _safe_scalar(
        db,
        select(func.count()).select_from(LeaveRequest).where(
            func.lower(LeaveRequest.status) == "rejected"
        ),
    )
    rejected_by_policy = _safe_scalar(
        db,
        select(func.count()).select_from(LeaveRequest).where(
            func.lower(LeaveRequest.status) == "rejected_by_policy"
        ),
    )

    by_status = _count_by_field(db, LeaveRequest, LeaveRequest.status)
    by_type = _count_by_field(db, LeaveRequest, LeaveRequest.leave_type)

    blocked_rows = _safe_scalars(
        db,
        select(LeaveRequest)
        .where(func.lower(LeaveRequest.status) == "rejected_by_policy")
        .order_by(LeaveRequest.updated_at.desc())
        .limit(5),
    )
    blocked_data = [
        {
            "ID": r.id,
            "Type": r.leave_type,
            "Raison": (r.automation_summary or "Politique RH")[:80],
            "Statut": r.status,
        }
        for r in blocked_rows
    ]

    # --- summary (natural French) ---
    if total == 0:
        summary = "Aucune demande de congé enregistrée pour le moment."
    else:
        parts = [f"Congés : {total} demande(s) enregistrée(s)."]
        if pending > 0:
            parts.append(f"{pending} en attente d'approbation.")
        else:
            parts.append("Aucune demande en attente actuellement.")
        if approved > 0:
            parts.append(f"{approved} approuvée(s).")
        if rejected > 0:
            parts.append(f"{rejected} refusée(s).")
        if rejected_by_policy > 0:
            parts.append(f"{rejected_by_policy} bloquée(s) par politique RH.")
        summary = " ".join(parts)

    visualizations: list[VisualizationData] = []

    if by_status:
        visualizations.append(
            VisualizationData(
                type="bar_chart",
                title="Demandes de congé par statut",
                description="Répartition des demandes selon leur statut.",
                data={
                    "xKey": "statut",
                    "yKey": "nombre",
                    "data": [{"statut": s, "nombre": c} for s, c in by_status],
                },
            )
        )

    if by_type:
        visualizations.append(
            VisualizationData(
                type="pie_chart",
                title="Demandes par type de congé",
                description="Distribution des demandes selon le type de congé.",
                data={
                    "data": [{"name": t, "value": c} for t, c in by_type],
                },
            )
        )

    if blocked_data:
        visualizations.append(
            VisualizationData(
                type="table",
                title="Demandes bloquées par politique RH",
                description="Dernières demandes refusées automatiquement.",
                data={"rows": blocked_data},
            )
        )

    return ToolResult(
        summary=summary,
        metrics={
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "rejected_by_policy": rejected_by_policy,
        },
        visualizations=visualizations,
        sources=[
            AssistantSource(
                title="Table leave_requests",
                source_type="database",
                reference="/api/leave-requests",
            )
        ],
        suggested_actions=_leave_actions(pending),
    )


# ---------------------------------------------------------------------------
# 3. Business summary  (user-facing — CRM + Leave only)
# ---------------------------------------------------------------------------

def get_business_summary(db: Session) -> ToolResult:
    """
    Combined CRM + Leave snapshot for résumé / situation / priorités queries.
    Does NOT include workflow executions or agent runs.
    """

    # CRM counts
    crm_total = _safe_scalar(db, select(func.count()).select_from(CrmLead))
    hot_leads = _safe_scalar(
        db,
        select(func.count()).select_from(CrmLead).where(
            func.lower(CrmLead.priority) == "high"
        ),
    )
    prospects = _safe_scalar(
        db,
        select(func.count()).select_from(CrmLead).where(
            func.lower(CrmLead.customer_status) == "prospect"
        ),
    )
    customers = _safe_scalar(
        db,
        select(func.count()).select_from(CrmLead).where(
            func.lower(CrmLead.customer_status) == "customer"
        ),
    )
    drafts_pending = _safe_scalar(
        db,
        select(func.count()).select_from(CrmEmailDraft).where(
            func.lower(CrmEmailDraft.status).in_(
                ["draft_generated", "edited", "reviewed"]
            )
        ),
    )

    # Leave counts
    leave_total = _safe_scalar(db, select(func.count()).select_from(LeaveRequest))
    leave_pending = _safe_scalar(
        db,
        select(func.count()).select_from(LeaveRequest).where(
            func.lower(LeaveRequest.status).in_(["pending", "manager_review_required"])
        ),
    )
    leave_approved = _safe_scalar(
        db,
        select(func.count()).select_from(LeaveRequest).where(
            func.lower(LeaveRequest.status) == "approved"
        ),
    )
    leave_rejected = _safe_scalar(
        db,
        select(func.count()).select_from(LeaveRequest).where(
            func.lower(LeaveRequest.status).in_(["rejected", "rejected_by_policy"])
        ),
    )

    # Hot leads table (up to 5)
    hot_rows = _safe_scalars(
        db,
        select(CrmLead)
        .where(func.lower(CrmLead.priority) == "high")
        .order_by(CrmLead.lead_score.desc())
        .limit(5),
    )
    hot_data = [
        {
            "Nom": l.full_name,
            "Entreprise": l.company_name,
            "Score": l.lead_score,
            "Statut": l.status,
        }
        for l in hot_rows
    ]

    # Pending leave table (up to 5)
    pending_rows = _safe_scalars(
        db,
        select(LeaveRequest)
        .where(
            func.lower(LeaveRequest.status).in_(
                ["pending", "manager_review_required"]
            )
        )
        .order_by(LeaveRequest.created_at.asc())
        .limit(5),
    )
    pending_data = [
        {
            "ID": r.id,
            "Type": r.leave_type,
            "Début": str(r.start_date),
            "Fin": str(r.end_date),
            "Statut": r.status,
        }
        for r in pending_rows
    ]

    # Draft table (up to 5)
    draft_rows = _safe_scalars(
        db,
        select(CrmEmailDraft)
        .where(
            func.lower(CrmEmailDraft.status).in_(
                ["draft_generated", "edited", "reviewed"]
            )
        )
        .order_by(CrmEmailDraft.created_at.desc())
        .limit(5),
    )
    draft_data = [
        {
            "ID": d.id,
            "Type": d.draft_type,
            "Statut": d.status,
            "Sujet": (d.subject or "—")[:60],
        }
        for d in draft_rows
    ]

    # --- KPI table ---
    kpi_rows: list[dict[str, Any]] = [
        {"Indicateur": "Leads CRM", "Valeur": crm_total},
        {"Indicateur": "Leads haute priorité", "Valeur": hot_leads},
        {"Indicateur": "Prospects", "Valeur": prospects},
        {"Indicateur": "Clients", "Valeur": customers},
        {"Indicateur": "Brouillons à valider", "Valeur": drafts_pending},
        {"Indicateur": "Demandes de congé", "Valeur": leave_total},
        {"Indicateur": "Congés en attente", "Valeur": leave_pending},
        {"Indicateur": "Congés approuvés", "Valeur": leave_approved},
        {"Indicateur": "Congés refusés", "Valeur": leave_rejected},
    ]

    # --- summary (natural French, no "0/0" patterns) ---
    crm_parts: list[str] = []
    if crm_total == 0:
        crm_parts.append("Aucun lead CRM enregistré.")
    else:
        crm_parts.append(f"{crm_total} lead(s) CRM")
        if hot_leads > 0:
            crm_parts.append(f"dont {hot_leads} haute priorité")
        if prospects > 0:
            crm_parts.append(f"{prospects} prospect(s)")
        if customers > 0:
            crm_parts.append(f"{customers} client(s)")

    leave_parts: list[str] = []
    if leave_total == 0:
        leave_parts.append("Aucune demande de congé enregistrée.")
    else:
        if leave_pending > 0:
            leave_parts.append(f"{leave_pending} demande(s) de congé en attente d'approbation")
        else:
            leave_parts.append("Aucune demande de congé en attente actuellement")
        if leave_approved > 0:
            leave_parts.append(f"{leave_approved} approuvée(s)")
        if leave_rejected > 0:
            leave_parts.append(f"{leave_rejected} refusée(s)")

    draft_part = (
        f"{drafts_pending} brouillon(s) d'e-mail à valider." if drafts_pending > 0 else ""
    )

    summary_parts = [
        "Situation actuelle :",
        ", ".join(crm_parts) + "." if crm_parts else "",
        ", ".join(leave_parts) + "." if leave_parts else "",
        draft_part,
    ]
    summary = " ".join(p for p in summary_parts if p)

    # --- visualizations ---
    visualizations: list[VisualizationData] = [
        VisualizationData(
            type="table",
            title="Indicateurs clés — CRM & Congés",
            description="Snapshot en temps réel des deux processus métier principaux.",
            data={"rows": kpi_rows},
        )
    ]

    if hot_data:
        visualizations.append(
            VisualizationData(
                type="table",
                title="Leads haute priorité",
                description="Leads nécessitant une action commerciale immédiate.",
                data={"rows": hot_data},
            )
        )

    if pending_data:
        visualizations.append(
            VisualizationData(
                type="table",
                title="Demandes de congé en attente",
                description="Demandes nécessitant une décision managériale.",
                data={"rows": pending_data},
            )
        )

    if draft_data:
        visualizations.append(
            VisualizationData(
                type="table",
                title="Brouillons d'e-mail à valider",
                description="E-mails générés par l'IA en attente de validation humaine.",
                data={"rows": draft_data},
            )
        )

    # Conditional suggested actions
    suggested: list[SuggestedAction] = []
    if hot_leads > 0:
        suggested.append(
            SuggestedAction(
                label="Voir les leads haute priorité",
                action_type="navigate",
                payload={"route": "/crm-leads"},
            )
        )
    if leave_pending > 0:
        suggested.append(
            SuggestedAction(
                label="Approuver les congés en attente",
                action_type="navigate",
                payload={"route": "/manager-approvals"},
            )
        )
    if drafts_pending > 0:
        suggested.append(
            SuggestedAction(
                label="Valider les brouillons d'e-mail",
                action_type="navigate",
                payload={"route": "/crm-leads"},
            )
        )
    # Always offer the two main sections
    suggested.append(
        SuggestedAction(
            label="Ouvrir le CRM",
            action_type="navigate",
            payload={"route": "/crm-leads"},
        )
    )
    suggested.append(
        SuggestedAction(
            label="Voir les demandes de congé",
            action_type="navigate",
            payload={"route": "/leave-request"},
        )
    )

    return ToolResult(
        summary=summary,
        metrics={
            "crm_total": crm_total,
            "hot_leads": hot_leads,
            "prospects": prospects,
            "customers": customers,
            "drafts_pending": drafts_pending,
            "leave_total": leave_total,
            "leave_pending": leave_pending,
            "leave_approved": leave_approved,
            "leave_rejected": leave_rejected,
        },
        visualizations=visualizations,
        sources=[
            AssistantSource(
                title="Table crm_leads",
                source_type="database",
                reference="/api/crm/leads",
            ),
            AssistantSource(
                title="Table crm_email_drafts",
                source_type="database",
                reference="/api/crm/email-drafts",
            ),
            AssistantSource(
                title="Table leave_requests",
                source_type="database",
                reference="/api/leave-requests",
            ),
        ],
        suggested_actions=suggested,
    )


# ---------------------------------------------------------------------------
# Internal-only tools (NOT called from the user-facing assistant in V1)
# These remain available for future use or direct internal calls.
# ---------------------------------------------------------------------------

def _get_workflow_analytics(db: Session) -> ToolResult:
    """Internal — workflow execution analytics. Not exposed to assistant V1."""
    total = _safe_scalar(db, select(func.count()).select_from(WorkflowExecution))
    failed = _safe_scalar(
        db,
        select(func.count()).select_from(WorkflowExecution).where(
            func.lower(WorkflowExecution.status).in_(["failed", "error"])
        ),
    )
    success = _safe_scalar(
        db,
        select(func.count()).select_from(WorkflowExecution).where(
            func.lower(WorkflowExecution.status).in_(["success", "completed"])
        ),
    )
    running = _safe_scalar(
        db,
        select(func.count()).select_from(WorkflowExecution).where(
            func.lower(WorkflowExecution.status).in_(["running", "queued", "pending"])
        ),
    )
    success_rate = round((success / total * 100), 1) if total > 0 else 0.0
    summary = (
        f"Automatisations : {total} exécution(s). "
        f"{success} réussie(s), {failed} en échec, {running} en cours. "
        f"Taux de succès : {success_rate} %."
    )
    return ToolResult(
        summary=summary,
        metrics={"total": total, "success": success, "failed": failed, "running": running},
        visualizations=[],
        sources=[
            AssistantSource(
                title="Table workflow_executions",
                source_type="workflow",
                reference="/api/workflow-monitoring",
            )
        ],
        suggested_actions=[],
    )


def get_automation_health(db: Session) -> ToolResult:
    """Workflow execution health exposed to the assistant with RBAC in service layer."""
    result = _get_workflow_analytics(db)
    metrics = result["metrics"]
    result["visualizations"] = [
        VisualizationData(
            type="kpi",
            title="Automatisations réussies",
            data={
                "label": "Succès",
                "value": str(metrics.get("success", 0)),
                "detail": "Exécutions terminées avec succès",
            },
        ),
        VisualizationData(
            type="kpi",
            title="Automatisations en échec",
            data={
                "label": "Échecs",
                "value": str(metrics.get("failed", 0)),
                "detail": "Exécutions à surveiller",
            },
        ),
        VisualizationData(
            type="kpi",
            title="Automatisations en attente",
            data={
                "label": "En attente",
                "value": str(metrics.get("running", 0)),
                "detail": "Exécutions running / queued / pending",
            },
        ),
        VisualizationData(
            type="bar_chart",
            title="Santé des automatisations",
            description="Répartition des exécutions par état opérationnel.",
            data={
                "xKey": "statut",
                "yKey": "nombre",
                "data": [
                    {"statut": "Succès", "nombre": metrics.get("success", 0)},
                    {"statut": "Échecs", "nombre": metrics.get("failed", 0)},
                    {"statut": "En attente", "nombre": metrics.get("running", 0)},
                ],
            },
        ),
    ]
    result["suggested_actions"] = [
        SuggestedAction(
            label="Ouvrir le monitoring",
            action_type="navigate",
            payload={"route": "/workflow-monitoring"},
        )
    ]
    return result


def _get_agent_analytics(db: Session) -> ToolResult:
    """Internal — agent run analytics. Not exposed to assistant V2."""
    total = _safe_scalar(db, select(func.count()).select_from(AgentRun))
    failed = _safe_scalar(
        db,
        select(func.count()).select_from(AgentRun).where(
            func.lower(AgentRun.status) == "failed"
        ),
    )
    success = _safe_scalar(
        db,
        select(func.count()).select_from(AgentRun).where(
            func.lower(AgentRun.status) == "success"
        ),
    )
    success_rate = round((success / total * 100), 1) if total > 0 else 0.0
    summary = (
        f"Agents IA : {total} exécution(s). "
        f"{success} réussie(s), {failed} en échec. "
        f"Taux de succès : {success_rate} %."
    )
    return ToolResult(
        summary=summary,
        metrics={"total": total, "success": success, "failed": failed},
        visualizations=[],
        sources=[
            AssistantSource(
                title="Table agent_runs",
                source_type="agent",
                reference="/api/agents",
            )
        ],
        suggested_actions=[],
    )


# ===========================================================================
# V2 PRECISE TOOLS — one tool per intent
# ===========================================================================

# ---------------------------------------------------------------------------
# Shared nav actions (safe routes only)
# ---------------------------------------------------------------------------

_CRM_NAV = SuggestedAction(
    label="Ouvrir le pipeline CRM",
    action_type="navigate",
    payload={"route": "/crm-leads"},
)
_LEAVE_NAV = SuggestedAction(
    label="Voir les demandes de congé",
    action_type="navigate",
    payload={"route": "/leave-request"},
)
_APPROVALS_NAV = SuggestedAction(
    label="Gérer les approbations",
    action_type="navigate",
    payload={"route": "/manager-approvals"},
)
_CRM_SOURCE = AssistantSource(
    title="Table crm_leads",
    source_type="database",
    reference="/api/crm/leads",
)
_LEAVE_SOURCE = AssistantSource(
    title="Table leave_requests",
    source_type="database",
    reference="/api/leave-requests",
)
_DRAFT_SOURCE = AssistantSource(
    title="Table crm_email_drafts",
    source_type="database",
    reference="/api/crm/email-drafts",
)


# ---------------------------------------------------------------------------
# CRM — get_crm_summary
# ---------------------------------------------------------------------------

def get_crm_summary(db: Session) -> ToolResult:
    """Full CRM overview: totals, priority, status, conversion, drafts."""
    total = _safe_scalar(db, select(func.count()).select_from(CrmLead))
    hot = _safe_scalar(db, select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.priority) == "high"))
    prospects = _safe_scalar(db, select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.customer_status) == "prospect"))
    customers = _safe_scalar(db, select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.customer_status) == "customer"))
    drafts = _safe_scalar(db, select(func.count()).select_from(CrmEmailDraft).where(func.lower(CrmEmailDraft.status).in_(["draft_generated", "edited", "reviewed"])))
    conversion = round(customers / total * 100, 1) if total > 0 else 0.0
    by_status = _count_by_field(db, CrmLead, CrmLead.status)
    by_priority = _count_by_field(db, CrmLead, CrmLead.priority)
    top_rows = _safe_scalars(
        db,
        select(CrmLead)
        .where(func.lower(CrmLead.priority) == "high")
        .order_by(CrmLead.lead_score.desc())
        .limit(8),
    )
    top_data = [{"Nom": lead.full_name, "Entreprise": lead.company_name, "Score": lead.lead_score, "Statut": lead.status} for lead in top_rows]

    if total == 0:
        summary = "Aucun lead enregistré dans le CRM pour le moment."
    else:
        parts = [f"Analyse CRM complète : {total} lead(s) au total."]
        if hot > 0:
            parts.append(f"{hot} haute priorité.")
        if prospects > 0:
            parts.append(f"{prospects} prospect(s).")
        if customers > 0:
            parts.append(f"{customers} client(s) — taux de conversion : {conversion} %.")
        if drafts > 0:
            parts.append(f"{drafts} brouillon(s) à valider.")
        summary = " ".join(parts)

    vizs: list[VisualizationData] = []
    vizs.append(
        VisualizationData(
            type="table",
            title="Indicateurs clés CRM",
            description="Vue synthétique du pipeline commercial.",
            data={
                "rows": [
                    {"Indicateur": "Leads CRM", "Valeur": total},
                    {"Indicateur": "Leads haute priorité", "Valeur": hot},
                    {"Indicateur": "Prospects", "Valeur": prospects},
                    {"Indicateur": "Clients", "Valeur": customers},
                    {"Indicateur": "Brouillons à valider", "Valeur": drafts},
                    {"Indicateur": "Taux de conversion", "Valeur": conversion},
                ]
            },
        )
    )
    if by_status:
        vizs.append(VisualizationData(type="bar_chart", title="Leads par statut", description="Répartition des leads selon leur statut.", data={"xKey": "statut", "yKey": "nombre", "data": [{"statut": s, "nombre": c} for s, c in by_status]}))
    if by_priority:
        vizs.append(VisualizationData(type="pie_chart", title="Leads par priorité", description="Distribution des leads selon leur priorité.", data={"data": [{"name": p, "value": c} for p, c in by_priority]}))
    if top_data:
        vizs.append(VisualizationData(type="table", title="Leads haute priorité", description="Leads nécessitant une action commerciale.", data={"rows": top_data}))

    actions = [_CRM_NAV]
    if hot > 0:
        actions.insert(0, SuggestedAction(label=f"Voir les {hot} leads haute priorité", action_type="navigate", payload={"route": "/crm-leads"}))
    if drafts > 0:
        actions.insert(0, SuggestedAction(label="Valider les brouillons", action_type="navigate", payload={"route": "/crm-leads"}))

    return ToolResult(summary=summary, metrics={"total": total, "hot": hot, "prospects": prospects, "customers": customers, "conversion_pct": conversion, "drafts": drafts}, visualizations=vizs, sources=[_CRM_SOURCE, _DRAFT_SOURCE], suggested_actions=actions)


# ---------------------------------------------------------------------------
# CRM — get_crm_priority_analysis
# ---------------------------------------------------------------------------

def get_crm_priority_analysis(db: Session) -> ToolResult:
    """Leads grouped by priority level with top-priority table."""
    total = _safe_scalar(db, select(func.count()).select_from(CrmLead))
    by_priority = _count_by_field(db, CrmLead, CrmLead.priority)
    hot = next((c for p, c in by_priority if p and p.lower() == "high"), 0)
    medium = next((c for p, c in by_priority if p and p.lower() == "medium"), 0)
    low = next((c for p, c in by_priority if p and p.lower() == "low"), 0)

    top_rows = _safe_scalars(db, select(CrmLead).where(func.lower(CrmLead.priority) == "high").order_by(CrmLead.lead_score.desc()).limit(8))
    top_data = [{"Nom": l.full_name, "Entreprise": l.company_name, "Score": l.lead_score, "Statut": l.status} for l in top_rows]

    if total == 0:
        summary = "Aucun lead enregistré dans le CRM."
    elif hot == 0:
        summary = f"Aucun lead haute priorité parmi les {total} leads enregistrés."
    else:
        summary = f"Analyse des priorités CRM : {hot} lead(s) haute priorité, {medium} priorité moyenne, {low} priorité basse sur {total} au total."

    vizs: list[VisualizationData] = []
    if by_priority:
        vizs.append(VisualizationData(type="pie_chart", title="Leads par priorité", description="Distribution des leads selon leur niveau de priorité.", data={"data": [{"name": p, "value": c} for p, c in by_priority]}))
        vizs.append(VisualizationData(type="bar_chart", title="Leads par priorité (barres)", description="Comparaison des niveaux de priorité.", data={"xKey": "priorité", "yKey": "nombre", "data": [{"priorité": p, "nombre": c} for p, c in by_priority]}))
    if top_data:
        vizs.append(VisualizationData(type="table", title="Leads haute priorité", description="Leads les mieux scorés parmi les priorités hautes.", data={"rows": top_data}))

    actions = [_CRM_NAV]
    if hot > 0:
        actions.insert(0, SuggestedAction(label=f"Voir les {hot} leads haute priorité", action_type="navigate", payload={"route": "/crm-leads"}))

    return ToolResult(summary=summary, metrics={"total": total, "high": hot, "medium": medium, "low": low}, visualizations=vizs, sources=[_CRM_SOURCE], suggested_actions=actions)


# ---------------------------------------------------------------------------
# CRM — get_crm_status_distribution
# ---------------------------------------------------------------------------

def get_crm_status_distribution(db: Session) -> ToolResult:
    """Leads grouped by status (new, hot, warm, cold, etc.)."""
    total = _safe_scalar(db, select(func.count()).select_from(CrmLead))
    by_status = _count_by_field(db, CrmLead, CrmLead.status)
    by_customer_status = _count_by_field(db, CrmLead, CrmLead.customer_status)

    if total == 0:
        summary = "Aucun lead enregistré dans le CRM."
    else:
        top = by_status[:3]
        top_str = ", ".join(f"{c} {s}" for s, c in top)
        summary = f"Distribution des {total} leads par statut : {top_str}."

    vizs: list[VisualizationData] = []
    if by_status:
        vizs.append(VisualizationData(type="bar_chart", title="Leads par statut", description="Répartition des leads selon leur statut actuel.", data={"xKey": "statut", "yKey": "nombre", "data": [{"statut": s, "nombre": c} for s, c in by_status]}))
    if by_customer_status:
        vizs.append(VisualizationData(type="pie_chart", title="Leads par stade client", description="Répartition lead / prospect / client.", data={"data": [{"name": s, "value": c} for s, c in by_customer_status]}))

    return ToolResult(summary=summary, metrics={"total": total, "by_status": dict(by_status)}, visualizations=vizs, sources=[_CRM_SOURCE], suggested_actions=[_CRM_NAV])


# ---------------------------------------------------------------------------
# CRM — get_crm_conversion_analysis
# ---------------------------------------------------------------------------

def get_crm_conversion_analysis(db: Session) -> ToolResult:
    """Conversion funnel: leads → prospects → customers."""
    total = _safe_scalar(db, select(func.count()).select_from(CrmLead))
    leads_only = _safe_scalar(db, select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.customer_status) == "lead"))
    prospects = _safe_scalar(db, select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.customer_status) == "prospect"))
    customers = _safe_scalar(db, select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.customer_status) == "customer"))
    conversion_rate = round(customers / total * 100, 1) if total > 0 else 0.0
    prospect_rate = round(prospects / total * 100, 1) if total > 0 else 0.0

    if total == 0:
        summary = "Aucun lead enregistré — impossible de calculer le taux de conversion."
    else:
        summary = (
            f"Taux de conversion CRM : {conversion_rate} % ({customers} client(s) sur {total} leads). "
            f"{prospects} prospect(s) en cours ({prospect_rate} %). "
            f"{leads_only} lead(s) non encore qualifié(s)."
        )

    funnel_data = [
        {"Étape": "Leads", "Nombre": total},
        {"Étape": "Prospects", "Nombre": prospects},
        {"Étape": "Clients", "Nombre": customers},
    ]
    kpi_data = {"label": "Taux de conversion", "value": f"{conversion_rate} %", "detail": f"{customers} clients / {total} leads"}

    vizs: list[VisualizationData] = [
        VisualizationData(type="kpi", title="Taux de conversion CRM", description="Pourcentage de leads convertis en clients.", data=kpi_data),
        VisualizationData(type="bar_chart", title="Entonnoir de conversion", description="Leads → Prospects → Clients.", data={"xKey": "Étape", "yKey": "Nombre", "data": funnel_data}),
    ]

    return ToolResult(summary=summary, metrics={"total": total, "leads_only": leads_only, "prospects": prospects, "customers": customers, "conversion_rate_pct": conversion_rate}, visualizations=vizs, sources=[_CRM_SOURCE], suggested_actions=[_CRM_NAV])


# ---------------------------------------------------------------------------
# CRM — get_crm_followup_recommendations
# ---------------------------------------------------------------------------

def get_crm_followup_recommendations(db: Session) -> ToolResult:
    """Prospects and leads that need follow-up action."""
    rows = _safe_scalars(
        db,
        select(CrmLead)
        .where(
            func.lower(CrmLead.customer_status).in_(["lead", "prospect"]),
            CrmLead.is_active.is_(True),
        )
        .order_by(CrmLead.lead_score.desc())
        .limit(10),
    )
    data = [
        {
            "Nom": l.full_name,
            "Entreprise": l.company_name,
            "Score": l.lead_score,
            "Statut": l.status,
            "Prochaine action": (l.next_action or "À définir")[:60],
        }
        for l in rows
    ]
    count = len(data)

    if count == 0:
        summary = "Aucun prospect ou lead actif nécessitant une relance pour le moment."
    else:
        summary = f"{count} prospect(s) ou lead(s) actif(s) nécessitent une relance ou une action commerciale."

    vizs: list[VisualizationData] = []
    if data:
        vizs.append(VisualizationData(type="table", title="Prospects à relancer", description="Leads et prospects actifs classés par score.", data={"rows": data}))

    return ToolResult(summary=summary, metrics={"followup_count": count}, visualizations=vizs, sources=[_CRM_SOURCE], suggested_actions=[_CRM_NAV])


# ---------------------------------------------------------------------------
# CRM — get_crm_draft_review_summary
# ---------------------------------------------------------------------------

def get_crm_draft_review_summary(db: Session) -> ToolResult:
    """Email drafts pending human review/approval."""
    total_drafts = _safe_scalar(db, select(func.count()).select_from(CrmEmailDraft))
    pending = _safe_scalar(db, select(func.count()).select_from(CrmEmailDraft).where(func.lower(CrmEmailDraft.status).in_(["draft_generated", "edited", "reviewed"])))
    approved = _safe_scalar(db, select(func.count()).select_from(CrmEmailDraft).where(func.lower(CrmEmailDraft.status) == "approved"))
    sent = _safe_scalar(db, select(func.count()).select_from(CrmEmailDraft).where(func.lower(CrmEmailDraft.status) == "sent"))
    rejected = _safe_scalar(db, select(func.count()).select_from(CrmEmailDraft).where(func.lower(CrmEmailDraft.status) == "rejected"))

    pending_rows = _safe_scalars(db, select(CrmEmailDraft).where(func.lower(CrmEmailDraft.status).in_(["draft_generated", "edited", "reviewed"])).order_by(CrmEmailDraft.created_at.desc()).limit(8))
    pending_data = [{"ID": d.id[:12], "Type": d.draft_type, "Statut": d.status, "Sujet": (d.subject or "—")[:50]} for d in pending_rows]

    by_status = [("En attente", pending), ("Approuvés", approved), ("Envoyés", sent), ("Rejetés", rejected)]
    by_status = [(s, c) for s, c in by_status if c > 0]

    if total_drafts == 0:
        summary = "Aucun brouillon d'e-mail enregistré dans le CRM."
    elif pending == 0:
        summary = f"Aucun brouillon en attente de validation. {approved} approuvé(s), {sent} envoyé(s)."
    else:
        summary = f"{pending} brouillon(s) d'e-mail en attente de validation humaine sur {total_drafts} au total."

    vizs: list[VisualizationData] = []
    if by_status:
        vizs.append(VisualizationData(type="bar_chart", title="Brouillons par statut", description="État des brouillons d'e-mail CRM.", data={"xKey": "statut", "yKey": "nombre", "data": [{"statut": s, "nombre": c} for s, c in by_status]}))
    if pending_data:
        vizs.append(VisualizationData(type="table", title="Brouillons en attente de validation", description="E-mails générés par l'IA nécessitant une relecture humaine.", data={"rows": pending_data}))

    actions = [_CRM_NAV]
    if pending > 0:
        actions.insert(0, SuggestedAction(label=f"Valider {pending} brouillon(s)", action_type="navigate", payload={"route": "/crm-leads"}))

    return ToolResult(summary=summary, metrics={"total": total_drafts, "pending": pending, "approved": approved, "sent": sent, "rejected": rejected}, visualizations=vizs, sources=[_DRAFT_SOURCE], suggested_actions=actions)


# ---------------------------------------------------------------------------
# CRM — get_crm_value_analysis
# ---------------------------------------------------------------------------

def get_crm_value_analysis(db: Session) -> ToolResult:
    """Pipeline commercial value analysis."""
    try:
        from sqlalchemy import cast, Float, func as sqlfunc
        stmt = select(
            func.count().label("total"),
            func.sum(CrmLead.estimated_value).label("total_value"),
            func.avg(CrmLead.estimated_value).label("avg_value"),
            func.max(CrmLead.estimated_value).label("max_value"),
        ).select_from(CrmLead).where(CrmLead.estimated_value.isnot(None))
        row = db.execute(stmt).one_or_none()
        total_with_value = int(row[0]) if row and row[0] else 0
        total_value = float(row[1]) if row and row[1] else 0.0
        avg_value = float(row[2]) if row and row[2] else 0.0
        max_value = float(row[3]) if row and row[3] else 0.0
    except SQLAlchemyError:
        db.rollback()
        total_with_value = total_value = avg_value = max_value = 0.0

    total = _safe_scalar(db, select(func.count()).select_from(CrmLead))

    # Top leads by value
    top_rows = _safe_scalars(db, select(CrmLead).where(CrmLead.estimated_value.isnot(None)).order_by(CrmLead.estimated_value.desc()).limit(8))
    top_data = [{"Nom": l.full_name, "Entreprise": l.company_name, "Valeur estimée": f"{float(l.estimated_value):,.0f} €", "Statut": l.status} for l in top_rows]

    if total_with_value == 0:
        summary = "Aucune valeur commerciale renseignée dans le pipeline CRM."
    else:
        summary = (
            f"Valeur commerciale du pipeline : {total_value:,.0f} € au total "
            f"({total_with_value} lead(s) valorisés sur {total}). "
            f"Valeur moyenne : {avg_value:,.0f} €. Valeur max : {max_value:,.0f} €."
        )

    kpi_data = {"label": "Valeur totale du pipeline", "value": f"{total_value:,.0f} €", "detail": f"{total_with_value} leads valorisés"}
    vizs: list[VisualizationData] = [
        VisualizationData(type="kpi", title="Valeur commerciale du pipeline", description="Somme des valeurs estimées des leads.", data=kpi_data),
    ]
    if top_data:
        vizs.append(VisualizationData(type="table", title="Top leads par valeur estimée", description="Leads avec la valeur commerciale la plus élevée.", data={"rows": top_data}))

    return ToolResult(summary=summary, metrics={"total_leads": total, "leads_with_value": total_with_value, "total_value": total_value, "avg_value": avg_value, "max_value": max_value}, visualizations=vizs, sources=[_CRM_SOURCE], suggested_actions=[_CRM_NAV])


# ---------------------------------------------------------------------------
# CRM — get_crm_comparison  (period over period, all maths computed here)
# ---------------------------------------------------------------------------

def _format_delta(current: int, previous: int) -> str:
    """Human-readable variation between two periods — computed in the backend."""
    delta = current - previous
    if previous == 0:
        if current == 0:
            return "aucune variation"
        return f"+{current} (nouvelle activité)"
    pct = round(delta / previous * 100)
    sign = "+" if delta > 0 else ""
    if delta == 0:
        return "stable (0 %)"
    return f"{sign}{delta} ({sign}{pct} %)"


def _count_created_between(db: Session, model: Any, start: datetime, end: datetime | None) -> int:
    stmt = select(func.count()).select_from(model).where(model.created_at >= start)
    if end is not None:
        stmt = stmt.where(model.created_at < end)
    return _safe_scalar(db, stmt)


def get_crm_comparison(db: Session) -> ToolResult:
    """Compare CRM activity of the last 7 days with the previous 7 days.

    Every value and variation is computed here from PostgreSQL — the LLM never
    recalculates these numbers, it only presents them.
    """
    now = datetime.now(timezone.utc)
    this_week_start = now - timedelta(days=7)
    prev_week_start = now - timedelta(days=14)

    leads_this = _count_created_between(db, CrmLead, this_week_start, None)
    leads_prev = _count_created_between(db, CrmLead, prev_week_start, this_week_start)

    hot_this = _safe_scalar(
        db,
        select(func.count()).select_from(CrmLead).where(
            CrmLead.created_at >= this_week_start, func.lower(CrmLead.priority) == "high"
        ),
    )
    hot_prev = _safe_scalar(
        db,
        select(func.count()).select_from(CrmLead).where(
            CrmLead.created_at >= prev_week_start,
            CrmLead.created_at < this_week_start,
            func.lower(CrmLead.priority) == "high",
        ),
    )
    drafts_this = _count_created_between(db, CrmEmailDraft, this_week_start, None)
    drafts_prev = _count_created_between(db, CrmEmailDraft, prev_week_start, this_week_start)

    total_recent = leads_this + leads_prev
    if total_recent == 0:
        summary = (
            "Aucun nouveau lead enregistré sur les 14 derniers jours : "
            "impossible de dégager une tendance hebdomadaire fiable."
        )
    else:
        summary = (
            f"Comparaison CRM sur 7 jours : {leads_this} nouveau(x) lead(s) cette semaine "
            f"contre {leads_prev} la semaine précédente ({_format_delta(leads_this, leads_prev)})."
        )

    vizs: list[VisualizationData] = [
        VisualizationData(
            type="kpi",
            title="Nouveaux leads (7 derniers jours)",
            data={
                "label": "Nouveaux leads cette semaine",
                "value": str(leads_this),
                "detail": f"{_format_delta(leads_this, leads_prev)} vs semaine précédente",
            },
        ),
        VisualizationData(
            type="kpi",
            title="Leads semaine précédente",
            data={
                "label": "Leads semaine précédente",
                "value": str(leads_prev),
                "detail": "Période de référence (J-14 à J-7)",
            },
        ),
    ]
    if hot_this or hot_prev:
        vizs.append(
            VisualizationData(
                type="kpi",
                title="Leads prioritaires (7 jours)",
                data={
                    "label": "Nouveaux leads prioritaires",
                    "value": str(hot_this),
                    "detail": f"{_format_delta(hot_this, hot_prev)} vs semaine précédente",
                },
            )
        )

    # Bar chart only when there is at least one data point worth comparing.
    if total_recent > 0:
        compare_rows = [
            {"période": "Cette semaine", "nombre": leads_this},
            {"période": "Semaine précédente", "nombre": leads_prev},
        ]
        vizs.append(
            VisualizationData(
                type="bar_chart",
                title="Comparaison hebdomadaire des leads",
                description="Nouveaux leads créés par période de 7 jours.",
                data={"xKey": "période", "yKey": "nombre", "data": compare_rows},
            )
        )

    return ToolResult(
        summary=summary,
        metrics={
            "leads_this_week": leads_this,
            "leads_prev_week": leads_prev,
            "leads_delta": leads_this - leads_prev,
            "hot_this_week": hot_this,
            "hot_prev_week": hot_prev,
            "drafts_this_week": drafts_this,
            "drafts_prev_week": drafts_prev,
        },
        visualizations=vizs,
        sources=[_CRM_SOURCE, _DRAFT_SOURCE],
        suggested_actions=[_CRM_NAV],
    )


# ---------------------------------------------------------------------------
# Leave — get_leave_summary
# ---------------------------------------------------------------------------

def get_leave_summary(db: Session) -> ToolResult:
    """Full leave request overview."""
    total = _safe_scalar(db, select(func.count()).select_from(LeaveRequest))
    pending = _safe_scalar(db, select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status).in_(["pending", "manager_review_required"])))
    approved = _safe_scalar(db, select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status) == "approved"))
    rejected = _safe_scalar(db, select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status) == "rejected"))
    blocked = _safe_scalar(db, select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status) == "rejected_by_policy"))
    by_type = _count_by_field(db, LeaveRequest, LeaveRequest.leave_type)

    if total == 0:
        summary = "Aucune demande de congé enregistrée pour le moment."
    else:
        parts = [f"Analyse des congés : {total} demande(s) au total."]
        if pending > 0:
            parts.append(f"{pending} en attente.")
        if approved > 0:
            parts.append(f"{approved} approuvée(s).")
        if rejected > 0:
            parts.append(f"{rejected} refusée(s).")
        if blocked > 0:
            parts.append(f"{blocked} bloquée(s) par politique RH.")
        summary = " ".join(parts)

    vizs: list[VisualizationData] = []
    by_status_data = [("En attente", pending), ("Approuvées", approved), ("Refusées", rejected), ("Bloquées", blocked)]
    by_status_data = [(s, c) for s, c in by_status_data if c > 0]
    if by_status_data:
        vizs.append(VisualizationData(type="bar_chart", title="Demandes de congé par statut", description="Répartition des demandes selon leur statut.", data={"xKey": "statut", "yKey": "nombre", "data": [{"statut": s, "nombre": c} for s, c in by_status_data]}))
    if by_type:
        vizs.append(VisualizationData(type="pie_chart", title="Demandes par type de congé", description="Distribution selon le type de congé.", data={"data": [{"name": t, "value": c} for t, c in by_type]}))

    actions = [_LEAVE_NAV]
    if pending > 0:
        actions.insert(0, SuggestedAction(label=f"Approuver {pending} demande(s) en attente", action_type="navigate", payload={"route": "/manager-approvals"}))

    return ToolResult(summary=summary, metrics={"total": total, "pending": pending, "approved": approved, "rejected": rejected, "blocked": blocked}, visualizations=vizs, sources=[_LEAVE_SOURCE], suggested_actions=actions)


# ---------------------------------------------------------------------------
# Leave — get_leave_status_distribution
# ---------------------------------------------------------------------------

def get_leave_status_distribution(db: Session) -> ToolResult:
    """Leave requests grouped by status."""
    total = _safe_scalar(db, select(func.count()).select_from(LeaveRequest))
    by_status = _count_by_field(db, LeaveRequest, LeaveRequest.status)
    by_type = _count_by_field(db, LeaveRequest, LeaveRequest.leave_type)

    if total == 0:
        summary = "Aucune demande de congé enregistrée."
    else:
        top = by_status[:3]
        top_str = ", ".join(f"{c} '{s}'" for s, c in top)
        summary = f"Distribution des {total} demandes de congé par statut : {top_str}."

    vizs: list[VisualizationData] = []
    if by_status:
        vizs.append(VisualizationData(type="bar_chart", title="Demandes de congé par statut", description="Répartition des demandes selon leur statut actuel.", data={"xKey": "statut", "yKey": "nombre", "data": [{"statut": s, "nombre": c} for s, c in by_status]}))
    if by_type:
        vizs.append(VisualizationData(type="pie_chart", title="Demandes par type de congé", description="Distribution selon le type de congé.", data={"data": [{"name": t, "value": c} for t, c in by_type]}))

    return ToolResult(summary=summary, metrics={"total": total, "by_status": dict(by_status)}, visualizations=vizs, sources=[_LEAVE_SOURCE], suggested_actions=[_LEAVE_NAV])


# ---------------------------------------------------------------------------
# Leave — get_leave_pending_approvals
# ---------------------------------------------------------------------------

def get_leave_pending_approvals(db: Session) -> ToolResult:
    """Leave requests waiting for manager decision."""
    rows = _safe_scalars(db, select(LeaveRequest).where(func.lower(LeaveRequest.status).in_(["pending", "manager_review_required"])).order_by(LeaveRequest.created_at.asc()).limit(10))
    data = [{"ID": r.id[:12], "Type": r.leave_type, "Début": str(r.start_date), "Fin": str(r.end_date), "Statut": r.status} for r in rows]
    count = len(data)

    if count == 0:
        summary = "Aucune demande de congé en attente d'approbation manager pour le moment."
    else:
        summary = f"{count} demande(s) de congé en attente d'une décision manager."

    vizs: list[VisualizationData] = []
    if data:
        vizs.append(VisualizationData(type="table", title="Demandes en attente d'approbation", description="Demandes nécessitant une décision managériale.", data={"rows": data}))
    kpi_data = {"label": "Demandes en attente", "value": str(count), "detail": "Décision manager requise"}
    vizs.insert(0, VisualizationData(type="kpi", title="Approbations en attente", description="Nombre de demandes nécessitant une décision.", data=kpi_data))

    actions = [_LEAVE_NAV]
    if count > 0:
        actions.insert(0, SuggestedAction(label=f"Traiter {count} demande(s)", action_type="navigate", payload={"route": "/manager-approvals"}))

    return ToolResult(summary=summary, metrics={"pending_count": count}, visualizations=vizs, sources=[_LEAVE_SOURCE], suggested_actions=actions)


# ---------------------------------------------------------------------------
# Leave — get_leave_block_reasons
# ---------------------------------------------------------------------------

def get_leave_block_reasons(db: Session) -> ToolResult:
    """Why leave requests were blocked (rejected_by_policy)."""
    blocked_rows = _safe_scalars(db, select(LeaveRequest).where(func.lower(LeaveRequest.status) == "rejected_by_policy").order_by(LeaveRequest.updated_at.desc()).limit(10))
    data = [{"ID": r.id[:12], "Type": r.leave_type, "Raison": (r.automation_summary or "Politique RH")[:80], "Recommandation": (r.automation_recommendation or "—")[:60]} for r in blocked_rows]
    count = len(data)

    if count == 0:
        summary = "Aucune demande de congé bloquée par politique RH pour le moment."
    else:
        summary = f"{count} demande(s) de congé bloquée(s) automatiquement par la politique RH."

    vizs: list[VisualizationData] = []
    if data:
        vizs.append(VisualizationData(type="table", title="Demandes bloquées par politique RH", description="Demandes refusées automatiquement avec la raison.", data={"rows": data}))

    return ToolResult(summary=summary, metrics={"blocked_count": count}, visualizations=vizs, sources=[_LEAVE_SOURCE], suggested_actions=[_LEAVE_NAV])


# ---------------------------------------------------------------------------
# Leave — get_leave_balance_block_analysis
# ---------------------------------------------------------------------------

def get_leave_balance_block_analysis(db: Session) -> ToolResult:
    """Leave requests blocked due to insufficient balance."""
    try:
        stmt = (
            select(LeaveRequest)
            .where(
                func.lower(LeaveRequest.status) == "rejected_by_policy",
                LeaveRequest.available_days.isnot(None),
                LeaveRequest.requested_days.isnot(None),
                LeaveRequest.requested_days > LeaveRequest.available_days,
            )
            .order_by(LeaveRequest.updated_at.desc())
            .limit(10)
        )
        rows = _safe_scalars(db, stmt)
    except SQLAlchemyError:
        db.rollback()
        rows = []

    data = [
        {
            "ID": r.id[:12],
            "Type": r.leave_type,
            "Jours demandés": float(r.requested_days) if r.requested_days else "—",
            "Jours disponibles": float(r.available_days) if r.available_days else "—",
            "Écart": round(float(r.requested_days or 0) - float(r.available_days or 0), 1),
        }
        for r in rows
    ]
    count = len(data)

    if count == 0:
        summary = "Aucune demande bloquée pour solde insuffisant détectée."
    else:
        summary = f"{count} demande(s) bloquée(s) en raison d'un solde de congé insuffisant."

    vizs: list[VisualizationData] = []
    if data:
        vizs.append(VisualizationData(type="table", title="Demandes bloquées — solde insuffisant", description="Demandes où les jours demandés dépassent le solde disponible.", data={"rows": data}))

    return ToolResult(summary=summary, metrics={"balance_block_count": count}, visualizations=vizs, sources=[_LEAVE_SOURCE], suggested_actions=[_LEAVE_NAV])


# ---------------------------------------------------------------------------
# Leave — get_leave_overlap_block_analysis
# ---------------------------------------------------------------------------

def get_leave_overlap_block_analysis(db: Session) -> ToolResult:
    """Leave requests potentially blocked due to date overlaps."""
    try:
        stmt = (
            select(LeaveRequest)
            .where(
                func.lower(LeaveRequest.status) == "rejected_by_policy",
                LeaveRequest.automation_summary.ilike("%chevauchement%"),
            )
            .order_by(LeaveRequest.updated_at.desc())
            .limit(10)
        )
        rows = _safe_scalars(db, stmt)
    except SQLAlchemyError:
        db.rollback()
        rows = []

    data = [
        {
            "ID": r.id[:12],
            "Type": r.leave_type,
            "Début": str(r.start_date),
            "Fin": str(r.end_date),
            "Raison": (r.automation_summary or "Chevauchement détecté")[:80],
        }
        for r in rows
    ]
    count = len(data)

    if count == 0:
        summary = "Aucun chevauchement de congé détecté dans les demandes bloquées."
    else:
        summary = f"{count} demande(s) bloquée(s) en raison d'un chevauchement de dates de congé."

    vizs: list[VisualizationData] = []
    if data:
        vizs.append(VisualizationData(type="table", title="Demandes bloquées — chevauchement", description="Demandes refusées pour conflit de dates.", data={"rows": data}))

    return ToolResult(summary=summary, metrics={"overlap_block_count": count}, visualizations=vizs, sources=[_LEAVE_SOURCE], suggested_actions=[_LEAVE_NAV])


# ---------------------------------------------------------------------------
# Leave — get_leave_approval_rate
# ---------------------------------------------------------------------------

def get_leave_approval_rate(db: Session) -> ToolResult:
    """Leave request approval rate KPI."""
    total = _safe_scalar(db, select(func.count()).select_from(LeaveRequest))
    approved = _safe_scalar(db, select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status) == "approved"))
    rejected = _safe_scalar(db, select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status).in_(["rejected", "rejected_by_policy"])))
    pending = _safe_scalar(db, select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status).in_(["pending", "manager_review_required"])))
    decided = approved + rejected
    approval_rate = round(approved / decided * 100, 1) if decided > 0 else 0.0

    if total == 0:
        summary = "Aucune demande de congé enregistrée — impossible de calculer le taux d'approbation."
    elif decided == 0:
        summary = f"Aucune décision prise pour le moment. {pending} demande(s) en attente."
    else:
        summary = (
            f"Taux d'approbation des congés : {approval_rate} % "
            f"({approved} approuvée(s) sur {decided} décisions). "
            f"{rejected} refusée(s). {pending} en attente."
        )

    kpi_data = {"label": "Taux d'approbation", "value": f"{approval_rate} %", "detail": f"{approved} approuvées / {decided} décisions"}
    rate_data = [("Approuvées", approved), ("Refusées", rejected), ("En attente", pending)]
    rate_data = [(s, c) for s, c in rate_data if c > 0]

    vizs: list[VisualizationData] = [
        VisualizationData(type="kpi", title="Taux d'approbation des congés", description="Pourcentage de demandes approuvées parmi les décisions prises.", data=kpi_data),
    ]
    if rate_data:
        vizs.append(VisualizationData(type="pie_chart", title="Répartition des décisions", description="Approuvées / Refusées / En attente.", data={"data": [{"name": s, "value": c} for s, c in rate_data]}))

    actions = [_LEAVE_NAV]
    if pending > 0:
        actions.insert(0, SuggestedAction(label=f"Traiter {pending} demande(s) en attente", action_type="navigate", payload={"route": "/manager-approvals"}))

    return ToolResult(summary=summary, metrics={"total": total, "approved": approved, "rejected": rejected, "pending": pending, "approval_rate_pct": approval_rate}, visualizations=vizs, sources=[_LEAVE_SOURCE], suggested_actions=actions)


# ---------------------------------------------------------------------------
# Business — get_business_summary  (replaces old get_business_summary)
# ---------------------------------------------------------------------------

def get_business_summary(db: Session) -> ToolResult:
    """Combined CRM + Leave snapshot. No workflow/agent data."""
    crm_total = _safe_scalar(db, select(func.count()).select_from(CrmLead))
    hot = _safe_scalar(db, select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.priority) == "high"))
    prospects = _safe_scalar(db, select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.customer_status) == "prospect"))
    customers = _safe_scalar(db, select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.customer_status) == "customer"))
    drafts = _safe_scalar(db, select(func.count()).select_from(CrmEmailDraft).where(func.lower(CrmEmailDraft.status).in_(["draft_generated", "edited", "reviewed"])))
    leave_total = _safe_scalar(db, select(func.count()).select_from(LeaveRequest))
    leave_pending = _safe_scalar(db, select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status).in_(["pending", "manager_review_required"])))
    leave_approved = _safe_scalar(db, select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status) == "approved"))
    leave_rejected = _safe_scalar(db, select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status).in_(["rejected", "rejected_by_policy"])))

    kpi_rows: list[dict[str, Any]] = [
        {"Indicateur": "Leads CRM", "Valeur": crm_total},
        {"Indicateur": "Leads haute priorité", "Valeur": hot},
        {"Indicateur": "Prospects", "Valeur": prospects},
        {"Indicateur": "Clients", "Valeur": customers},
        {"Indicateur": "Brouillons à valider", "Valeur": drafts},
        {"Indicateur": "Demandes de congé", "Valeur": leave_total},
        {"Indicateur": "Congés en attente", "Valeur": leave_pending},
        {"Indicateur": "Congés approuvés", "Valeur": leave_approved},
        {"Indicateur": "Congés refusés", "Valeur": leave_rejected},
    ]

    crm_str = f"{crm_total} lead(s) CRM" + (f" dont {hot} haute priorité" if hot > 0 else "")
    leave_str = (f"{leave_pending} demande(s) de congé en attente" if leave_pending > 0 else "Aucune demande de congé en attente")
    summary = f"Situation actuelle : {crm_str}. {leave_str}." + (f" {drafts} brouillon(s) à valider." if drafts > 0 else "")

    hot_rows = _safe_scalars(db, select(CrmLead).where(func.lower(CrmLead.priority) == "high").order_by(CrmLead.lead_score.desc()).limit(5))
    hot_data = [{"Nom": l.full_name, "Entreprise": l.company_name, "Score": l.lead_score, "Statut": l.status} for l in hot_rows]
    pending_rows = _safe_scalars(db, select(LeaveRequest).where(func.lower(LeaveRequest.status).in_(["pending", "manager_review_required"])).order_by(LeaveRequest.created_at.asc()).limit(5))
    pending_data = [{"ID": r.id[:12], "Type": r.leave_type, "Début": str(r.start_date), "Fin": str(r.end_date), "Statut": r.status} for r in pending_rows]

    vizs: list[VisualizationData] = [VisualizationData(type="table", title="Indicateurs clés — CRM & Congés", description="Snapshot en temps réel des deux processus métier.", data={"rows": kpi_rows})]
    if hot_data:
        vizs.append(VisualizationData(type="table", title="Leads haute priorité", description="Leads nécessitant une action commerciale.", data={"rows": hot_data}))
    if pending_data:
        vizs.append(VisualizationData(type="table", title="Demandes de congé en attente", description="Demandes nécessitant une décision managériale.", data={"rows": pending_data}))

    suggested: list[SuggestedAction] = []
    if hot > 0:
        suggested.append(SuggestedAction(label="Voir les leads haute priorité", action_type="navigate", payload={"route": "/crm-leads"}))
    if leave_pending > 0:
        suggested.append(SuggestedAction(label="Approuver les congés en attente", action_type="navigate", payload={"route": "/manager-approvals"}))
    if drafts > 0:
        suggested.append(SuggestedAction(label="Valider les brouillons", action_type="navigate", payload={"route": "/crm-leads"}))
    suggested.extend([_CRM_NAV, _LEAVE_NAV])

    return ToolResult(summary=summary, metrics={"crm_total": crm_total, "hot": hot, "prospects": prospects, "customers": customers, "drafts": drafts, "leave_total": leave_total, "leave_pending": leave_pending, "leave_approved": leave_approved, "leave_rejected": leave_rejected}, visualizations=vizs, sources=[_CRM_SOURCE, _DRAFT_SOURCE, _LEAVE_SOURCE], suggested_actions=suggested)


# ---------------------------------------------------------------------------
# Business — get_today_actions
# ---------------------------------------------------------------------------

def get_today_actions(db: Session) -> ToolResult:
    """Actionable items for today: hot leads, pending approvals, drafts."""
    hot = _safe_scalar(db, select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.priority) == "high"))
    drafts = _safe_scalar(db, select(func.count()).select_from(CrmEmailDraft).where(func.lower(CrmEmailDraft.status).in_(["draft_generated", "edited", "reviewed"])))
    leave_pending = _safe_scalar(db, select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status).in_(["pending", "manager_review_required"])))

    hot_rows = _safe_scalars(db, select(CrmLead).where(func.lower(CrmLead.priority) == "high").order_by(CrmLead.lead_score.desc()).limit(5))
    hot_data = [{"Nom": l.full_name, "Entreprise": l.company_name, "Score": l.lead_score, "Action": (l.next_action or "À définir")[:50]} for l in hot_rows]
    draft_rows = _safe_scalars(db, select(CrmEmailDraft).where(func.lower(CrmEmailDraft.status).in_(["draft_generated", "edited", "reviewed"])).order_by(CrmEmailDraft.created_at.desc()).limit(5))
    draft_data = [{"ID": d.id[:12], "Type": d.draft_type, "Statut": d.status, "Sujet": (d.subject or "—")[:50]} for d in draft_rows]
    pending_rows = _safe_scalars(db, select(LeaveRequest).where(func.lower(LeaveRequest.status).in_(["pending", "manager_review_required"])).order_by(LeaveRequest.created_at.asc()).limit(5))
    pending_data = [{"ID": r.id[:12], "Type": r.leave_type, "Début": str(r.start_date), "Fin": str(r.end_date)} for r in pending_rows]

    total_actions = (1 if hot > 0 else 0) + (1 if drafts > 0 else 0) + (1 if leave_pending > 0 else 0)

    if total_actions == 0:
        summary = "Aucune action urgente à traiter pour le moment. Tout est à jour."
    else:
        parts = []
        if hot > 0:
            parts.append(f"{hot} lead(s) haute priorité à traiter")
        if drafts > 0:
            parts.append(f"{drafts} brouillon(s) d'e-mail à valider")
        if leave_pending > 0:
            parts.append(f"{leave_pending} demande(s) de congé en attente d'approbation")
        summary = "Actions à traiter aujourd'hui : " + ", ".join(parts) + "."

    vizs: list[VisualizationData] = []
    if hot_data:
        vizs.append(VisualizationData(type="table", title="Leads haute priorité à traiter", description="Leads nécessitant une action commerciale immédiate.", data={"rows": hot_data}))
    if pending_data:
        vizs.append(VisualizationData(type="table", title="Approbations de congé en attente", description="Demandes nécessitant une décision managériale.", data={"rows": pending_data}))
    if draft_data:
        vizs.append(VisualizationData(type="table", title="Brouillons d'e-mail à valider", description="E-mails générés par l'IA en attente de validation.", data={"rows": draft_data}))

    suggested: list[SuggestedAction] = []
    if hot > 0:
        suggested.append(SuggestedAction(label=f"Traiter {hot} lead(s) prioritaire(s)", action_type="navigate", payload={"route": "/crm-leads"}))
    if leave_pending > 0:
        suggested.append(SuggestedAction(label=f"Approuver {leave_pending} demande(s)", action_type="navigate", payload={"route": "/manager-approvals"}))
    if drafts > 0:
        suggested.append(SuggestedAction(label=f"Valider {drafts} brouillon(s)", action_type="navigate", payload={"route": "/crm-leads"}))
    if not suggested:
        suggested = [_CRM_NAV, _LEAVE_NAV]

    return ToolResult(summary=summary, metrics={"hot_leads": hot, "drafts_pending": drafts, "leave_pending": leave_pending, "total_actions": total_actions}, visualizations=vizs, sources=[_CRM_SOURCE, _DRAFT_SOURCE, _LEAVE_SOURCE], suggested_actions=suggested)
