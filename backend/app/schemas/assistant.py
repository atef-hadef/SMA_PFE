from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Precise user-facing intents — V2
# Workflow and agent intents are intentionally absent: the assistant focuses
# only on CRM and Leave Request processes.
# ---------------------------------------------------------------------------
AssistantIntent = Literal[
    # CRM — precise
    "crm_summary",
    "crm_priority_analysis",
    "crm_status_distribution",
    "crm_conversion_analysis",
    "crm_followup_recommendations",
    "crm_draft_review_summary",
    "crm_value_analysis",
    "crm_comparison",
    # Leave Request — precise
    "leave_summary",
    "leave_status_distribution",
    "leave_pending_approvals",
    "leave_block_reasons",
    "leave_balance_block_analysis",
    "leave_overlap_block_analysis",
    "leave_approval_rate",
    # Business / global
    "business_summary",
    "today_actions",
    "automation_health",
    # Meta
    "general",       # Greeting / help
    "out_of_scope",  # Workflow, agents, unrelated — polite redirect
    "unknown",       # Fallback when nothing matches
]

# Response mode hints the frontend on how to render the answer
AssistantMode = Literal["text", "table", "chart", "mixed"]
AssistantDisplayMode = Literal["text", "legacy", "openui"]


# ---------------------------------------------------------------------------
# Visualisation payload (chart / table data)
# ---------------------------------------------------------------------------
class VisualizationData(BaseModel):
    # kpi added for single-value metric cards
    type: Literal["bar_chart", "line_chart", "pie_chart", "table", "kpi"]
    title: str
    description: str | None = None
    # Generic key-value payload — the frontend decides how to render it
    data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Suggested follow-up action
# ---------------------------------------------------------------------------
class SuggestedAction(BaseModel):
    label: str
    action_type: Literal[
        "navigate",
        "query",
        "trigger_agent",
        "open_modal",
        "refresh",
        "filter",
        "open_details",
        "prepare_followups",
        "generate_email_draft",
        "create_task",
        "launch_report",
        "send_approved_email",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Source reference (document / record that informed the answer)
# ---------------------------------------------------------------------------
class AssistantSource(BaseModel):
    title: str
    source_type: Literal["database", "document", "workflow", "agent", "external"]
    reference: str | None = None


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class AssistantHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=8192)


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    # Optional conversation history for multi-turn context
    conversation_id: str | None = None
    # Recent turns sent by the frontend so the LLM fallback can ground itself.
    # Ignored by deterministic intents — they remain stateless.
    conversation_history: list[AssistantHistoryMessage] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class AssistantChatResponse(BaseModel):
    answer: str
    intent: AssistantIntent
    mode: AssistantMode
    sources: list[AssistantSource] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    visualizations: list[VisualizationData] = Field(default_factory=list)
    conversation_id: str | None = None
    display_mode: AssistantDisplayMode | None = None
    openui_content: str | None = None
    openui_version: str | None = None


class AssistantActionRequest(BaseModel):
    action: SuggestedAction
    idempotency_key: str | None = Field(default=None, max_length=128)
    confirmed: bool = False


class AssistantActionResponse(BaseModel):
    status: Literal["accepted", "rejected", "deferred"]
    message: str
