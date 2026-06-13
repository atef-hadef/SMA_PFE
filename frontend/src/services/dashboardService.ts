import { get } from './apiClient'

type DashboardBusinessActivity = {
  title: string
  description: string
  time: string
  tone: 'green' | 'orange' | 'red' | 'blue' | 'slate'
}

type DashboardSummary = {
  leave_requests: number
  pending_approvals: number
  crm_leads: number
  active_agents: number
  hot_leads?: number | null
  prospects?: number | null
  customers?: number | null
  drafts_to_review?: number | null
  automation_successful?: number | null
  automation_failed?: number | null
  automation_issues?: number | null
  automation_pending?: number | null
  recent_business_activity?: DashboardBusinessActivity[]
}

function getDashboardSummary() {
  return get<DashboardSummary>('/dashboard/summary')
}

export type { DashboardBusinessActivity, DashboardSummary }
export { getDashboardSummary }
