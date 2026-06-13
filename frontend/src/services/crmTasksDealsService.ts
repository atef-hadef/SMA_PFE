import { get, patch, post, remove } from './apiClient'

type CrmTaskStatus = 'pending' | 'done' | 'cancelled'
type CrmTaskPriority = 'low' | 'medium' | 'high'

type CrmTaskItem = {
  id: string
  lead_id: string | null
  lead_full_name: string | null
  lead_company_name: string | null
  owner_user_id: string
  owner_full_name: string | null
  owner_email: string | null
  title: string
  description: string | null
  due_date: string
  status: CrmTaskStatus
  priority: CrmTaskPriority
  task_type: string | null
  reminder_sent_at: string | null
  next_reminder_at: string | null
  completed_at: string | null
  created_by: string | null
  created_at: string
  updated_at: string
  days_until_due: number
  is_overdue: boolean
  comments_count: number
}

type CrmTaskListResponse = {
  count: number
  items: CrmTaskItem[]
}

type CrmTaskCreateInput = {
  title: string
  description?: string | null
  due_date: string
  priority?: CrmTaskPriority
  lead_id?: string | null
  owner_user_id: string
}

type CrmTaskUpdateInput = {
  title?: string
  description?: string | null
  due_date?: string
  priority?: CrmTaskPriority
  status?: CrmTaskStatus
  owner_user_id?: string
}

type CrmDealStage =
  | 'discovery'
  | 'proposal'
  | 'negotiation'
  | 'closing'
  | 'won'
  | 'lost'

type CrmDealItem = {
  id: string
  lead_id: string
  lead_full_name: string | null
  lead_company_name: string | null
  owner_user_id: string
  owner_full_name: string | null
  owner_email: string | null
  title: string
  stage: CrmDealStage
  previous_stage: string | null
  amount: string | number | null
  currency: string
  probability_percent: number
  expected_close_date: string | null
  notes: string | null
  won_reason: string | null
  lost_reason: string | null
  closed_at: string | null
  created_at: string
  updated_at: string
  comments_count: number
}

type CrmDealListResponse = {
  count: number
  items: CrmDealItem[]
}

type CrmDealCreateInput = {
  lead_id: string
  owner_user_id: string
  title: string
  amount?: number | string | null
  currency?: string
  probability_percent?: number
  expected_close_date?: string | null
  notes?: string | null
  stage?: CrmDealStage
}

type CrmDealUpdateInput = {
  title?: string
  amount?: number | string | null
  currency?: string
  probability_percent?: number
  expected_close_date?: string | null
  notes?: string | null
  owner_user_id?: string
}

type CrmDealStageTransitionInput = {
  new_stage: CrmDealStage
  reason?: string | null
  trigger_workflow?: boolean
}

type CrmDealStageTransitionResponse = {
  deal_id: string
  new_stage: CrmDealStage
  previous_stage: string | null
  workflow_triggered: boolean
  n8n_response: unknown
  message: string
}

// -------- Tasks --------

function listCrmTasks(params: {
  status?: CrmTaskStatus
  ownerUserId?: string
  leadId?: string
} = {}) {
  const query = new URLSearchParams()
  if (params.status) query.set('status', params.status)
  if (params.ownerUserId) query.set('owner_user_id', params.ownerUserId)
  if (params.leadId) query.set('lead_id', params.leadId)
  const qs = query.toString()
  return get<CrmTaskListResponse>(`/crm/tasks${qs ? `?${qs}` : ''}`)
}

function getCrmTask(taskId: string) {
  return get<CrmTaskItem>(`/crm/tasks/${taskId}`)
}

function createCrmTask(input: CrmTaskCreateInput) {
  return post<CrmTaskItem>('/crm/tasks', input)
}

function updateCrmTask(taskId: string, input: CrmTaskUpdateInput) {
  return patch<CrmTaskItem>(`/crm/tasks/${taskId}`, input)
}

function deleteCrmTask(taskId: string) {
  return remove<null>(`/crm/tasks/${taskId}`)
}

// -------- Deals --------

function listCrmDeals(params: {
  stage?: CrmDealStage
  ownerUserId?: string
  leadId?: string
} = {}) {
  const query = new URLSearchParams()
  if (params.stage) query.set('stage', params.stage)
  if (params.ownerUserId) query.set('owner_user_id', params.ownerUserId)
  if (params.leadId) query.set('lead_id', params.leadId)
  const qs = query.toString()
  return get<CrmDealListResponse>(`/crm/deals${qs ? `?${qs}` : ''}`)
}

function getCrmDeal(dealId: string) {
  return get<CrmDealItem>(`/crm/deals/${dealId}`)
}

function createCrmDeal(input: CrmDealCreateInput) {
  return post<CrmDealItem>('/crm/deals', input)
}

function updateCrmDeal(dealId: string, input: CrmDealUpdateInput) {
  return patch<CrmDealItem>(`/crm/deals/${dealId}`, input)
}

function transitionCrmDealStage(dealId: string, input: CrmDealStageTransitionInput) {
  return post<CrmDealStageTransitionResponse>(`/crm/deals/${dealId}/transition`, input)
}

function deleteCrmDeal(dealId: string) {
  return remove<null>(`/crm/deals/${dealId}`)
}

// -------- Comments (tasks + deals) --------

type CrmCommentEntityType = 'task' | 'deal'

type CrmCommentItem = {
  id: string
  entity_type: CrmCommentEntityType
  entity_id: string
  author_user_id: string
  author_full_name: string
  author_email: string | null
  content: string
  created_at: string
  updated_at: string
}

type CrmCommentListResponse = {
  count: number
  items: CrmCommentItem[]
}

function listCrmTaskComments(taskId: string) {
  return get<CrmCommentListResponse>(`/crm/tasks/${taskId}/comments`)
}

function createCrmTaskComment(taskId: string, content: string) {
  return post<CrmCommentItem>(`/crm/tasks/${taskId}/comments`, { content })
}

function deleteCrmTaskComment(taskId: string, commentId: string) {
  return remove<null>(`/crm/tasks/${taskId}/comments/${commentId}`)
}

function listCrmDealComments(dealId: string) {
  return get<CrmCommentListResponse>(`/crm/deals/${dealId}/comments`)
}

function createCrmDealComment(dealId: string, content: string) {
  return post<CrmCommentItem>(`/crm/deals/${dealId}/comments`, { content })
}

function deleteCrmDealComment(dealId: string, commentId: string) {
  return remove<null>(`/crm/deals/${dealId}/comments/${commentId}`)
}

// -------- Team members (owner picker) --------

type CrmTeamMember = {
  id: string
  full_name: string
  email: string
  role_id: string
  job_title: string | null
}

type CrmTeamMemberListResponse = {
  count: number
  items: CrmTeamMember[]
}

function listCrmTeamMembers() {
  return get<CrmTeamMemberListResponse>('/crm/team-members')
}

export type {
  CrmTaskItem,
  CrmTaskListResponse,
  CrmTaskCreateInput,
  CrmTaskUpdateInput,
  CrmTaskStatus,
  CrmTaskPriority,
  CrmDealItem,
  CrmDealListResponse,
  CrmDealCreateInput,
  CrmDealUpdateInput,
  CrmDealStage,
  CrmDealStageTransitionInput,
  CrmDealStageTransitionResponse,
  CrmCommentItem,
  CrmCommentListResponse,
  CrmCommentEntityType,
  CrmTeamMember,
  CrmTeamMemberListResponse,
}

export {
  listCrmTasks,
  getCrmTask,
  createCrmTask,
  updateCrmTask,
  deleteCrmTask,
  listCrmDeals,
  getCrmDeal,
  createCrmDeal,
  updateCrmDeal,
  transitionCrmDealStage,
  deleteCrmDeal,
  listCrmTaskComments,
  createCrmTaskComment,
  deleteCrmTaskComment,
  listCrmDealComments,
  createCrmDealComment,
  deleteCrmDealComment,
  listCrmTeamMembers,
}
