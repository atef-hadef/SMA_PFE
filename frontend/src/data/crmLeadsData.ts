import type { TableRow } from '../components/common'

type CrmKpiCard = {
  label: string
  value: string
  trend?: string
}

type LeadPriority = 'Hot' | 'Warm' | 'Cold'
type LeadSentiment = 'Positive' | 'Neutral' | 'Negative'
type LeadUrgency = 'High' | 'Medium' | 'Low'

type CrmLead = {
  id: string
  lead: string
  company: string
  owner: string
  priority: LeadPriority
  customerStatus: string
  estimatedValue: string
  source: string
  nextAction: string
  activeLabel: string
  activeStatus: TableRow['status']
  sentiment: LeadSentiment
  urgency: LeadUrgency
  status: string
  score: string
}

type ScoringSummary = {
  headline: string
  description: string
  status: TableRow['status']
}

type RoutingSummary = {
  title: string
  detail: string
}

const crmKpiCards: CrmKpiCard[] = [
  { label: 'Qualified Leads', value: '128', trend: '+12% this week' },
  { label: 'Hot Leads', value: '24', trend: '8 need action' },
  { label: 'Warm Leads', value: '61', trend: 'Pipeline growth stable' },
  { label: 'Cold Leads', value: '43', trend: 'Automated nurture active' },
]

const crmLeads: CrmLead[] = [
  {
    id: 'lead-1',
    lead: 'Northwind Logistics',
    company: 'Northwind Group',
    owner: 'AI Agent - Sales Pulse',
    priority: 'Hot',
    customerStatus: 'Prospect',
    estimatedValue: '15000.00',
    source: 'Web',
    nextAction: 'Schedule discovery call',
    activeLabel: 'Active',
    activeStatus: 'success',
    sentiment: 'Positive',
    urgency: 'High',
    status: 'Hot',
    score: '94',
  },
  {
    id: 'lead-2',
    lead: 'Apex Retail Expansion',
    company: 'Apex Retail',
    owner: 'Mariam R.',
    priority: 'Warm',
    customerStatus: 'Lead',
    estimatedValue: '8000.00',
    source: 'Referral',
    nextAction: 'Send product comparison',
    activeLabel: 'Active',
    activeStatus: 'success',
    sentiment: 'Neutral',
    urgency: 'Medium',
    status: 'Warm',
    score: '72',
  },
  {
    id: 'lead-3',
    lead: 'Orion SaaS Demo',
    company: 'Orion Tech',
    owner: 'AI Agent - Delta',
    priority: 'Hot',
    customerStatus: 'VIP',
    estimatedValue: '12000.00',
    source: 'Partner',
    nextAction: 'Confirm technical demo',
    activeLabel: 'Active',
    activeStatus: 'success',
    sentiment: 'Positive',
    urgency: 'High',
    status: 'Hot',
    score: '91',
  },
  {
    id: 'lead-4',
    lead: 'Atlas Manufacturing Quote',
    company: 'Atlas Manufacturing',
    owner: 'Julien P.',
    priority: 'Cold',
    customerStatus: 'New',
    estimatedValue: '2500.00',
    source: 'Email',
    nextAction: 'Add to nurturing campaign',
    activeLabel: 'Active',
    activeStatus: 'success',
    sentiment: 'Negative',
    urgency: 'Low',
    status: 'Cold',
    score: '38',
  },
]

const scoringSummary: ScoringSummary[] = [
  {
    headline: 'Top scoring lead',
    description: 'Northwind Logistics is the strongest opportunity based on engagement and fit.',
    status: 'success',
  },
  {
    headline: 'Moderate follow-up cluster',
    description: 'Warm leads are stable and should remain in a guided nurture sequence.',
    status: 'info',
  },
  {
    headline: 'Needs human review',
    description: 'One cold lead has a negative sentiment signal and low conversion probability.',
    status: 'warning',
  },
]

const routingSummary: RoutingSummary[] = [
  {
    title: 'Hot leads',
    detail: 'Route directly to senior sales owners for immediate outreach.',
  },
  {
    title: 'Warm leads',
    detail: 'Keep in a scoring loop and notify assigned representatives after each interaction.',
  },
  {
    title: 'Cold leads',
    detail: 'Send to automated nurture campaigns until engagement improves.',
  },
]

const leadTableRows: CrmLead[] = crmLeads

export type { CrmKpiCard, CrmLead, LeadPriority, LeadSentiment, LeadUrgency, RoutingSummary, ScoringSummary }
export { crmKpiCards, crmLeads, leadTableRows, routingSummary, scoringSummary }
