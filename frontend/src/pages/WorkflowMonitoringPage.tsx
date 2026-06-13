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
import { workflowExecutions as fallbackExecutions } from '../data/workflowMonitoringData'
import {
  getWorkflowExecutionById,
  getWorkflowExecutions,
  retryWorkflowExecution,
  type WorkflowExecutionDetail,
  type WorkflowExecutionRecord,
} from '../services/workflowService'
import { useAuth } from '../auth/useAuth'

type BusinessStatus = 'success' | 'failed' | 'running' | 'queued'

type ProcessRow = {
  id: string
  workflow: string
  process: string
  status: BusinessStatus
  statusLabel: string
  summary: string
  duration: string
  lastExecution: string
  currentStep: string
  related: string
}

const RETRY_REASON = 'Relance manuelle depuis l’espace Automatisations'

function formatDateTime(value: string | null | undefined) {
  if (!value) return 'Non renseigné'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Non renseigné'
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(parsed)
}

function mapStatusLabel(status: BusinessStatus) {
  if (status === 'success') return 'Réussi'
  if (status === 'failed') return 'En erreur'
  if (status === 'queued') return 'En attente'
  return 'En cours'
}

function mapStatusTone(status: BusinessStatus): BadgeTone {
  if (status === 'success') return 'green'
  if (status === 'failed') return 'red'
  if (status === 'queued') return 'orange'
  return 'blue'
}

function mapProcessLabel(process: string, workflowName = '') {
  const lower = `${process} ${workflowName}`.toLowerCase()
  if (lower.includes('crm') && (lower.includes('score') || lower.includes('analys'))) {
    return 'CRM — Analyse et scoring'
  }
  if (lower.includes('crm') && lower.includes('convert')) return 'CRM — Conversion client'
  if (lower.includes('crm') || lower.includes('lead')) return 'CRM — Communication commerciale'
  if (lower.includes('leave') || lower.includes('cong')) return 'Congés — Validation manager'
  if (lower.includes('odoo') || lower.includes('rh')) return 'Odoo — Synchronisation RH'
  if (lower.includes('gmail') || lower.includes('email') || lower.includes('mail')) {
    return 'Gmail — Envoi email approuvé'
  }
  if (lower.includes('agent')) return 'Agents IA — Exécution automatique'
  return process || 'Processus métier'
}

function buildSummary(row: WorkflowExecutionRecord): string {
  if (row.status === 'success') return 'Automatisation terminée avec succès.'
  if (row.status === 'failed') return 'Une étape métier a échoué et doit être vérifiée.'
  if (row.status === 'queued') return 'En attente de traitement automatique.'
  return 'Automatisation en cours d’exécution.'
}

function buildCurrentStep(row: WorkflowExecutionRecord): string {
  const process = `${row.process} ${row.workflow_name}`.toLowerCase()
  if (row.status === 'failed') return 'Étape bloquée'
  if (row.status === 'queued') return 'En file d’attente'
  if (row.status === 'running') return 'Exécution en cours'
  if (process.includes('leave') || process.includes('cong')) return 'Validation manager'
  if (process.includes('crm')) return 'Communication CRM'
  if (process.includes('odoo') || process.includes('rh')) return 'Synchronisation RH'
  if (process.includes('gmail') || process.includes('email')) return 'Envoi email approuvé'
  return 'Étape métier récente'
}

function getRecommendedAction(row: ProcessRow): string {
  if (row.status === 'failed') return 'Relancer l’automatisation après vérification.'
  if (row.status === 'queued' || row.status === 'running') return 'Surveiller la fin du traitement.'
  return 'Aucune action requise.'
}

function mapExecutionToRow(execution: WorkflowExecutionRecord): ProcessRow {
  return {
    id: execution.id,
    workflow: execution.workflow_name,
    process: mapProcessLabel(execution.process, execution.workflow_name),
    status: execution.status,
    statusLabel: mapStatusLabel(execution.status),
    summary: buildSummary(execution),
    duration: execution.duration,
    lastExecution: formatDateTime(execution.started_at),
    currentStep: buildCurrentStep(execution),
    related: execution.related_object,
  }
}

function mapFallbackExecutionToRow(
  row: (typeof fallbackExecutions)[number],
): ProcessRow {
  const status: BusinessStatus =
    row.status === 'danger' ? 'failed' : row.status === 'warning' ? 'queued' : 'success'
  return {
    id: row.id,
    workflow: row.workflow,
    process: mapProcessLabel(row.process, row.workflow),
    status,
    statusLabel: mapStatusLabel(status),
    summary:
      status === 'failed'
        ? 'Exemple hors ligne : relance manuelle recommandée.'
        : status === 'queued'
          ? 'Exemple hors ligne : en attente de décision métier.'
          : 'Exemple hors ligne : exécution terminée.',
    duration: row.duration,
    lastExecution: row.lastExecution,
    currentStep: buildCurrentStep({
      id: row.id,
      workflow_name: row.workflow,
      process: row.process,
      status,
      related_object: row.businessObjectId,
      started_at: new Date().toISOString(),
      finished_at: null,
      duration: row.duration,
      triggered_by: row.triggerSource,
      agent: row.automationAgent,
    }),
    related: row.businessObjectId,
  }
}

function WorkflowMonitoringPage() {
  const { hasPermission } = useAuth()
  const canRetryWorkflow = hasPermission('workflow.executions.retry')
  const [rows, setRows] = useState<ProcessRow[]>([])
  const [selectedDetail, setSelectedDetail] = useState<WorkflowExecutionDetail | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDetailLoading, setIsDetailLoading] = useState(false)
  const [isUsingFallback, setIsUsingFallback] = useState(false)
  const [retryMessage, setRetryMessage] = useState('')
  const [retryError, setRetryError] = useState('')

  useEffect(() => {
    let isMounted = true
    async function loadExecutions() {
      setIsLoading(true)
      try {
        const response = await getWorkflowExecutions()
        if (!isMounted) return
        setRows(response.items.map(mapExecutionToRow))
        setIsUsingFallback(false)
        setSelectedId(response.items[0]?.id ?? null)
      } catch {
        if (!isMounted) return
        const mapped = fallbackExecutions.map(mapFallbackExecutionToRow)
        setRows(mapped)
        setIsUsingFallback(true)
        setSelectedId(mapped[0]?.id ?? null)
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }
    void loadExecutions()
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
        const detail = await getWorkflowExecutionById(selectedId)
        if (isMounted) setSelectedDetail(detail)
      } catch {
        if (isMounted) setSelectedDetail(null)
      } finally {
        if (isMounted) setIsDetailLoading(false)
      }
    }
    void loadDetail()
    return () => {
      isMounted = false
      setSelectedDetail(null)
    }
  }, [selectedId, isUsingFallback])

  const summary = useMemo(
    () => ({
      success: rows.filter((row) => row.status === 'success').length,
      pending: rows.filter((row) => row.status === 'queued' || row.status === 'running').length,
      failed: rows.filter((row) => row.status === 'failed').length,
      toCheck: rows.filter((row) => row.status === 'failed' || row.status === 'queued').length,
    }),
    [rows],
  )

  async function handleRetry(executionId: string) {
    setRetryError('')
    setRetryMessage('')
    if (!canRetryWorkflow) {
      setRetryError('Votre role ne permet pas de relancer une execution.')
      return
    }
    if (isUsingFallback) {
      setRetryError('La relance est désactivée en mode hors ligne.')
      return
    }
    try {
      const response = await retryWorkflowExecution(executionId, RETRY_REASON)
      setRetryMessage(
        response.message || 'L’automatisation a été relancée. Suivez son statut depuis cette page.',
      )
    } catch {
      setRetryError('La relance n’a pas pu être envoyée. Vérifiez le service d’automatisation.')
    }
  }

  const selectedRow = rows.find((row) => row.id === selectedId) ?? rows[0]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Automatisations"
        title="Supervision des processus métier"
        subtitle="Surveillez les automatisations CRM, congés, emails et synchronisation RH. Les détails techniques restent cachés par défaut."
        statusLabel={
          summary.failed > 0
            ? `${summary.failed} incident${summary.failed === 1 ? '' : 's'}`
            : 'Opérations saines'
        }
        statusTone={summary.failed > 0 ? 'danger' : 'success'}
      />

      {isLoading ? <LoadingState message="Chargement des automatisations..." /> : null}
      {isUsingFallback ? (
        <ErrorState
          tone="warning"
          title="Données en direct indisponibles"
          message="Affichage d’exemples hors ligne. Les relances sont désactivées."
        />
      ) : null}
      {retryMessage ? (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-200">
          {retryMessage}
        </div>
      ) : null}
      {retryError ? (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm font-medium text-rose-200">
          {retryError}
        </div>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Réussies"
          value={String(summary.success)}
          tone="emerald"
          icon="check"
          helper="Sur la période récente"
        />
        <KpiCard
          label="En attente"
          value={String(summary.pending)}
          tone="amber"
          icon="clock"
          helper="En cours ou en file"
        />
        <KpiCard
          label="En erreur"
          value={String(summary.failed)}
          tone="rose"
          icon="alert"
          helper={summary.failed > 0 ? 'Relance nécessaire' : 'Aucune erreur'}
        />
        <KpiCard
          label="À vérifier"
          value={String(summary.toCheck)}
          tone="sky"
          icon="eye"
          helper="Supervision humaine"
        />
      </section>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <AppCard
          eyebrow="Processus métier"
          title="Automatisations en cours"
          description="Cliquez sur un processus pour afficher son détail sur la droite."
        >
          {rows.length === 0 ? (
            <EmptyState
              icon="workflow"
              title="Aucune automatisation récente"
              description="Les automatisations apparaîtront ici dès leur exécution."
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {rows.map((row) => {
                const isActive = row.id === selectedId
                return (
                  <article
                    key={row.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedId(row.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') setSelectedId(row.id)
                    }}
                    className={`cursor-pointer rounded-xl border px-4 py-4 transition ${
                      isActive
                        ? 'border-emerald-500/40 bg-emerald-500/10'
                        : 'border-slate-800 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-900/70'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-bold text-white">{row.process}</p>
                        <p className="truncate text-xs text-slate-400">{row.currentStep}</p>
                      </div>
                      <PriorityBadge
                        label={row.statusLabel}
                        tone={mapStatusTone(row.status)}
                        withDot
                      />
                    </div>
                    <dl className="mt-3 grid gap-2 text-xs text-slate-300">
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-500">Étape actuelle</dt>
                        <dd className="font-semibold text-slate-200">{row.currentStep}</dd>
                      </div>
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-500">Dernière exécution</dt>
                        <dd className="text-slate-200">{row.lastExecution}</dd>
                      </div>
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-500">Action recommandée</dt>
                        <dd className="max-w-[12rem] text-right text-slate-200">
                          {getRecommendedAction(row)}
                        </dd>
                      </div>
                    </dl>
                    <p className="mt-3 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs leading-5 text-slate-400">
                      {row.summary}
                    </p>
                    {row.status === 'failed' && canRetryWorkflow ? (
                      <div className="mt-3">
                        <ActionButton
                          label={
                            <span className="inline-flex items-center gap-1.5">
                              <Icon name="reload" size={14} />
                              Relancer
                            </span>
                          }
                          onClick={() => void handleRetry(row.id)}
                          disabled={isUsingFallback || !canRetryWorkflow}
                          size="sm"
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
          title={selectedRow?.process ?? 'Aucune automatisation sélectionnée'}
          description={selectedRow?.summary ?? 'Sélectionnez une automatisation à gauche pour voir les détails.'}
          actions={
            selectedRow ? (
              <StatusBadge
                label={selectedRow.statusLabel}
                status={
                  selectedRow.status === 'success'
                    ? 'success'
                    : selectedRow.status === 'failed'
                      ? 'danger'
                      : selectedRow.status === 'queued'
                        ? 'warning'
                        : 'info'
                }
              />
            ) : null
          }
        >
          {selectedRow ? (
            <div className="space-y-4">
              <dl className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                  <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    Processus
                  </dt>
                  <dd className="mt-1 font-semibold text-white">{selectedRow.process}</dd>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 sm:col-span-2">
                  <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    Étape actuelle
                  </dt>
                  <dd className="mt-1 font-semibold text-white">{selectedRow.currentStep}</dd>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 sm:col-span-2">
                  <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    Action recommandée
                  </dt>
                  <dd className="mt-1 font-semibold text-white">
                    {getRecommendedAction(selectedRow)}
                  </dd>
                </div>
              </dl>

              {selectedRow.status === 'failed' && canRetryWorkflow ? (
                <ActionButton
                  label={
                    <span className="inline-flex items-center gap-1.5">
                      <Icon name="reload" size={14} />
                      Relancer l’automatisation
                    </span>
                  }
                  onClick={() => void handleRetry(selectedRow.id)}
                  disabled={isUsingFallback || !canRetryWorkflow}
                />
              ) : null}

              {isDetailLoading ? (
                <LoadingState message="Chargement des détails techniques..." />
              ) : null}

              <TechnicalDetailsPanel title="Détails techniques">
                <dl className="grid gap-2 sm:grid-cols-2">
                  <div>
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      Référence d’exécution
                    </dt>
                    <dd className="break-words text-sm text-slate-300">{selectedRow.id}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      Workflow
                    </dt>
                    <dd className="break-words text-sm text-slate-300">{selectedRow.workflow}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      Durée
                    </dt>
                    <dd className="break-words text-sm text-slate-300">{selectedRow.duration}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      Objet métier
                    </dt>
                    <dd className="break-words text-sm text-slate-300">{selectedRow.related}</dd>
                  </div>
                  {selectedDetail ? (
                    <>
                      <div className="sm:col-span-2">
                        <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                          Entrée métier
                        </dt>
                        <dd className="text-sm text-slate-300">{selectedDetail.input_summary}</dd>
                      </div>
                      <div className="sm:col-span-2">
                        <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                          Sortie métier
                        </dt>
                        <dd className="text-sm text-slate-300">{selectedDetail.output_summary}</dd>
                      </div>
                      {selectedDetail.error_message ? (
                        <div className="sm:col-span-2">
                          <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                            Message d’erreur
                          </dt>
                          <dd className="text-sm text-rose-200">
                            {selectedDetail.error_message}
                          </dd>
                        </div>
                      ) : null}
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

export default WorkflowMonitoringPage
