import { get } from './apiClient'

export type ActivityItem = {
  id: string
  entity_type: string
  entity_id?: string | null
  action: string
  actor_id?: string | null
  actor_name?: string | null
  details?: Record<string, unknown> | null
  created_at: string
}

export type ActivityListResponse = {
  count: number
  scope: 'all' | 'hr' | 'own' | string
  items: ActivityItem[]
}

export type ActivityPeriod = 'today' | 'week' | 'month'

function getRecentActivities(
  params: { limit?: number; entityType?: string; period?: ActivityPeriod } = {},
) {
  const q = new URLSearchParams()
  if (params.limit) q.set('limit', String(params.limit))
  if (params.entityType) q.set('entity_type', params.entityType)
  if (params.period) q.set('period', params.period)
  const qs = q.toString()
  return get<ActivityListResponse>(`/activities/recent${qs ? `?${qs}` : ''}`)
}

export { getRecentActivities }
