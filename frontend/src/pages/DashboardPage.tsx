import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import {
  ActionButton,
  ActivityTimeline,
  AppCard,
  ErrorState,
  Icon,
  KpiCard,
  LoadingState,
  PageHeader,
  PriorityBadge,
  StatusBadge,
  type ActivityTimelineItem,
  type BadgeTone,
  type IconName,
  type KpiTone,
} from '../components/common'
import { AreaChart, BarChart, DonutChart, FunnelChart, type ChartDatum } from '../components/dashboard/Charts'
import { getCrmLeads, type CrmLeadRecord } from '../services/crmService'
import {
  getDashboardSummary,
  type DashboardBusinessActivity,
  type DashboardSummary,
} from '../services/dashboardService'
import { getMyLeaveRequests, getPendingLeaveRequests, type LeaveRequestHistoryRecord, type PendingLeaveRequestRecord } from '../services/leaveService'
import { computeCrmMetrics, type CrmMetrics as ComputedCrmMetrics } from '../utils/crmMetrics'
import { formatCrmCurrency } from '../utils/crmDisplay'

type PriorityAction = {
  title: string
  description: string
  badge: string
  badgeTone: BadgeTone
  actionLabel: string
  route: string
}

type CrmMetrics = ComputedCrmMetrics

type LeaveMetrics = {
  submitted: number
  inAiAnalysis: number
  managerReview: number
  approved: number
  rejected: number
  nextAction: string
}

 

function buildLeaveMetrics(
  myRequests: LeaveRequestHistoryRecord[],
  pendingRequests: PendingLeaveRequestRecord[],
  summary: DashboardSummary | null,
): LeaveMetrics {
  // Use pending requests (manager inbox) as the authoritative source for managerReview
  const managerReview = pendingRequests.length > 0
    ? pendingRequests.length
    : myRequests.filter((r) => r.status === 'manager_review_required').length ||
      summary?.pending_approvals ||
      0

  // submitted: prefer myRequests count, fall back to summary aggregate
  const submitted = myRequests.length > 0
    ? myRequests.length
    : summary?.leave_requests || 0

  const inAiAnalysis = myRequests.filter((r) => r.status === 'pending').length
  const approved = myRequests.filter((r) => r.status === 'approved').length
  const rejected = myRequests.filter((r) => r.status === 'rejected').length

  let nextAction = 'Aucune action requise'
  if (managerReview > 0) nextAction = 'Décision manager attendue'
  else if (inAiAnalysis > 0) nextAction = 'Analyse automatique en cours'
  else if (submitted === 0) nextAction = 'Soumettre une demande si besoin'

  return { submitted, inAiAnalysis, managerReview, approved, rejected, nextAction }
}

function buildPriorityActions(crm: CrmMetrics, leave: LeaveMetrics): PriorityAction[] {
  const actions: PriorityAction[] = []

  if (crm.draftsToReview > 0) {
    actions.push({
      title: `${crm.draftsToReview} brouillon${crm.draftsToReview === 1 ? '' : 's'} CRM à valider`,
      description: 'Relisez la communication générée avant approbation et envoi.',
      badge: 'CRM',
      badgeTone: 'blue',
      actionLabel: 'Ouvrir le CRM',
      route: '/crm-leads',
    })
  }

  if (crm.followUpProspects > 0 || crm.hotLeads > 0) {
    const count = crm.followUpProspects || crm.hotLeads
    actions.push({
      title: `${count} prospect${count === 1 ? '' : 's'} à relancer`,
      description: 'Une action commerciale rapide peut améliorer la conversion.',
      badge: 'Commercial',
      badgeTone: 'orange',
      actionLabel: 'Voir les prospects',
      route: '/crm-leads',
    })
  }

  if (crm.prospectsReadyToConvert > 0) {
    const c = crm.prospectsReadyToConvert
    actions.push({
      title: `${c} prospect${c === 1 ? '' : 's'} prêt${c === 1 ? '' : 's'} à convertir`,
      description: 'Vérifier la conversion client et valider si approprié.',
      badge: 'Conversion',
      badgeTone: 'orange',
      actionLabel: 'Vérifier les conversions',
      route: '/crm-leads',
    })
  }

  if (leave.inAiAnalysis > 0) {
    actions.push({
      title: `${leave.inAiAnalysis} demande${leave.inAiAnalysis === 1 ? '' : 's'} de congé à traiter`,
      description: 'Le processus d’analyse automatique est en cours côté RH.',
      badge: 'Congés',
      badgeTone: 'purple',
      actionLabel: 'Voir les demandes',
      route: '/leave-requests',
    })
  }

  if (leave.managerReview > 0) {
    actions.push({
      title: `${leave.managerReview} décision${leave.managerReview === 1 ? '' : 's'} manager en attente`,
      description: 'Une décision humaine est nécessaire pour finaliser la demande.',
      badge: 'Manager',
      badgeTone: 'red',
      actionLabel: 'Ouvrir les validations',
      route: '/manager-approvals',
    })
  }

  return actions
}

function getKpiTone(index: number): { tone: KpiTone; icon: IconName } {
  const tones: Array<{ tone: KpiTone; icon: IconName }> = [
    { tone: 'rose', icon: 'target' },
    { tone: 'sky', icon: 'crm' },
    { tone: 'amber', icon: 'file' },
    { tone: 'emerald', icon: 'check' },
    { tone: 'violet', icon: 'leave' },
    { tone: 'amber', icon: 'clock' },
    { tone: 'emerald', icon: 'check' },
    { tone: 'slate', icon: 'alert' },
  ]
  return tones[index] ?? { tone: 'slate', icon: 'activity' }
}

// Turn backend (often English / technical) activity labels into clean French.
function humanizeActivityTitle(title: string): string {
  const t = title.toLowerCase()
  if (t.includes('completed') || t.includes('success') || t.includes('terminé')) return 'Automatisation terminée'
  if (t.includes('progress') || t.includes('running') || t.includes('en cours')) return 'Automatisation en cours'
  if (t.includes('attention') || t.includes('failed') || t.includes('error') || t.includes('échec')) return 'Automatisation en échec'
  if (t.includes('queued') || t.includes('pending') || t.includes('attente')) return 'Automatisation en attente'
  if (t.includes('draft') || t.includes('brouillon')) return 'Brouillon d’e-mail généré'
  if (t.includes('lead') || t.includes('prospect')) return 'Activité commerciale (CRM)'
  if (t.includes('leave') || t.includes('congé')) return 'Demande de congé'
  return title
}

function humanizeActivityDescription(description: string): string {
  const d = description.trim().toLowerCase()
  if (d === 'crm') return 'Processus CRM'
  if (d === 'leave' || d === 'congé' || d === 'rh') return 'Processus Congés'
  if (!description.trim()) return 'Événement métier'
  return description.charAt(0).toUpperCase() + description.slice(1)
}

const MONTHS_FR: Record<string, string> = {
  jan: 'janv.', feb: 'févr.', mar: 'mars', apr: 'avr.', may: 'mai', jun: 'juin',
  jul: 'juil.', aug: 'août', sep: 'sept.', oct: 'oct.', nov: 'nov.', dec: 'déc.',
}
function humanizeTime(time: string): string {
  const t = time.trim()
  if (/today/i.test(t)) return "Aujourd'hui"
  if (/yesterday/i.test(t)) return 'Hier'
  // "Jun 08" -> "08 juin"
  const m = t.match(/^([A-Za-z]{3})\s+(\d{1,2})$/)
  if (m) {
    const month = MONTHS_FR[m[1].toLowerCase()]
    if (month) return `${m[2]} ${month}`
  }
  return time
}

function mapActivityToTimeline(activities?: DashboardBusinessActivity[]): ActivityTimelineItem[] {
  const allowedEvents = [
    'lead',
    'crm',
    'brouillon',
    'email',
    'prospect',
    'client',
    'congé',
    'manager',
    'rh',
    'automation',
  ]
  const source = activities?.filter((activity) => {
    const haystack = `${activity.title} ${activity.description}`.toLowerCase()
    return allowedEvents.some((keyword) => haystack.includes(keyword))
  })

  if (!source || source.length === 0) {
    return [
      {
        id: 'fallback-lead',
        title: 'Nouveau lead créé',
        description: 'Un prospect est prêt à être qualifié.',
        time: 'Aujourd’hui',
        tone: 'blue',
      },
      {
        id: 'fallback-draft',
        title: 'Brouillon CRM généré',
        description: 'Une communication attend une validation humaine.',
        time: 'Aujourd’hui',
        tone: 'orange',
      },
      {
        id: 'fallback-leave',
        title: 'Demande de congé soumise',
        description: 'Analyse automatique en cours.',
        time: 'Aujourd’hui',
        tone: 'purple',
      },
    ]
  }

  return source.slice(0, 6).map((activity, index) => ({
    id: `activity-${index}`,
    title: humanizeActivityTitle(activity.title),
    description: humanizeActivityDescription(activity.description),
    time: humanizeTime(activity.time),
    tone: activity.tone === 'slate' ? 'slate' : activity.tone,
  }))
}

// Weekly "new leads" buckets over the last 6 weeks, from each lead's created_at.
function buildLeadTrend(leads: CrmLeadRecord[]): ChartDatum[] {
  const weeks = 6
  const now = new Date()
  const buckets = Array.from({ length: weeks }, (_, i) => {
    const end = new Date(now)
    end.setHours(23, 59, 59, 999)
    end.setDate(now.getDate() - (weeks - 1 - i) * 7)
    const start = new Date(end)
    start.setDate(end.getDate() - 6)
    start.setHours(0, 0, 0, 0)
    return { start, end, count: 0, label: `${start.getDate()}/${start.getMonth() + 1}` }
  })
  for (const lead of leads) {
    if (!lead.created_at) continue
    const created = new Date(lead.created_at)
    if (Number.isNaN(created.getTime())) continue
    const bucket = buckets.find((b) => created >= b.start && created <= b.end)
    if (bucket) bucket.count += 1
  }
  return buckets.map((b) => ({ label: b.label, value: b.count }))
}

function DashboardPage() {
  const navigate = useNavigate()
  const { hasAnyPermission, hasPermission, user } = useAuth()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [leads, setLeads] = useState<CrmLeadRecord[]>([])
  const [leaveRequests, setLeaveRequests] = useState<LeaveRequestHistoryRecord[]>([])
  const [pendingLeaveRequests, setPendingLeaveRequests] = useState<PendingLeaveRequestRecord[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isCrmFallback, setIsCrmFallback] = useState(false)
  const canViewCrm = hasPermission('crm.leads.view')
  const canViewOwnLeave = hasPermission('leave.request.view_own')
  const canViewAllLeave = hasPermission('leave.request.view_all')
  const canApproveLeave = hasPermission('leave.request.approve')
  const canViewLeave = canViewOwnLeave || canViewAllLeave || hasPermission('leave.request.create')
  const canViewManagerInbox = canViewAllLeave || canApproveLeave
  const canViewWorkflow = hasAnyPermission(['workflow.monitor.view', 'workflow.executions.view'])
  const canViewAgents = hasPermission('agents.view')

  useEffect(() => {
    let isMounted = true

    async function loadData() {
      setIsLoading(true)
      setErrorMessage(null)

      try {
        const [summaryResult, leadsResult, leaveResult, pendingLeaveResult] = await Promise.allSettled([
          getDashboardSummary(),
          canViewCrm ? getCrmLeads() : Promise.resolve(null),
          canViewOwnLeave ? getMyLeaveRequests() : Promise.resolve(null),
          canViewManagerInbox ? getPendingLeaveRequests() : Promise.resolve(null),
        ])

        if (!isMounted) return

        if (summaryResult.status === 'fulfilled') {
          setSummary(summaryResult.value)
        } else {
          setErrorMessage('Résumé du tableau de bord indisponible. Les autres données restent affichées si disponibles.')
        }

        if (leadsResult.status === 'fulfilled' && leadsResult.value) {
          setLeads(leadsResult.value.items)
          setIsCrmFallback(false)
        } else {
          setLeads([])
          setIsCrmFallback(canViewCrm)
        }

        // /leave-requests/mine may not exist on all backends — handle gracefully
        if (leaveResult.status === 'fulfilled' && leaveResult.value) {
          setLeaveRequests(leaveResult.value.items)
        } else {
          setLeaveRequests([])
        }

        // /leave-requests/pending is the authoritative source for manager inbox
        if (pendingLeaveResult.status === 'fulfilled' && pendingLeaveResult.value) {
          setPendingLeaveRequests(pendingLeaveResult.value.items)
        } else {
          setPendingLeaveRequests([])
        }

        if (import.meta.env.DEV) {
          console.group('FlowPilot metrics debug')
          if (leadsResult.status === 'fulfilled' && leadsResult.value) {
            const rawItems = leadsResult.value.items
            console.log('normalized CRM leads length', rawItems.length)
            console.table(rawItems.map((l) => ({
              id: l.id,
              customer_status: l.customer_status,
              status: l.status,
              lifecycle_stage: l.crm_display_state?.lifecycle_stage,
              display_stage: l.crm_display_state?.display_stage,
              current_state: l.crm_display_state?.current_state,
              score: l.score,
              estimated_value: l.estimated_value,
            })))
          }
          console.groupEnd()
        }
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    void loadData()
    return () => {
      isMounted = false
    }
  }, [canViewCrm, canViewManagerInbox, canViewOwnLeave])

  const crmMetrics = useMemo(() => {
    if (leads && leads.length > 0) {
      const metrics = computeCrmMetrics(leads)
      if (import.meta.env.DEV) {
        console.log('computed CRM metrics', metrics)
      }
      return metrics
    }
    if (summary) {
      return {
        totalLeads: summary.crm_leads || 0,
        prospects: summary.prospects || 0,
        customers: summary.customers || 0,
        activeCustomers: 0,
        inactiveCustomers: 0,
        vipCustomers: 0,
        hotLeads: summary.hot_leads || 0,
        draftsToReview: summary.drafts_to_review || 0,
        estimatedValueTotal: 0,
        estimatedTotal: formatCrmCurrency(0),
        estimatedTotalValue: 0,
        prospectsToFollow: summary.prospects || 0,
        prospectsReadyToConvert: summary.prospects || 0,
        followUpProspects: summary.prospects || 0,
        nextAction: 'Aucune action requise',
      }
    }
    return computeCrmMetrics([])
  }, [leads, summary])
  const leaveMetrics = useMemo(() => {
    const metrics = buildLeaveMetrics(leaveRequests, pendingLeaveRequests, summary)
    if (import.meta.env.DEV) {
      console.log('leave metrics', metrics)
    }
    return metrics
  }, [leaveRequests, pendingLeaveRequests, summary])
  const priorityActions = useMemo(() => {
    function canAccessRoute(route: string) {
      if (route === '/crm-leads') return canViewCrm
      if (route === '/leave-requests') return canViewLeave
      if (route === '/manager-approvals') return canViewManagerInbox
      return true
    }

    return buildPriorityActions(crmMetrics, leaveMetrics).filter((action) =>
      canAccessRoute(action.route),
    )
  }, [canViewCrm, canViewLeave, canViewManagerInbox, crmMetrics, leaveMetrics])
  const recentActivity = useMemo(() => {
    return mapActivityToTimeline(summary?.recent_business_activity).filter((item) => {
      const haystack = `${item.title} ${item.description}`.toLowerCase()
      const isCrm = ['lead', 'crm', 'brouillon', 'email', 'prospect', 'client'].some((keyword) =>
        haystack.includes(keyword),
      )
      const isLeave = ['congé', 'leave', 'manager', 'rh'].some((keyword) =>
        haystack.includes(keyword),
      )
      if (isCrm && !canViewCrm) return false
      if (isLeave && !canViewLeave) return false
      return true
    })
  }, [canViewCrm, canViewLeave, summary])

  const leadTrend = useMemo(() => buildLeadTrend(leads), [leads])
  const pipelineDistribution = useMemo<ChartDatum[]>(() => {
    const leadsOnly = Math.max(0, crmMetrics.totalLeads - crmMetrics.prospects - crmMetrics.customers)
    return [
      { label: 'Leads', value: leadsOnly, color: '#38bdf8' },
      { label: 'Prospects', value: crmMetrics.prospects, color: '#a78bfa' },
      { label: 'Clients', value: crmMetrics.customers, color: '#34d399' },
    ].filter((d) => d.value > 0)
  }, [crmMetrics])
  const leadsByStatus = useMemo<ChartDatum[]>(() => {
    const palette: Record<string, string> = { hot: '#fb7185', warm: '#fbbf24', cold: '#38bdf8', new: '#34d399' }
    const counts = new Map<string, number>()
    for (const lead of leads) counts.set(lead.status, (counts.get(lead.status) ?? 0) + 1)
    const order = ['hot', 'warm', 'cold', 'new']
    return order
      .filter((s) => counts.has(s))
      .map((s) => ({ label: s.charAt(0).toUpperCase() + s.slice(1), value: counts.get(s) ?? 0, color: palette[s] }))
  }, [leads])
  const conversionFunnel = useMemo<ChartDatum[]>(
    () =>
      [
        { label: 'Leads', value: crmMetrics.totalLeads, color: '#38bdf8' },
        { label: 'Prospects', value: crmMetrics.prospects, color: '#a78bfa' },
        { label: 'Clients', value: crmMetrics.customers, color: '#34d399' },
      ].filter((d) => d.value > 0),
    [crmMetrics],
  )
  const leaveByStatus = useMemo<ChartDatum[]>(
    () =>
      [
        { label: 'En attente', value: leaveMetrics.inAiAnalysis, color: '#a78bfa' },
        { label: 'Manager', value: leaveMetrics.managerReview, color: '#fbbf24' },
        { label: 'Approuvées', value: leaveMetrics.approved, color: '#34d399' },
        { label: 'Refusées', value: leaveMetrics.rejected, color: '#fb7185' },
      ].filter((d) => d.value > 0),
    [leaveMetrics],
  )
  const topLeads = useMemo(
    () => [...leads].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 6),
    [leads],
  )
  const leadTrendDelta = useMemo(() => {
    if (leadTrend.length < 2) return null
    const current = leadTrend[leadTrend.length - 1].value
    const previous = leadTrend[leadTrend.length - 2].value
    return { current, previous, delta: current - previous }
  }, [leadTrend])

  const kpis = [
    ...(canViewCrm
      ? [
          { label: 'Leads chauds', value: crmMetrics.hotLeads, helper: 'Priorité commerciale' },
          { label: 'Prospects à suivre', value: crmMetrics.prospects, helper: 'Relance utile' },
          { label: 'Clients convertis', value: crmMetrics.customers, helper: 'Comptes convertis' },
        ]
      : []),
    ...(canViewLeave
      ? [
          {
            label: 'Demandes de congé',
            value: leaveMetrics.inAiAnalysis + leaveMetrics.managerReview,
            helper: canViewManagerInbox ? 'Analyse ou décision' : 'Mes demandes',
          },
        ]
      : []),
    ...(canViewManagerInbox
      ? [
          { label: 'Validations manager', value: leaveMetrics.managerReview, helper: 'Décision requise' },
        ]
      : []),
    ...(canViewWorkflow
      ? [
          {
            label: 'Automatisations à surveiller',
            value: summary?.automation_issues ?? 0,
            helper: 'Incidents ou files',
          },
        ]
      : []),
    ...(canViewAgents
      ? [
          {
            label: 'Agents actifs',
            value: summary?.active_agents ?? 0,
            helper: 'Supervision IA',
          },
        ]
      : []),
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="FlowPilot AI"
        title="Tableau de bord métier"
        subtitle={`Vue adaptée aux permissions du rôle ${user?.role_name ?? ''}.`}
        statusLabel={priorityActions.length > 0 ? `${priorityActions.length} priorité(s)` : 'Aucune action urgente'}
        statusTone={priorityActions.length > 0 ? 'warning' : 'success'}
      />

      {isLoading ? <LoadingState message="Chargement des données métier..." /> : null}
      {errorMessage ? (
        <ErrorState tone="warning" title="Données partielles" message={errorMessage} />
      ) : null}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi, index) => {
          const { tone, icon } = getKpiTone(index)
          const showTrend = index === 0 && canViewCrm && leadTrendDelta
          const trend = showTrend
            ? `${leadTrendDelta.delta >= 0 ? '+' : ''}${leadTrendDelta.delta} vs sem. dernière`
            : undefined
          const trendDirection =
            leadTrendDelta && leadTrendDelta.delta < 0 ? 'down' : leadTrendDelta && leadTrendDelta.delta === 0 ? 'flat' : 'up'
          return (
            <KpiCard
              key={kpi.label}
              label={kpi.label}
              value={String(kpi.value)}
              helper={kpi.helper}
              tone={tone}
              icon={icon}
              trend={trend}
              trendDirection={trendDirection}
            />
          )
        })}
      </section>

      <AppCard
        eyebrow="Priorités métier"
        title="Actions à traiter"
        description="Ce qui nécessite une attention commerciale, RH ou manager."
      >
        {priorityActions.length === 0 ? (
          <p className="text-sm text-slate-400">Aucune action requise pour le moment.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {priorityActions.map((action) => (
              <div
                key={action.title}
                className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/50 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-white">{action.title}</p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">{action.description}</p>
                  </div>
                  <PriorityBadge label={action.badge} tone={action.badgeTone} withDot />
                </div>
                <ActionButton
                  label={
                    <span className="inline-flex items-center gap-1.5">
                      {action.actionLabel}
                      <Icon name="chevron-right" size={14} />
                    </span>
                  }
                  variant="secondary"
                  size="sm"
                  onClick={() => navigate(action.route)}
                />
              </div>
            ))}
          </div>
        )}
      </AppCard>

      {canViewCrm ? (
        <>
          {isCrmFallback ? (
            <p className="text-xs text-slate-400">Mode démonstration — données CRM en direct indisponibles.</p>
          ) : null}
          <div className="grid items-start gap-5 xl:grid-cols-3">
            <AppCard
              className="xl:col-span-2"
              eyebrow="Acquisition"
              title="Nouveaux leads par semaine"
              description="Leads créés sur les 6 dernières semaines."
              actions={
                leadTrendDelta ? (
                  <span
                    className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-semibold ${
                      leadTrendDelta.delta >= 0
                        ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                        : 'border-rose-500/30 bg-rose-500/10 text-rose-200'
                    }`}
                  >
                    <Icon name={leadTrendDelta.delta >= 0 ? 'trending-up' : 'trending-down'} size={14} />
                    {leadTrendDelta.delta >= 0 ? '+' : ''}
                    {leadTrendDelta.delta} cette semaine
                  </span>
                ) : null
              }
            >
              <AreaChart data={leadTrend} />
            </AppCard>
            <AppCard eyebrow="Pipeline" title="Répartition du pipeline" description="Leads, prospects et clients.">
              <DonutChart data={pipelineDistribution} centerLabel="Total" />
            </AppCard>
          </div>

          <div className="grid items-start gap-5 xl:grid-cols-3">
            <AppCard eyebrow="Conversion" title="Entonnoir commercial" description="Du lead au client converti.">
              <FunnelChart data={conversionFunnel} />
            </AppCard>
            <AppCard eyebrow="Qualité" title="Leads par statut" description="Température des leads.">
              <BarChart data={leadsByStatus} />
            </AppCard>
            <AppCard eyebrow="Top" title="Leads prioritaires" description="Mieux scorés du pipeline." bodyClassName="p-0">
              {topLeads.length === 0 ? (
                <p className="p-5 text-sm text-slate-400">Aucun lead disponible.</p>
              ) : (
                <ul className="divide-y divide-slate-800">
                  {topLeads.map((lead) => (
                    <li key={lead.id} className="flex items-center justify-between gap-3 px-5 py-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-white">{lead.name}</p>
                        <p className="truncate text-xs text-slate-500">{lead.company}</p>
                      </div>
                      <span className="shrink-0 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-bold text-emerald-200">
                        {lead.score}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </AppCard>
          </div>
        </>
      ) : null}

      <div className="grid items-start gap-5 xl:grid-cols-2">
        {canViewLeave && leaveByStatus.length > 0 ? (
          <AppCard
            eyebrow="Congés"
            title="Demandes de congé par statut"
            description={canViewManagerInbox ? 'Vue RH / manager — part de chaque statut.' : 'Suivi de vos demandes par statut.'}
          >
            <DonutChart data={leaveByStatus} centerLabel="Demandes" />
          </AppCard>
        ) : null}

        <AppCard
          className={canViewLeave && leaveByStatus.length > 0 ? '' : 'xl:col-span-2'}
          eyebrow="Activité récente"
          title="Événements métier"
          description="Dernières opérations enregistrées."
          actions={
            <StatusBadge
              label={`${recentActivity.length} événement${recentActivity.length === 1 ? '' : 's'}`}
              status="info"
            />
          }
        >
          <ActivityTimeline
            items={recentActivity}
            emptyTitle="Aucune activité récente"
            emptyDescription="Les nouveaux événements CRM et congés apparaîtront ici."
          />
        </AppCard>
      </div>

    </div>
  )
}

export default DashboardPage
