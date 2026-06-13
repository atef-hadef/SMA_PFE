"""
assistant_service.py — Precise intent classification + tool registry — V2.

Flow:
  1. Classify the user message via deterministic keyword regex (precise intents).
  2. Dispatch to the matching read-only analytics tool via the tool registry.
  3. Return a typed AssistantChatResponse.
  4. Fall back to a static French answer if the DB is unavailable.

Rules:
  - No LLM / OpenRouter calls.
  - No n8n calls.
  - No database writes.
  - Workflow and agent intents are NOT routed — out_of_scope only.
  - All user-facing text is in French.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable
from typing import Final

from sqlalchemy.orm import Session

from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantIntent,
    AssistantSource,
    SuggestedAction,
    VisualizationData,
)
from app.services.assistant_llm import (
    build_grounding_snapshot,
    build_system_prompt,
    call_openrouter,
)
from app.services.assistant_tools import (
    ToolResult,
    get_business_summary,
    get_crm_comparison,
    get_crm_conversion_analysis,
    get_crm_draft_review_summary,
    get_crm_followup_recommendations,
    get_crm_priority_analysis,
    get_crm_status_distribution,
    get_crm_summary,
    get_crm_value_analysis,
    get_automation_health,
    get_leave_approval_rate,
    get_leave_balance_block_analysis,
    get_leave_block_reasons,
    get_leave_overlap_block_analysis,
    get_leave_pending_approvals,
    get_leave_status_distribution,
    get_leave_summary,
    get_today_actions,
)
from app.services.openui_service import OPENUI_VERSION, build_openui_response

logger = logging.getLogger(__name__)

CRM_INTENTS: Final[set[AssistantIntent]] = {
    "crm_summary",
    "crm_priority_analysis",
    "crm_status_distribution",
    "crm_conversion_analysis",
    "crm_followup_recommendations",
    "crm_draft_review_summary",
    "crm_value_analysis",
    "crm_comparison",
}
LEAVE_INTENTS: Final[set[AssistantIntent]] = {
    "leave_summary",
    "leave_status_distribution",
    "leave_pending_approvals",
    "leave_block_reasons",
    "leave_balance_block_analysis",
    "leave_overlap_block_analysis",
    "leave_approval_rate",
}
BUSINESS_INTENTS: Final[set[AssistantIntent]] = {
    "business_summary",
    "today_actions",
    "automation_health",
    "general",
}
MONITORING_INTENTS: Final[set[AssistantIntent]] = {
    "automation_health",
}


# ---------------------------------------------------------------------------
# Precise deterministic intent classification
#
# Rules:
#   - Patterns are tested in order; first match wins.
#   - More specific patterns come before broader ones.
#   - Out-of-scope patterns (workflow, agents) are checked last.
#   - All patterns use re.I | re.UNICODE for accent-safe matching.
# ---------------------------------------------------------------------------

_INTENT_PATTERNS: Final[list[tuple[re.Pattern[str], AssistantIntent]]] = [

    # ---- CRM precise intents (order: most specific first) ----

    # crm_comparison — period-over-period questions (this week vs last week).
    # Placed first because the phrasing often carries no explicit CRM keyword.
    (re.compile(
        r"\b(compare[rz]?|comparaison|comparatif"
        r"|semaine\s+(pr[eé]c[eé]dente|derni[eè]re|d.avant)"
        r"|mois\s+(pr[eé]c[eé]dent|dernier)"
        r"|par\s+rapport\s+[àa]\s+la\s+semaine"
        r"|[eé]volution\s+hebdomadaire|d.une\s+semaine\s+[àa]\s+l.autre"
        r"|versus|\bvs\b)\b",
        re.I | re.UNICODE,
    ), "crm_comparison"),

    # crm_priority_analysis — questions about lead priority levels
    (re.compile(
        r"\b(priorit[eé]|prioritaires|haute\s+priorit[eé]|leads?\s+prioritaires?"
        r"|urgents?|leads?\s+chauds?|hot\s+leads?)\b",
        re.I | re.UNICODE,
    ), "crm_priority_analysis"),

    # crm_status_distribution — questions about lead status breakdown
    (re.compile(
        r"\b(statut|statuts|par\s+statut|r[eé]partition|distribution)"
        r".*\b(lead|leads?|crm|prospect|pipeline)\b"
        r"|\b(lead|leads?|crm|prospect|pipeline)\b"
        r".*\b(statut|statuts|par\s+statut|r[eé]partition|distribution)\b",
        re.I | re.UNICODE,
    ), "crm_status_distribution"),

    # crm_conversion_analysis — conversion rate questions
    (re.compile(
        r"\b(taux\s+de\s+conversion|conversion|convertis?|converti[eé]s?|entonnoir)\b",
        re.I | re.UNICODE,
    ), "crm_conversion_analysis"),

    # crm_followup_recommendations — follow-up / relance questions
    (re.compile(
        r"\b(relance[rs]?|n[eé]cessitent?\s+une\s+relance|prospects?\s+[àa]\s+relancer"
        r"|suivis?|follow.?up|[àa]\s+contacter|action\s+commerciale)\b",
        re.I | re.UNICODE,
    ), "crm_followup_recommendations"),

    # crm_draft_review_summary — email draft review questions
    (re.compile(
        r"\b(brouillon|brouillons|draft|drafts|[àa]\s+valider|[àa]\s+relire"
        r"|e.?mails?\s+g[eé]n[eé]r[eé]s?|validation\s+crm)\b",
        re.I | re.UNICODE,
    ), "crm_draft_review_summary"),

    # crm_value_analysis — pipeline value / commercial value questions
    (re.compile(
        r"\b(valeur|valeurs|valeur\s+commerciale|pipeline\s+commercial"
        r"|valeur\s+estim[eé]e?|montant|chiffre\s+d.affaires?|revenue)\b",
        re.I | re.UNICODE,
    ), "crm_value_analysis"),

    # crm_summary — explicit CRM summary, before the global summary pattern
    (re.compile(
        r"\b(r[eé]sum[eé]|resume|synth[eè]se|synthese|bilan|vue\s+d.ensemble|analyse|rapport|dashboard|tableau\s+de\s+bord)"
        r".*\b(crm|leads?|prospects?|pipeline|commercial)\b"
        r"|\b(crm|leads?|prospects?|pipeline|commercial)\b"
        r".*\b(r[eé]sum[eé]|resume|synth[eè]se|synthese|bilan|vue\s+d.ensemble|analyse|rapport|dashboard|tableau\s+de\s+bord)\b",
        re.I | re.UNICODE,
    ), "crm_summary"),

    # crm_summary — broad CRM analysis request
    (re.compile(
        r"\b(analyse\s+crm|analyse\s+des?\s+leads?|vue\s+crm|bilan\s+crm"
        r"|situation\s+crm|rapport\s+crm|crm\s+complet)\b",
        re.I | re.UNICODE,
    ), "crm_summary"),

    # ---- Leave Request precise intents ----

    # leave_pending_approvals — how many waiting for manager
    (re.compile(
        r"\b(attendent?\s+le\s+manager|en\s+attente\s+d.approbation"
        r"|approbations?\s+en\s+attente|d[eé]cision\s+manager"
        r"|combien.*attendent?|manager.*attendent?)\b",
        re.I | re.UNICODE,
    ), "leave_pending_approvals"),

    # leave_block_reasons — why are requests blocked
    (re.compile(
        r"\b(pourquoi.*bloqu[eé]|bloqu[eé]e?s?\s+pourquoi|raisons?\s+de\s+blocage"
        r"|raisons?\s+de\s+refus|pourquoi.*refus[eé]|motifs?\s+de\s+refus"
        r"|bloqu[eé]e?s?\s+les\s+demandes?|demandes?.*bloqu[eé]e?s?"
        r"|bloquees?|bloqu[eé]es?)\b",
        re.I | re.UNICODE,
    ), "leave_block_reasons"),

    # leave_balance_block_analysis — balance / solde problems
    (re.compile(
        r"\b(solde|soldes|probl[eè]mes?\s+de\s+solde|solde\s+insuffisant"
        r"|jours?\s+disponibles?|jours?\s+restants?|balance)\b",
        re.I | re.UNICODE,
    ), "leave_balance_block_analysis"),

    # leave_overlap_block_analysis — overlap / chevauchement
    (re.compile(
        r"\b(chevauchement|chevauchements?|overlap|conflits?\s+de\s+dates?"
        r"|dates?\s+qui\s+se\s+chevauchent?)\b",
        re.I | re.UNICODE,
    ), "leave_overlap_block_analysis"),

    # leave_approval_rate — approval rate KPI
    (re.compile(
        r"\b(taux\s+d.approbation|taux\s+d.accord|taux\s+de\s+refus"
        r"|pourcentage.*approuv[eé]|approbation.*taux)\b",
        re.I | re.UNICODE,
    ), "leave_approval_rate"),

    # leave_status_distribution — leave requests by status
    (re.compile(
        r"\b(statut|statuts|par\s+statut|r[eé]partition|distribution)"
        r".*\b(cong[eé]|demandes?|absences?)\b"
        r"|\b(cong[eé]|demandes?|absences?)\b"
        r".*\b(statut|statuts|par\s+statut|r[eé]partition|distribution)\b",
        re.I | re.UNICODE,
    ), "leave_status_distribution"),

    # leave_summary — broad leave analysis
    (re.compile(
        r"\b(analyse\s+des?\s+cong[eé]s?|bilan\s+des?\s+cong[eé]s?"
        r"|situation\s+des?\s+cong[eé]s?|rapport\s+des?\s+cong[eé]s?"
        r"|vue\s+d.ensemble.*cong[eé]|cong[eé]s?\s+complets?)\b",
        re.I | re.UNICODE,
    ), "leave_summary"),

    # leave_summary — explicit leave summary, before the global summary pattern
    (re.compile(
        r"\b(r[eé]sum[eé]|resume|synth[eè]se|synthese|bilan|vue\s+d.ensemble|analyse|rapport|dashboard|tableau\s+de\s+bord)"
        r".*\b(cong[eé]s?|absences?|demandes?\s+de\s+cong[eé])\b"
        r"|\b(cong[eé]s?|absences?|demandes?\s+de\s+cong[eé])\b"
        r".*\b(r[eé]sum[eé]|resume|synth[eè]se|synthese|bilan|vue\s+d.ensemble|analyse|rapport|dashboard|tableau\s+de\s+bord)\b",
        re.I | re.UNICODE,
    ), "leave_summary"),

    # ---- Business / global intents ----

    # automation_health — controlled workflow monitoring summary
    (re.compile(
        r"\b(sant[eé]\s+des?\s+automatisations?|automatisations?|monitoring"
        r"|workflows?|workflow|n8n|ex[eé]cutions?|succ[eè]s.*[eé]checs?"
        r"|[eé]checs?.*automatisation)\b",
        re.I | re.UNICODE,
    ), "automation_health"),

    # today_actions — what to do today
    (re.compile(
        r"\b(aujourd.?hui|ce\s+matin|ce\s+jour|[àa]\s+traiter\s+aujourd.?hui"
        r"|que\s+dois.?je\s+faire|actions?\s+du\s+jour|priorit[eé]s?\s+du\s+jour"
        r"|quoi\s+faire|que\s+faire)\b",
        re.I | re.UNICODE,
    ), "today_actions"),

    # business_summary — explicit global situation / dashboard
    (re.compile(
        r"\b(tableau\s+de\s+bord\s+(global|g[eé]n[eé]ral|m[eé]tier)"
        r"|situation\s+g[eé]n[eé]rale?|bilan\s+g[eé]n[eé]ral?"
        r"|vue\s+d.ensemble\s+(globale?|m[eé]tier|de\s+l.activit[eé])"
        r"|(r[eé]sum[eé]|resume)\s+(global|g[eé]n[eé]ral|general|m[eé]tier|metier|de\s+l.activit[eé])"
        r"|toute\s+l.activit[eé]|activit[eé]\s+m[eé]tier|kpi\s+globaux|m[eé]triques?\s+globales?)\b",
        re.I | re.UNICODE,
    ), "business_summary"),

    # ---- Broad CRM fallback (catches remaining CRM questions) ----
    (re.compile(
        r"\b(lead|leads?|prospect|prospects?|client|clients?|crm|pipeline|score|contact)\b",
        re.I | re.UNICODE,
    ), "crm_summary"),

    # ---- Broad Leave fallback (catches remaining leave questions) ----
    (re.compile(
        r"\b(cong[eé]|cong[eé]s|absence|absences|demande|demandes"
        r"|approbation|approbations|rh|leave|vacation|holiday|time.?off)\b",
        re.I | re.UNICODE,
    ), "leave_summary"),

    # ---- Out of scope — workflow / agent / unrelated ----
    (re.compile(
        r"\b(trigger"
        r"|agent\s+ia|agents?\s+ia|bot|mod[eè]le\s+ia|logs?|erreurs?\s+syst[eè]me"
        r"|m[eé]t[eé]o|heure|temps|news|actualit[eé])\b",
        re.I | re.UNICODE,
    ), "out_of_scope"),

    # ---- General greeting / help ----
    (re.compile(
        r"\b(bonjour|salut|bonsoir|hello|hi|hey|aide|help"
        r"|que\s+peux.tu|tu\s+peux\s+faire|what\s+can\s+you)\b",
        re.I | re.UNICODE,
    ), "general"),
]


def _classify_intent(message: str) -> AssistantIntent:
    for pattern, intent in _INTENT_PATTERNS:
        if pattern.search(message):
            return intent
    return "unknown"


# ---------------------------------------------------------------------------
# Tool registry — maps each intent to exactly one read-only tool function
# ---------------------------------------------------------------------------

_TOOL_REGISTRY: Final[dict[AssistantIntent, Callable[[Session], ToolResult]]] = {
    # CRM
    "crm_summary": get_crm_summary,
    "crm_priority_analysis": get_crm_priority_analysis,
    "crm_status_distribution": get_crm_status_distribution,
    "crm_conversion_analysis": get_crm_conversion_analysis,
    "crm_followup_recommendations": get_crm_followup_recommendations,
    "crm_draft_review_summary": get_crm_draft_review_summary,
    "crm_value_analysis": get_crm_value_analysis,
    "crm_comparison": get_crm_comparison,
    # Leave
    "leave_summary": get_leave_summary,
    "leave_status_distribution": get_leave_status_distribution,
    "leave_pending_approvals": get_leave_pending_approvals,
    "leave_block_reasons": get_leave_block_reasons,
    "leave_balance_block_analysis": get_leave_balance_block_analysis,
    "leave_overlap_block_analysis": get_leave_overlap_block_analysis,
    "leave_approval_rate": get_leave_approval_rate,
    # Business
    "business_summary": get_business_summary,
    "today_actions": get_today_actions,
    "automation_health": get_automation_health,
    # general also gets business_summary
    "general": get_business_summary,
}


# ---------------------------------------------------------------------------
# Static fallback answers — used when DB is unavailable
# ---------------------------------------------------------------------------

_STATIC_ANSWERS: Final[dict[AssistantIntent, str]] = {
    "crm_summary": "Je peux vous aider avec l'analyse CRM. Consultez la section CRM pour les données en direct.",
    "crm_priority_analysis": "Je peux analyser les leads par priorité. Consultez la section CRM pour les données en direct.",
    "crm_status_distribution": "Je peux afficher la distribution des leads par statut. Consultez la section CRM.",
    "crm_conversion_analysis": "Je peux calculer le taux de conversion CRM. Consultez la section CRM pour les données en direct.",
    "crm_followup_recommendations": "Je peux identifier les prospects à relancer. Consultez la section CRM.",
    "crm_draft_review_summary": "Je peux lister les brouillons à valider. Consultez la section CRM.",
    "crm_value_analysis": "Je peux analyser la valeur commerciale du pipeline. Consultez la section CRM.",
    "crm_comparison": "Je peux comparer l'activité CRM d'une semaine à l'autre. Consultez la section CRM pour les données en direct.",
    "leave_summary": "Je peux analyser les demandes de congé. Consultez la section Congés.",
    "leave_status_distribution": "Je peux afficher les demandes de congé par statut. Consultez la section Congés.",
    "leave_pending_approvals": "Je peux lister les demandes en attente d'approbation. Consultez la section Validations.",
    "leave_block_reasons": "Je peux expliquer pourquoi des demandes sont bloquées. Consultez la section Congés.",
    "leave_balance_block_analysis": "Je peux analyser les problèmes de solde. Consultez la section Congés.",
    "leave_overlap_block_analysis": "Je peux détecter les chevauchements de congé. Consultez la section Congés.",
    "leave_approval_rate": "Je peux calculer le taux d'approbation des congés. Consultez la section Congés.",
    "business_summary": "Je peux vous donner un résumé de la situation CRM et des congés.",
    "today_actions": "Je peux vous indiquer les actions prioritaires du jour.",
    "automation_health": "Je peux analyser la santé des automatisations si vous avez la permission monitoring.",
    "general": "Bonjour ! Je suis FlowPilot AI. Je peux vous aider avec le CRM et les demandes de congé.",
    "out_of_scope": (
        "Pour cette version, je peux analyser uniquement les processus CRM et Demandes de congé. "
        "Les workflows, agents IA et autres sujets ne sont pas couverts par cet assistant."
    ),
    "unknown": (
        "Je n'ai pas bien compris votre demande. "
        "Je peux vous aider avec le CRM ou les demandes de congé. "
        "Pouvez-vous reformuler ?"
    ),
}

_OUT_OF_SCOPE_ACTIONS: Final[list[SuggestedAction]] = [
    SuggestedAction(label="Analyser le CRM", action_type="query", payload={"message": "Donne-moi une analyse CRM"}),
    SuggestedAction(label="Analyser les demandes de congé", action_type="query", payload={"message": "Donne-moi une analyse des congés"}),
    SuggestedAction(label="Voir les priorités métier", action_type="query", payload={"message": "Que dois-je traiter aujourd'hui ?"}),
]

_UNKNOWN_ACTIONS: Final[list[SuggestedAction]] = [
    SuggestedAction(label="Leads par priorité", action_type="query", payload={"message": "Montre-moi les leads par priorité"}),
    SuggestedAction(label="Demandes de congé en attente", action_type="query", payload={"message": "Combien de demandes attendent le manager ?"}),
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def _call_tool(intent: AssistantIntent, db: Session) -> ToolResult | None:
    tool_fn = _TOOL_REGISTRY.get(intent)
    if tool_fn is None:
        return None
    try:
        return tool_fn(db)
    except Exception:
        logger.exception("Assistant tool failed for intent '%s'.", intent)
        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def process_chat(
    request: AssistantChatRequest,
    db: Session,
    permissions: list[str] | None = None,
    user_full_name: str = "",
    user_role_name: str = "",
) -> AssistantChatResponse:
    """
    Classify the message, dispatch to the matching tool, return a response.
    The DB session is injected by the API layer; this function never writes to it.

    Hybrid behaviour:
      - All 17 specific intents stay on the deterministic analytics path
        and keep their visualisations / sources / suggested actions.
      - `unknown` and `general` are routed through OpenRouter when the API
        key is configured, so the assistant can handle open questions and
        email drafting without losing the structured path for the rest.
      - If OpenRouter is unavailable, the existing static fallbacks apply.
    """
    intent: AssistantIntent = _classify_intent(request.message)
    conversation_id = request.conversation_id or str(uuid.uuid4())
    effective_intent = _resolve_authorized_intent(intent, permissions or [])

    if effective_intent is None:
        return AssistantChatResponse(
            answer=(
                "Votre role ne permet pas d'analyser ce domaine. "
                "Je peux uniquement afficher les informations autorisees par vos permissions."
            ),
            intent=intent,
            mode="text",
            sources=[],
            suggested_actions=[],
            visualizations=[],
            conversation_id=conversation_id,
            display_mode="text",
        )

    # out_of_scope stays deterministic — we intentionally do NOT call the LLM
    # to keep the assistant focused on CRM + Leave.
    if effective_intent == "out_of_scope":
        return AssistantChatResponse(
            answer=_STATIC_ANSWERS[effective_intent],
            intent=effective_intent,
            mode="text",
            sources=[],
            suggested_actions=_OUT_OF_SCOPE_ACTIONS,
            visualizations=[],
            conversation_id=conversation_id,
            display_mode="text",
        )

    # `general` (greetings, capability questions) and `unknown` (no rule
    # matched) are exactly the cases where a grounded LLM adds value.
    if effective_intent in ("general", "unknown"):
        history = [
            {"role": m.role, "content": m.content}
            for m in request.conversation_history
        ]
        llm_answer = _try_llm_fallback(
            db=db,
            user_message=request.message,
            history=history,
            user_full_name=user_full_name,
            user_role_name=user_role_name,
        )
        if llm_answer is not None:
            return AssistantChatResponse(
                answer=llm_answer,
                intent=effective_intent,
                mode="text",
                sources=[
                    AssistantSource(
                        title="FlowPilot AI (modèle OpenRouter)",
                        source_type="external",
                        reference=None,
                    )
                ],
                suggested_actions=(
                    _UNKNOWN_ACTIONS if effective_intent == "unknown" else _OUT_OF_SCOPE_ACTIONS
                ),
                visualizations=[],
                conversation_id=conversation_id,
                display_mode="text",
            )
        return AssistantChatResponse(
            answer=_STATIC_ANSWERS[effective_intent],
            intent=effective_intent,
            mode="text",
            sources=[],
            suggested_actions=_UNKNOWN_ACTIONS,
            visualizations=[],
            conversation_id=conversation_id,
            display_mode="text",
        )

    tool_result = _call_tool(effective_intent, db)

    if tool_result is not None:
        answer = tool_result["summary"]
        visualizations: list[VisualizationData] = tool_result["visualizations"]
        sources: list[AssistantSource] = tool_result["sources"]
        suggested_actions: list[SuggestedAction] = tool_result["suggested_actions"]
        mode = "mixed" if visualizations else "text"
    else:
        # Graceful static fallback (DB unavailable)
        answer = _STATIC_ANSWERS.get(effective_intent, _STATIC_ANSWERS["unknown"])
        visualizations = []
        sources = []
        suggested_actions = _OUT_OF_SCOPE_ACTIONS
        mode = "text"

    response = AssistantChatResponse(
        answer=answer,
        intent=effective_intent,
        mode=mode,  # type: ignore[arg-type]
        sources=sources,
        suggested_actions=suggested_actions,
        visualizations=visualizations,
        conversation_id=conversation_id,
        display_mode="legacy" if visualizations else "text",
    )

    openui_content = build_openui_response(
        request_message=request.message,
        response=response,
        permissions=permissions or [],
    )
    if openui_content:
        response.display_mode = "openui"
        response.openui_content = openui_content
        response.openui_version = OPENUI_VERSION

    return response


def _resolve_authorized_intent(
    intent: AssistantIntent,
    permissions: list[str],
) -> AssistantIntent | None:
    has_crm = "crm.leads.view" in permissions
    has_leave = _has_any(
        permissions,
        [
            "leave.request.view_own",
            "leave.request.view_all",
            "leave.request.create",
            "leave.request.approve",
        ],
    )

    if intent in CRM_INTENTS:
        return intent if has_crm else None

    if intent in LEAVE_INTENTS:
        return intent if has_leave else None

    if intent in MONITORING_INTENTS:
        return intent if "workflow.monitor.view" in permissions else None

    if intent in BUSINESS_INTENTS:
        if has_crm and has_leave:
            return intent
        if has_crm:
            return "crm_summary"
        if has_leave:
            return "leave_summary"
        return None

    return intent


def _has_any(permissions: list[str], required_permissions: list[str]) -> bool:
    return not set(permissions).isdisjoint(required_permissions)


def _try_llm_fallback(
    *,
    db: Session,
    user_message: str,
    history: list[dict[str, str]],
    user_full_name: str,
    user_role_name: str,
) -> str | None:
    """Build a grounded prompt and ask OpenRouter. Returns None on any failure."""
    try:
        snapshot = build_grounding_snapshot(db)
    except Exception:
        logger.exception("Failed to build grounding snapshot — skipping LLM.")
        return None
    system_prompt = build_system_prompt(user_role_name, user_full_name, snapshot)
    return call_openrouter(system_prompt=system_prompt, history=history, user_message=user_message)
