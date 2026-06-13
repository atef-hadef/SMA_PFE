import type { TableRow } from '../components/common'

type AgentKpi = {
  label: string
  value: string
  trend?: string
}

type AIAgent = {
  id: string
  name: string
  process: 'Leave' | 'CRM' | 'Monitoring'
  status: TableRow['status']
  lastExecution: string
  successRate: string
}

type SelectedAgent = {
  name: string
  process: string
  status: string
  inputDescription: string
  outputDescription: string
}

type AgentSummary = {
  title: string
  detail: string
  status: TableRow['status']
}

const agentKpis: AgentKpi[] = [
  { label: 'Total Agents', value: '8', trend: 'All agents available' },
  { label: 'Active Agents', value: '6', trend: '2 in standby' },
  { label: 'Warning Agents', value: '1', trend: 'Needs routing check' },
  { label: 'Average Success Rate', value: '94%', trend: '+2% this week' },
]

const aiAgents: AIAgent[] = [
  {
    id: 'agent-1',
    name: 'Leave Validation Agent',
    process: 'Leave',
    status: 'success',
    lastExecution: '2 min ago',
    successRate: '98%',
  },
  {
    id: 'agent-2',
    name: 'Manager Decision Agent',
    process: 'Leave',
    status: 'warning',
    lastExecution: '11 min ago',
    successRate: '89%',
  },
  {
    id: 'agent-3',
    name: 'Lead Collection Agent',
    process: 'CRM',
    status: 'success',
    lastExecution: '5 min ago',
    successRate: '97%',
  },
  {
    id: 'agent-4',
    name: 'AI Analysis Agent A3',
    process: 'CRM',
    status: 'success',
    lastExecution: '1 min ago',
    successRate: '96%',
  },
  {
    id: 'agent-5',
    name: 'Predictive Scoring Agent A4',
    process: 'CRM',
    status: 'success',
    lastExecution: '4 min ago',
    successRate: '95%',
  },
  {
    id: 'agent-6',
    name: 'Routing Agent A5',
    process: 'CRM',
    status: 'info',
    lastExecution: '8 min ago',
    successRate: '93%',
  },
  {
    id: 'agent-7',
    name: 'Communication Agent A6',
    process: 'CRM',
    status: 'success',
    lastExecution: '3 min ago',
    successRate: '95%',
  },
  {
    id: 'agent-8',
    name: 'Reporting Agent A7',
    process: 'Monitoring',
    status: 'info',
    lastExecution: '12 min ago',
    successRate: '92%',
  },
]

const selectedAgent: SelectedAgent = {
  name: 'Routing Agent A5',
  process: 'CRM',
  status: 'Ready to route leads by score and sentiment',
  inputDescription: 'Receives lead score, sentiment, urgency, and ownership context.',
  outputDescription: 'Returns the routed owner, next action, and escalation recommendation.',
}

const agentSummary: AgentSummary[] = [
  {
    title: 'Leave process agents',
    detail: 'Leave Validation Agent and Manager Decision Agent support HR approvals.',
    status: 'warning',
  },
  {
    title: 'CRM process agents',
    detail: 'A3 to A6 support capture, scoring, analysis, and communication.',
    status: 'success',
  },
  {
    title: 'Monitoring agent',
    detail: 'Reporting Agent A7 summarizes execution health and workflow alerts.',
    status: 'info',
  },
]

export type { AIAgent, AgentKpi, AgentSummary, SelectedAgent }
export { agentKpis, agentSummary, aiAgents, selectedAgent }
