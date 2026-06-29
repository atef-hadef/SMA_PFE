import { useEffect, useMemo, useState } from 'react'
import {
  AppCard,
  EmptyState,
  ErrorState,
  Icon,
  LoadingState,
  PageHeader,
  PriorityBadge,
  StatusBadge,
} from '../components/common'
import { pendingTeamRequests, selectedRequest } from '../data/managerApprovalData'
import {
  approveStandalone,
  getLeaveRequestsHistory,
  getPendingLeaveRequests,
  rejectStandalone,
  type LeaveRequestHistoryRecord,
  type PendingLeaveRequestRecord,
} from '../services/leaveService'
import {
  formatLeavePeriod,
  formatLeaveStatus,
  formatRecommendation,
  formatRiskLevel,
  getLeaveStatusTone,
  getRecommendationTone,
  getRiskTone,
} from '../utils/leaveDisplay'
import { useAuth } from '../auth/useAuth'

// ── Types ────────────────────────────────────────────────────────────────────

type BadgeTone = 'green' | 'orange' | 'red' | 'blue' | 'slate'
type NumericValue = number | string | null | undefined

type ApprovalCard = {
  id: string
  employee: string
  department: string
  leaveType: string
  reason: string
  startDate: string
  endDate: string
  days: number
  period: string
  recommendation: string
  recommendationTone: BadgeTone
  risk: string
  riskTone: BadgeTone
  conflict: boolean
  status: string
  statusTone: BadgeTone
  availableDays: NumericValue
  requestedDays: NumericValue
  balanceGapDays: NumericValue
  aiExplanation: string | null
  decisionReasons: string[]
  blockingReasons: string[]
  approvalFactors: string[]
  rejectionFactors: string[]
  managerGuidance: string | null
  canManagerOverride: boolean | null
  canSyncWithOdoo: boolean
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function daysBetween(startDate: string, endDate: string) {
  const diff =
    (new Date(`${endDate}T00:00:00`).getTime() - new Date(`${startDate}T00:00:00`).getTime()) /
    (1000 * 60 * 60 * 24)
  return Math.max(1, Math.round(diff) + 1)
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error && error.message) return error.message
  return 'La décision n\u2019a pas pu être transmise. Vérifiez les services métier puis réessayez.'
}

function parseNumberValue(value: NumericValue) {
  if (value === null || value === undefined) return null
  if (typeof value === 'number') return Number.isFinite(value) ? value : null

  const normalized = value.trim().replace(',', '.')
  if (!normalized) return null

  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
}

function formatDays(value: NumericValue) {
  const parsed = parseNumberValue(value)
  if (parsed === null) return 'Non renseigné'

  const formatted = Number.isInteger(parsed) ? `${parsed}` : parsed.toFixed(1).replace('.', ',')
  return `${formatted} jour${Math.abs(parsed) === 1 ? '' : 's'}`
}

function compactReasons(...groups: Array<string[] | undefined>) {
  return groups.flatMap((group) => group ?? []).filter(Boolean)
}

function mapPendingRequestToCard(request: PendingLeaveRequestRecord): ApprovalCard {
  const periodDays = daysBetween(request.start_date, request.end_date)
  const requestedDays = parseNumberValue(request.requested_days) ?? periodDays
  return {
    id: request.id,
    employee: request.employee_name,
    department: request.department,
    leaveType: request.leave_type,
    reason: request.reason,
    startDate: request.start_date,
    endDate: request.end_date,
    period: formatLeavePeriod(request.start_date, request.end_date),
    days: requestedDays,
    recommendation: formatRecommendation(request.ai_recommendation),
    recommendationTone: getRecommendationTone(request.ai_recommendation),
    risk: formatRiskLevel(request.risk_level),
    riskTone: getRiskTone(request.risk_level, request.conflict_detected),
    conflict: request.conflict_detected,
    status: formatLeaveStatus(request.status),
    statusTone: getLeaveStatusTone(request.status),
    availableDays: request.available_days ?? null,
    requestedDays,
    balanceGapDays: request.balance_gap_days ?? null,
    aiExplanation: request.ai_explanation ?? request.automation_summary ?? null,
    decisionReasons: compactReasons(request.decision_reasons, request.score_reasons),
    blockingReasons: request.blocking_reasons ?? [],
    approvalFactors: request.approval_factors ?? [],
    rejectionFactors: request.rejection_factors ?? [],
    managerGuidance: request.manager_guidance,
    canManagerOverride: request.can_manager_override,
    canSyncWithOdoo: request.can_sync_with_odoo,
  }
}

function fallbackCards(): ApprovalCard[] {
  return pendingTeamRequests.map((request, index) => {
    const isWarning = request.status === 'warning'
    const [leaveType, employee] = (request.process ?? '').split(' - ')
    return {
      id: request.id,
      employee: employee || selectedRequest.employee,
      department: request.owner,
      leaveType: leaveType || selectedRequest.leaveType,
      reason:
        index === 0
          ? 'Exemple hors ligne : demande de congé annuel à valider.'
          : 'Exemple hors ligne : demande en attente de décision manager.',
      startDate: '2026-04-22',
      endDate: '2026-04-24',
      period: 'du 22/04/2026 au 24/04/2026',
      days: 3,
      recommendation: isWarning ? 'Vérification manager recommandée' : 'Approbation recommandée',
      recommendationTone: isWarning ? 'orange' : 'green',
      risk: isWarning ? 'Moyen' : 'Faible',
      riskTone: isWarning ? 'orange' : 'green',
      conflict: isWarning,
      status: 'Validation manager requise',
      statusTone: 'orange',
      availableDays: 13,
      requestedDays: 24,
      balanceGapDays: 11,
      aiExplanation: 'La demande dépasse le solde disponible.',
      decisionReasons: ['Solde disponible insuffisant', 'Durée demandée supérieure au solde'],
      blockingReasons: ['Le solde disponible ne couvre pas la période demandée'],
      approvalFactors: ['Validation RH exceptionnelle requise'],
      rejectionFactors: ['Demande supérieure au solde disponible'],
      managerGuidance: 'Refuser la demande ou demander une réduction de la période.',
      canManagerOverride: true,
      canSyncWithOdoo: true,
    }
  })
}

function formatDecisionDate(value: string | null | undefined): string {
  if (!value) return 'Non renseigné'
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  } catch {
    return value
  }
}

function getOdooSyncLabel(status: string | null | undefined): string {
  if (status === 'synced') return 'Synchronisée'
  if (status === 'failed') return 'Erreur synchronisation'
  if (status === 'pending') return 'En attente'
  return 'Non renseigné'
}

function getOdooSyncTone(status: string | null | undefined): BadgeTone {
  if (status === 'synced') return 'green'
  if (status === 'failed') return 'red'
  return 'slate'
}

function verdictClasses(tone: BadgeTone): string {
  if (tone === 'green') return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100'
  if (tone === 'red') return 'border-rose-500/40 bg-rose-500/10 text-rose-100'
  if (tone === 'orange') return 'border-amber-500/40 bg-amber-500/10 text-amber-100'
  return 'border-slate-700 bg-slate-900/60 text-slate-100'
}

// ── Component ────────────────────────────────────────────────────────────────

function ManagerApprovalPage() {
  const { hasPermission } = useAuth()
  const canApproveLeave = hasPermission('leave.request.approve')
  const canRejectLeave = hasPermission('leave.request.reject')
  const [pendingRequests, setPendingRequests] = useState<PendingLeaveRequestRecord[]>([])
  const [historyRecords, setHistoryRecords] = useState<LeaveRequestHistoryRecord[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isHistoryLoading, setIsHistoryLoading] = useState(true)
  const [isDeciding, setIsDeciding] = useState(false)
  const [isUsingFallback, setIsUsingFallback] = useState(false)
  const [decisionMessage, setDecisionMessage] = useState('')
  const [decisionError, setDecisionError] = useState('')
  const [managerComment, setManagerComment] = useState('')

  async function loadPendingRequests() {
    setIsLoading(true)
    try {
      const response = await getPendingLeaveRequests()
      setPendingRequests(response.items)
      setSelectedId((current) => {
        if (response.items.some((request) => request.id === current)) return current
        return response.items[0]?.id ?? ''
      })
      setIsUsingFallback(false)
    } catch {
      setPendingRequests([])
      setSelectedId(pendingTeamRequests[0]?.id ?? '')
      setIsUsingFallback(true)
    } finally {
      setIsLoading(false)
    }
  }

  async function loadHistory() {
    setIsHistoryLoading(true)
    try {
      const response = await getLeaveRequestsHistory()
      // Keep only decided requests for the history section
      setHistoryRecords(
        response.items.filter((r) => r.status === 'approved' || r.status === 'rejected'),
      )
    } catch {
      setHistoryRecords([])
    } finally {
      setIsHistoryLoading(false)
    }
  }

  useEffect(() => {
    void Promise.resolve().then(async () => {
      await Promise.allSettled([loadPendingRequests(), loadHistory()])
    })
  }, [])

  const cards = useMemo(
    () => (isUsingFallback ? fallbackCards() : pendingRequests.map(mapPendingRequestToCard)),
    [isUsingFallback, pendingRequests],
  )
  const activeCard = cards.find((card) => card.id === selectedId) ?? cards[0]

  const summary = useMemo(
    () => ({
      pending: cards.length,
      highRisk: cards.filter((card) => card.risk === 'Élevé').length,
      conflicts: cards.filter((card) => card.conflict).length,
      recommendedApprovals: cards.filter((card) => card.recommendation.includes('Approbation')).length,
    }),
    [cards],
  )

  async function handleDecision(decision: 'approve' | 'reject') {
    if ((decision === 'approve' && !canApproveLeave) || (decision === 'reject' && !canRejectLeave)) {
      setDecisionMessage('')
      setDecisionError('Votre role ne permet pas cette decision.')
      return
    }

    if (decision === 'reject' && !managerComment.trim()) {
      setDecisionMessage('')
      setDecisionError('Un commentaire est obligatoire pour refuser une demande.')
      return
    }

    if (!activeCard?.id || isUsingFallback) {
      setDecisionMessage('')
      setDecisionError('La décision ne peut pas être envoyée sans connexion au backend.')
      return
    }

    setIsDeciding(true)
    setDecisionMessage('')
    setDecisionError('')

    try {
      if (decision === 'approve') {
        await approveStandalone(
          activeCard.id,
          managerComment.trim() || 'Demande approuvée depuis FlowPilot.',
        )
      } else {
        await rejectStandalone(activeCard.id, managerComment.trim())
      }

      setDecisionMessage(
        decision === 'approve'
          ? 'Demande approuvée. Le collaborateur va être notifié par email.'
          : 'Demande refusée. Le collaborateur va être notifié par email.',
      )
      // Refresh both sections after a decision
      await Promise.allSettled([loadPendingRequests(), loadHistory()])
      setManagerComment('')
    } catch (error) {
      setDecisionMessage('')
      setDecisionError(getErrorMessage(error))
    } finally {
      setIsDeciding(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Ressources humaines"
        title="Validations manager"
        subtitle="Validez ou refusez les demandes de congé de votre équipe."
        statusLabel={`${summary.pending} décision${summary.pending === 1 ? '' : 's'} en attente`}
        statusTone={summary.pending > 0 ? 'warning' : 'success'}
      />

      {isLoading ? <LoadingState message="Chargement des demandes en attente..." /> : null}
      {isUsingFallback ? (
        <ErrorState
          tone="warning"
          title="Données en direct indisponibles"
          message="Les exemples ci-dessous servent de démonstration. Les décisions sont désactivées."
        />
      ) : null}

      {/* ── Demandes à valider ─────────────────────────────────────────────── */}
      <div className="grid gap-5 lg:grid-cols-[380px_minmax(0,1fr)]">
        <AppCard eyebrow="Inbox" title="Demandes à traiter">
          {cards.length === 0 ? (
            <EmptyState
              icon="check"
              title="Aucune demande en attente"
              description="Toutes les demandes ont été traitées. Les nouvelles arriveront ici après analyse IA."
            />
          ) : (
            <ul className="space-y-2">
              {cards.map((card) => {
                const isActive = card.id === activeCard?.id
                return (
                  <li key={card.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(card.id)}
                      className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                        isActive
                          ? 'border-emerald-500/40 bg-emerald-500/10 shadow-inner shadow-emerald-500/20'
                          : 'border-slate-800 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-900/60'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-white">{card.employee}</p>
                          <p className="truncate text-xs text-slate-400">{card.leaveType}</p>
                          <p className="mt-1 text-[11px] text-slate-500">{card.period}</p>
                        </div>
                        <PriorityBadge label={card.risk} tone={card.riskTone} size="sm" />
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <StatusBadge label={card.status} status="warning" size="sm" />
                        {card.conflict ? (
                          <StatusBadge label="Conflit détecté" status="danger" size="sm" />
                        ) : null}
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </AppCard>

        <div className="space-y-5">
          {activeCard ? (
            <>
              <AppCard
                eyebrow="Demande"
                title={activeCard.employee}
                description={`${activeCard.department} · ${activeCard.leaveType}`}
                actions={<PriorityBadge label={activeCard.status} tone={activeCard.statusTone} />}
              >
                <dl className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Période</dt>
                    <dd className="mt-1 font-semibold text-white">{activeCard.period}</dd>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Jours</dt>
                    <dd className="mt-1 font-semibold text-white">{formatDays(activeCard.requestedDays)}</dd>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Solde dispo</dt>
                    <dd className="mt-1 font-semibold text-white">{formatDays(activeCard.availableDays)}</dd>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 sm:col-span-3">
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Motif</dt>
                    <dd className="mt-1 text-sm leading-6 text-slate-200">{activeCard.reason}</dd>
                  </div>
                </dl>
              </AppCard>

              <AppCard eyebrow="Analyse IA" title="Verdict & aide à la décision">
                <div className={`rounded-xl border p-4 ${verdictClasses(activeCard.recommendationTone)}`}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] opacity-80">
                        Verdict IA
                      </p>
                      <p className="mt-1 text-lg font-bold">{activeCard.recommendation}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <PriorityBadge label={`Risque : ${activeCard.risk}`} tone={activeCard.riskTone} size="sm" />
                      <PriorityBadge
                        label={activeCard.conflict ? 'Conflit équipe' : 'Pas de conflit'}
                        tone={activeCard.conflict ? 'red' : 'green'}
                        size="sm"
                      />
                    </div>
                  </div>
                  {activeCard.aiExplanation ? (
                    <p className="mt-3 text-sm leading-6">{activeCard.aiExplanation}</p>
                  ) : null}
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Solde disponible</p>
                    <p className="mt-1 text-sm font-semibold text-white">{formatDays(activeCard.availableDays)}</p>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Jours demandés</p>
                    <p className="mt-1 text-sm font-semibold text-white">{formatDays(activeCard.requestedDays)}</p>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Écart de solde</p>
                    <p className="mt-1 text-sm font-semibold text-white">{formatDays(activeCard.balanceGapDays)}</p>
                  </div>
                </div>

                {activeCard.decisionReasons.length > 0 ? (
                  <div className="mt-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Raisons principales</p>
                    <ul className="mt-2 space-y-1 text-sm text-slate-300">
                      {activeCard.decisionReasons.map((reason) => (
                        <li key={reason} className="flex gap-2">
                          <span className="mt-2 h-1.5 w-1.5 rounded-full bg-emerald-400" />
                          <span>{reason}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {activeCard.blockingReasons.length > 0 ? (
                  <div className="mt-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-rose-200">Points bloquants</p>
                    <p className="mt-2 text-sm text-rose-100">{activeCard.blockingReasons.join(' ')}</p>
                  </div>
                ) : null}

                {activeCard.managerGuidance ? (
                  <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-200">Conseil au manager</p>
                    <p className="mt-2 text-sm leading-6 text-amber-100">{activeCard.managerGuidance}</p>
                  </div>
                ) : null}
              </AppCard>

              <AppCard
                eyebrow="Décision manager"
                title="Valider ou refuser"
                description="Ajoutez un commentaire interne avant de transmettre la décision au SIRH."
              >
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                    Commentaire <span className="text-slate-500">(obligatoire pour refuser)</span>
                  </span>
                  <textarea
                    rows={3}
                    value={managerComment}
                    onChange={(event) => setManagerComment(event.target.value)}
                    placeholder="Motivez votre décision…"
                    className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20"
                  />
                </label>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => void handleDecision('approve')}
                    disabled={isDeciding || isUsingFallback || !activeCard || !canApproveLeave}
                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-3 text-sm font-semibold text-slate-950 shadow-md shadow-emerald-500/20 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                  >
                    <Icon name="check" size={16} />
                    {isDeciding ? 'Traitement…' : 'Approuver'}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDecision('reject')}
                    disabled={isDeciding || isUsingFallback || !activeCard || !canRejectLeave || !managerComment.trim()}
                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-rose-600 px-4 py-3 text-sm font-semibold text-white shadow-md shadow-rose-600/20 transition hover:bg-rose-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                  >
                    <Icon name="close" size={16} />
                    Refuser
                  </button>
                </div>
                {canRejectLeave && !managerComment.trim() ? (
                  <p className="mt-2 text-[11px] text-slate-500">Un commentaire est requis pour refuser.</p>
                ) : null}

                {decisionMessage ? (
                  <div className="mt-4 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-200">
                    {decisionMessage}
                  </div>
                ) : null}
                {decisionError ? (
                  <div className="mt-4 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm font-medium text-rose-200">
                    {decisionError}
                  </div>
                ) : null}
              </AppCard>
            </>
          ) : (
            <EmptyState
              icon="check"
              title="Aucune demande sélectionnée"
              description="Aucune décision manager n'est en attente."
            />
          )}
        </div>
      </div>

      {/* ── Décisions récentes ─────────────────────────────────────────────── */}
      <AppCard
        eyebrow="Historique"
        title="Décisions récentes"
        description="Demandes approuvées ou refusées. Les décisions en attente n'apparaissent pas ici."
        actions={
          <StatusBadge
            label={`${historyRecords.length} décision${historyRecords.length === 1 ? '' : 's'}`}
            status="info"
          />
        }
      >
        {isHistoryLoading ? (
          <p className="text-sm text-slate-400">Chargement de l'historique...</p>
        ) : historyRecords.length === 0 ? (
          <EmptyState
            icon="file"
            title="Aucune décision enregistrée"
            description="Les demandes approuvées ou refusées apparaîtront ici après traitement."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-950/70 text-[11px] uppercase tracking-[0.14em] text-slate-400">
                <tr>
                  <th className="px-4 py-3 font-semibold">Employé</th>
                  <th className="px-4 py-3 font-semibold">Département</th>
                  <th className="px-4 py-3 font-semibold">Type de congé</th>
                  <th className="px-4 py-3 font-semibold">Période</th>
                  <th className="px-4 py-3 font-semibold">Jours</th>
                  <th className="px-4 py-3 font-semibold">Décision</th>
                  <th className="px-4 py-3 font-semibold">Date de décision</th>
                  <th className="px-4 py-3 font-semibold">Sync RH</th>
                  <th className="px-4 py-3 font-semibold">Commentaire</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {historyRecords.map((record) => {
                  const decisionTone: BadgeTone = record.status === 'approved' ? 'green' : 'red'
                  const decisionLabel = record.status === 'approved' ? 'Approuvée' : 'Refusée'
                  const syncTone = getOdooSyncTone(record.odoo_sync_status)
                  const syncLabel = getOdooSyncLabel(record.odoo_sync_status)
                  const days = record.requested_days
                    ? `${record.requested_days} j`
                    : `${daysBetween(record.start_date, record.end_date)} j`

                  return (
                    <tr key={record.id} className="hover:bg-slate-900/40">
                      <td className="px-4 py-3 font-semibold text-white">
                        {record.employee_name}
                      </td>
                      <td className="px-4 py-3 text-slate-300">{record.department}</td>
                      <td className="px-4 py-3 text-slate-300">{record.leave_type}</td>
                      <td className="px-4 py-3 whitespace-nowrap text-slate-300">
                        {formatLeavePeriod(record.start_date, record.end_date)}
                      </td>
                      <td className="px-4 py-3 text-slate-300">{days}</td>
                      <td className="px-4 py-3">
                        <PriorityBadge label={decisionLabel} tone={decisionTone} withDot />
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-slate-300">
                        {formatDecisionDate(record.decided_at ?? record.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <PriorityBadge label={syncLabel} tone={syncTone} size="sm" />
                      </td>
                      <td className="max-w-[200px] px-4 py-3 text-slate-400">
                        {record.manager_comment || '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </AppCard>
    </div>
  )
}

export default ManagerApprovalPage
