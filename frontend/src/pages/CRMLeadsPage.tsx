import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ActionButton,
  AppCard,
  ErrorState,
  Icon,
  KpiCard,
  LoadingState,
  PageHeader,
  PriorityBadge,
  StatusBadge,
  type BadgeTone,
} from '../components/common'
import { leadTableRows } from '../data/crmLeadsData'
import { getCrmLeads } from '../services/crmService'
import { computeCrmMetrics } from '../utils/crmMetrics'
import type { CrmLeadRecord } from '../services/crmService'
import {
  formatCrmCurrency,
  formatCrmDate,
  getCrmBusinessStateLabel,
  getCrmNextActionLabel,
  getCrmOwnerLabel,
  getCrmPriorityLabel,
  getCrmUiState,
  isCrmHotLead,
  isCrmLeadNeedingAction,
} from '../utils/crmDisplay'

type FilterKey =
  | 'all'
  | 'leads'
  | 'prospects'
  | 'conversion_pending'
  | 'customers'
  | 'vip'
  | 'hot'
  | 'drafts'
  | 'needs_action'
type PriorityFilter = 'all' | 'high' | 'medium' | 'low'
type SortColumn = 'status' | 'score' | 'lastContact'
type SortDirection = 'asc' | 'desc'

type LeadRow = {
  id: string
  name: string
  company: string
  email: string
  status: string
  priority: string
  score: number
  estimatedValue: string
  productService: string
  owner: string
  lastContact: string
  lastContactIso: string
  nextAction: string
  communicationStatus: string
  needsHumanAction: boolean
  isHot: boolean
  isCustomer: boolean
  isVip: boolean
  isDraftWaiting: boolean
  isConversionPending: boolean
  priorityLower: string
}

const FILTER_OPTIONS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'Tous' },
  { key: 'leads', label: 'Leads' },
  { key: 'prospects', label: 'Prospects' },
  { key: 'conversion_pending', label: 'Conversion en cours' },
  { key: 'customers', label: 'Clients' },
  { key: 'vip', label: 'VIP / Fidèles' },
  { key: 'hot', label: 'Leads chauds' },
  { key: 'drafts', label: 'Brouillons à valider' },
  { key: 'needs_action', label: 'Action requise' },
]

const PRIORITY_OPTIONS: { key: PriorityFilter; label: string }[] = [
  { key: 'all', label: 'Toutes priorités' },
  { key: 'high', label: 'Élevée' },
  { key: 'medium', label: 'Moyenne' },
  { key: 'low', label: 'Faible' },
]

function formatPersonName(value?: string | null) {
  if (!value) return 'Non renseigné'
  const trimmed = value.trim()
  if (!trimmed) return 'Non renseigné'
  return trimmed
    .split(/\s+/)
    .map((word) =>
      word
        .split('-')
        .map((part) =>
          part.charAt(0).toUpperCase() + part.slice(1).toLowerCase(),
        )
        .join('-'),
    )
    .join(' ')
}

function getStatusTone(status: string): BadgeTone {
  const lower = status.toLowerCase()
  if (lower.includes('vip') || lower.includes('fid')) return 'orange'
  if (lower.includes('client')) return 'green'
  if (lower === 'prospect') return 'purple'
  if (lower === 'lead') return 'blue'
  return 'slate'
}

function getPriorityTone(priority: string): BadgeTone {
  const lower = priority.toLowerCase()
  if (lower.includes('élev') || lower.includes('urg') || lower.includes('high')) return 'red'
  if (lower.includes('moy') || lower.includes('medium')) return 'orange'
  return 'blue'
}

function getPriorityLevel(priority: string): PriorityFilter {
  const lower = priority.toLowerCase()
  if (lower.includes('élev') || lower.includes('urg') || lower.includes('high')) return 'high'
  if (lower.includes('moy') || lower.includes('medium')) return 'medium'
  if (lower.includes('faibl') || lower.includes('low') || lower.includes('cold')) return 'low'
  return 'medium'
}

function getScoreTone(score: number): BadgeTone {
  if (Number.isNaN(score)) return 'slate'
  if (score >= 85) return 'green'
  if (score >= 60) return 'orange'
  return 'slate'
}

function mapLeadToRow(lead: CrmLeadRecord): LeadRow {
  const uiState = getCrmUiState(lead)
  const statusLabel = getCrmBusinessStateLabel(lead)
  const priorityLabel = getCrmPriorityLabel(lead.priority, lead.status)
  const lowerStatus = statusLabel.toLowerCase()

  return {
    id: lead.id,
    name: formatPersonName(lead.name),
    company: lead.company || 'Société non renseignée',
    email: lead.email,
    status: statusLabel,
    priority: priorityLabel,
    priorityLower: priorityLabel.toLowerCase(),
    score: Number(lead.score) || 0,
    estimatedValue: formatCrmCurrency(lead.estimated_value),
    productService: lead.product_service || 'Non renseigné',
    owner: getCrmOwnerLabel(lead.assigned_to),
    lastContact: formatCrmDate(lead.last_contact_at || lead.created_at),
    lastContactIso: lead.last_contact_at || lead.created_at || '',
    nextAction: getCrmNextActionLabel(lead),
    communicationStatus: uiState.badgeLabel,
    needsHumanAction: isCrmLeadNeedingAction(lead),
    isHot: isCrmHotLead(lead),
    isCustomer: lowerStatus.includes('client'),
    isVip: lowerStatus.includes('vip') || lowerStatus.includes('fid'),
    isDraftWaiting:
      uiState.dashboardBucket === 'communication_to_review' ||
      uiState.dashboardBucket === 'welcome_to_review' ||
      uiState.dashboardBucket === 'communication_awaiting_decision',
    isConversionPending:
      Boolean(lead.crm_display_state?.conversion_pending) ||
      uiState.stateKey === 'conversion_pending',
  }
}

function mapFallbackRow(lead: (typeof leadTableRows)[number]): LeadRow {
  const fallbackLead = {
    status: lead.status,
    customer_status: lead.customerStatus,
    priority: lead.priority,
    next_action: lead.nextAction,
  }
  const statusLabel = getCrmBusinessStateLabel(fallbackLead)
  const priorityLabel = getCrmPriorityLabel(lead.priority, lead.status)
  return {
    id: lead.id,
    name: formatPersonName(lead.lead),
    company: lead.company,
    email: 'demo@flowpilot.ai',
    status: statusLabel,
    priority: priorityLabel,
    priorityLower: priorityLabel.toLowerCase(),
    score: Number(lead.score) || 0,
    estimatedValue: formatCrmCurrency(lead.estimatedValue),
    productService: 'Non renseigné',
    owner: getCrmOwnerLabel(lead.owner),
    lastContact: 'Exemple hors ligne',
    lastContactIso: '',
    nextAction: getCrmNextActionLabel(fallbackLead),
    communicationStatus: getCrmUiState(fallbackLead).badgeLabel,
    needsHumanAction: true,
    isHot: isCrmHotLead(fallbackLead),
    isCustomer: statusLabel.toLowerCase().includes('client'),
    isVip: statusLabel.toLowerCase().includes('vip'),
    isDraftWaiting: false,
    isConversionPending: false,
  }
}

function CRMLeadsPage() {
  const navigate = useNavigate()
  const [rows, setRows] = useState<LeadRow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUsingFallback, setIsUsingFallback] = useState(false)
  const [rawLeads, setRawLeads] = useState<CrmLeadRecord[]>([])
  const [filter, setFilter] = useState<FilterKey>('all')
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all')
  const [search, setSearch] = useState('')
  const [ownerFilter, setOwnerFilter] = useState<string>('all')
  // Tri-state column sort: same column cycles asc -> desc -> reset.
  // Clicking a new column always starts at asc.
  const [sortColumn, setSortColumn] = useState<SortColumn | null>(null)
  const [sortDirection, setSortDirection] = useState<SortDirection | null>(null)

  function handleSort(column: SortColumn) {
    if (sortColumn !== column) {
      setSortColumn(column)
      setSortDirection('asc')
      return
    }
    if (sortDirection === 'asc') {
      setSortDirection('desc')
      return
    }
    // Third click on the same column: reset to natural order.
    setSortColumn(null)
    setSortDirection(null)
  }

  useEffect(() => {
    let isMounted = true

    async function loadLeads() {
      setIsLoading(true)
      try {
        const response = await getCrmLeads()
        if (!isMounted) return
        setRows(response.items.map(mapLeadToRow))
        setRawLeads(response.items)
        setIsUsingFallback(false)
      } catch {
        if (!isMounted) return
        setRows([])
        setRawLeads([])
        setIsUsingFallback(true)
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    void loadLeads()
    return () => {
      isMounted = false
    }
  }, [])

  const displayedRows = isUsingFallback ? leadTableRows.map(mapFallbackRow) : rows

  const ownerOptions = useMemo(() => {
    const owners = new Set<string>()
    displayedRows.forEach((row) => owners.add(row.owner))
    return ['all', ...Array.from(owners).sort()]
  }, [displayedRows])

  const filteredRows = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()
    return displayedRows.filter((row) => {
      if (filter === 'leads' && !row.status.toLowerCase().includes('lead')) return false
      if (filter === 'prospects' && !row.status.toLowerCase().includes('prospect')) return false
      if (filter === 'conversion_pending' && !row.isConversionPending) return false
      if (filter === 'customers' && !row.isCustomer) return false
      if (filter === 'vip' && !row.isVip) return false
      if (filter === 'hot' && !row.isHot) return false
      if (filter === 'drafts' && !row.isDraftWaiting) return false
      if (filter === 'needs_action' && !row.needsHumanAction) return false

      if (priorityFilter !== 'all' && getPriorityLevel(row.priority) !== priorityFilter) return false
      if (ownerFilter !== 'all' && row.owner !== ownerFilter) return false

      if (!normalizedSearch) return true
      return [
        row.name,
        row.company,
        row.email,
        row.status,
        row.productService,
        row.owner,
        row.nextAction,
      ]
        .join(' ')
        .toLowerCase()
        .includes(normalizedSearch)
    })
  }, [displayedRows, filter, priorityFilter, ownerFilter, search])

  const sortedRows = useMemo(() => {
    if (!sortColumn || !sortDirection) return filteredRows
    // Copy to avoid mutating the memoized filteredRows array.
    const rows = [...filteredRows]
    const factor = sortDirection === 'asc' ? 1 : -1

    rows.sort((a, b) => {
      if (sortColumn === 'score') {
        return (a.score - b.score) * factor
      }
      if (sortColumn === 'status') {
        return a.status.localeCompare(b.status, 'fr', { sensitivity: 'base' }) * factor
      }
      // lastContact: missing values bubble to the END regardless of direction,
      // so a sort never surfaces "Exemple hors ligne" or unknowns at the top.
      const aTime = a.lastContactIso ? new Date(a.lastContactIso).getTime() : NaN
      const bTime = b.lastContactIso ? new Date(b.lastContactIso).getTime() : NaN
      const aMissing = Number.isNaN(aTime)
      const bMissing = Number.isNaN(bTime)
      if (aMissing && bMissing) return 0
      if (aMissing) return 1
      if (bMissing) return -1
      return (aTime - bTime) * factor
    })
    return rows
  }, [filteredRows, sortColumn, sortDirection])

  const totals = useMemo(() => {
    if (!isUsingFallback) {
      const m = computeCrmMetrics(rawLeads)
      return {
        prospects: m.prospects,
        customers: m.customers,
        hot: m.hotLeads,
        drafts: m.draftsToReview,
      }
    }
    return {
      prospects: displayedRows.filter((row) => row.status.toLowerCase().includes('prospect')).length,
      customers: displayedRows.filter((row) => row.isCustomer).length,
      hot: displayedRows.filter((row) => row.isHot).length,
      drafts: displayedRows.filter((row) => row.isDraftWaiting).length,
    }
  }, [displayedRows, isUsingFallback, rawLeads])

  const showProductServiceColumn = useMemo(() => {
    if (filteredRows.length === 0) return true
    const usefulValues = filteredRows.filter(
      (row) => row.productService && row.productService !== 'Non renseigné',
    ).length
    return usefulValues / filteredRows.length >= 0.35
  }, [filteredRows])

  function openLeadDetails(id: string) {
    navigate(`/crm-lead-details?leadId=${encodeURIComponent(id)}`)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="CRM intelligent"
        title="Pipeline commercial piloté par l’IA"
        subtitle="Qualification automatique, scoring IA, rédaction de communications et supervision humaine du cycle lead → client."
        statusLabel={isUsingFallback ? 'Mode hors ligne' : `${displayedRows.length} contacts`}
        statusTone={isUsingFallback ? 'warning' : 'success'}
      />

      {isLoading ? <LoadingState message="Chargement des leads CRM..." /> : null}
      {isUsingFallback ? (
        <ErrorState
          tone="warning"
          title="Données CRM en direct indisponibles"
          message="Affichage des leads d’exemple hors ligne. Les actions commerciales sont désactivées."
        />
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Prospects"
          value={String(totals.prospects)}
          tone="violet"
          icon="crm"
          helper="Communication engagée"
        />
        <KpiCard
          label="Clients"
          value={String(totals.customers)}
          tone="emerald"
          icon="client"
          helper="Conversion confirmée"
        />
        <KpiCard
          label="Leads chauds"
          value={String(totals.hot)}
          tone="rose"
          icon="spark"
          helper="Réponse rapide attendue"
        />
        <KpiCard
          label="Brouillons à valider"
          value={String(totals.drafts)}
          tone="sky"
          icon="file"
          helper="Supervision humaine"
        />
      </section>

      <AppCard
        eyebrow="Filtres"
        title="Recherche et segmentation"
        description="Combinez recherche, statut, priorité et responsable pour affiner le pipeline."
      >
        <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <label className="relative block">
            <span className="sr-only">Rechercher</span>
            <Icon
              name="search"
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
            />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Rechercher par nom, société, email..."
              className="w-full rounded-lg border border-slate-800 bg-slate-950/80 py-2.5 pl-10 pr-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20"
            />
          </label>
          <label className="block">
            <span className="sr-only">Priorité</span>
            <select
              value={priorityFilter}
              onChange={(event) => setPriorityFilter(event.target.value as PriorityFilter)}
              className="w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20"
            >
              {PRIORITY_OPTIONS.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="sr-only">Responsable</span>
            <select
              value={ownerFilter}
              onChange={(event) => setOwnerFilter(event.target.value)}
              className="w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20"
            >
              {ownerOptions.map((owner) => (
                <option key={owner} value={owner}>
                  {owner === 'all' ? 'Tous les responsables' : owner}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {FILTER_OPTIONS.map((option) => {
            const isActive = filter === option.key
            return (
              <button
                key={option.key}
                type="button"
                onClick={() => setFilter(option.key)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                  isActive
                    ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200'
                    : 'border-slate-800 bg-slate-950/60 text-slate-300 hover:border-slate-700 hover:bg-slate-800/60 hover:text-white'
                }`}
              >
                {option.label}
              </button>
            )
          })}
        </div>
      </AppCard>

      <AppCard
        eyebrow="Pipeline"
        title="Liste des contacts CRM"
        description="Cliquez sur une ligne pour ouvrir la fiche client complète."
        actions={
          <StatusBadge
            label={`${filteredRows.length} affiché${filteredRows.length === 1 ? '' : 's'}`}
            status="info"
          />
        }
        bodyClassName=""
      >
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-950/70 text-[11px] uppercase tracking-[0.14em] text-slate-400">
              <tr>
                <th className="px-5 py-3 font-semibold">Client / prospect</th>
                <th className="px-5 py-3 font-semibold">Société</th>
                <SortableHeader
                  label="Statut"
                  column="status"
                  activeColumn={sortColumn}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <th className="px-5 py-3 font-semibold">Priorité</th>
                <SortableHeader
                  label="Score IA"
                  column="score"
                  activeColumn={sortColumn}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <th className="px-5 py-3 font-semibold">Valeur</th>
                {showProductServiceColumn ? (
                  <th className="px-5 py-3 font-semibold">Offre</th>
                ) : null}
                <th className="px-5 py-3 font-semibold">Responsable</th>
                <SortableHeader
                  label="Dernier contact"
                  column="lastContact"
                  activeColumn={sortColumn}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <th className="px-5 py-3 font-semibold">Prochaine action</th>
                <th className="px-5 py-3 font-semibold">Communication</th>
                <th className="px-5 py-3 font-semibold text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredRows.length === 0 ? (
                <tr>
                  <td
                    colSpan={showProductServiceColumn ? 12 : 11}
                    className="px-5 py-10 text-center text-sm text-slate-400"
                  >
                    Aucun contact ne correspond aux filtres actuels.
                  </td>
                </tr>
              ) : (
                sortedRows.map((row) => (
                  <tr
                    key={row.id}
                    className="cursor-pointer transition hover:bg-slate-900/60"
                    onClick={() => openLeadDetails(row.id)}
                  >
                    <td className="px-5 py-4">
                      <p className="font-semibold text-white">{row.name}</p>
                      <p className="text-[11px] text-slate-500">{row.email}</p>
                    </td>
                    <td className="px-5 py-4 text-slate-300">{row.company}</td>
                    <td className="px-5 py-4">
                      <PriorityBadge label={row.status} tone={getStatusTone(row.status)} />
                    </td>
                    <td className="px-5 py-4">
                      <PriorityBadge
                        label={row.priority}
                        tone={getPriorityTone(row.priority)}
                        withDot
                      />
                    </td>
                    <td className="px-5 py-4">
                      <PriorityBadge
                        label={String(row.score)}
                        tone={getScoreTone(row.score)}
                      />
                    </td>
                    <td className="px-5 py-4 text-slate-200">{row.estimatedValue}</td>
                    {showProductServiceColumn ? (
                      <td className="max-w-[180px] px-5 py-4 text-slate-300">
                        {row.productService}
                      </td>
                    ) : null}
                    <td className="px-5 py-4 text-slate-300">{row.owner}</td>
                    <td className="px-5 py-4 text-slate-300">{row.lastContact}</td>
                    <td className="max-w-[280px] px-5 py-4 leading-6 text-slate-300">
                      {row.nextAction}
                    </td>
                    <td className="px-5 py-4">
                      <PriorityBadge
                        label={row.communicationStatus}
                        tone={row.isDraftWaiting ? 'orange' : 'blue'}
                        size="sm"
                      />
                    </td>
                    <td className="px-5 py-4 text-right">
                      <ActionButton
                        label={
                          <span className="inline-flex items-center gap-1">
                            <Icon name="eye" size={14} />
                            Voir
                          </span>
                        }
                        variant="secondary"
                        size="sm"
                        onClick={() => openLeadDetails(row.id)}
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </AppCard>
    </div>
  )
}

type SortableHeaderProps = {
  label: string
  column: SortColumn
  activeColumn: SortColumn | null
  direction: SortDirection | null
  onSort: (column: SortColumn) => void
  align?: 'left' | 'right'
}

function SortableHeader({
  label,
  column,
  activeColumn,
  direction,
  onSort,
  align = 'left',
}: SortableHeaderProps) {
  const isActive = activeColumn === column && direction !== null
  const ariaSort: 'ascending' | 'descending' | 'none' = !isActive
    ? 'none'
    : direction === 'asc'
      ? 'ascending'
      : 'descending'

  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={`px-5 py-3 font-semibold ${align === 'right' ? 'text-right' : ''}`}
    >
      <button
        type="button"
        onClick={() => onSort(column)}
        className={`inline-flex items-center gap-1.5 font-semibold uppercase tracking-[0.14em] transition ${
          isActive ? 'text-emerald-300' : 'text-slate-400 hover:text-slate-200'
        }`}
        title={
          !isActive
            ? `Trier par ${label} (croissant)`
            : direction === 'asc'
              ? `Trier par ${label} (décroissant)`
              : `Désactiver le tri sur ${label}`
        }
      >
        <span>{label}</span>
        {isActive ? (
          <Icon
            name="chevron-down"
            size={12}
            className={`transition-transform ${direction === 'asc' ? 'rotate-180' : ''}`}
          />
        ) : (
          <Icon name="chevron-down" size={12} className="opacity-30" />
        )}
      </button>
    </th>
  )
}

export default CRMLeadsPage
