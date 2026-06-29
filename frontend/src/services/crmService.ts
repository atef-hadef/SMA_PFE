import { get, patch, post, remove } from './apiClient'

type CrmLeadInput = {
  name: string
  company: string
  email: string
  source: string
  message: string
}

type CrmLeadRecord = {
  id: string
  name: string
  company: string
  email: string
  phone?: string | null
  source: string
  customer_status?: string | null
  status: 'new' | 'hot' | 'warm' | 'cold'
  score: number
  priority?: string | null
  customer_category?: string | null
  product_service?: string | null
  estimated_value?: string | number | null
  location?: string | null
  is_active?: boolean
  next_action?: string | null
  sentiment: 'positive' | 'neutral' | 'negative'
  urgency: 'low' | 'medium' | 'high'
  assigned_to: string
  created_at: string
  last_contact_at?: string | null
  crm_display_state?: CrmDisplayState | null
}

type CrmDisplayState = {
  lifecycle_stage:
    | 'lead'
    | 'prospect'
    | 'customer'
    | 'active_customer'
    | 'inactive_customer'
    | 'loyal_customer'
    | 'vip_customer'
  display_stage: string
  current_state:
    | 'lead_collected'
    | 'lead_analyzed'
    | 'prospect_qualified'
    | 'draft_missing'
    | 'draft_generated'
    | 'draft_reviewed'
    | 'draft_approved'
    | 'email_sending'
    | 'email_sent_waiting_response'
    | 'positive_response_recorded'
    | 'negative_response_recorded'
    | 'neutral_response_recorded'
    | 'follow_up_required'
    | 'conversion_ready'
    | 'customer_converted'
    | 'welcome_draft_generated'
    | 'welcome_draft_approved'
    | 'welcome_email_sent'
    | 'failed'
  latest_draft_id?: string | null
  latest_draft_type?: 'communication' | 'welcome' | null
  latest_draft_status?: string | null
  response_state:
    | 'none'
    | 'waiting_response'
    | 'positive_response'
    | 'negative_response'
    | 'neutral_response'
    | 'follow_up_required'
    | 'not_interested'
    | 'unqualified'
    | 'unknown'
  latest_email_status: 'none' | 'sending' | 'sent' | 'failed'
  communication_email_sent: boolean
  welcome_email_sent: boolean
  waiting_for_response: boolean
  positive_response_recorded: boolean
  negative_response_recorded: boolean
  neutral_response_recorded: boolean
  follow_up_required: boolean
  conversion_ready: boolean
  conversion_pending?: boolean
  customer_converted: boolean
  needs_human_review: boolean
  needs_human_action: boolean
  primary_action: string
  secondary_actions: string[]
  computed_next_action: string
  ai_insight_text: string
  business_summary_text: string
  language: 'fr' | 'en'
  warnings: string[]
}

type CrmInteractionHistoryItem = {
  id: string
  interaction_type: string
  channel?: string | null
  summary: string
  interaction_date: string
  created_by?: string | null
  created_at: string
  business_label?: string | null
  draft_subject?: string | null
  draft_body?: string | null
  draft_status?: string | null
  draft_type?: 'communication' | 'welcome' | string | null
}

type CrmLeadInteractionInput = {
  interaction_type: 'email_reply' | 'phone_call' | 'meeting' | 'whatsapp' | 'manual_note'
  outcome:
    | 'confirmed_interest'
    | 'requested_more_information'
    | 'accepted_next_step'
    | 'no_response'
    | 'not_interested'
  note: string
  next_action?: string | null
  follow_up_date?: string | null
  created_by: string
}

type CrmLeadResponseType =
  | 'interested'
  | 'not_interested'
  | 'needs_more_info'
  | 'callback_requested'
  | 'no_response'

type CrmLeadResponseItem = {
  id: string
  lead_id: string
  response_type: CrmLeadResponseType
  notes?: string | null
  next_action?: string | null
  next_action_date?: string | null
  recorded_by?: string | null
  recorded_by_name?: string | null
  recorded_at: string
}

type CrmLeadResponseInput = {
  response_type: CrmLeadResponseType
  notes?: string | null
  next_action?: string | null
  next_action_date?: string | null
}

type CrmLeadResponseListResponse = { count: number; items: CrmLeadResponseItem[] }

type CrmLeadResponseCreatedResponse = {
  response: CrmLeadResponseItem
  lead_status?: string | null
  lead_customer_status?: string | null
  created_task_id?: string | null
  message: string
}

type CrmLeadDraftItem = {
  draft_type: 'sales' | 'welcome'
  subject?: string | null
  body?: string | null
  status?: string | null
  generated_at: string
  summary?: string | null
  channel?: string | null
}

type CrmEmailAttachmentItem = {
  id: string
  draft_id: string
  file_name: string
  mime_type?: string | null
  file_size_bytes: number
  uploaded_by?: string | null
  created_at: string
}

type CrmEmailDraftItem = {
  id: string
  lead_id: string
  draft_type: 'sales' | 'welcome' | 'follow_up' | 'reactivation' | 'proposal'
  subject?: string | null
  body?: string | null
  status:
    | 'draft_generated'
    | 'edited'
    | 'reviewed'
    | 'approved'
    | 'sending'
    | 'rejected'
    | 'sent'
    | 'failed'
  tone?: string | null
  cta?: string | null
  generated_by_agent?: string | null
  rejection_reason?: string | null
  created_at: string
  updated_at: string
  reviewed_at?: string | null
  approved_at?: string | null
  rejected_at?: string | null
  sent_at?: string | null
  edited_by?: string | null
  edited_by_name?: string | null
  reviewed_by?: string | null
  reviewed_by_name?: string | null
  approved_by?: string | null
  approved_by_name?: string | null
  rejected_by?: string | null
  rejected_by_name?: string | null
  attachments: CrmEmailAttachmentItem[]
}

type CrmEmailDraftUpdateInput = {
  subject?: string
  body?: string
  edited_by?: string
}

type ShapFactor = {
  feature: string
  label: string
  shap_value: number
  direction: 'positive' | 'negative' | string
  impact_pct: number
  description: string
}

type ShapExplanation = {
  explanation_text?: string
  top_factors?: ShapFactor[]
  model_version?: string
  delta?: number | null
  scored_at?: string
}

type CrmLeadDetail = CrmLeadRecord & {
  phone: string
  intention: string
  message: string
  ai_summary: string
  recommended_action: string
  notes?: string | null
  // Scoring ML (module Data Science). Null tant que le modèle n'a pas scoré le
  // lead -> l'UI retombe sur le score LLM (score) inchangé.
  ml_score?: number | null
  ml_probability?: number | null
  ml_category?: 'hot' | 'warm' | 'cold' | null
  ml_confidence?: number | null
  shap_explanation?: ShapExplanation | null
  drafts?: CrmLeadDraftItem[]
  interaction_history?: CrmInteractionHistoryItem[]
}

type CrmLeadCreatedResponse = {
  id: string
  name: string
  company: string
  email: string
  source: string
  status: 'new'
  score: number
  created_at: string
}

type CrmCommunicationDraftResponse = {
  lead_id: string
  n8n_response: unknown
}

type CrmCustomerConversionResponse = {
  lead_id: string
  message: string
  n8n_response: unknown
}

type CrmCustomerConversionInput = {
  human_validated: true
  validation_reason: string
  evidence_source: string
  next_action: string
  conversion_note: string
  requested_by: string
}

type CrmEmailDraftSendResponse = {
  ok: boolean
  message: string
}

type PaginationMeta = {
  page: number
  page_size: number
  total_items: number
  total_pages: number
}

type PaginatedResponse<T> = {
  items: T[]
  pagination: PaginationMeta
}

type LeadAnalysisInput = {
  leadId: string
}

type LeadScoringInput = {
  leadId: string
}

// Default page_size aligned with the backend cap (max 100, see crm_service.py
// get_crm_leads). Avoids the silent 20-row truncation the backend now enforces
// since Phase 4. Callers can still pass smaller pages once a real paginator UI
// is added.
function getCrmLeads(options: { page?: number; pageSize?: number } = {}) {
  const page = options.page ?? 1
  const pageSize = options.pageSize ?? 100
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  return get<PaginatedResponse<CrmLeadRecord>>(`/crm/leads?${params.toString()}`)
}

function getCrmLeadById(leadId: string) {
  return get<CrmLeadDetail>(`/crm/leads/${leadId}`)
}

function createCrmLead(input: CrmLeadInput) {
  return post<CrmLeadCreatedResponse>('/crm/leads', input)
}

function analyzeCrmLead(input: LeadAnalysisInput) {
  return post<{ leadId: string; sentiment: string; intention: string; urgency: string }>(
    `/crm/leads/${input.leadId}/analyze`,
    input,
  )
}

function scoreCrmLead(input: LeadScoringInput) {
  return post<{ leadId: string; score: number }>(`/crm/leads/${input.leadId}/score`, input)
}

function generateCommunicationDraft(leadId: string) {
  return post<CrmCommunicationDraftResponse>(
    `/crm/leads/${leadId}/generate-communication-draft`,
  )
}

function createLeadInteraction(leadId: string, input: CrmLeadInteractionInput) {
  return post<CrmInteractionHistoryItem>(`/crm/leads/${leadId}/interactions`, input)
}

function convertLeadToCustomer(leadId: string, input: CrmCustomerConversionInput) {
  return post<CrmCustomerConversionResponse>(
    `/crm/leads/${leadId}/convert-to-customer`,
    input,
  )
}

function getLeadDrafts(leadId: string) {
  return get<CrmEmailDraftItem[]>(`/crm/leads/${leadId}/drafts`)
}

function recordLeadResponse(leadId: string, input: CrmLeadResponseInput) {
  return post<CrmLeadResponseCreatedResponse>(`/crm/leads/${leadId}/responses`, input)
}

function getLeadResponses(leadId: string) {
  return get<CrmLeadResponseListResponse>(`/crm/leads/${leadId}/responses`)
}

function updateEmailDraft(draftId: string, payload: CrmEmailDraftUpdateInput) {
  return patch<CrmEmailDraftItem>(`/crm/email-drafts/${draftId}`, payload)
}

function reviewEmailDraft(draftId: string) {
  return post<CrmEmailDraftItem>(`/crm/email-drafts/${draftId}/review`)
}

function approveEmailDraft(draftId: string) {
  return post<CrmEmailDraftItem>(`/crm/email-drafts/${draftId}/approve`)
}

function rejectEmailDraft(draftId: string, reason: string) {
  // rejected_by is set server-side from the authenticated current_user
  // (see crm.py reject endpoint). No need to send it from the client.
  return post<CrmEmailDraftItem>(`/crm/email-drafts/${draftId}/reject`, {
    rejection_reason: reason,
  })
}

function uploadDraftAttachment(draftId: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  // uploaded_by is set server-side from current_user (see crm.py upload).

  return post<CrmEmailAttachmentItem>(`/crm/email-drafts/${draftId}/attachments`, formData)
}

function deleteDraftAttachment(draftId: string, attachmentId: string) {
  return remove<null>(`/crm/email-drafts/${draftId}/attachments/${attachmentId}`)
}

function sendApprovedEmailDraft(draftId: string) {
  return post<CrmEmailDraftSendResponse>(`/crm/email-drafts/${draftId}/send`)
}

export type {
  CrmCommunicationDraftResponse,
  CrmCustomerConversionInput,
  CrmCustomerConversionResponse,
  CrmEmailAttachmentItem,
  CrmEmailDraftItem,
  CrmEmailDraftSendResponse,
  CrmEmailDraftUpdateInput,
  CrmLeadInteractionInput,
  CrmLeadCreatedResponse,
  CrmLeadDetail,
  CrmLeadInput,
  CrmLeadDraftItem,
  CrmLeadResponseType,
  CrmLeadResponseItem,
  CrmLeadResponseInput,
  CrmLeadResponseListResponse,
  CrmLeadResponseCreatedResponse,
  CrmDisplayState,
  CrmInteractionHistoryItem,
  CrmLeadRecord,
  LeadAnalysisInput,
  LeadScoringInput,
  PaginatedResponse,
  ShapFactor,
  ShapExplanation,
}
export {
  analyzeCrmLead,
  convertLeadToCustomer,
  createLeadInteraction,
  createCrmLead,
  generateCommunicationDraft,
  getLeadDrafts,
  recordLeadResponse,
  getLeadResponses,
  getCrmLeadById,
  getCrmLeads,
  approveEmailDraft,
  deleteDraftAttachment,
  rejectEmailDraft,
  reviewEmailDraft,
  scoreCrmLead,
  sendApprovedEmailDraft,
  updateEmailDraft,
  uploadDraftAttachment,
}
