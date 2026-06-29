"""Module Congés STANDALONE (sans Odoo).

Service entièrement autonome : les soldes, conflits d'équipe, burnout et
analytics sont calculés depuis PostgreSQL. Les notifications email passent par
deux workflows n8n dédiés (``leave-standalone``). Tous les appels n8n sont
encapsulés dans des try/except silencieux : si n8n est indisponible, la
demande continue sans erreur.

Ce service NE dépend PAS de ``leave_service.py`` (intégration Odoo).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import LeaveAllocation, LeaveRequest, LeaveType, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes — logique de départements basée sur les rôles existants
# ---------------------------------------------------------------------------

DEPARTMENT_CONFIG: dict[str, dict[str, Any]] = {
    "role_sales": {
        "department_name": "Commercial",
        "manager_role_id": "role_manager",
        "peer_roles": ["role_sales"],
    },
    "role_manager": {
        "department_name": "Commercial",
        "manager_role_id": "role_admin",
        "peer_roles": ["role_manager"],
    },
    "role_hr": {
        "department_name": "RH",
        "manager_role_id": "role_admin",
        "peer_roles": ["role_hr"],
    },
    "role_ai_supervisor": {
        "department_name": "IA",
        "manager_role_id": "role_admin",
        "peer_roles": ["role_ai_supervisor"],
    },
    "role_admin": {
        "department_name": "Direction",
        "manager_role_id": None,
        "peer_roles": ["role_admin"],
    },
}

DEFAULT_ALLOCATIONS_BY_TYPE: dict[str, int] = {
    "vacation": 25,
    "sick": 15,
    "personal": 5,
    "rtt": 10,
    "unpaid": 0,
}

ACTIVE_STATUS = "active"
OVERLAP_STATUSES = ("pending", "manager_review_required", "approved")
PENDING_STATUSES = ("pending", "manager_review_required")
NOTIFY_MANAGER_PATH = "flowpilot/leave-standalone/notify-manager"
NOTIFY_EMPLOYEE_PATH = "flowpilot/leave-standalone/notify-employee"

# Le type "sans solde" n'est jamais bloqué par une vérification de solde.
UNLIMITED_LEAVE_TYPES = {"unpaid"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _get_user(employee_id: str, db: Session) -> User | None:
    return db.get(User, employee_id)


def _department_config(role_id: str | None) -> dict[str, Any]:
    if role_id and role_id in DEPARTMENT_CONFIG:
        return DEPARTMENT_CONFIG[role_id]
    return {"department_name": "Inconnu", "manager_role_id": None, "peer_roles": []}


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def _leave_type_label(leave_type: str, db: Session) -> str:
    try:
        label = db.scalar(
            select(LeaveType.label_fr).where(LeaveType.code == leave_type),
        )
    except Exception:  # pragma: no cover - defensive
        label = None
    return label or leave_type


def _periods_overlap(
    start_a: date,
    end_a: date,
    start_b: date,
    end_b: date,
) -> bool:
    return start_a <= end_b and end_a >= start_b


# ---------------------------------------------------------------------------
# 3. get_employee_manager
# ---------------------------------------------------------------------------

def get_employee_manager(employee_id: str, db: Session) -> User | None:
    """Retourne le manager direct d'un employé d'après son rôle."""
    employee = _get_user(employee_id, db)
    if employee is None:
        return None

    manager_role_id = _department_config(employee.role_id).get("manager_role_id")
    if not manager_role_id:
        return None

    return db.scalars(
        select(User)
        .where(User.role_id == manager_role_id)
        .where(User.status == ACTIVE_STATUS)
        .order_by(User.id)
    ).first()


# ---------------------------------------------------------------------------
# 4. get_department_peers
# ---------------------------------------------------------------------------

def get_department_peers(employee_id: str, db: Session) -> list[User]:
    """Retourne les collègues du même département (mêmes rôles), sauf l'employé."""
    employee = _get_user(employee_id, db)
    if employee is None:
        return []

    peer_roles = _department_config(employee.role_id).get("peer_roles", [])
    if not peer_roles:
        return []

    return list(
        db.scalars(
            select(User)
            .where(User.role_id.in_(peer_roles))
            .where(User.status == ACTIVE_STATUS)
            .where(User.id != employee_id)
            .order_by(User.id)
        ).all()
    )


# ---------------------------------------------------------------------------
# 5. get_leave_balance
# ---------------------------------------------------------------------------

def get_leave_balance(
    employee_id: str,
    leave_type: str,
    year: int,
    db: Session,
) -> dict[str, Any]:
    """Calcule le solde d'un type de congé depuis PostgreSQL."""
    start_of_year, end_of_year = _year_bounds(year)

    allocation = db.scalar(
        select(LeaveAllocation.allocated_days)
        .where(LeaveAllocation.employee_id == employee_id)
        .where(LeaveAllocation.year == year)
        .where(LeaveAllocation.leave_type == leave_type)
    )
    if allocation is not None:
        allocated = _to_float(allocation)
    else:
        allocated = float(DEFAULT_ALLOCATIONS_BY_TYPE.get(leave_type, 0))

    def _sum_days(statuses: tuple[str, ...]) -> float:
        total = db.scalar(
            select(func.coalesce(func.sum(LeaveRequest.requested_days), 0))
            .where(LeaveRequest.user_id == employee_id)
            .where(LeaveRequest.leave_type == leave_type)
            .where(LeaveRequest.status.in_(statuses))
            .where(LeaveRequest.start_date >= start_of_year)
            .where(LeaveRequest.start_date <= end_of_year)
        )
        return _to_float(total)

    used = _sum_days(("approved",))
    pending = _sum_days(PENDING_STATUSES)
    available = allocated - used - pending

    return {
        "leave_type": leave_type,
        "allocated": round(allocated, 2),
        "used": round(used, 2),
        "pending": round(pending, 2),
        "available": round(available, 2),
        "year": year,
    }


# ---------------------------------------------------------------------------
# 6. get_all_balances
# ---------------------------------------------------------------------------

def get_all_balances(employee_id: str, year: int, db: Session) -> list[dict[str, Any]]:
    """Retourne tous les soldes (un par type) pour un employé."""
    return [
        get_leave_balance(employee_id, leave_type, year, db)
        for leave_type in DEFAULT_ALLOCATIONS_BY_TYPE
    ]


# ---------------------------------------------------------------------------
# 7. check_period_overlap
# ---------------------------------------------------------------------------

def check_period_overlap(
    employee_id: str,
    start_date: date,
    end_date: date,
    exclude_request_id: str | None,
    db: Session,
) -> bool:
    """True si l'employé a déjà une demande active chevauchant la période."""
    statement = (
        select(LeaveRequest.id)
        .where(LeaveRequest.user_id == employee_id)
        .where(LeaveRequest.status.in_(OVERLAP_STATUSES))
        .where(LeaveRequest.start_date <= end_date)
        .where(LeaveRequest.end_date >= start_date)
    )
    if exclude_request_id:
        statement = statement.where(LeaveRequest.id != exclude_request_id)

    return db.scalar(statement.limit(1)) is not None


# ---------------------------------------------------------------------------
# 9. calculate_working_days
# ---------------------------------------------------------------------------

def calculate_working_days(start_date: date, end_date: date) -> int:
    """Nombre de jours ouvrables (lundi-vendredi), week-ends exclus."""
    if end_date < start_date:
        return 0

    days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # 0=lundi … 4=vendredi
            days += 1
        current += timedelta(days=1)
    return days


# ---------------------------------------------------------------------------
# 8. check_team_conflicts
# ---------------------------------------------------------------------------

def check_team_conflicts(
    employee_id: str,
    start_date: date,
    end_date: date,
    db: Session,
) -> dict[str, Any]:
    """Conflits avec les collègues DU MÊME DÉPARTEMENT uniquement."""
    peers = get_department_peers(employee_id, db)
    team_size = len(peers) + 1  # l'employé + ses pairs

    conflicting_peers: list[dict[str, Any]] = []
    for peer in peers:
        peer_leaves = db.scalars(
            select(LeaveRequest)
            .where(LeaveRequest.user_id == peer.id)
            .where(LeaveRequest.status == "approved")
            .where(LeaveRequest.start_date <= end_date)
            .where(LeaveRequest.end_date >= start_date)
        ).all()

        for leave in peer_leaves:
            overlap_start = max(start_date, leave.start_date)
            overlap_end = min(end_date, leave.end_date)
            overlap_days = calculate_working_days(overlap_start, overlap_end)
            conflicting_peers.append(
                {
                    "employee_id": peer.id,
                    "employee_name": peer.full_name,
                    "start_date": leave.start_date.isoformat(),
                    "end_date": leave.end_date.isoformat(),
                    "overlap_days": overlap_days,
                }
            )
            break  # un seul conflit suffit à marquer ce collègue absent

    on_leave_count = len(conflicting_peers)
    team_occupation_pct = (
        round((on_leave_count / team_size) * 100, 1) if team_size else 0.0
    )
    has_conflict = on_leave_count > 0

    if on_leave_count == 0:
        risk_level = "low"
        risk_message = "Aucun conflit d'équipe sur cette période"
    elif team_occupation_pct > 50:
        risk_level = "critical"
        risk_message = (
            f"{on_leave_count} collègue(s) déjà en congé "
            f"({team_occupation_pct}% de l'équipe) — couverture critique"
        )
    elif team_occupation_pct > 33:
        risk_level = "high"
        risk_message = (
            f"{on_leave_count} collègue(s) déjà en congé "
            f"({team_occupation_pct}% de l'équipe)"
        )
    else:
        risk_level = "medium"
        risk_message = f"{on_leave_count} collègue en congé sur cette période"

    return {
        "has_conflict": has_conflict,
        "team_size": team_size,
        "on_leave_count": on_leave_count,
        "team_occupation_pct": team_occupation_pct,
        "conflicting_peers": conflicting_peers,
        "risk_level": risk_level,
        "risk_message": risk_message,
    }


# ---------------------------------------------------------------------------
# 10. detect_burnout_risk
# ---------------------------------------------------------------------------

def detect_burnout_risk(employee_id: str, db: Session) -> dict[str, Any]:
    """Détecte le risque de burnout d'un employé."""
    today = utc_now().date()
    year = today.year
    start_of_year, end_of_year = _year_bounds(year)

    last_leave_end = db.scalar(
        select(func.max(LeaveRequest.end_date))
        .where(LeaveRequest.user_id == employee_id)
        .where(LeaveRequest.status == "approved")
    )

    leaves_taken_this_year = db.scalar(
        select(func.count())
        .select_from(LeaveRequest)
        .where(LeaveRequest.user_id == employee_id)
        .where(LeaveRequest.status == "approved")
        .where(LeaveRequest.start_date >= start_of_year)
        .where(LeaveRequest.start_date <= end_of_year)
    ) or 0

    rejection_count_this_year = db.scalar(
        select(func.count())
        .select_from(LeaveRequest)
        .where(LeaveRequest.user_id == employee_id)
        .where(LeaveRequest.status == "rejected")
        .where(LeaveRequest.start_date >= start_of_year)
        .where(LeaveRequest.start_date <= end_of_year)
    ) or 0

    vacation = get_leave_balance(employee_id, "vacation", year, db)
    allocated = vacation["allocated"]
    unused_days_pct = (
        round((vacation["available"] / allocated) * 100, 1) if allocated > 0 else 0.0
    )

    signals: list[str] = []
    if last_leave_end is None:
        days_since_last_leave: int | None = None
        signals.append("Aucun congé approuvé enregistré")
    else:
        days_since_last_leave = max((today - last_leave_end).days, 0)
        if days_since_last_leave > 60:
            signals.append(f"Pas de congé depuis {days_since_last_leave} jours")

    if leaves_taken_this_year <= 2:
        signals.append(f"Seulement {leaves_taken_this_year} congé(s) cette année")
    if unused_days_pct > 80:
        signals.append(
            f"{unused_days_pct}% du solde de congés payés non utilisé"
        )
    if rejection_count_this_year > 0:
        signals.append(f"{rejection_count_this_year} demande(s) refusée(s) cette année")

    if days_since_last_leave is None or days_since_last_leave > 180:
        risk_level = "high"
    elif days_since_last_leave > 90:
        risk_level = "medium"
    elif days_since_last_leave > 60:
        risk_level = "low"
    else:
        risk_level = "none"

    recommendations = {
        "high": (
            "Risque de burnout élevé : encourager activement la prise de congé "
            "et planifier un point RH."
        ),
        "medium": (
            "Surveiller la charge : proposer au collaborateur de poser des congés "
            "prochainement."
        ),
        "low": "Vigilance légère : aucune action urgente nécessaire.",
        "none": "Aucun signal de burnout détecté.",
    }

    return {
        "risk_level": risk_level,
        "days_since_last_leave": days_since_last_leave,
        "leaves_taken_this_year": int(leaves_taken_this_year),
        "rejection_count_this_year": int(rejection_count_this_year),
        "unused_days_pct": unused_days_pct,
        "signals": signals,
        "recommendation": recommendations[risk_level],
    }


# ---------------------------------------------------------------------------
# Webhooks n8n (silencieux si indisponibles)
# ---------------------------------------------------------------------------

def _standalone_webhook_url(path: str) -> str:
    base = settings.N8N_WEBHOOK_BASE_URL.rstrip("/")
    return f"{base}/{path}"


def _post_standalone_webhook(path: str, payload: dict[str, Any]) -> None:
    """POST best-effort vers n8n. Toute erreur est avalée (fallback silencieux)."""
    url = _standalone_webhook_url(path)
    try:
        request = Request(
            url,
            data=json.dumps(payload, default=str).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-FlowPilot-Secret": settings.FLOWPILOT_N8N_SHARED_SECRET,
            },
            method="POST",
        )
        with urlopen(request, timeout=10):
            pass
    except Exception as exc:  # noqa: BLE001 - fallback silencieux volontaire
        logger.warning("n8n standalone webhook indisponible (%s): %s", path, exc)


# ---------------------------------------------------------------------------
# 11. create_leave_request_standalone
# ---------------------------------------------------------------------------

def create_leave_request_standalone(
    employee_id: str,
    leave_type: str,
    start_date: date,
    end_date: date,
    reason: str,
    db: Session,
) -> tuple[LeaveRequest, dict[str, Any]]:
    """Crée une demande standalone et notifie le manager via n8n."""
    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="La date de fin ne peut pas être antérieure à la date de début.",
        )

    requested_days = calculate_working_days(start_date, end_date)
    if requested_days <= 0:
        raise HTTPException(
            status_code=422,
            detail="La période demandée ne contient aucun jour ouvrable.",
        )

    year = start_date.year
    balance = get_leave_balance(employee_id, leave_type, year, db)
    available = balance["available"]

    if leave_type not in UNLIMITED_LEAVE_TYPES and requested_days > available:
        raise HTTPException(
            status_code=422,
            detail=(
                "Solde insuffisant : vous demandez "
                f"{requested_days} jour(s) mais seulement {available} jour(s) "
                "sont disponibles."
            ),
        )

    if check_period_overlap(employee_id, start_date, end_date, None, db):
        raise HTTPException(
            status_code=422,
            detail="Cette période chevauche déjà une de vos demandes en cours.",
        )

    team_conflicts = check_team_conflicts(employee_id, start_date, end_date, db)
    burnout_risk = detect_burnout_risk(employee_id, db)
    manager = get_employee_manager(employee_id, db)
    employee = _get_user(employee_id, db)

    now = utc_now()
    leave_request = LeaveRequest(
        id=f"leave_{uuid4().hex[:8]}",
        user_id=employee_id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status="pending",
        odoo_sync_status=None,
        requested_days=Decimal(str(requested_days)),
        available_days=Decimal(str(available)),
        created_at=now,
        updated_at=now,
    )
    db.add(leave_request)
    db.commit()
    db.refresh(leave_request)

    context_info = {
        "requested_days": requested_days,
        "available_days": available,
        "balance": balance,
        "team_conflicts": team_conflicts,
        "burnout_risk": burnout_risk,
        "manager_id": manager.id if manager else None,
        "manager_name": manager.full_name if manager else None,
        "manager_email": manager.email if manager else None,
    }

    payload = {
        "leave_request_id": leave_request.id,
        "employee_id": employee_id,
        "employee_name": employee.full_name if employee else employee_id,
        "employee_email": employee.email if employee else None,
        "manager_id": manager.id if manager else None,
        "manager_name": manager.full_name if manager else None,
        "manager_email": manager.email if manager else None,
        "leave_type": leave_type,
        "leave_type_label": _leave_type_label(leave_type, db),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "requested_days": requested_days,
        "reason": reason,
        "available_days": available,
        "team_conflicts": team_conflicts,
        "burnout_risk": burnout_risk,
        "frontend_url": settings.FRONTEND_ORIGIN,
    }
    _post_standalone_webhook(NOTIFY_MANAGER_PATH, payload)

    return leave_request, context_info


# ---------------------------------------------------------------------------
# 12/13. approve / reject standalone
# ---------------------------------------------------------------------------

def _decide_leave_standalone(
    request_id: str,
    manager_id: str,
    comment: str,
    decision: str,
    db: Session,
) -> LeaveRequest:
    leave_request = db.get(LeaveRequest, request_id)
    if leave_request is None:
        raise HTTPException(status_code=404, detail="Demande de congé introuvable.")

    expected_manager = get_employee_manager(leave_request.user_id, db)
    if expected_manager is None or expected_manager.id != manager_id:
        raise HTTPException(
            status_code=403,
            detail="Vous n'êtes pas le manager responsable de cette demande.",
        )

    if leave_request.status not in PENDING_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cette demande a déjà été traitée "
                f"(statut actuel : {leave_request.status})."
            ),
        )

    now = utc_now()
    leave_request.status = decision
    leave_request.reviewed_by = manager_id
    leave_request.reviewed_at = now
    leave_request.decision_comment = comment
    leave_request.updated_at = now
    db.commit()
    db.refresh(leave_request)

    employee = _get_user(leave_request.user_id, db)
    payload = {
        "leave_request_id": leave_request.id,
        "decision": decision,
        "employee_id": leave_request.user_id,
        "employee_email": employee.email if employee else None,
        "employee_name": employee.full_name if employee else leave_request.user_id,
        "manager_name": expected_manager.full_name,
        "decision_comment": comment,
        "leave_type": leave_request.leave_type,
        "leave_type_label": _leave_type_label(leave_request.leave_type, db),
        "start_date": leave_request.start_date.isoformat(),
        "end_date": leave_request.end_date.isoformat(),
        "requested_days": _to_float(leave_request.requested_days),
        "frontend_url": settings.FRONTEND_ORIGIN,
    }
    _post_standalone_webhook(NOTIFY_EMPLOYEE_PATH, payload)

    return leave_request


def approve_leave_standalone(
    request_id: str,
    manager_id: str,
    comment: str,
    db: Session,
) -> LeaveRequest:
    """Approuve une demande standalone et notifie l'employé."""
    return _decide_leave_standalone(request_id, manager_id, comment, "approved", db)


def reject_leave_standalone(
    request_id: str,
    manager_id: str,
    comment: str,
    db: Session,
) -> LeaveRequest:
    """Refuse une demande standalone et notifie l'employé."""
    return _decide_leave_standalone(request_id, manager_id, comment, "rejected", db)


# ---------------------------------------------------------------------------
# 14. get_analytics
# ---------------------------------------------------------------------------

def get_analytics(db: Session) -> dict[str, Any]:
    """Analytics congés pour le dashboard RH."""
    now = utc_now()
    year = now.year
    start_of_year, end_of_year = _year_bounds(year)

    requests = list(
        db.scalars(
            select(LeaveRequest)
            .where(LeaveRequest.start_date >= start_of_year)
            .where(LeaveRequest.start_date <= end_of_year)
            .order_by(LeaveRequest.created_at.desc())
        ).all()
    )

    total_this_year = len(requests)
    approved = sum(1 for r in requests if r.status == "approved")
    rejected = sum(1 for r in requests if r.status == "rejected")
    pending = sum(1 for r in requests if r.status in PENDING_STATUSES)

    by_type: dict[str, dict[str, float]] = {}
    for request in requests:
        bucket = by_type.setdefault(request.leave_type, {"count": 0, "days": 0.0})
        bucket["count"] += 1
        bucket["days"] += _to_float(request.requested_days)
    for bucket in by_type.values():
        bucket["count"] = int(bucket["count"])
        bucket["days"] = round(bucket["days"], 2)

    employee_ids = sorted({r.user_id for r in requests})
    by_employee: list[dict[str, Any]] = []
    burnout_alerts: list[dict[str, Any]] = []
    for employee_id in employee_ids:
        employee = _get_user(employee_id, db)
        employee_requests = [r for r in requests if r.user_id == employee_id]
        approved_days = round(
            sum(
                _to_float(r.requested_days)
                for r in employee_requests
                if r.status == "approved"
            ),
            2,
        )
        vacation_balance = get_leave_balance(employee_id, "vacation", year, db)
        burnout = detect_burnout_risk(employee_id, db)

        by_employee.append(
            {
                "employee_id": employee_id,
                "employee_name": employee.full_name if employee else employee_id,
                "total_requests": len(employee_requests),
                "approved_days": approved_days,
                "remaining_vacation": vacation_balance["available"],
                "burnout_risk": burnout["risk_level"],
            }
        )

        if burnout["risk_level"] in {"medium", "high"}:
            burnout_alerts.append(
                {
                    "employee_id": employee_id,
                    "employee_name": employee.full_name if employee else employee_id,
                    "risk_level": burnout["risk_level"],
                    "days_since_last_leave": burnout["days_since_last_leave"],
                    "signals": burnout["signals"],
                }
            )

    pending_over_48h: list[dict[str, Any]] = []
    for request in requests:
        if request.status not in PENDING_STATUSES:
            continue
        created_at = request.created_at
        if created_at is None:
            continue
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        hours_pending = (now - created_at).total_seconds() / 3600
        if hours_pending > 48:
            employee = _get_user(request.user_id, db)
            pending_over_48h.append(
                {
                    "request_id": request.id,
                    "employee_name": employee.full_name if employee else request.user_id,
                    "submitted_at": created_at.isoformat(),
                    "hours_pending": round(hours_pending, 1),
                }
            )

    return {
        "total_this_year": total_this_year,
        "approved": approved,
        "rejected": rejected,
        "pending": pending,
        "by_type": by_type,
        "by_employee": by_employee,
        "burnout_alerts": burnout_alerts,
        "pending_over_48h": pending_over_48h,
    }
