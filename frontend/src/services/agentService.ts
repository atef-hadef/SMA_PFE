import { get, post } from './apiClient'

type AgentRecord = {
  id: string
  name: string
  process: string
  status: 'active' | 'inactive' | 'degraded'
  type: string
  success_rate: number
  last_execution: string
  description: string
}

type AgentRecentRun = {
  execution_id: string
  status: 'success' | 'failed' | 'running' | 'queued'
  duration: string
  started_at: string
}

type AgentDetail = AgentRecord & {
  input_description: string
  output_description: string
  tools: string[]
  related_workflows: string[]
  recent_runs: AgentRecentRun[]
}

type RunAgentResponse = {
  agent_id: string
  run_status: 'queued'
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

function getAgents() {
  return get<PaginatedResponse<AgentRecord>>('/agents')
}

function getAgentById(agentId: string) {
  return get<AgentDetail>(`/agents/${agentId}`)
}

function runAgent(agentId: string, payload: Record<string, unknown> = {}) {
  return post<RunAgentResponse>(`/agents/${agentId}/run`, { payload })
}

export type {
  AgentDetail,
  AgentRecentRun,
  AgentRecord,
  PaginatedResponse,
  RunAgentResponse,
}
export { getAgentById, getAgents, runAgent }
