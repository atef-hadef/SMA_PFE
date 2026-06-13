import { get, post } from './apiClient'

type WorkflowExecutionRecord = {
  id: string
  workflow_name: string
  process: string
  status: 'success' | 'failed' | 'running' | 'queued'
  related_object: string
  started_at: string
  finished_at: string | null
  duration: string
  triggered_by: string
  agent: string
}

type WorkflowStep = {
  name: string
  status: 'success' | 'failed' | 'running' | 'queued'
  duration: string
}

type WorkflowExecutionDetail = WorkflowExecutionRecord & {
  input_summary: string
  output_summary: string
  steps: WorkflowStep[]
  error_message: string | null
}

type RetryWorkflowExecutionResponse = {
  execution_id: string
  retry_status: 'queued'
  message: string
  requested_at: string
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

function getWorkflowExecutions() {
  return get<PaginatedResponse<WorkflowExecutionRecord>>('/workflow-executions')
}

function getWorkflowExecutionById(executionId: string) {
  return get<WorkflowExecutionDetail>(`/workflow-executions/${executionId}`)
}

function retryWorkflowExecution(executionId: string, reason: string) {
  return post<RetryWorkflowExecutionResponse>(
    `/workflow-executions/${executionId}/retry`,
    { reason },
  )
}

export type {
  PaginatedResponse,
  RetryWorkflowExecutionResponse,
  WorkflowExecutionDetail,
  WorkflowExecutionRecord,
  WorkflowStep,
}
export { getWorkflowExecutionById, getWorkflowExecutions, retryWorkflowExecution }
