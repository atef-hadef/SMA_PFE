import type { TableRow } from '../components/common'

type WorkflowKpi = {
  label: string
  value: string
  trend?: string
}

type WorkflowExecution = {
  id: string
  workflow: string
  process: 'Leave' | 'CRM' | 'Monitoring'
  businessObjectId: string
  status: 'success' | 'warning' | 'danger' | 'info'
  duration: string
  successRate: string
  lastExecution: string
  triggerSource: string
  automationAgent: string
}

type SelectedExecution = {
  workflow: string
  executionId: string
  process: string
  businessObjectId: string
  status: string
  duration: string
  inputSummary: string
  outputSummary: string
  errorMessage: string
}

type WorkflowSummary = {
  title: string
  detail: string
  status: TableRow['status']
}

const workflowKpis: WorkflowKpi[] = [
  { label: 'Total Executions', value: '248', trend: '+18 today' },
  { label: 'Successful Runs', value: '221', trend: '89% success' },
  { label: 'Failed Runs', value: '9', trend: '3 need retry' },
  { label: 'Average Duration', value: '1.8 min', trend: '-12% vs last week' },
]

const workflowExecutions: WorkflowExecution[] = [
  {
    id: 'we-1',
    workflow: 'Leave Validation Flow',
    process: 'Leave',
    businessObjectId: 'LR-1024',
    status: 'success',
    duration: '1.2 min',
    successRate: '98%',
    lastExecution: '2 min ago',
    triggerSource: 'Employee Portal',
    automationAgent: 'Leave Validation Agent',
  },
  {
    id: 'we-2',
    workflow: 'Manager Decision Flow',
    process: 'Leave',
    businessObjectId: 'LR-1024',
    status: 'warning',
    duration: '2.4 min',
    successRate: '91%',
    lastExecution: '11 min ago',
    triggerSource: 'Approval Queue',
    automationAgent: 'Manager Decision Agent',
  },
  {
    id: 'we-3',
    workflow: 'CRM Lead Scoring Flow',
    process: 'CRM',
    businessObjectId: 'LEAD-8804',
    status: 'success',
    duration: '1.0 min',
    successRate: '97%',
    lastExecution: '4 min ago',
    triggerSource: 'CRM Intake',
    automationAgent: 'Lead Scoring Agent',
  },
  {
    id: 'we-4',
    workflow: 'AI Analysis Agent A3',
    process: 'CRM',
    businessObjectId: 'LEAD-8804',
    status: 'info',
    duration: '1.6 min',
    successRate: '95%',
    lastExecution: '7 min ago',
    triggerSource: 'Lead Analysis',
    automationAgent: 'AI Analysis Agent A3',
  },
  {
    id: 'we-5',
    workflow: 'Monitoring Report A7',
    process: 'Monitoring',
    businessObjectId: 'MON-77',
    status: 'danger',
    duration: '3.1 min',
    successRate: '84%',
    lastExecution: '18 min ago',
    triggerSource: 'Monitoring Schedule',
    automationAgent: 'Reporting Agent A7',
  },
]

const selectedExecution: SelectedExecution = {
  workflow: 'CRM Lead Scoring Flow',
  executionId: 'EXEC-9081',
  process: 'CRM',
  businessObjectId: 'LEAD-8804',
  status: 'Completed successfully with one retry step',
  duration: '1.0 min',
  inputSummary: 'Incoming lead score, sentiment, urgency, and owner context were received by the workflow.',
  outputSummary: 'Lead was scored, routed to the owner, and the next action was stored in the CRM record.',
  errorMessage: 'No active error. Previous retry was resolved after the payload format was normalized.',
}

const errorMessage = {
  title: 'Execution Error Panel',
  detail: 'No blocking error in the selected execution. Use retry only when a failure is detected.',
}

const workflowSummary: WorkflowSummary[] = [
  {
    title: 'Leave process',
    detail: 'Routing and approval steps remain stable with good success rates.',
    status: 'warning',
  },
  {
    title: 'CRM process',
    detail: 'Lead capture, scoring, and communication executions are healthy.',
    status: 'success',
  },
  {
    title: 'Monitoring process',
    detail: 'Reporting and alerting runs continue to surface periodic warnings.',
    status: 'info',
  },
]

export type { SelectedExecution, WorkflowExecution, WorkflowKpi, WorkflowSummary }
export { errorMessage, selectedExecution, workflowExecutions, workflowKpis, workflowSummary }
