import { useEffect, useMemo, useState } from 'react'
import {
  ActionButton,
  AppCard,
  EmptyState,
  ErrorState,
  Icon,
  KpiCard,
  LoadingState,
  PageHeader,
  PriorityBadge,
  StatusBadge,
  TechnicalDetailsPanel,
  type BadgeTone,
} from '../components/common'
import { aiAgents as fallbackAgents } from '../data/aiAgentsData'
import { getAgentById, getAgents, runAgent } from '../services/agentService'
import type { AgentDetail, AgentRecord } from '../services/agentService'
import { useAuth } from '../auth/useAuth'

type AgentCard = {
  id: string
  name: string
  role: string
  process: string
  status: 'active' | 'idle' | 'degraded' | 'inactive'
  statusLabel: string
  lastRun: string
  successRate: string
  impact: string
  needsAttention: boolean
}

const MANUAL_RUN_PAYLOAD = { reason: 'Lancement manuel depuis le centre Agents IA' }

function formatDateTime(value: string | null | undefined) {
  if (!value) return 'Non renseigné'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Non renseigné'
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(parsed)
}

function mapStatus(status: AgentRecord['status']): AgentCard['status'] {
  if (status === 'active') return 'active'
  if (status === 'degraded') return 'degraded'
  return 'inactive'
}

function mapStatusLabel(status: AgentCard['status']) {
  if (status === 'active') return 'Actif'
  if (status === 'degraded') return 'À surveiller'
  if (status === 'idle') return 'En attente'
  return 'Inactif'
}

function mapStatusTone(status: AgentCard['status']): BadgeTone {
  if (status === 'active') return 'green'
  if (status === 'degraded') return 'orange'
  if (status === 'idle') return 'blue'
  return 'slate'
}

function normalizeAgentText(agent: Pick<AgentRecord, 'name' | 'process' | 'type'>) {
  return `${agent.name} ${agent.process} ${agent.type}`.toLowerCase()
}

function formatPercent(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return 'Non renseigné'
  const numeric = typeof value === 'number' ? value : Number(String(value).replace('%', '').trim())
  if (Number.isNaN(numeric)) return String(value)
  return `${Math.round(numeric)} %`
}

function localizeProcess(process: string) {
  const lower = process.toLowerCase()
  if (lower.includes('leave') || lower.includes('cong')) return 'Congés'
  if (lower.includes('crm')) return 'CRM'
  if (lower.includes('odoo') || lower.includes('rh')) return 'Synchronisation RH/Odoo'
  if (lower.includes('gmail') || lower.includes('email')) return 'Email/Gmail'
  if (lower.includes('monit')) return 'Supervision'
  return process || 'Processus métier'
}

function businessAgentName(agent: Pick<AgentRecord, 'name' | 'process' | 'type'>) {
  const lower = normalizeAgentText(agent)
  if (lower.includes('crm') && (lower.includes('score') || lower.includes('analys'))) {
    return 'Agent Analyse CRM'
  }
  if (lower.includes('crm') && (lower.includes('route') || lower.includes('assign'))) {
    return 'Agent Routage Commercial'
  }
  if (lower.includes('crm') || lower.includes('lead')) return 'Agent Communication CRM'
  if (lower.includes('leave') || lower.includes('cong')) return 'Agent Analyse Congé'
  if (lower.includes('odoo') || lower.includes('rh')) return 'Agent Synchronisation Odoo'
  if (lower.includes('gmail') || lower.includes('email') || lower.includes('mail')) {
    return 'Agent Email/Gmail'
  }
  return agent.name || 'Assistant IA'
}

function businessImpact(agent: Pick<AgentRecord, 'name' | 'process' | 'type'>) {
  const lower = normalizeAgentText(agent)
  if (lower.includes('crm') && (lower.includes('score') || lower.includes('analys'))) {
    return 'Leads qualifiés et priorités commerciales clarifiées.'
  }
  if (lower.includes('crm')) return 'Communications commerciales préparées et suivies.'
  if (lower.includes('leave') || lower.includes('cong')) {
    return 'Demandes de congé analysées pour décision manager.'
  }
  if (lower.includes('odoo') || lower.includes('rh')) {
    return 'Synchronisation RH sécurisée après décision.'
  }
  if (lower.includes('gmail') || lower.includes('email') || lower.includes('mail')) {
    return 'Emails approuvés envoyés automatiquement.'
  }
  return 'Impact métier suivi par FlowPilot AI.'
}

function mapAgentToCard(agent: AgentRecord): AgentCard {
  const status = mapStatus(agent.status)
  return {
    id: agent.id,
    name: businessAgentName(agent),
    role: agent.description || 'Assistant métier FlowPilot AI',
    process: localizeProcess(agent.process),
    status,
    statusLabel: mapStatusLabel(status),
    lastRun: formatDateTime(agent.last_execution),
    successRate: formatPercent(agent.success_rate),
    impact: businessImpact(agent),
    needsAttention: status === 'degraded' || status === 'inactive',
  }
}

function mapFallbackAgent(agent: (typeof fallbackAgents)[number]): AgentCard {
  const status: AgentCard['status'] = agent.status === 'warning' ? 'degraded' : 'active'
  return {
    id: agent.id,
    name: businessAgentName({ name: agent.name, process: agent.process, type: '' }),
    role: 'Assistant métier FlowPilot AI',
    process: localizeProcess(agent.process),
    status,
    statusLabel: mapStatusLabel(status),
    lastRun: agent.lastExecution,
    successRate: formatPercent(agent.successRate),
    impact: businessImpact({ name: agent.name, process: agent.process, type: '' }),
    needsAttention: status === 'degraded',
  }
}

function AIAgentCenterPage() {
  const { hasPermission } = useAuth()
  const canRunAgent = hasPermission('agents.run')
  const [cards, setCards] = useState<AgentCard[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<AgentDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDetailLoading, setIsDetailLoading] = useState(false)
  const [isUsingFallback, setIsUsingFallback] = useState(false)
  const [runMessage, setRunMessage] = useState('')
  const [runError, setRunError] = useState('')

  useEffect(() => {
    let isMounted = true
    async function loadAgents() {
      setIsLoading(true)
      try {
        const response = await getAgents()
        if (!isMounted) return
        const mapped = response.items.map(mapAgentToCard)
        setCards(mapped)
        setSelectedId(mapped[0]?.id ?? null)
        setIsUsingFallback(false)
      } catch {
        if (!isMounted) return
        const mapped = fallbackAgents.map(mapFallbackAgent)
        setCards(mapped)
        setSelectedId(mapped[0]?.id ?? null)
        setIsUsingFallback(true)
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }
    void loadAgents()
    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    if (!selectedId || isUsingFallback) {
      return
    }
    let isMounted = true
    async function loadDetail() {
      if (!selectedId) return
      setIsDetailLoading(true)
      try {
        const response = await getAgentById(selectedId)
        if (isMounted) setDetail(response)
      } catch {
        if (isMounted) setDetail(null)
      } finally {
        if (isMounted) setIsDetailLoading(false)
      }
    }
    void loadDetail()
    return () => {
      isMounted = false
      setDetail(null)
    }
  }, [selectedId, isUsingFallback])

  const summary = useMemo(
    () => ({
      total: cards.length,
      active: cards.filter((card) => card.status === 'active').length,
      degraded: cards.filter((card) => card.status === 'degraded').length,
      inactive: cards.filter((card) => card.status === 'inactive').length,
    }),
    [cards],
  )

  async function handleRun(agentId: string) {
    setRunError('')
    setRunMessage('')
    if (!canRunAgent) {
      setRunError('Votre role ne permet pas de lancer un agent IA.')
      return
    }
    if (isUsingFallback) {
      setRunError('Le lancement manuel est désactivé en mode hors ligne.')
      return
    }
    try {
      const response = await runAgent(agentId, MANUAL_RUN_PAYLOAD)
      setRunMessage(response.message || 'Agent lancé. Suivez son impact métier dans cette vue.')
    } catch {
      setRunError('L’agent IA n’a pas pu être lancé. Vérifiez la connexion au service.')
    }
  }

  const selected = cards.find((card) => card.id === selectedId) ?? cards[0]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Agents IA"
        title="Centre des assistants métier"
        subtitle="Les assistants IA supervisent le CRM, les congés et les automatisations. Lancez un agent manuellement pour vérifier son impact."
        statusLabel={`${summary.active}/${summary.total} agents actifs`}
        statusTone={summary.degraded > 0 || summary.inactive > 0 ? 'warning' : 'success'}
      />

      {isLoading ? <LoadingState message="Chargement des agents IA..." /> : null}
      {isUsingFallback ? (
        <ErrorState
          tone="warning"
          title="Données des agents indisponibles"
          message="Affichage d’exemples hors ligne. Le lancement manuel est désactivé."
        />
      ) : null}
      {runMessage ? (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-200">
          {runMessage}
        </div>
      ) : null}
      {runError ? (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm font-medium text-rose-200">
          {runError}
        </div>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Agents totaux"
          value={String(summary.total)}
          tone="emerald"
          icon="bot"
          helper="Assistants disponibles"
        />
        <KpiCard
          label="Actifs"
          value={String(summary.active)}
          tone="emerald"
          icon="check"
          helper="Prêts à exécuter"
        />
        <KpiCard
          label="À surveiller"
          value={String(summary.degraded)}
          tone="amber"
          icon="alert"
          helper="Revue recommandée"
        />
        <KpiCard
          label="Inactifs"
          value={String(summary.inactive)}
          tone="slate"
          icon="clock"
          helper="Attente d’événement"
        />
      </section>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <AppCard
          eyebrow="Catalogue"
          title="Agents IA FlowPilot"
          description="Chaque agent prend en charge un processus métier spécifique."
        >
          {cards.length === 0 ? (
            <EmptyState
              icon="bot"
              title="Aucun agent disponible"
              description="Les agents apparaîtront ici une fois déployés."
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {cards.map((card) => {
                const isActive = card.id === selectedId
                return (
                  <article
                    key={card.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedId(card.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') setSelectedId(card.id)
                    }}
                    className={`cursor-pointer rounded-xl border px-4 py-4 transition ${
                      isActive
                        ? 'border-emerald-500/40 bg-emerald-500/10'
                        : 'border-slate-800 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-900/70'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-linear-to-br from-emerald-500 to-emerald-600 text-white">
                          <Icon name="bot" />
                        </span>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-bold text-white">{card.name}</p>
                          <p className="truncate text-xs text-slate-400">{card.process}</p>
                        </div>
                      </div>
                      <PriorityBadge
                        label={card.statusLabel}
                        tone={mapStatusTone(card.status)}
                        withDot
                      />
                    </div>
                    <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-3">
                      <div>
                        <dt className="text-slate-500">Dernière exécution</dt>
                        <dd className="mt-0.5 font-semibold text-slate-200">{card.lastRun}</dd>
                      </div>
                      <div>
                        <dt className="text-slate-500">Succès</dt>
                        <dd className="mt-0.5 font-semibold text-slate-200">{card.successRate}</dd>
                      </div>
                      <div>
                        <dt className="text-slate-500">Action requise</dt>
                        <dd className="mt-0.5 font-semibold text-slate-200">
                          {card.needsAttention ? 'Revue IA' : 'Aucune action requise'}
                        </dd>
                      </div>
                    </dl>
                    {canRunAgent ? (
                      <div className="mt-4">
                        <ActionButton
                          label={
                            <span className="inline-flex items-center gap-1.5">
                              <Icon name="send" size={14} />
                              Lancer l’agent
                            </span>
                          }
                          size="sm"
                          onClick={() => void handleRun(card.id)}
                          disabled={isUsingFallback || !canRunAgent}
                        />
                      </div>
                    ) : null}
                  </article>
                )
              })}
            </div>
          )}
        </AppCard>

        <AppCard
          eyebrow="Détail"
          title={selected?.name ?? 'Aucun agent sélectionné'}
          description={selected?.role ?? 'Choisissez un agent à gauche pour afficher son rôle et son impact.'}
          actions={
            selected ? (
              <StatusBadge
                label={selected.statusLabel}
                status={
                  selected.status === 'active'
                    ? 'success'
                    : selected.status === 'degraded'
                      ? 'warning'
                      : 'neutral'
                }
              />
            ) : null
          }
        >
          {selected ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    Processus lié
                  </p>
                  <p className="mt-1 font-semibold text-white">{selected.process}</p>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    Taux de succès
                  </p>
                  <p className="mt-1 font-semibold text-white">{selected.successRate}</p>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 sm:col-span-2">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    Impact métier
                  </p>
                  <p className="mt-1 font-semibold text-white">
                    {detail?.output_description || selected.impact}
                  </p>
                </div>
              </div>

              {canRunAgent ? (
                <ActionButton
                  label={
                    <span className="inline-flex items-center gap-1.5">
                      <Icon name="send" size={14} />
                      Lancer l’agent
                    </span>
                  }
                  onClick={() => void handleRun(selected.id)}
                  disabled={isUsingFallback || !canRunAgent}
                />
              ) : null}

              {isDetailLoading ? (
                <LoadingState message="Chargement du détail de l’agent..." />
              ) : null}

              <TechnicalDetailsPanel title="Détails techniques">
                <dl className="grid gap-2 sm:grid-cols-2">
                  <div>
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      Identifiant
                    </dt>
                    <dd className="break-words text-sm text-slate-300">{selected.id}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      Dernière exécution
                    </dt>
                    <dd className="text-sm text-slate-300">{selected.lastRun}</dd>
                  </div>
                  {detail ? (
                    <>
                      <div className="sm:col-span-2">
                        <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                          Entrée métier
                        </dt>
                        <dd className="text-sm text-slate-300">{detail.input_description}</dd>
                      </div>
                      <div className="sm:col-span-2">
                        <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                          Outils mobilisés
                        </dt>
                        <dd className="text-sm text-slate-300">
                          {detail.tools.length > 0 ? detail.tools.join(', ') : 'Non renseigné'}
                        </dd>
                      </div>
                      <div className="sm:col-span-2">
                        <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                          Automatisations liées
                        </dt>
                        <dd className="text-sm text-slate-300">
                          {detail.related_workflows.length > 0
                            ? detail.related_workflows.join(', ')
                            : 'Non renseigné'}
                        </dd>
                      </div>
                    </>
                  ) : null}
                </dl>
              </TechnicalDetailsPanel>
            </div>
          ) : null}
        </AppCard>
      </div>
    </div>
  )
}

export default AIAgentCenterPage
