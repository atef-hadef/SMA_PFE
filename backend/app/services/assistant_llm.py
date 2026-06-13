"""
assistant_llm.py — Optional OpenRouter LLM fallback for the assistant.

Used ONLY for open-ended intents (`unknown`, `general`) where the
deterministic rule engine has no specific tool to dispatch. Every other
intent stays on the structured analytics path in `assistant_service.py`
so visualisations, sources and suggested actions remain available.

Design rules:
  - Graceful degradation: if the API key is missing, httpx is unavailable,
    or the upstream call fails, callers receive `None` and fall back to
    the existing static text. The assistant never crashes because of LLM.
  - Grounded context: the system prompt is built from the same read-only
    DB snapshot the deterministic tools use, so the model has factual
    business numbers to anchor its answers — no hallucinated KPIs.
  - Role-aware: `role_name` (from `AuthUser`) shapes the persona section
    of the prompt. The data section is identical for every role; the
    permission layer at the endpoint already gates what the user sees.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CrmEmailDraft, CrmLead, LeaveRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Snapshot used to ground the LLM
# ---------------------------------------------------------------------------

def _safe_int(db: Session, stmt: Any) -> int:
    try:
        return int(db.scalar(stmt) or 0)
    except SQLAlchemyError:
        db.rollback()
        return 0


def build_grounding_snapshot(db: Session) -> dict[str, Any]:
    """Read-only counts used to ground the LLM. Never raises."""
    snapshot: dict[str, Any] = {
        "crm": {"total": 0, "hot": 0, "prospects": 0, "customers": 0, "drafts_pending": 0},
        "leave": {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "blocked": 0},
        "top_hot_leads": [],
    }

    snapshot["crm"]["total"] = _safe_int(db, select(func.count()).select_from(CrmLead))
    snapshot["crm"]["hot"] = _safe_int(
        db,
        select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.priority) == "high"),
    )
    snapshot["crm"]["prospects"] = _safe_int(
        db,
        select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.customer_status) == "prospect"),
    )
    snapshot["crm"]["customers"] = _safe_int(
        db,
        select(func.count()).select_from(CrmLead).where(func.lower(CrmLead.customer_status) == "customer"),
    )
    snapshot["crm"]["drafts_pending"] = _safe_int(
        db,
        select(func.count()).select_from(CrmEmailDraft).where(
            func.lower(CrmEmailDraft.status).in_(["draft_generated", "edited", "reviewed"])
        ),
    )

    snapshot["leave"]["total"] = _safe_int(db, select(func.count()).select_from(LeaveRequest))
    snapshot["leave"]["pending"] = _safe_int(
        db,
        select(func.count()).select_from(LeaveRequest).where(
            func.lower(LeaveRequest.status).in_(["pending", "manager_review_required"])
        ),
    )
    snapshot["leave"]["approved"] = _safe_int(
        db,
        select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status) == "approved"),
    )
    snapshot["leave"]["rejected"] = _safe_int(
        db,
        select(func.count()).select_from(LeaveRequest).where(func.lower(LeaveRequest.status) == "rejected"),
    )
    snapshot["leave"]["blocked"] = _safe_int(
        db,
        select(func.count()).select_from(LeaveRequest).where(
            func.lower(LeaveRequest.status) == "rejected_by_policy"
        ),
    )

    try:
        rows = db.scalars(
            select(CrmLead)
            .where(func.lower(CrmLead.priority) == "high")
            .order_by(CrmLead.lead_score.desc())
            .limit(5)
        ).all()
        snapshot["top_hot_leads"] = [
            {
                "name": r.full_name,
                "company": r.company_name,
                "score": r.lead_score,
                "status": r.status,
                "next_action": (r.next_action or "—")[:80],
            }
            for r in rows
        ]
    except SQLAlchemyError:
        db.rollback()

    return snapshot


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_ROLE_HINTS: dict[str, str] = {
    "admin": (
        "L'utilisateur est administrateur : il a une vision système. "
        "Tu peux évoquer les KPI globaux, l'état des données et la gouvernance."
    ),
    "manager": (
        "L'utilisateur est manager : il pilote son équipe. "
        "Privilégie les éléments d'approbation et la performance globale."
    ),
    "commercial": (
        "L'utilisateur est commercial : il pilote son pipeline CRM. "
        "Privilégie les leads, relances et brouillons d'e-mail."
    ),
}


def build_system_prompt(role_name: str, full_name: str, snapshot: dict[str, Any]) -> str:
    role_key = (role_name or "").strip().lower()
    role_hint = _ROLE_HINTS.get(role_key, "")

    crm = snapshot["crm"]
    leave = snapshot["leave"]

    hot_leads_block = "Aucun lead haute priorité actuellement."
    if snapshot["top_hot_leads"]:
        lines = [
            f"  - {l['name']} ({l['company']}) — score {l['score']}, statut {l['status']}"
            f", prochaine action: {l['next_action']}"
            for l in snapshot["top_hot_leads"]
        ]
        hot_leads_block = "\n".join(lines)

    return f"""Tu es FlowPilot AI, l'assistant métier de la plateforme FlowPilot.
Tu aides {full_name or "l'utilisateur"} ({role_name or "utilisateur"}).
{role_hint}

PÉRIMÈTRE STRICT : tu réponds uniquement sur le CRM (leads, prospects,
brouillons d'e-mail) et les demandes de congé. Pour tout autre sujet
(workflows n8n, agents IA, météo, etc.), redirige poliment vers ces deux
processus.

RÈGLES IMPÉRATIVES :
- Réponds toujours en français, de manière concise et actionnable.
- N'invente JAMAIS de chiffre métier. Utilise UNIQUEMENT les données ci-dessous.
- Si la question demande un chiffre absent du contexte, dis-le clairement
  et invite l'utilisateur à consulter la page concernée.
- Si on te demande de rédiger un e-mail commercial, génère-le complet
  (objet + corps) en français professionnel.
- N'utilise pas d'emoji.
- Pour les listes, utilise des tirets.

DONNÉES MÉTIER EN TEMPS RÉEL (PostgreSQL, lecture seule) :

CRM :
- Total leads : {crm['total']}
- Leads haute priorité : {crm['hot']}
- Prospects en cours : {crm['prospects']}
- Clients convertis : {crm['customers']}
- Brouillons d'e-mail en attente de validation : {crm['drafts_pending']}

CONGÉS :
- Total demandes : {leave['total']}
- En attente d'approbation : {leave['pending']}
- Approuvées : {leave['approved']}
- Refusées : {leave['rejected']}
- Bloquées par politique RH : {leave['blocked']}

TOP LEADS HAUTE PRIORITÉ :
{hot_leads_block}
"""


# ---------------------------------------------------------------------------
# OpenRouter call (sync — matches the existing sync endpoint)
# ---------------------------------------------------------------------------

def call_openrouter(
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
) -> str | None:
    """
    Call OpenRouter. Returns the assistant text on success, or None on any
    failure (missing key, missing httpx, network error, malformed response).
    Callers MUST handle the None case with a static fallback.
    """
    if not settings.OPENROUTER_API_KEY:
        logger.info("OpenRouter disabled (no API key configured).")
        return None

    try:
        import httpx  # local import — keeps httpx optional at module load
    except ImportError:
        logger.warning("httpx not installed — OpenRouter fallback disabled.")
        return None

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    # Trim history to the last 8 turns to keep the prompt small
    for msg in history[-8:]:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": settings.OPENROUTER_MAX_TOKENS,
        "temperature": 0.4,
    }
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.FRONTEND_ORIGIN,
        "X-Title": "FlowPilot AI Assistant",
    }

    try:
        with httpx.Client(timeout=settings.OPENROUTER_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.exception("OpenRouter call failed.")
        return None

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logger.warning("OpenRouter response missing expected fields: %r", data)
        return None

    if not isinstance(text, str) or not text.strip():
        return None
    return text.strip()
