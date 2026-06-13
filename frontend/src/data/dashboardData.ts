import type { TableRow } from '../components/common'

type StatItem = {
  label: string
  value: string
  trend?: string
}

type InsightItem = {
  title: string
  description: string
}

type HealthItem = {
  label: string
  status: TableRow['status']
  detail: string
}

const statCards: StatItem[] = [
  { label: 'Leave Requests', value: '24', trend: '+4 today' },
  { label: 'Pending Approvals', value: '8', trend: '-2 vs yesterday' },
  { label: 'Open CRM Leads', value: '128', trend: '+12% this week' },
  { label: 'Active Agents', value: '7', trend: '2 in monitoring mode' },
]

const recentProcessActivity: TableRow[] = [
  {
    id: '1',
    process: 'Leave Request #1024',
    owner: 'Sarah N.',
    status: 'warning',
  },
  {
    id: '2',
    process: 'CRM Lead Qualification',
    owner: 'AI Agent - Delta',
    status: 'success',
  },
  {
    id: '3',
    process: 'Workflow Health Check',
    owner: 'Ops Team',
    status: 'info',
  },
]

const aiInsights: InsightItem[] = [
  {
    title: 'Approval bottleneck detected',
    description: 'Three leave requests are waiting on the same manager queue.',
  },
  {
    title: 'High-value lead cluster',
    description: 'Two CRM leads match the top conversion profile from last week.',
  },
  {
    title: 'Agent workload balanced',
    description: 'Active AI agents are within safe processing thresholds.',
  },
]

const workflowHealth: HealthItem[] = [
  {
    label: 'Leave workflow',
    status: 'warning',
    detail: 'Minor delay in approval routing',
  },
  {
    label: 'CRM pipeline',
    status: 'success',
    detail: 'Lead scoring is stable',
  },
  {
    label: 'AI orchestration',
    status: 'success',
    detail: 'All agents responding normally',
  },
]

export type { HealthItem, InsightItem, StatItem }
export { aiInsights, recentProcessActivity, statCards, workflowHealth }
