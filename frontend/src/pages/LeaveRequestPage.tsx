import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ActionButton,
  AppCard,
  ErrorState,
  Icon,
  PageHeader,
  PriorityBadge,
} from '../components/common'
import {
  createStandaloneRequest,
  getLeaveTypes,
  getMyBalance,
  getMyLeaveRequests,
  type LeaveBalanceItem,
  type LeaveBalancePrecheckResponse,
  type LeaveRequestCreatePayload,
  type LeaveRequestCreatedResponse,
  type LeaveRequestHistoryRecord,
  type LeaveTypeOption,
} from '../services/leaveService'
import { ApiRequestError } from '../services/apiClient'
import {
  formatLeavePeriod,
  formatLeaveStatus,
  getLeaveStatusTone,
  type BadgeTone,
} from '../utils/leaveDisplay'
import { useAuth } from '../auth/useAuth'

type LeaveFormState = LeaveRequestCreatePayload
type NumericValue = number | string | null | undefined

const initialLeaveFormState: LeaveFormState = {
  leave_type: '',
  start_date: '',
  end_date: '',
  reason: '',
}

const leaveTypeOptions = [
  { value: 'Congé annuel', label: 'Congé annuel' },
  { value: 'Congé maladie', label: 'Congé maladie' },
  { value: 'Congé exceptionnel', label: 'Congé exceptionnel' },
  { value: 'Télétravail', label: 'Télétravail' },
  { value: 'RTT', label: 'RTT' },
]

function toStatusType(tone: BadgeTone): 'success' | 'warning' | 'danger' | 'info' | 'neutral' {
  if (tone === 'green') return 'success'
  if (tone === 'orange') return 'warning'
  if (tone === 'red') return 'danger'
  if (tone === 'blue') return 'info'
  return 'neutral'
}

function validateLeaveForm(formState: LeaveFormState) {
  if (!formState.leave_type.trim()) return 'Le type de congé est obligatoire.'
  if (!formState.start_date) return 'La date de début est obligatoire.'
  if (!formState.end_date) return 'La date de fin est obligatoire.'
  if (!formState.reason.trim()) return 'Le motif est obligatoire.'
  if (formState.end_date < formState.start_date) {
    return 'La date de fin ne peut pas être antérieure à la date de début.'
  }
  return null
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error && error.message) return error.message
  return 'La demande n’a pas pu être envoyée. Vérifiez les services métier puis réessayez.'
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

function isLeavePrecheckResponse(value: unknown): value is LeaveBalancePrecheckResponse {
  return Boolean(
    value &&
      typeof value === 'object' &&
      ('available_days' in value || 'conflict_detected' in value || 'error_code' in value),
  )
}

function getOverlapLeaveText(leave: Record<string, unknown>) {
  const dateFrom = typeof leave.date_from === 'string' ? leave.date_from : null
  const dateTo = typeof leave.date_to === 'string' ? leave.date_to : null
  const numberOfDays =
    typeof leave.number_of_days === 'number' || typeof leave.number_of_days === 'string'
      ? formatDays(leave.number_of_days)
      : null

  if (!dateFrom || !dateTo) {
    return null
  }

  return `${formatLeavePeriod(dateFrom, dateTo)}${numberOfDays ? ` — ${numberOfDays}` : ''}`
}

function getOverlapRequestedPeriod(
  warning: LeaveBalancePrecheckResponse,
  formState: LeaveFormState,
) {
  const dateFrom = warning.date_from || formState.start_date
  const dateTo = warning.date_to || formState.end_date
  if (!dateFrom || !dateTo) return 'Non renseignée'
  return formatLeavePeriod(dateFrom, dateTo)
}

function computeWorkingDays(start: string, end: string) {
  if (!start || !end) return 0
  const startDate = new Date(start)
  const endDate = new Date(end)
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return 0
  if (endDate < startDate) return 0

  let days = 0
  const cursor = new Date(startDate)
  while (cursor <= endDate) {
    const weekday = cursor.getDay()
    if (weekday !== 0 && weekday !== 6) days += 1
    cursor.setDate(cursor.getDate() + 1)
  }
  return days
}

function balanceTone(available: number, allocated: number) {
  if (allocated <= 0) return { bar: 'bg-slate-500', text: 'text-slate-300' }
  const pct = (available / allocated) * 100
  if (pct > 50) return { bar: 'bg-emerald-500', text: 'text-emerald-300' }
  if (pct >= 20) return { bar: 'bg-amber-500', text: 'text-amber-300' }
  return { bar: 'bg-rose-500', text: 'text-rose-300' }
}

function LeaveRequestPage() {
  const { hasPermission } = useAuth()
  const canCreateLeaveRequest = hasPermission('leave.request.create')
  const [formState, setFormState] = useState<LeaveFormState>(initialLeaveFormState)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [lastRequest, setLastRequest] = useState<LeaveRequestCreatedResponse | null>(null)
  const [balanceWarning, setBalanceWarning] = useState<LeaveBalancePrecheckResponse | null>(null)
  const [overlapWarning, setOverlapWarning] = useState<LeaveBalancePrecheckResponse | null>(null)
  const [balances, setBalances] = useState<LeaveBalanceItem[]>([])
  const [leaveTypes, setLeaveTypes] = useState<LeaveTypeOption[]>([])
  const [myRequests, setMyRequests] = useState<LeaveRequestHistoryRecord[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function loadLeaveContext() {
      try {
        const [balanceItems, typeItems] = await Promise.all([getMyBalance(), getLeaveTypes()])
        if (!active) return
        setBalances(balanceItems ?? [])
        setLeaveTypes(typeItems ?? [])
      } catch {
        // silencieux : la page reste utilisable sans les soldes
      }
    }
    void loadLeaveContext()
    return () => {
      active = false
    }
  }, [])

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const res = await getMyLeaveRequests()
      setMyRequests(res?.items ?? [])
    } catch {
      // silencieux : la page reste utilisable sans l'historique
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadHistory()
  }, [loadHistory])

  const typeOptions = useMemo(
    () =>
      leaveTypes.length
        ? leaveTypes.map((type) => ({ value: type.code, label: type.label_fr }))
        : leaveTypeOptions,
    [leaveTypes],
  )

  const requestedDays = useMemo(
    () => computeWorkingDays(formState.start_date, formState.end_date),
    [formState.start_date, formState.end_date],
  )

  const selectedBalance = balances.find((balance) => balance.leave_type === formState.leave_type)

  const isInsufficientBalance =
    !!selectedBalance &&
    formState.leave_type !== 'unpaid' &&
    requestedDays > 0 &&
    requestedDays > selectedBalance.available

  async function handleSubmit() {
    setSuccessMessage(null)
    setErrorMessage(null)
    setBalanceWarning(null)
    setOverlapWarning(null)

    if (!canCreateLeaveRequest) {
      setErrorMessage('Votre role ne permet pas de creer une demande de conge.')
      return
    }

    const validationError = validateLeaveForm(formState)
    if (validationError) {
      setErrorMessage(validationError)
      return
    }

    try {
      setIsSubmitting(true)
      const createdRequest = await createStandaloneRequest(formState)
      setLastRequest(createdRequest)
      setSuccessMessage(
        'Demande envoyée avec succès. L’analyse automatique et le circuit manager ont été déclenchés.',
      )
      setFormState(initialLeaveFormState)
      void loadHistory()
    } catch (error) {
      if (
        error instanceof ApiRequestError &&
        error.code === 'INSUFFICIENT_LEAVE_BALANCE' &&
        isLeavePrecheckResponse(error.data)
      ) {
        setBalanceWarning(error.data)
        setOverlapWarning(null)
        setLastRequest(null)
        setSuccessMessage(null)
        return
      }
      if (
        error instanceof ApiRequestError &&
        error.code === 'LEAVE_PERIOD_OVERLAP' &&
        isLeavePrecheckResponse(error.data)
      ) {
        setOverlapWarning(error.data)
        setBalanceWarning(null)
        setLastRequest(null)
        setSuccessMessage(null)
        return
      }
      setErrorMessage(getErrorMessage(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Ressources humaines"
        title="Demande de congé"
        subtitle="Soumettez une demande et suivez son statut."
        statusLabel={lastRequest ? formatLeaveStatus(lastRequest.status) : 'Formulaire prêt'}
        statusTone={lastRequest ? toStatusType(getLeaveStatusTone(lastRequest.status)) : 'info'}
      />

      {balances.length ? (
        <AppCard
          eyebrow="Soldes"
          title="Mes soldes de congés — 2026"
          description="Suivi en temps réel de vos droits restants par type de congé."
        >
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {balances
              .filter((balance) => balance.leave_type !== 'unpaid')
              .map((balance) => {
                const tone = balanceTone(balance.available, balance.allocated)
                const pct =
                  balance.allocated > 0
                    ? Math.max(0, Math.min(100, (balance.available / balance.allocated) * 100))
                    : 0
                return (
                  <div
                    key={balance.leave_type}
                    className="rounded-lg border border-slate-800 bg-slate-950/50 p-4"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-white">
                        {balance.leave_type_label}
                      </span>
                      <span className={`text-sm font-bold ${tone.text}`}>
                        {balance.available}/{balance.allocated} j
                      </span>
                    </div>
                    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-800">
                      <div
                        className={`h-full rounded-full ${tone.bar}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <p className="mt-2 text-xs text-slate-400">
                      {balance.used} jours utilisés · {balance.pending} en attente
                    </p>
                  </div>
                )
              })}
          </div>
        </AppCard>
      ) : null}

      <AppCard eyebrow="Formulaire" title="Nouvelle demande">
          <div className="space-y-4">
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                Type de congé
              </span>
              <select
                value={formState.leave_type}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, leave_type: event.target.value }))
                }
                disabled={!canCreateLeaveRequest || isSubmitting}
                className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20"
              >
                <option value="">Sélectionner un type de congé</option>
                {typeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  Date de début
                </span>
                <input
                  type="date"
                  value={formState.start_date}
                  onChange={(event) =>
                    setFormState((current) => ({ ...current, start_date: event.target.value }))
                  }
                  disabled={!canCreateLeaveRequest || isSubmitting}
                  className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  Date de fin
                </span>
                <input
                  type="date"
                  value={formState.end_date}
                  onChange={(event) =>
                    setFormState((current) => ({ ...current, end_date: event.target.value }))
                  }
                  disabled={!canCreateLeaveRequest || isSubmitting}
                  className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20"
                />
              </label>
            </div>

            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                Motif
              </span>
              <textarea
                rows={4}
                value={formState.reason}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, reason: event.target.value }))
                }
                disabled={!canCreateLeaveRequest || isSubmitting}
                placeholder="Expliquez brièvement la raison de votre demande..."
                className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20"
              />
            </label>

            {successMessage ? (
              <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-200">
                {successMessage}
              </div>
            ) : null}

            {errorMessage ? (
              <ErrorState title="Demande impossible" message={errorMessage} tone="danger" />
            ) : null}

            {!canCreateLeaveRequest ? (
              <ErrorState
                title="Action non autorisee"
                message="Vous pouvez consulter cette page, mais votre role ne permet pas de soumettre une nouvelle demande."
                tone="warning"
              />
            ) : null}

            {balanceWarning ? (
              <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-amber-100">
                      Demande non transmise : solde insuffisant
                    </p>
                    <p className="mt-1 text-sm leading-6 text-amber-50/90">
                      {balanceWarning.ai_explanation || balanceWarning.message || 'La demande depasse le solde disponible.'}
                    </p>
                  </div>
                  <PriorityBadge
                    label={balanceWarning.recommendation_label || 'Refus recommande'}
                    tone="red"
                    size="sm"
                  />
                </div>

                <dl className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border border-amber-400/20 bg-slate-950/40 p-3">
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-amber-200">
                      Solde disponible
                    </dt>
                    <dd className="mt-1 font-semibold text-white">
                      {formatDays(balanceWarning.available_days)}
                    </dd>
                  </div>
                  <div className="rounded-lg border border-amber-400/20 bg-slate-950/40 p-3">
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-amber-200">
                      Jours demandés
                    </dt>
                    <dd className="mt-1 font-semibold text-white">
                      {formatDays(balanceWarning.requested_days)}
                    </dd>
                  </div>
                  <div className="rounded-lg border border-amber-400/20 bg-slate-950/40 p-3">
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-amber-200">
                      Écart
                    </dt>
                    <dd className="mt-1 font-semibold text-white">
                      {formatDays(balanceWarning.balance_gap_days)}
                    </dd>
                  </div>
                </dl>

                <div className="mt-4 rounded-lg border border-amber-400/20 bg-slate-950/40 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-200">
                    Action recommandée
                  </p>
                  <p className="mt-2 text-sm leading-6 text-amber-50">
                    {balanceWarning.employee_guidance ||
                      balanceWarning.manager_guidance ||
                      'Veuillez reduire la periode demandee ou contacter le service RH pour une exception.'}
                  </p>
                </div>
              </div>
            ) : null}

            {overlapWarning ? (
              <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-rose-100">
                      Demande non transmise : période déjà réservée
                    </p>
                    <p className="mt-1 text-sm leading-6 text-rose-50/90">
                      {overlapWarning.ai_explanation ||
                        overlapWarning.message ||
                        'La période demandée chevauche déjà un congé validé.'}
                    </p>
                  </div>
                  <PriorityBadge
                    label={overlapWarning.recommendation_label || 'Modifier la période'}
                    tone="red"
                    size="sm"
                  />
                </div>

                <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg border border-rose-400/20 bg-slate-950/40 p-3">
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-rose-200">
                      Période demandée
                    </dt>
                    <dd className="mt-1 font-semibold text-white">
                      {getOverlapRequestedPeriod(overlapWarning, formState)}
                    </dd>
                  </div>
                  <div className="rounded-lg border border-rose-400/20 bg-slate-950/40 p-3">
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-rose-200">
                      Conflit détecté
                    </dt>
                    <dd className="mt-1 font-semibold text-white">
                      {overlapWarning.conflict_detected === false ? 'Non' : 'Oui'}
                    </dd>
                  </div>
                </dl>

                <div className="mt-4 rounded-lg border border-rose-400/20 bg-slate-950/40 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-rose-200">
                    Période déjà réservée
                  </p>
                  {overlapWarning.overlapping_leaves?.length ? (
                    <ul className="mt-2 space-y-2 text-sm leading-6 text-rose-50">
                      {overlapWarning.overlapping_leaves.map((leave, index) => {
                        const overlapText = getOverlapLeaveText(leave)
                        return overlapText ? <li key={`${overlapText}-${index}`}>{overlapText}</li> : null
                      })}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm leading-6 text-rose-50">
                      Une période déjà réservée a été détectée, mais le détail des dates n’est pas disponible.
                    </p>
                  )}
                </div>

                <div className="mt-4 rounded-lg border border-rose-400/20 bg-slate-950/40 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-rose-200">
                    Action recommandée
                  </p>
                  <p className="mt-2 text-sm leading-6 text-rose-50">
                    {overlapWarning.employee_guidance ||
                      'La période demandée chevauche déjà un congé validé. Veuillez choisir d’autres dates.'}
                  </p>
                </div>
              </div>
            ) : null}

            {isInsufficientBalance && selectedBalance ? (
              <ErrorState
                title="Solde insuffisant"
                message={`⚠️ Vous demandez ${requestedDays} jour(s) mais seulement ${selectedBalance.available} jour(s) sont disponibles pour ${selectedBalance.leave_type_label}.`}
                tone="danger"
              />
            ) : null}

            <div className="flex flex-wrap items-center justify-end gap-3">
              <ActionButton
                label="Réinitialiser"
                variant="secondary"
                onClick={() => {
                  setFormState(initialLeaveFormState)
                  setErrorMessage(null)
                  setSuccessMessage(null)
                  setBalanceWarning(null)
                  setOverlapWarning(null)
                }}
                disabled={isSubmitting || !canCreateLeaveRequest}
              />
              <ActionButton
                label={
                  <span className="inline-flex items-center gap-1.5">
                    <Icon name="send" size={14} />
                    {isSubmitting ? 'Envoi...' : 'Soumettre la demande'}
                  </span>
                }
                onClick={() => void handleSubmit()}
                disabled={isSubmitting || !canCreateLeaveRequest || isInsufficientBalance}
              />
            </div>
          </div>
        </AppCard>

      <AppCard
        eyebrow="Historique"
        title="Mes demandes passées"
        actions={<PriorityBadge label={`${myRequests.length}`} tone="blue" size="sm" />}
      >
        {historyLoading ? (
          <p className="px-1 py-4 text-sm text-slate-400">Chargement de l’historique…</p>
        ) : myRequests.length === 0 ? (
          <p className="px-1 py-4 text-sm text-slate-400">
            Aucune demande pour le moment. Votre première demande apparaîtra ici.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-800 text-xs uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-3 py-2.5">Type</th>
                  <th className="px-3 py-2.5">Période</th>
                  <th className="px-3 py-2.5">Jours</th>
                  <th className="px-3 py-2.5">Statut</th>
                  <th className="px-3 py-2.5">Commentaire manager</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {myRequests.map((req) => {
                  const rejected = req.status.toLowerCase().includes('reject')
                  return (
                    <tr key={req.id} className="text-slate-200">
                      <td className="px-3 py-2.5 font-medium">{req.leave_type}</td>
                      <td className="px-3 py-2.5 text-slate-300">
                        {formatLeavePeriod(req.start_date, req.end_date)}
                      </td>
                      <td className="px-3 py-2.5 text-slate-300">{formatDays(req.requested_days)}</td>
                      <td className="px-3 py-2.5">
                        <PriorityBadge
                          label={formatLeaveStatus(req.status)}
                          tone={getLeaveStatusTone(req.status)}
                          size="sm"
                        />
                      </td>
                      <td className="px-3 py-2.5 text-xs text-slate-400">
                        {rejected && req.manager_comment ? req.manager_comment : '—'}
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

export default LeaveRequestPage
