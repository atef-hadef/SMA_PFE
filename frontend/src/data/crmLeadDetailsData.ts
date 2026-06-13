import type { TableRow } from '../components/common'

type LeadProfile = {
  name: string
  company: string
  role: string
  source: string
  owner: string
  score: string
}

type LeadMetric = {
  label: string
  value: string
  trend?: string
}

type LeadAnalysisItem = {
  label: string
  value: string
  status: TableRow['status']
}

type TimelineItem = {
  title: string
  detail: string
  status: TableRow['status']
}

type NextActionItem = {
  title: string
  detail: string
}

const leadProfile: LeadProfile = {
  name: 'Northwind Logistics',
  company: 'Northwind Group',
  role: 'VP of Operations',
  source: 'Inbound demo request',
  owner: 'AI Agent - Sales Pulse',
  score: '94/100',
}

const leadMetrics: LeadMetric[] = [
  { label: 'Current Score', value: '94', trend: 'Top conversion potential' },
  { label: 'Engagement', value: 'High', trend: 'Opened 4 emails' },
  { label: 'Routing State', value: 'Ready', trend: 'Assigned to senior sales' },
]

const leadAnalysis: LeadAnalysisItem[] = [
  { label: 'Sentiment', value: 'Positive', status: 'success' },
  { label: 'Intention', value: 'Purchase-ready', status: 'success' },
  { label: 'Urgency', value: 'High', status: 'warning' },
]

const routingTimeline: TimelineItem[] = [
  {
    title: 'Lead captured',
    detail: 'Inbound demo request submitted from the website form.',
    status: 'info',
  },
  {
    title: 'AI scored',
    detail: 'Lead scored 94 with high sentiment and strong fit signals.',
    status: 'success',
  },
  {
    title: 'Routed to owner',
    detail: 'Assigned to senior sales owner for immediate follow-up.',
    status: 'warning',
  },
]

const emailPreview = {
  subject: 'Thanks for your interest in FlowPilot AI',
  greeting: 'Hello Northwind team,',
  body:
    'Thanks for requesting a demo. Your engagement score looks strong, so I wanted to share a quick overview and propose a short discovery call this week.',
  closing: 'Best regards,\nFlowPilot AI Sales Team',
}

const nextAction: NextActionItem[] = [
  {
    title: 'Recommended next action',
    detail: 'Send a personalized follow-up and schedule a discovery call within 24 hours.',
  },
  {
    title: 'Routing suggestion',
    detail: 'Keep the lead with the senior sales owner because urgency and score are both high.',
  },
]

export type {
  LeadAnalysisItem,
  LeadMetric,
  LeadProfile,
  NextActionItem,
  TimelineItem,
}
export { emailPreview, leadAnalysis, leadMetrics, leadProfile, nextAction, routingTimeline }
