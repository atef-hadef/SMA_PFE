import { get, post } from './apiClient'

type LeaveRequestHistoryRecord = {
  id: string
  employee_id: string
  employee_name: string
  department: string
  leave_type: string
  start_date: string
  end_date: string
  requested_days: number | null
  reason: string
  status: string
  manager_comment: string | null
  decided_at: string | null
  created_at: string
  odoo_sync_status: string | null
}

type LeaveRequestCreatePayload = {
  leave_type: string
  start_date: string
  end_date: string
  reason: string
}

type LeaveRequestCreatedResponse = {
  id: string
  employee_id: string
  leave_type: string
  start_date: string
  end_date: string
  reason: string
  status:
    | 'pending'
    | 'manager_review_required'
    | 'approved'
    | 'rejected'
    | 'cancelled'
    | 'odoo_sync_failed'
  created_at: string
  odoo_sync_status?: 'pending' | 'synced' | 'failed' | string | null
}

type LeaveBalancePrecheckResponse = {
  ok?: boolean | null
  status?: string | null
  error_code?: string | null
  available_days: number | string | null
  requested_days: number | string | null
  balance_gap_days: number | string | null
  has_enough_balance: boolean | null
  recommendation: string | null
  recommendation_label: string | null
  risk_level: string | null
  ai_explanation: string | null
  employee_guidance?: string | null
  manager_guidance: string | null
  message?: string | null
  conflict_detected?: boolean | null
  conflict_type?: string | null
  overlapping_leave_count?: number | null
  overlapping_leaves?: Array<Record<string, unknown>>
  date_from?: string | null
  date_to?: string | null
}

type LeaveRequestRecord = {
  id: string
  employeeName: string
  leaveType: string
  startDate: string
  endDate: string
  status: 'pending' | 'manager_review_required' | 'approved' | 'rejected' | 'cancelled' | 'odoo_sync_failed'
}

type PendingLeaveRequestRecord = {
  id: string
  employee_id: string
  employee_name: string
  department: string
  leave_type: string
  start_date: string
  end_date: string
  reason: string
  status: 'pending' | 'manager_review_required'
  created_at: string
  ai_recommendation: 'approve' | 'reject' | 'review'
  risk_level: 'low' | 'medium' | 'high'
  conflict_detected: boolean
  automation_summary: string | null
  available_days: number | string | null
  requested_days: number | string | null
  balance_gap_days: number | string | null
  ai_explanation: string | null
  decision_reasons: string[]
  blocking_reasons: string[]
  approval_factors: string[]
  rejection_factors: string[]
  score_reasons: string[]
  manager_guidance: string | null
  can_manager_override: boolean | null
  can_sync_with_odoo: boolean
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

type LeaveDecisionResponse = {
  id: string
  status: 'approved' | 'rejected'
  manager_comment: string
  updated_at: string
}

function getLeaveRequestsHistory(status?: string) {
  const path = status ? `/leave-requests?status=${encodeURIComponent(status)}` : '/leave-requests'
  return get<PaginatedResponse<LeaveRequestHistoryRecord>>(path)
}

function createLeaveRequest(payload: LeaveRequestCreatePayload) {
  return post<LeaveRequestCreatedResponse>('/leave-requests', payload)
}

function getMyLeaveRequests() {
  return get<PaginatedResponse<LeaveRequestHistoryRecord>>('/leave-requests/my')
}

function getPendingLeaveRequests() {
  return get<PaginatedResponse<PendingLeaveRequestRecord>>('/leave-requests/pending')
}

function approveLeaveRequest(requestId: string, comment: string) {
  return post<LeaveDecisionResponse>(`/leave-requests/${requestId}/approve`, {
    comment,
  })
}

function rejectLeaveRequest(requestId: string, comment: string) {
  return post<LeaveDecisionResponse>(`/leave-requests/${requestId}/reject`, {
    comment,
  })
}

// --- Module Congés STANDALONE (sans Odoo) ---

type LeaveBalanceItem = {
  leave_type: string
  leave_type_label: string
  allocated: number
  used: number
  pending: number
  available: number
  year: number
}

type LeaveTypeOption = {
  id: string
  code: string
  label_fr: string
  label_en?: string | null
  default_days: number
  requires_document: boolean
}

type LeaveAllocationDetail = {
  leave_type: string
  leave_type_label: string
  allocated_days: number
  used_days: number
  available_days: number
}

type LeaveAllocationGroup = {
  employee_id: string
  employee_name: string
  year: number
  allocations: LeaveAllocationDetail[]
}

type LeaveAllocationUpsertPayload = {
  employee_id: string
  year: number
  leave_type: string
  allocated_days: number
}

type LeaveAllocationUpsertResponse = {
  id: string
  employee_id: string
  year: number
  leave_type: string
  allocated_days: number
}

type LeaveAnalyticsEmployee = {
  employee_id: string
  employee_name: string
  total_requests: number
  approved_days: number
  remaining_vacation: number
  burnout_risk: string
}

type LeaveBurnoutAlert = {
  employee_id: string
  employee_name: string
  risk_level: string
  days_since_last_leave: number | null
  signals: string[]
}

type LeavePendingOver48h = {
  request_id: string
  employee_name: string
  submitted_at: string
  hours_pending: number
}

type LeaveAnalyticsResponse = {
  total_this_year: number
  approved: number
  rejected: number
  pending: number
  by_type: Record<string, { count: number; days: number }>
  by_employee: LeaveAnalyticsEmployee[]
  burnout_alerts: LeaveBurnoutAlert[]
  pending_over_48h: LeavePendingOver48h[]
}

function getMyBalance() {
  return get<LeaveBalanceItem[]>('/leave-requests/my-balance')
}

function getLeaveTypes() {
  return get<LeaveTypeOption[]>('/leave-requests/leave-types')
}

function createStandaloneRequest(payload: LeaveRequestCreatePayload) {
  return post<LeaveRequestCreatedResponse>('/leave-requests/standalone', payload)
}

function approveStandalone(requestId: string, comment: string) {
  return post<LeaveRequestCreatedResponse>(
    `/leave-requests/${requestId}/approve-standalone`,
    { comment },
  )
}

function rejectStandalone(requestId: string, comment: string) {
  return post<LeaveRequestCreatedResponse>(
    `/leave-requests/${requestId}/reject-standalone`,
    { comment },
  )
}

function getAllocations(year = 2026, employeeId?: string) {
  const params = new URLSearchParams({ year: String(year) })
  if (employeeId) params.set('employee_id', employeeId)
  return get<LeaveAllocationGroup[]>(`/leave-requests/allocations?${params.toString()}`)
}

function upsertAllocation(payload: LeaveAllocationUpsertPayload) {
  return post<LeaveAllocationUpsertResponse>('/leave-requests/allocations', payload)
}

function getAnalytics() {
  return get<LeaveAnalyticsResponse>('/leave-requests/analytics')
}

export type {
  LeaveRequestCreatedResponse,
  LeaveBalancePrecheckResponse,
  LeaveRequestCreatePayload,
  LeaveDecisionResponse,
  LeaveRequestHistoryRecord,
  LeaveRequestRecord,
  PaginatedResponse,
  PendingLeaveRequestRecord,
  LeaveBalanceItem,
  LeaveTypeOption,
  LeaveAllocationDetail,
  LeaveAllocationGroup,
  LeaveAllocationUpsertPayload,
  LeaveAllocationUpsertResponse,
  LeaveAnalyticsEmployee,
  LeaveBurnoutAlert,
  LeavePendingOver48h,
  LeaveAnalyticsResponse,
}
export {
  approveLeaveRequest,
  createLeaveRequest,
  getLeaveRequestsHistory,
  getMyLeaveRequests,
  getPendingLeaveRequests,
  rejectLeaveRequest,
  getMyBalance,
  getLeaveTypes,
  createStandaloneRequest,
  approveStandalone,
  rejectStandalone,
  getAllocations,
  upsertAllocation,
  getAnalytics,
}
