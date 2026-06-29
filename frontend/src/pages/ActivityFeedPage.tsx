import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AppCard,
  EmptyState,
  ErrorState,
  Icon,
  LoadingState,
  PageHeader,
  StatusBadge,
} from '../components/common'
import type { IconName } from '../components/common/Icon'
import type { StatusType } from '../components/common/StatusBadge'
import { getRecentActivities } from '../services/activitiesService'
import type { ActivityItem, ActivityPeriod } from '../services/activitiesService'

type EntityMeta = { label: string; icon: IconName; tone: StatusType }

const ENTITY_META: Record<string, EntityMeta> = {
  lead: { label: 'Lead', icon: 'crm', tone: 'info' },
  email_draft: { label: 'Email', icon: 'mail', tone: 'warning' },
  response: { label: 'Réponse', icon: 'mail', tone: 'success' },
  leave_request: { label: 'Congé', icon: 'leave', tone: 'info' },
  leave_allocation: { label: 'Allocation', icon: 'settings', tone: 'neutral' },
}

const ACTION_VERBS: Record<string, string> = {
  created: 'a créé',
  updated: 'a modifié',
  approved: 'a approuvé',
  rejected: 'a rejeté',
  sent: 'a envoyé',
  recorded: 'a enregistré',
  converted: 'a converti',
}

const TYPE_FILTERS: { key: string; label: string }[] = [
  { key: 'all', label: 'Tout' },
  { key: 'lead', label: 'Leads' },
  { key: 'email_draft', label: 'Emails' },
  { key: 'response', label: 'Réponses' },
  { key: 'leave_request', label: 'Congés' },
  { key: 'leave_allocation', label: 'Allocations' },
]

const PERIOD_FILTERS: { key: ActivityPeriod | 'all'; label: string }[] = [
  { key: 'all', label: 'Tout' },
  { key: 'today', label: "Aujourd'hui" },
  { key: 'week', label: 'Semaine' },
  { key: 'month', label: 'Mois' },
]

const SCOPE_LABEL: Record<string, string> = {
  all: 'Toutes les activités de la plateforme',
  hr: 'Activités RH (congés & allocations)',
  own: 'Vos activités',
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return "à l'instant"
  if (min < 60) return `il y a ${min} min`
  const h = Math.floor(min / 60)
  if (h < 24) return `il y a ${h} h`
  const d = Math.floor(h / 24)
  if (d < 30) return `il y a ${d} j`
  return new Date(iso).toLocaleDateString('fr-FR')
}

function initials(name?: string | null) {
  if (!name) return '?'
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase())
      .join('') || '?'
  )
}

function entityLink(item: ActivityItem): string | null {
  const leadId = (item.details?.lead_id as string | undefined) ?? null
  switch (item.entity_type) {
    case 'lead':
      return `/crm-lead-details?leadId=${item.entity_id}`
    case 'email_draft':
    case 'response':
      return leadId ? `/crm-lead-details?leadId=${leadId}` : null
    case 'leave_request':
      return '/manager-approvals'
    case 'leave_allocation':
      return '/leave-allocations'
    default:
      return null
  }
}

function describe(item: ActivityItem): string {
  const actor = item.actor_name || 'Un utilisateur'
  const verb = ACTION_VERBS[item.action] || item.action
  const meta = ENTITY_META[item.entity_type]
  const noun = meta ? meta.label.toLowerCase() : item.entity_type
  const label =
    (item.details?.company as string | undefined) ||
    (item.details?.name as string | undefined) ||
    (item.details?.subject as string | undefined) ||
    (item.details?.employee_id as string | undefined) ||
    (item.details?.response_type as string | undefined)
  return label ? `${actor} ${verb} un ${noun} « ${label} »` : `${actor} ${verb} un ${noun}`
}

function ActivityFeedPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<ActivityItem[]>([])
  const [scope, setScope] = useState<string>('own')
  const [type, setType] = useState<string>('all')
  const [period, setPeriod] = useState<ActivityPeriod | 'all'>('all')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await getRecentActivities({
        limit: 50,
        entityType: type === 'all' ? undefined : type,
        period: period === 'all' ? undefined : period,
      })
      setItems(res.items)
      setScope(res.scope)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Impossible de charger les activités.')
    } finally {
      setIsLoading(false)
    }
  }, [type, period])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const content = useMemo(() => {
    if (isLoading) return <LoadingState message="Chargement des activités..." />
    if (error)
      return <ErrorState message={error} actionLabel="Réessayer" onAction={() => void refresh()} />
    if (items.length === 0)
      return (
        <EmptyState
          title="Aucune activité"
          description="Aucune activité ne correspond aux filtres sélectionnés."
          icon="clock"
        />
      )
    return (
      <ol className="relative space-y-4 border-l border-slate-800 pl-6">
        {items.map((item) => {
          const meta = ENTITY_META[item.entity_type]
          const link = entityLink(item)
          return (
            <li key={item.id} className="relative">
              <span className="absolute -left-[33px] flex h-7 w-7 items-center justify-center rounded-full border border-slate-700 bg-slate-900 text-xs font-bold text-emerald-300">
                {initials(item.actor_name)}
              </span>
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm text-slate-100">
                      <Icon
                        name={meta?.icon ?? 'spark'}
                        size={13}
                        className="mr-1 inline text-slate-400"
                      />
                      {describe(item)}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-500">{relativeTime(item.created_at)}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <StatusBadge
                      label={meta?.label ?? item.entity_type}
                      status={meta?.tone ?? 'neutral'}
                      size="sm"
                    />
                    {link ? (
                      <button
                        type="button"
                        onClick={() => navigate(link)}
                        className="rounded-md border border-slate-700 px-2 py-1 text-[11px] text-slate-300 transition hover:border-emerald-500/40 hover:text-emerald-200"
                      >
                        Ouvrir
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            </li>
          )
        })}
      </ol>
    )
  }, [isLoading, error, items, navigate, refresh])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Activité"
        title="Activités récentes"
        subtitle={SCOPE_LABEL[scope] ?? 'Journal des actions récentes'}
      />
      <section className="flex flex-wrap items-center gap-2">
        {TYPE_FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setType(f.key)}
            className={`rounded-md border px-3 py-1.5 text-xs transition ${
              type === f.key
                ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200'
                : 'border-slate-700 text-slate-400 hover:bg-slate-800/70 hover:text-slate-100'
            }`}
          >
            {f.label}
          </button>
        ))}
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value as ActivityPeriod | 'all')}
          className="ml-auto rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100"
        >
          {PERIOD_FILTERS.map((p) => (
            <option key={p.key} value={p.key}>
              {p.label}
            </option>
          ))}
        </select>
      </section>
      <AppCard title="Journal d'activité" eyebrow="Timeline">
        <div className="px-5 py-4">{content}</div>
      </AppCard>
    </div>
  )
}

export default ActivityFeedPage
