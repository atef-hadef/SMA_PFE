"""OpenUI formatter for the FlowPilot assistant.

This service receives an already-authorized AssistantChatResponse and formats
it as OpenUI Lang. It never queries PostgreSQL and never executes
model-generated SQL. All numbers come from the existing assistant tools before
this service is called.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from app.core.config import settings
from app.schemas.assistant import AssistantChatResponse, AssistantIntent, AssistantSource, SuggestedAction, VisualizationData

logger = logging.getLogger(__name__)

OPENUI_VERSION = "0.5"
DisplayCategory = Literal[
    "simple_answer",
    "single_metric",
    "entity_list",
    "data_table",
    "analytical_dashboard",
    "comparison_dashboard",
    "funnel_analysis",
    "trend_analysis",
    "alert_summary",
    "workflow_action",
    "global_summary",
]
BusinessDomain = Literal["crm", "leave", "automation", "global"]

TECHNICAL_KEYS = {
    "id",
    "ID",
    "workflow_execution_id",
    "agent_run_id",
    "payload",
    "raw_payload",
    "sql",
    "webhook_url",
    "webhook_name",
    "trace_id",
}

DASHBOARD_INTENTS: set[AssistantIntent] = {
    "crm_summary",
    "crm_status_distribution",
    "crm_conversion_analysis",
    "crm_value_analysis",
    "crm_comparison",
    "leave_summary",
    "leave_status_distribution",
    "leave_approval_rate",
    "business_summary",
    "automation_health",
}

TABLE_INTENTS: set[AssistantIntent] = {
    "crm_priority_analysis",
    "crm_followup_recommendations",
    "crm_draft_review_summary",
    "leave_pending_approvals",
    "leave_block_reasons",
    "leave_balance_block_analysis",
    "leave_overlap_block_analysis",
    "today_actions",
}

WORKFLOW_ACTION_KEYWORDS = ("prepare", "prépare", "relance", "relances", "draft", "brouillon", "email")


def choose_display_category(intent: AssistantIntent, message: str, visualizations: list[VisualizationData]) -> DisplayCategory:
    lowered = message.lower()
    if intent == "crm_comparison" or any(
        keyword in lowered
        for keyword in ("compare", "comparaison", "semaine précédente", "semaine precedente", "semaine derniere", "semaine dernière")
    ):
        return "comparison_dashboard"
    if any(keyword in lowered for keyword in WORKFLOW_ACTION_KEYWORDS) and "relance" in lowered:
        return "workflow_action"
    if intent == "automation_health":
        return "alert_summary"
    if intent == "business_summary":
        return "global_summary"
    if "combien" in lowered and any(keyword in lowered for keyword in ("lead", "hot", "priorit", "congé", "conge", "demande")):
        return "single_metric"
    if intent == "crm_conversion_analysis":
        return "funnel_analysis"
    if intent in {"crm_status_distribution", "leave_status_distribution"}:
        return "trend_analysis"
    if intent in TABLE_INTENTS:
        return "entity_list"
    if intent in DASHBOARD_INTENTS and len(visualizations) > 1:
        return "analytical_dashboard"
    return "simple_answer"


def build_openui_response(
    *,
    request_message: str,
    response: AssistantChatResponse,
    permissions: list[str] | None = None,
) -> str | None:
    """Return OpenUI Lang content, or None to keep the legacy renderer.

    Generation strategy (Thesys-C1 style):
      1. Ask Mistral (via OpenRouter, JSON mode) to design the dashboard freely
         from the real backend data — `generate_dashboard_with_llm`.
      2. If the model is unavailable / errors / returns invalid output, fall
         back to the deterministic Python templates (`_build_deterministic_openui`).

    The LLM never touches SQL: it only receives the dict already produced by the
    authorized backend tool, so numbers cannot be invented or recalculated.
    """
    if not settings.OPENUI_ENABLED:
        return None
    if response.intent in {"out_of_scope", "unknown", "general"}:
        return None

    category = choose_display_category(response.intent, request_message, response.visualizations)
    try:
        llm_content = generate_dashboard_with_llm(
            question=request_message,
            intent=response.intent,
            data=_serialize_response_for_llm(response),
            permissions=permissions or [],
        )
        if _looks_like_openui(llm_content):
            return llm_content
        return _build_deterministic_openui(response=response, category=category)
    except Exception:
        logger.exception("OpenUI formatting failed; falling back to legacy renderer.")
        return None


# ===========================================================================
# LLM dashboard generation (Mistral via OpenRouter, JSON mode)
#
# The model designs the dashboard freely from the authorized backend data and
# returns a constrained JSON tree. We then convert that JSON to the OpenUI Lang
# string the frontend already understands. The model never emits the DSL
# directly and never sees SQL — only the dict produced by the backend tool.
# ===========================================================================

LLM_DASHBOARD_TIMEOUT_SECONDS = 15.0
LLM_DASHBOARD_MAX_TOKENS = 2000

# JSON "type" -> builder. Unknown types are silently dropped (graceful).
_COMPONENT_BUILDERS: dict[str, Any] = {}

_DASHBOARD_SYSTEM_PROMPT = """Tu es le moteur de Generative UI de FlowPilot, une plateforme RH/CRM.
À partir d'une question utilisateur et de données métier RÉELLES déjà calculées par le backend,
tu conçois un tableau de bord adaptatif (style Thesys C1) et tu le renvoies sous forme de JSON STRICT.

RÉPONSE : un objet JSON unique, AUCUN texte avant ou après, AUCun bloc markdown.

Structure racine :
{
  "title": "titre court du dashboard",
  "summary": "1 à 2 phrases qui répondent directement à la question",
  "sections": [ { "title": "string|null", "description": "string|null", "components": [ <composant>, ... ] } ]
}

Composants disponibles (champ "type" obligatoire) :
- {"type":"kpi_grid","cards":[{"label","value","detail?","trend?","currency?","tone?"}]}  // 2 à 6 KPI
- {"type":"single_metric","label","value","detail?","tone?","currency?"}  // réponse courte "combien"
- {"type":"bar_chart","title","description?","data":[{"label","value","secondaryValue?"}]}
- {"type":"line_chart","title","description?","data":[{"label","value"}]}
- {"type":"pie_chart","title","description?","data":[{"label","value"}]}
- {"type":"funnel_chart","title","description?","data":[{"label","value"}]}  // conversion lead->prospect->client
- {"type":"table","title","description?","columns":[{"key","label","align?"}],"rows":[{...}]}
- {"type":"priority_lead_table","title","description?","rows":[{"name","company?","score?","status?","nextAction?","owner?"}]}
- {"type":"alert_list","title?","items":[...],"tone?"}
- {"type":"insight_list","title?","items":[...]}        // observations factuelles
- {"type":"recommendation_list","title?","items":[...]} // conseils IA, jamais des certitudes
- {"type":"suggested_actions","title?","actions":[{"label","actionType","route?","message?","requiresConfirmation?"}]}
- {"type":"workflow_health","title?","successCount","failureCount","pendingCount","summary?"}
- {"type":"source_list","sources":[{"label","type?"}]}
- {"type":"text","title?","text","tone?"}
- {"type":"insufficient_data","title","message","detail?"}
- {"type":"empty_state","title","message"}

Valeurs autorisées :
- tone : neutral | success | warning | danger | info
- actionType : navigate | refresh | filter | open_details | prepare_followups | generate_email_draft | create_task | launch_report | send_approved_email | query

RÈGLES STRICTES :
0. L'exemple en bas n'est qu'une illustration de STRUCTURE. Ne recopie JAMAIS ses phrases, ses
   libellés ni ses valeurs. Rédige chaque observation, recommandation et résumé à partir des
   CHIFFRES RÉELS et des NOMS présents dans "data" (scores, statuts, entreprises, dates...).
   Tes observations doivent citer des éléments concrets des données (ex : un nom de lead, un score,
   un écart chiffré), pas des généralités.
1. N'invente JAMAIS de chiffres. Utilise UNIQUEMENT les valeurs présentes dans le contexte "data" fourni.
2. Adapte le layout à la question :
   - question de comparaison → bar_chart en premier, puis KPI de variation ;
   - résumé / vue d'ensemble → kpi_grid en premier, puis graphique, puis insights ;
   - question d'alerte / santé → alert_list ou workflow_health en premier ;
   - question "combien" simple → un seul single_metric, pas de graphiques inutiles.
3. Ne mélange jamais les domaines : utilise seulement les données fournies (un seul domaine par réponse).
4. Termine toujours par une section avec "suggested_actions" en réutilisant EXACTEMENT les routes présentes
   dans data.suggested_actions (ex : /crm-leads, /leave-request, /manager-approvals). Ne propose pas d'action
   dont la route n'existe pas dans data.suggested_actions.
5. Toute action mutante (envoi d'e-mail, création de tâche, préparation de relances) doit avoir
   "requiresConfirmation": true.
6. Si data est vide / null / sans visualisation exploitable → renvoie une section avec un seul
   "insufficient_data" qui explique pourquoi aucune tendance fiable n'est possible.
7. Inclus toujours une "source_list" finale, avec des libellés lisibles
   (ex : "Données CRM", "Brouillons CRM", "Demandes de congé"), jamais de noms de table bruts.
8. N'inclus JAMAIS d'identifiants techniques, d'UUID, de SQL, de payload brut ni de jargon technique
   ("calculé depuis PostgreSQL", etc.).
9. Toute la rédaction est en français, professionnelle et concise.

EXEMPLE DE STRUCTURE UNIQUEMENT (illustre la forme JSON — n'en recopie NI les libellés NI les phrases) :
{
  "title": "Résumé CRM",
  "summary": "<phrase rédigée à partir des vrais chiffres de data>",
  "sections": [
    {"title":"Indicateurs","components":[
      {"type":"kpi_grid","cards":[
        {"label":"Leads","value":12,"detail":"Total du pipeline","tone":"info"},
        {"label":"Haute priorité","value":2,"detail":"Action requise","tone":"warning"},
        {"label":"Clients","value":3,"detail":"Conversions","tone":"success"}
      ]}
    ]},
    {"title":"Répartition","components":[
      {"type":"bar_chart","title":"Leads par statut","data":[{"label":"hot","value":2},{"label":"warm","value":6},{"label":"cold","value":4}]}
    ]},
    {"title":"Analyse","components":[
      {"type":"insight_list","items":["<observation factuelle citant un chiffre/nom réel de data>"]},
      {"type":"recommendation_list","items":["<recommandation concrète déduite des données>"]}
    ]},
    {"title":"Suite","components":[
      {"type":"suggested_actions","actions":[{"label":"Ouvrir le pipeline CRM","actionType":"navigate","route":"/crm-leads"}]},
      {"type":"source_list","sources":[{"label":"Données CRM","type":"database"}]}
    ]}
  ]
}
"""


def generate_dashboard_with_llm(
    *,
    question: str,
    intent: AssistantIntent,
    data: dict[str, Any],
    permissions: list[str],
) -> str | None:
    """Generate an OpenUI dashboard with Mistral (JSON mode). None on any failure.

    Args:
        question: the original natural-language user question.
        intent: the detected business intent (single domain only).
        data: the serialized, already-authorized backend payload (answer +
            visualizations + suggested_actions + sources). No SQL, no DB access.
        permissions: the caller's permission codes, so the model avoids
            suggesting actions the user cannot perform.

    Returns:
        OpenUI Lang string (``root = AssistantDashboard(...)``) or ``None`` to
        let the deterministic template fallback take over.
    """
    if not settings.OPENUI_ENABLED:
        return None
    if not settings.OPENROUTER_API_KEY:
        logger.info("OpenRouter API key missing; skipping LLM dashboard generation.")
        return None

    try:
        import httpx
    except ImportError:
        logger.warning("httpx unavailable; LLM dashboard generation skipped.")
        return None

    payload = {
        "model": settings.OPENUI_MODEL or settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": _dashboard_system_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question,
                        "intent": intent,
                        "permissions": permissions,
                        "data": data,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": LLM_DASHBOARD_MAX_TOKENS,
    }
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.FRONTEND_ORIGIN,
        "X-Title": "FlowPilot AI Generative UI",
    }

    try:
        with httpx.Client(timeout=LLM_DASHBOARD_TIMEOUT_SECONDS) as client:
            upstream = client.post(
                f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            upstream.raise_for_status()
            content = upstream.json()["choices"][0]["message"]["content"]
    except Exception:
        logger.warning("LLM dashboard call failed; using deterministic fallback.", exc_info=True)
        return None

    if not isinstance(content, str):
        return None

    try:
        parsed = json.loads(_strip_fences(content.strip()))
    except (json.JSONDecodeError, ValueError):
        logger.warning("LLM dashboard returned invalid JSON; using deterministic fallback.")
        return None

    openui = _dashboard_json_to_openui(parsed)
    if not _looks_like_openui(openui):
        logger.warning("LLM dashboard JSON did not yield a valid dashboard; using fallback.")
        return None
    return openui


def _serialize_response_for_llm(response: AssistantChatResponse) -> dict[str, Any]:
    """Build the read-only data context handed to the model (never SQL)."""
    return {
        "answer": response.answer,
        "visualizations": [_dump_visualization(v) for v in response.visualizations],
        "suggested_actions": [_dump_action(a) for a in response.suggested_actions],
        "sources": [_dump_source(s) for s in response.sources],
    }


def _dashboard_system_prompt() -> str:
    """System prompt describing the strict JSON contract and the components."""
    return _DASHBOARD_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# JSON -> OpenUI Lang conversion (deterministic, validates component names)
# ---------------------------------------------------------------------------

def _dashboard_json_to_openui(payload: Any) -> str | None:
    """Convert the model's JSON dashboard tree into an OpenUI Lang string."""
    if not isinstance(payload, dict):
        return None
    title = str(payload.get("title") or "Tableau de bord FlowPilot")
    summary = str(payload.get("summary") or "")
    raw_sections = payload.get("sections")
    if not isinstance(raw_sections, list):
        return None

    sections: list[str] = []
    for raw_section in raw_sections[:6]:
        if not isinstance(raw_section, dict):
            continue
        components = raw_section.get("components")
        if not isinstance(components, list):
            continue
        children: list[str] = []
        for node in components[:8]:
            built = _node_to_openui(node)
            if built:
                children.append(built)
        if not children:
            continue
        section_title = raw_section.get("title")
        section_desc = raw_section.get("description")
        sections.append(
            _component(
                "DashboardSection",
                str(section_title) if section_title else None,
                str(section_desc) if section_desc else None,
                [_raw(child) for child in children],
            )
        )

    if not sections:
        return None

    return _component(
        "AssistantDashboard",
        title,
        summary,
        [_raw(", ".join(sections))],
        assignment="root",
    )


def _node_to_openui(node: Any) -> str | None:
    """Map one JSON component node to its OpenUI Lang component call."""
    if not isinstance(node, dict):
        return None
    node_type = str(node.get("type") or "").lower()
    builder = _COMPONENT_BUILDERS.get(node_type)
    if builder is None:
        return None
    try:
        return builder(node)
    except Exception:
        logger.debug("Failed to build LLM component node '%s'.", node_type, exc_info=True)
        return None


def _coerce_points(raw: Any) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return points
    for item in raw[:10]:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        value = _to_float(item.get("value"))
        if label is None or value is None:
            continue
        point: dict[str, Any] = {"label": str(label), "value": value}
        secondary = _to_float(item.get("secondaryValue"))
        if secondary is not None:
            point["secondaryValue"] = secondary
        points.append(point)
    return points


def _coerce_str_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if isinstance(item, (str, int, float)) and str(item).strip()][:6]


def _coerce_tone(raw: Any) -> str:
    tone = str(raw or "neutral").lower()
    return tone if tone in {"neutral", "success", "warning", "danger", "info"} else "neutral"


_ACTION_TYPES = {
    "navigate", "refresh", "filter", "open_details", "prepare_followups",
    "generate_email_draft", "create_task", "launch_report", "send_approved_email", "query",
}
_MUTATING_ACTION_TYPES = {
    "prepare_followups", "generate_email_draft", "create_task", "launch_report", "send_approved_email",
}


def _build_kpi_grid(node: dict[str, Any]) -> str | None:
    cards: list[str] = []
    for card in (node.get("cards") or [])[:6]:
        if not isinstance(card, dict) or card.get("label") is None or card.get("value") is None:
            continue
        cards.append(
            _component(
                "KpiCard",
                str(card.get("label")),
                card.get("value"),
                str(card["detail"]) if card.get("detail") else None,
                str(card["trend"]) if card.get("trend") else None,
                str(card["currency"]) if card.get("currency") else None,
                _coerce_tone(card.get("tone")),
            )
        )
    if not cards:
        return None
    return _component("KpiGrid", [_raw(", ".join(cards))])


def _build_single_metric(node: dict[str, Any]) -> str | None:
    if node.get("label") is None or node.get("value") is None:
        return None
    return _component(
        "SingleMetricCard",
        str(node.get("label")),
        node.get("value"),
        str(node["detail"]) if node.get("detail") else None,
        _coerce_tone(node.get("tone")),
        str(node["currency"]) if node.get("currency") else None,
    )


def _build_chart(name: str):
    def builder(node: dict[str, Any]) -> str | None:
        points = _coerce_points(node.get("data"))
        if not points:
            return None
        return _component(
            name,
            str(node.get("title") or "Visualisation"),
            str(node["description"]) if node.get("description") else None,
            points,
        )
    return builder


def _build_table(node: dict[str, Any]) -> str | None:
    rows = _sanitize_rows(_rows_from_viz(VisualizationData(type="table", title="t", data={"rows": node.get("rows") or []})))
    if not rows:
        return None
    raw_columns = node.get("columns")
    if isinstance(raw_columns, list) and raw_columns:
        columns = [
            {
                "key": str(col.get("key")),
                "label": str(col.get("label") or col.get("key")),
                "align": col.get("align") if col.get("align") in {"left", "center", "right"} else ("right" if _is_numeric_column(rows, str(col.get("key"))) else "left"),
            }
            for col in raw_columns
            if isinstance(col, dict) and col.get("key")
        ]
    else:
        columns = [
            {"key": key, "label": key, "align": "right" if _is_numeric_column(rows, key) else "left"}
            for key in rows[0].keys()
        ]
    return _component(
        "SmartDataTable",
        str(node.get("title") or "Données"),
        str(node["description"]) if node.get("description") else None,
        columns,
        rows,
        "Aucune donnée disponible.",
    )


def _build_priority_lead_table(node: dict[str, Any]) -> str | None:
    mapped: list[dict[str, Any]] = []
    for row in (node.get("rows") or [])[: settings.OPENUI_MAX_TABLE_ROWS]:
        if not isinstance(row, dict) or row.get("name") is None:
            continue
        mapped.append(
            {
                "name": row.get("name"),
                "company": row.get("company"),
                "score": row.get("score"),
                "status": row.get("status"),
                "nextAction": row.get("nextAction") or row.get("next_action"),
                "owner": row.get("owner"),
            }
        )
    if not mapped:
        return None
    return _component(
        "PriorityLeadTable",
        str(node.get("title") or "Leads prioritaires"),
        str(node["description"]) if node.get("description") else "Leads nécessitant une action commerciale.",
        mapped,
        "Aucun lead prioritaire disponible.",
    )


def _build_alert_list(node: dict[str, Any]) -> str | None:
    items = _coerce_str_list(node.get("items"))
    if not items:
        return None
    return _component("AlertList", str(node.get("title") or "Alertes"), items, _coerce_tone(node.get("tone") or "warning"))


def _build_insight_list(node: dict[str, Any]) -> str | None:
    items = _coerce_str_list(node.get("items"))
    if not items:
        return None
    return _component("InsightList", str(node.get("title") or "Observations"), items)


def _build_recommendation_list(node: dict[str, Any]) -> str | None:
    items = _coerce_str_list(node.get("items"))
    if not items:
        return None
    return _component("RecommendationList", str(node.get("title") or "Recommandations IA"), items)


def _build_suggested_actions(node: dict[str, Any]) -> str | None:
    mapped: list[dict[str, Any]] = []
    for action in (node.get("actions") or [])[:5]:
        if not isinstance(action, dict) or not action.get("label"):
            continue
        action_type = str(action.get("actionType") or "navigate")
        if action_type not in _ACTION_TYPES:
            action_type = "navigate"
        requires_confirmation = bool(action.get("requiresConfirmation")) or action_type in _MUTATING_ACTION_TYPES
        mapped.append(
            {
                "label": str(action.get("label")),
                "actionType": action_type,
                "route": str(action["route"]) if action.get("route") else None,
                "targetId": str(action["targetId"]) if action.get("targetId") else None,
                "message": str(action["message"]) if action.get("message") else None,
                "requiresConfirmation": requires_confirmation,
            }
        )
    if not mapped:
        return None
    return _component("SuggestedActions", str(node.get("title") or "Actions suggérées"), mapped)


def _build_workflow_health(node: dict[str, Any]) -> str | None:
    return _component(
        "WorkflowHealthCard",
        str(node.get("title") or "Santé des automatisations"),
        int(_to_float(node.get("successCount")) or 0),
        int(_to_float(node.get("failureCount")) or 0),
        int(_to_float(node.get("pendingCount")) or 0),
        str(node["summary"]) if node.get("summary") else None,
    )


def _build_source_list(node: dict[str, Any]) -> str | None:
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for src in node.get("sources") or []:
        if not isinstance(src, dict) or not src.get("label"):
            continue
        label = _friendly_source(str(src.get("label")))
        if label in seen:  # dedupe — two raw tables can map to the same friendly label
            continue
        seen.add(label)
        sources.append({"label": label, "type": str(src["type"]) if src.get("type") else None})
    if not sources:
        return None
    return _component("SourceList", sources[:5])


def _build_text(node: dict[str, Any]) -> str | None:
    text = node.get("text")
    if not text:
        return None
    return _component("TextBlock", str(node["title"]) if node.get("title") else None, str(text), _coerce_tone(node.get("tone")))


def _build_insufficient_data(node: dict[str, Any]) -> str | None:
    message = node.get("message")
    if not message:
        return None
    return _component(
        "InsufficientDataState",
        str(node.get("title") or "Données limitées"),
        str(message),
        str(node["detail"]) if node.get("detail") else None,
    )


def _build_empty_state(node: dict[str, Any]) -> str | None:
    return _component(
        "EmptyState",
        str(node.get("title") or "Aucune donnée"),
        str(node.get("message") or "Aucune donnée disponible pour cette question."),
    )


_COMPONENT_BUILDERS.update(
    {
        "kpi_grid": _build_kpi_grid,
        "single_metric": _build_single_metric,
        "bar_chart": _build_chart("BarChartCard"),
        "line_chart": _build_chart("LineChartCard"),
        "pie_chart": _build_chart("PieChartCard"),
        "funnel_chart": _build_chart("FunnelChartCard"),
        "table": _build_table,
        "priority_lead_table": _build_priority_lead_table,
        "alert_list": _build_alert_list,
        "insight_list": _build_insight_list,
        "recommendation_list": _build_recommendation_list,
        "suggested_actions": _build_suggested_actions,
        "workflow_health": _build_workflow_health,
        "source_list": _build_source_list,
        "text": _build_text,
        "insufficient_data": _build_insufficient_data,
        "empty_state": _build_empty_state,
    }
)


def _build_deterministic_openui(
    *,
    response: AssistantChatResponse,
    category: DisplayCategory,
) -> str | None:
    sections: list[str] = []
    domain = _domain_for_intent(response.intent)
    visualizations = _filter_visualizations_for_domain(response.visualizations, domain)
    actions = _filter_actions_for_domain(response.suggested_actions, domain)
    sources = _filter_sources_for_domain(response.sources, domain)

    kpis = _kpi_cards(visualizations, domain)
    charts = [_chart_component(viz) for viz in visualizations if viz.type in {"bar_chart", "line_chart", "pie_chart"}]
    tables = [
        _table_component(viz, domain)
        for viz in visualizations
        if viz.type == "table" and not _looks_like_kpi_table(_rows_from_viz(viz))
    ]
    charts = [item for item in charts if item]
    tables = [item for item in tables if item]
    workflow_health = _workflow_health_component(visualizations)

    if category == "single_metric":
        single_metric = _single_metric_component(visualizations, domain)
        if single_metric:
            sections.append(_component("DashboardSection", "Réponse directe", None, [_raw(single_metric)]))
        charts = []
        tables = []
    elif workflow_health:
        sections.append(_component("DashboardSection", "Santé opérationnelle", None, [_raw(workflow_health)]))
    elif kpis:
        sections.append(_component("DashboardSection", "Indicateurs", None, [_raw(_component("KpiGrid", [_raw(", ".join(kpis))]))]))

    if category == "simple_answer":
        if not kpis and not charts and not tables:
            return None
    elif charts:
        title = "Comparaison" if category == "comparison_dashboard" else "Visualisations"
        sections.append(_component("DashboardSection", title, None, [_raw(item) for item in charts[:2]]))

    if tables:
        if category == "workflow_action":
            title = "Actions à préparer"
        elif domain == "crm":
            title = "Leads à suivre"
        elif domain == "leave":
            title = "Demandes à traiter"
        else:
            title = "Données détaillées"
        sections.append(_component("DashboardSection", title, None, [_raw(item) for item in tables[:2]]))

    insufficiency = _insufficient_data_component(response=response, category=category, visualizations=visualizations, domain=domain)
    if insufficiency:
        sections.append(_component("DashboardSection", "Fiabilité de lecture", None, [_raw(insufficiency)]))

    alerts = [] if category == "single_metric" else _alerts_from_response(response=response, visualizations=visualizations, domain=domain)
    if alerts:
        sections.append(_component("DashboardSection", "Alertes", None, [_raw(_component("AlertList", "Points d'attention", alerts, "warning"))]))

    insights = [] if category == "single_metric" else _insights_from_response(response, visualizations)
    if insights:
        sections.append(_component("DashboardSection", "Analyse", None, [_raw(_component("InsightList", "Observations", insights))]))

    recommendations = [] if category == "single_metric" else _recommendations_from_response(response=response, visualizations=visualizations, domain=domain)
    if recommendations:
        sections.append(_component("DashboardSection", "Recommandations", None, [_raw(_component("RecommendationList", "Recommandations IA", recommendations))]))

    actions_component = _actions_component(actions, category)
    sources_component = _sources_component(sources)
    guidance_children = [_raw(item) for item in [actions_component, sources_component] if item]
    if guidance_children:
        sections.append(_component("DashboardSection", "Suite", None, guidance_children))

    if not sections:
        return None

    return _component(
        "AssistantDashboard",
        _title_for_intent(response.intent),
        response.answer,
        [_raw(", ".join(sections))],
        assignment="root",
    )


def _kpi_cards(visualizations: list[VisualizationData], domain: BusinessDomain) -> list[str]:
    cards: list[str] = []
    for viz in visualizations:
        if viz.type == "kpi":
            label = str(viz.data.get("label") or viz.title)
            if not _label_matches_domain(label, domain):
                continue
            value = viz.data.get("value", "0")
            detail = viz.data.get("detail")
            cards.append(_component("KpiCard", label, value, detail, None, None, _tone_for_metric(label, value)))
        elif viz.type == "table":
            rows = _rows_from_viz(viz)
            if _looks_like_kpi_table(rows):
                for row in rows[:6]:
                    label = str(row.get("Indicateur") or row.get("label") or "Indicateur")
                    if not _label_matches_domain(label, domain):
                        continue
                    cards.append(
                        _component(
                            "KpiCard",
                            label,
                            row.get("Valeur") or row.get("value") or 0,
                            _short_kpi_detail(label, viz.description),
                            None,
                            _currency_for_row(row),
                            _tone_for_metric(label, row.get("Valeur") or row.get("value") or 0),
                        )
                    )
    return cards[:6]


def _single_metric_component(visualizations: list[VisualizationData], domain: BusinessDomain) -> str | None:
    for viz in visualizations:
        if viz.type == "kpi":
            label = str(viz.data.get("label") or viz.title)
            if _label_matches_domain(label, domain):
                return _component(
                    "SingleMetricCard",
                    label,
                    viz.data.get("value", "0"),
                    viz.data.get("detail") or _short_kpi_detail(label, None),
                    _tone_for_metric(label, viz.data.get("value", "0")),
                    _currency_for_row(viz.data),
                )
        if viz.type == "table":
            rows = _rows_from_viz(viz)
            if _looks_like_kpi_table(rows):
                for row in rows:
                    label = str(row.get("Indicateur") or row.get("label") or "Indicateur")
                    if _label_matches_domain(label, domain):
                        return _component(
                            "SingleMetricCard",
                            label,
                            row.get("Valeur") or row.get("value") or 0,
                            _short_kpi_detail(label, viz.description),
                            _tone_for_metric(label, row.get("Valeur") or row.get("value") or 0),
                            _currency_for_row(row),
                        )
            sanitized = _sanitize_rows(rows)
            if domain == "crm" and _looks_like_priority_lead_table(sanitized, viz.title):
                return _component(
                    "SingleMetricCard",
                    "Leads haute priorité",
                    len(sanitized),
                    "Leads à fort potentiel nécessitant une action commerciale.",
                    "warning" if sanitized else "info",
                    None,
                )
        if viz.type in {"bar_chart", "pie_chart", "line_chart"}:
            for point in _chart_points(viz):
                label = point["label"].lower()
                if domain == "crm" and any(keyword in label for keyword in ("high", "hot", "haute", "priorit")):
                    return _component(
                        "SingleMetricCard",
                        "Leads haute priorité",
                        point["value"],
                        "Leads nécessitant une action commerciale rapide.",
                        "warning" if point["value"] > 0 else "info",
                        None,
                    )
                if domain == "leave" and any(keyword in label for keyword in ("pending", "attente")):
                    return _component(
                        "SingleMetricCard",
                        "Demandes en attente",
                        point["value"],
                        "Demandes en attente d'une décision manager.",
                        "warning" if point["value"] > 0 else "info",
                        None,
                    )
    return None


def _chart_component(viz: VisualizationData) -> str | None:
    points = _chart_points(viz)
    if not points:
        return None
    if viz.type == "pie_chart":
        name = "PieChartCard"
    elif "conversion" in viz.title.lower():
        name = "FunnelChartCard"
    elif viz.type == "line_chart":
        name = "LineChartCard"
    else:
        name = "BarChartCard"
    return _component(name, viz.title, viz.description, points)


def _table_component(viz: VisualizationData, domain: BusinessDomain) -> str | None:
    rows = _sanitize_rows(_rows_from_viz(viz))
    if not rows:
        return _component("EmptyState", viz.title, viz.description or "Aucune donnée disponible.")
    if domain == "crm" and _looks_like_priority_lead_table(rows, viz.title):
        return _priority_lead_table_component(viz.title, viz.description, rows)
    columns = [{"key": key, "label": key, "align": "right" if _is_numeric_column(rows, key) else "left"} for key in rows[0].keys()]
    return _component("SmartDataTable", viz.title, viz.description, columns, rows, "Aucune donnée disponible.")


def _priority_lead_table_component(title: str, description: str | None, rows: list[dict[str, Any]]) -> str:
    mapped: list[dict[str, Any]] = []
    for row in rows[: settings.OPENUI_MAX_TABLE_ROWS]:
        mapped.append(
            {
                "name": row.get("Nom") or row.get("Lead") or row.get("name") or row.get("lead") or "-",
                "company": row.get("Entreprise") or row.get("Société") or row.get("company"),
                "score": row.get("Score") or row.get("score"),
                "status": row.get("Statut") or row.get("status"),
                "nextAction": row.get("Prochaine action") or row.get("next_action") or row.get("Action"),
                "owner": row.get("Propriétaire") or row.get("owner"),
            }
        )
    return _component(
        "PriorityLeadTable",
        title,
        description or "Leads nécessitant une action commerciale.",
        mapped,
        "Aucun lead prioritaire disponible.",
    )


def _actions_component(actions: list[SuggestedAction], category: DisplayCategory) -> str | None:
    if not actions:
        return None
    mapped = []
    for action in actions[:5]:
        payload = action.payload or {}
        is_mutation = action.action_type not in {"navigate", "query", "refresh", "filter", "open_details", "open_modal"}
        mapped.append(
            {
                "label": action.label,
                "actionType": action.action_type if action.action_type != "open_modal" else "open_details",
                "route": payload.get("route"),
                "targetId": payload.get("target_id") or payload.get("id"),
                "message": payload.get("message"),
                "requiresConfirmation": bool(is_mutation or category == "workflow_action" or payload.get("requires_confirmation")),
            }
        )
    return _component("SuggestedActions", "Actions suggérées", mapped)


def _sources_component(sources: list[AssistantSource]) -> str | None:
    if not sources:
        return None
    return _component("SourceList", [{"label": _friendly_source(source.title), "type": source.source_type} for source in sources[:5]])


def _domain_for_intent(intent: AssistantIntent) -> BusinessDomain:
    if intent.startswith("crm_"):
        return "crm"
    if intent.startswith("leave_"):
        return "leave"
    if intent == "automation_health":
        return "automation"
    return "global"


def _filter_visualizations_for_domain(visualizations: list[VisualizationData], domain: BusinessDomain) -> list[VisualizationData]:
    if domain == "global":
        return visualizations
    return [viz for viz in visualizations if _text_matches_domain(f"{viz.title} {viz.description or ''}", domain)]


def _filter_actions_for_domain(actions: list[SuggestedAction], domain: BusinessDomain) -> list[SuggestedAction]:
    if domain == "global":
        return actions

    filtered: list[SuggestedAction] = []
    for action in actions:
        payload = action.payload or {}
        route = str(payload.get("route") or "")
        text = f"{action.label} {route}"
        if _text_matches_domain(text, domain):
            filtered.append(action)
    return filtered


def _filter_sources_for_domain(sources: list[AssistantSource], domain: BusinessDomain) -> list[AssistantSource]:
    if domain == "global":
        return sources
    return [source for source in sources if _text_matches_domain(f"{source.title} {source.reference or ''}", domain)]


def _text_matches_domain(text: str, domain: BusinessDomain) -> bool:
    lowered = text.lower()
    if domain == "crm":
        return any(keyword in lowered for keyword in ("crm", "lead", "prospect", "pipeline", "client", "commercial", "brouillon", "conversion"))
    if domain == "leave":
        return any(keyword in lowered for keyword in ("leave", "cong", "absence", "approbation", "rh", "solde"))
    if domain == "automation":
        return any(keyword in lowered for keyword in ("workflow", "automation", "automatisation", "monitoring", "n8n", "execution", "exécution"))
    return True


def _label_matches_domain(label: str, domain: BusinessDomain) -> bool:
    if domain == "global":
        return True
    return _text_matches_domain(label, domain)


def _short_kpi_detail(label: str, fallback: str | None) -> str:
    """Return a short, indicator-specific hint — never a generic repeated line.

    Each KPI gets its own contextual sub-text so the dashboard does not repeat
    the same phrase on every card. Returns "" (no sub-text) when no specific
    context applies, keeping the card compact.
    """
    lowered = label.lower()
    # CRM — ordered most specific first
    if "conversion" in lowered or "taux" in lowered:
        return "Part des leads devenus clients"
    if any(keyword in lowered for keyword in ("hot", "haute priorité", "prioritaire", "priorité")):
        return "Action commerciale requise"
    if "prospect" in lowered:
        return "En cours de qualification"
    if "client" in lowered:
        return "Conversions réalisées"
    if "brouillon" in lowered or "draft" in lowered:
        return "En attente de relecture humaine"
    if "lead" in lowered:
        return "Total du pipeline commercial"
    # Leave
    if "attente" in lowered:
        return "Décision manager requise"
    if "approuv" in lowered:
        return "Demandes validées"
    if "refus" in lowered or "bloqu" in lowered:
        return "Demandes refusées ou bloquées"
    if "cong" in lowered or "demande" in lowered or "absence" in lowered:
        return "Total des demandes enregistrées"
    return fallback or ""


def _tone_for_metric(label: str, value: Any) -> str:
    lowered = label.lower()
    numeric = _to_float(value) or 0
    if any(keyword in lowered for keyword in ("échec", "refus", "bloqu", "conflit")) and numeric > 0:
        return "danger"
    if any(keyword in lowered for keyword in ("attente", "priorit", "hot", "brouillon")) and numeric > 0:
        return "warning"
    if any(keyword in lowered for keyword in ("succès", "approuv", "client")) and numeric > 0:
        return "success"
    return "info"


def _workflow_health_component(visualizations: list[VisualizationData]) -> str | None:
    success_count = 0
    failure_count = 0
    pending_count = 0
    for viz in visualizations:
        for row in _rows_from_viz(viz):
            label = str(row.get("Indicateur") or row.get("label") or row.get("Statut") or row.get("name") or "")
            value = row.get("Valeur") or row.get("value") or row.get("count") or row.get("Nombre") or 0
            numeric = int(_to_float(value) or 0)
            lowered = label.lower()
            if any(keyword in lowered for keyword in ("succès", "success", "réussi")):
                success_count += numeric
            elif any(keyword in lowered for keyword in ("échec", "failed", "failure", "erreur")):
                failure_count += numeric
            elif any(keyword in lowered for keyword in ("attente", "pending", "queue")):
                pending_count += numeric
        if viz.type == "kpi":
            label = str(viz.data.get("label") or viz.title)
            value = int(_to_float(viz.data.get("value")) or 0)
            lowered = label.lower()
            if "succ" in lowered:
                success_count += value
            elif "échec" in lowered or "echec" in lowered or "erreur" in lowered:
                failure_count += value
            elif "attente" in lowered or "pending" in lowered:
                pending_count += value

    if success_count == 0 and failure_count == 0 and pending_count == 0:
        return None
    summary = "Synthèse des exécutions connues, sans exposition des logs techniques."
    return _component("WorkflowHealthCard", "Santé des automatisations", success_count, failure_count, pending_count, summary)


def _insufficient_data_component(
    *,
    response: AssistantChatResponse,
    category: DisplayCategory,
    visualizations: list[VisualizationData],
    domain: BusinessDomain,
) -> str | None:
    if category not in {"analytical_dashboard", "comparison_dashboard", "trend_analysis", "funnel_analysis"}:
        return None
    rows = [row for viz in visualizations for row in _rows_from_viz(viz) if not _looks_like_kpi_table([row])]
    points = [point for viz in visualizations for point in _chart_points(viz)]
    if len(rows) + len(points) > 1:
        return None
    if domain == "crm":
        message = "Le volume CRM disponible est faible. Les faits sont affichés, mais aucune tendance fiable ne doit être déduite."
    elif domain == "leave":
        message = "Le volume de demandes est faible. La synthèse reste factuelle et ne conclut pas à une tendance RH."
    else:
        message = "Le volume de données disponible est limité. L'analyse reste prudente."
    return _component("InsufficientDataState", "Données limitées", message, response.answer)


def _alerts_from_response(
    *,
    response: AssistantChatResponse,
    visualizations: list[VisualizationData],
    domain: BusinessDomain,
) -> list[str]:
    alerts: list[str] = []
    if domain == "automation":
        for point in [point for viz in visualizations for point in _chart_points(viz)]:
            if any(keyword in point["label"].lower() for keyword in ("échec", "echec", "failed", "erreur")) and point["value"] > 0:
                alerts.append("Des échecs d'automatisation sont présents et doivent être vérifiés avant relance.")
                break
    if domain == "crm":
        for row in [row for viz in visualizations for row in _rows_from_viz(viz)]:
            score = _to_float(row.get("Score") or row.get("score"))
            status = str(row.get("Statut") or row.get("status") or "").lower()
            if (score is not None and score >= 80) or "hot" in status:
                alerts.append("Au moins un lead prioritaire nécessite une action commerciale.")
                break
    if domain == "leave" and "attente" in response.answer.lower():
        alerts.append("Des demandes peuvent nécessiter une décision ou une vérification RH.")
    return alerts[:3]


def _looks_like_priority_lead_table(rows: list[dict[str, Any]], title: str) -> bool:
    lowered_title = title.lower()
    if any(keyword in lowered_title for keyword in ("lead", "prospect", "priorit", "relance")):
        return True
    if not rows:
        return False
    keys = {key.lower() for key in rows[0].keys()}
    return bool({"nom", "entreprise", "score", "statut"} & keys) and ("score" in keys or "statut" in keys)


def _chart_points(viz: VisualizationData) -> list[dict[str, Any]]:
    data = viz.data
    rows = data.get("data") if isinstance(data.get("data"), list) else _rows_from_viz(viz)
    x_key = data.get("xKey")
    y_key = data.get("yKey")
    points: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if isinstance(x_key, str) and isinstance(y_key, str):
            label = row.get(x_key)
            value = row.get(y_key)
        else:
            label = row.get("name") or row.get("label") or row.get("Statut") or row.get("Indicateur")
            value = row.get("value") or row.get("count") or row.get("nombre") or row.get("Nombre") or row.get("Valeur")
        numeric = _to_float(value)
        if label is not None and numeric is not None:
            points.append({"label": str(label), "value": numeric})
    return points[:10]


def _rows_from_viz(viz: VisualizationData) -> list[dict[str, Any]]:
    rows = viz.data.get("rows") or viz.data.get("data")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _sanitize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    max_rows = max(1, settings.OPENUI_MAX_TABLE_ROWS)
    sanitized: list[dict[str, Any]] = []
    for row in rows[:max_rows]:
        clean = {
            str(key): _safe_cell(value)
            for key, value in row.items()
            if str(key) not in TECHNICAL_KEYS and not str(key).lower().endswith("_id")
        }
        if clean:
            sanitized.append(clean)
    return sanitized


def _safe_cell(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _looks_like_kpi_table(rows: list[dict[str, Any]]) -> bool:
    return bool(rows) and ("Indicateur" in rows[0] and "Valeur" in rows[0])


def _currency_for_row(row: dict[str, Any]) -> str | None:
    currency = row.get("Devise") or row.get("Currency") or row.get("currency")
    if isinstance(currency, str) and currency.strip():
        return currency.strip()
    return None


def _is_numeric_column(rows: list[dict[str, Any]], key: str) -> bool:
    return any(isinstance(row.get(key), (int, float)) for row in rows)


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ".").replace("%", "").strip())
        except ValueError:
            return None
    return None


def _insights_from_response(response: AssistantChatResponse, visualizations: list[VisualizationData]) -> list[str]:
    facts: list[str] = []
    if response.answer:
        facts.append(response.answer)
    for viz in visualizations[:2]:
        if viz.description:
            facts.append(viz.description)
    return facts[:3]


def _recommendations_from_response(
    *,
    response: AssistantChatResponse,
    visualizations: list[VisualizationData],
    domain: BusinessDomain,
) -> list[str]:
    recommendations: list[str] = []
    rows = [row for viz in visualizations for row in _rows_from_viz(viz)]

    if domain == "crm":
        high_priority_rows = [
            row
            for row in rows
            if (_to_float(row.get("Score") or row.get("score")) or 0) >= 80
            or "hot" in str(row.get("Statut") or row.get("status") or "").lower()
        ]
        if high_priority_rows:
            recommendations.append("Traiter le lead prioritaire avant d'élargir l'analyse du pipeline.")
            recommendations.append("Préparer une relance personnalisée après vérification du contexte commercial.")
        if len(rows) <= 1:
            recommendations.append("Le volume CRM est faible : rester factuel et éviter de conclure une tendance.")
    elif domain == "leave":
        if "attente" in response.answer.lower():
            recommendations.append("Prioriser les demandes en attente selon les règles RH et la disponibilité manager.")
        if len(rows) <= 1:
            recommendations.append("Conserver une lecture prudente tant que le volume de demandes reste limité.")
    elif domain == "automation":
        if any("échec" in point["label"].lower() and point["value"] > 0 for viz in visualizations for point in _chart_points(viz)):
            recommendations.append("Analyser les échecs avant toute relance de workflow.")
        recommendations.append("Surveiller les exécutions en attente avant de déclencher une action automatique.")
    else:
        recommendations.append("Traiter chaque domaine dans sa page dédiée pour une analyse plus fine.")

    return recommendations[:3]


def _friendly_source(title: str) -> str:
    lowered = title.lower()
    if "crm_email" in lowered or "draft" in lowered:
        return "Brouillons CRM"
    if "crm" in lowered or "lead" in lowered:
        return "Données CRM"
    if "leave" in lowered or "cong" in lowered:
        return "Demandes de congé"
    if "workflow" in lowered:
        return "Monitoring des automatisations"
    return title.replace("Table ", "")


def _title_for_intent(intent: AssistantIntent) -> str:
    labels: dict[AssistantIntent, str] = {
        "crm_summary": "Résumé CRM",
        "crm_priority_analysis": "Leads prioritaires",
        "crm_status_distribution": "Répartition CRM",
        "crm_conversion_analysis": "Conversion CRM",
        "crm_followup_recommendations": "Relances CRM",
        "crm_draft_review_summary": "Brouillons CRM",
        "crm_value_analysis": "Valeur du pipeline",
        "crm_comparison": "Comparaison hebdomadaire CRM",
        "leave_summary": "Résumé des congés",
        "leave_status_distribution": "Statuts des congés",
        "leave_pending_approvals": "Approbations en attente",
        "leave_block_reasons": "Blocages congés",
        "leave_balance_block_analysis": "Solde congés",
        "leave_overlap_block_analysis": "Chevauchements congés",
        "leave_approval_rate": "Taux d'approbation",
        "business_summary": "Dashboard métier",
        "automation_health": "Santé des automatisations",
        "today_actions": "Actions du jour",
        "general": "Assistant FlowPilot",
        "out_of_scope": "Hors périmètre",
        "unknown": "Assistant FlowPilot",
    }
    return labels.get(intent, "Dashboard FlowPilot")


class _Raw:
    def __init__(self, value: str) -> None:
        self.value = value


def _raw(value: str) -> _Raw:
    return _Raw(value)


def _component(name: str, *args: Any, assignment: str | None = None) -> str:
    rendered = ", ".join(_literal(arg) for arg in args)
    expr = f"{name}({rendered})"
    if assignment:
        return f"{assignment} = {expr}"
    return expr


def _literal(value: Any) -> str:
    if isinstance(value, _Raw):
        return value.value
    if isinstance(value, list):
        return "[" + ", ".join(_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_safe_key(k)}: {_literal(v)}" for k, v in value.items() if v is not None) + "}"
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False, default=str)


def _safe_key(key: Any) -> str:
    key_str = str(key)
    if key_str.isascii() and key_str.replace("_", "").isalnum() and not key_str[0].isdigit():
        return key_str
    return json.dumps(key_str, ensure_ascii=False)


def _looks_like_openui(content: str | None) -> bool:
    if not content:
        return False
    stripped = _strip_fences(content)
    return "root =" in stripped and "AssistantDashboard(" in stripped


def _strip_fences(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _dump_visualization(viz: VisualizationData) -> dict[str, Any]:
    return {"type": viz.type, "title": viz.title, "description": viz.description, "data": viz.data}


def _dump_action(action: SuggestedAction) -> dict[str, Any]:
    return {"label": action.label, "action_type": action.action_type, "payload": action.payload}


def _dump_source(source: AssistantSource) -> dict[str, Any]:
    return {"title": source.title, "source_type": source.source_type, "reference": source.reference}
