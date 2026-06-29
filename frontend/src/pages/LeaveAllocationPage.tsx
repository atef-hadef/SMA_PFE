import { useEffect, useMemo, useState } from 'react'
import {
  AppCard,
  ErrorState,
  Icon,
  LoadingState,
  PageHeader,
  PriorityBadge,
  type BadgeTone,
} from '../components/common'
import {
  getAllocations,
  getAnalytics,
  upsertAllocation,
  type LeaveAllocationGroup,
  type LeaveAnalyticsResponse,
} from '../services/leaveService'

const ALLOCATION_YEAR = 2026

const TYPE_COLUMNS = [
  { code: 'vacation', label: 'Congés payés' },
  { code: 'sick', label: 'Maladie' },
  { code: 'personal', label: 'Personnel' },
  { code: 'rtt', label: 'RTT' },
] as const

type CellMap = Record<string, number>

function cellKey(employeeId: string, code: string) {
  return `${employeeId}:${code}`
}

function buildMatrix(groups: LeaveAllocationGroup[]): CellMap {
  const map: CellMap = {}
  for (const group of groups) {
    for (const column of TYPE_COLUMNS) {
      const detail = group.allocations.find((item) => item.leave_type === column.code)
      map[cellKey(group.employee_id, column.code)] = detail ? detail.allocated_days : 0
    }
  }
  return map
}

function riskTone(level: string): BadgeTone {
  if (level === 'high') return 'red'
  if (level === 'medium') return 'orange'
  return 'green'
}

function formatHours(hours: number) {
  if (hours >= 48) {
    const days = Math.floor(hours / 24)
    return `${days} jour(s)`
  }
  return `${Math.round(hours)} h`
}

function LeaveAllocationPage() {
  const [groups, setGroups] = useState<LeaveAllocationGroup[]>([])
  const [analytics, setAnalytics] = useState<LeaveAnalyticsResponse | null>(null)
  const [values, setValues] = useState<CellMap>({})
  const [original, setOriginal] = useState<CellMap>({})
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  async function loadData() {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const [allocationGroups, analyticsData] = await Promise.all([
        getAllocations(ALLOCATION_YEAR),
        getAnalytics(),
      ])
      const safeGroups = allocationGroups ?? []
      const matrix = buildMatrix(safeGroups)
      setGroups(safeGroups)
      setValues(matrix)
      setOriginal(matrix)
      setSavedKeys(new Set())
      setAnalytics(analyticsData ?? null)
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : 'Le chargement des allocations a échoué.',
      )
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  const dirtyKeys = useMemo(
    () => Object.keys(values).filter((key) => values[key] !== original[key]),
    [values, original],
  )

  function handleCellChange(employeeId: string, code: string, raw: string) {
    const parsed = Number(raw)
    const safe = Number.isFinite(parsed) ? Math.min(365, Math.max(0, parsed)) : 0
    setValues((current) => ({ ...current, [cellKey(employeeId, code)]: safe }))
    setSuccessMessage(null)
  }

  async function handleSave() {
    if (!dirtyKeys.length) return
    setIsSaving(true)
    setErrorMessage(null)
    setSuccessMessage(null)
    const justSaved = new Set<string>()
    try {
      for (const key of dirtyKeys) {
        const [employeeId, code] = key.split(':')
        await upsertAllocation({
          employee_id: employeeId,
          year: ALLOCATION_YEAR,
          leave_type: code,
          allocated_days: values[key],
        })
        justSaved.add(key)
      }
      setOriginal((current) => {
        const next = { ...current }
        for (const key of justSaved) next[key] = values[key]
        return next
      })
      setSavedKeys(justSaved)
      setSuccessMessage(`${justSaved.size} allocation(s) sauvegardée(s).`)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'La sauvegarde a échoué.')
    } finally {
      setIsSaving(false)
    }
  }

  function cellClasses(key: string) {
    if (values[key] !== original[key]) {
      return 'border-amber-500/60 bg-amber-500/10 text-amber-100'
    }
    if (savedKeys.has(key)) {
      return 'border-emerald-500/60 bg-emerald-500/10 text-emerald-100'
    }
    return 'border-slate-800 bg-slate-950/60 text-slate-100'
  }

  const stats = [
    { label: 'Total 2026', value: analytics?.total_this_year ?? 0, tone: 'text-white' },
    { label: 'Approuvées', value: analytics?.approved ?? 0, tone: 'text-emerald-300' },
    { label: 'Refusées', value: analytics?.rejected ?? 0, tone: 'text-rose-300' },
    { label: 'En attente', value: analytics?.pending ?? 0, tone: 'text-amber-300' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Ressources humaines"
        title="Allocation des congés"
        subtitle="Droits annuels de congés par employé."
        statusLabel={`Année ${ALLOCATION_YEAR}`}
        statusTone="info"
      />

      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
        <div className="flex items-center gap-2">
          <Icon name="users" size={16} className="text-slate-400" />
          <span className="text-sm text-slate-300">
            <span className="font-bold text-white">{groups.length}</span> employés
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${dirtyKeys.length ? 'bg-amber-400' : 'bg-slate-600'}`} />
          <span className="text-sm text-slate-300">
            <span className={`font-bold ${dirtyKeys.length ? 'text-amber-300' : 'text-white'}`}>
              {dirtyKeys.length}
            </span>{' '}
            modif. non sauvegardées
          </span>
        </div>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={isSaving || dirtyKeys.length === 0}
          className="ml-auto inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow-md shadow-emerald-500/20 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
        >
          {isSaving ? 'Sauvegarde…' : `💾 Sauvegarder${dirtyKeys.length ? ` (${dirtyKeys.length})` : ''}`}
        </button>
      </div>

      {errorMessage ? (
        <ErrorState title="Erreur" message={errorMessage} tone="danger" />
      ) : null}

      {successMessage ? (
        <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-200">
          {successMessage}
        </div>
      ) : null}

      {isLoading ? (
        <LoadingState label="Chargement des allocations..." />
      ) : (
        <>
          <AppCard
            title={`Allocations ${ALLOCATION_YEAR}`}
            actions={
              <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-400">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded border border-slate-700 bg-slate-950/60" /> Inchangé
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded border border-amber-500/60 bg-amber-500/10" /> Modifié
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded border border-emerald-500/60 bg-emerald-500/10" /> Sauvegardé
                </span>
              </div>
            }
          >
            {groups.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-800 bg-slate-950/40 p-6 text-center text-sm text-slate-400">
                Aucune allocation enregistrée pour {ALLOCATION_YEAR}.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      <th className="px-3 py-1.5">Employé</th>
                      {TYPE_COLUMNS.map((column) => (
                        <th key={column.code} className="px-2 py-1.5 text-center">
                          {column.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {groups.map((group) => (
                      <tr key={group.employee_id} className="border-t border-slate-800">
                        <td className="px-3 py-2 font-medium text-white">
                          {group.employee_name}
                        </td>
                        {TYPE_COLUMNS.map((column) => {
                          const key = cellKey(group.employee_id, column.code)
                          return (
                            <td key={column.code} className="px-2 py-1.5 text-center">
                              <input
                                type="number"
                                min={0}
                                max={365}
                                value={values[key] ?? 0}
                                onChange={(event) =>
                                  handleCellChange(
                                    group.employee_id,
                                    column.code,
                                    event.target.value,
                                  )
                                }
                                className={`w-16 rounded-lg border px-2 py-1 text-center outline-none transition focus:ring-2 focus:ring-emerald-500/20 ${cellClasses(key)}`}
                              />
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </AppCard>

          <AppCard title="Analytics congés">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {stats.map((stat) => (
                <div
                  key={stat.label}
                  className="rounded-lg border border-slate-800 bg-slate-950/50 p-3"
                >
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    {stat.label}
                  </p>
                  <p className={`mt-1 text-xl font-bold ${stat.tone}`}>{stat.value}</p>
                </div>
              ))}
            </div>

            <div className="mt-5 grid gap-5 lg:grid-cols-2">
              <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
                <p className="text-sm font-semibold text-white">⚠️ Alertes burnout</p>
                {analytics?.burnout_alerts?.length ? (
                  <ul className="mt-3 space-y-3">
                    {analytics.burnout_alerts.map((alert) => (
                      <li
                        key={alert.employee_id}
                        className="rounded-lg border border-slate-800 bg-slate-950/60 p-3"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-medium text-white">
                            {alert.employee_name}
                          </span>
                          <PriorityBadge
                            label={alert.risk_level}
                            tone={riskTone(alert.risk_level)}
                            size="sm"
                          />
                        </div>
                        {alert.days_since_last_leave !== null ? (
                          <p className="mt-1 text-xs text-slate-400">
                            {alert.days_since_last_leave} jours sans congé
                          </p>
                        ) : null}
                        {alert.signals.length ? (
                          <ul className="mt-2 space-y-1 text-xs text-slate-300">
                            {alert.signals.map((signal, index) => (
                              <li key={`${alert.employee_id}-${index}`}>• {signal}</li>
                            ))}
                          </ul>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 text-sm text-slate-400">
                    Aucun signal de burnout détecté.
                  </p>
                )}
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
                <p className="text-sm font-semibold text-white">⏰ En attente &gt; 48h</p>
                {analytics?.pending_over_48h?.length ? (
                  <ul className="mt-3 space-y-2">
                    {analytics.pending_over_48h.map((item) => (
                      <li
                        key={item.request_id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-sm"
                      >
                        <span className="font-medium text-white">{item.employee_name}</span>
                        <span className="text-xs text-amber-300">
                          {formatHours(item.hours_pending)} en attente
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 text-sm text-slate-400">
                    Aucune demande en attente depuis plus de 48h.
                  </p>
                )}
              </div>
            </div>
          </AppCard>
        </>
      )}
    </div>
  )
}

export default LeaveAllocationPage
