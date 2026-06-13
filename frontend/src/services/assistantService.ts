import { post } from './apiClient'

// ---------------------------------------------------------------------------
// Request / Response types — mirror backend schemas/assistant.py V2
// ---------------------------------------------------------------------------

type AssistantIntent =
  | 'crm_summary'
  | 'crm_priority_analysis'
  | 'crm_status_distribution'
  | 'crm_conversion_analysis'
  | 'crm_followup_recommendations'
  | 'crm_draft_review_summary'
  | 'crm_value_analysis'
  | 'crm_comparison'
  | 'leave_summary'
  | 'leave_status_distribution'
  | 'leave_pending_approvals'
  | 'leave_block_reasons'
  | 'leave_balance_block_analysis'
  | 'leave_overlap_block_analysis'
  | 'leave_approval_rate'
  | 'business_summary'
  | 'today_actions'
  | 'automation_health'
  | 'general'
  | 'out_of_scope'
  | 'unknown'
  // legacy broad intents kept for backward compat
  | 'crm_query'
  | 'leave_query'

type AssistantMode = 'text' | 'table' | 'chart' | 'mixed'
type AssistantDisplayMode = 'text' | 'legacy' | 'openui'

type VisualizationData = {
  type: 'bar_chart' | 'line_chart' | 'pie_chart' | 'table' | 'kpi'
  title: string
  description?: string | null
  /** Generic payload — shape depends on `type` */
  data: Record<string, unknown>
}

type SuggestedAction = {
  label: string
  action_type:
    | 'navigate'
    | 'query'
    | 'trigger_agent'
    | 'open_modal'
    | 'refresh'
    | 'filter'
    | 'open_details'
    | 'prepare_followups'
    | 'generate_email_draft'
    | 'create_task'
    | 'launch_report'
    | 'send_approved_email'
  payload: Record<string, unknown>
}

type AssistantSource = {
  title: string
  source_type: 'database' | 'document' | 'workflow' | 'agent' | 'external'
  reference?: string | null
}

type AssistantHistoryMessage = {
  role: 'user' | 'assistant'
  content: string
}

type AssistantChatRequest = {
  message: string
  conversation_id?: string | null
  /** Recent turns sent so the LLM fallback (unknown/general intents) can ground itself. */
  conversation_history?: AssistantHistoryMessage[]
  context?: Record<string, unknown>
}

type AssistantActionRequest = {
  action: SuggestedAction
  idempotency_key?: string | null
  confirmed?: boolean
}

type AssistantActionResponse = {
  status: 'accepted' | 'rejected' | 'deferred'
  message: string
}

type AssistantChatResponse = {
  answer: string
  intent: AssistantIntent
  mode: AssistantMode
  sources: AssistantSource[]
  suggested_actions: SuggestedAction[]
  visualizations: VisualizationData[]
  conversation_id?: string | null
  display_mode?: AssistantDisplayMode | null
  openui_content?: string | null
  openui_version?: string | null
}

// ---------------------------------------------------------------------------
// API call — React calls only FastAPI, never n8n or OpenRouter
// ---------------------------------------------------------------------------

function sendAssistantMessage(request: AssistantChatRequest) {
  return post<AssistantChatResponse>('/assistant/chat', request)
}

function validateAssistantAction(request: AssistantActionRequest) {
  return post<AssistantActionResponse>('/assistant/actions', request)
}

export type {
  AssistantActionRequest,
  AssistantActionResponse,
  AssistantChatRequest,
  AssistantChatResponse,
  AssistantDisplayMode,
  AssistantHistoryMessage,
  AssistantIntent,
  AssistantMode,
  AssistantSource,
  SuggestedAction,
  VisualizationData,
}
export { sendAssistantMessage, validateAssistantAction }
