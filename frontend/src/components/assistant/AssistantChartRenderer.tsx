/**
 * AssistantChartRenderer — V2
 *
 * Renders visualizations returned by the assistant backend.
 * Supports: bar_chart, pie_chart, line_chart, table, kpi.
 * Pure Tailwind CSS — no external chart library required.
 */

import type { VisualizationData } from '../../services/assistantService'

// ---------------------------------------------------------------------------
// Color palette
// ---------------------------------------------------------------------------

const SERIES_COLORS_BG = [
  'bg-emerald-500',
  'bg-sky-500',
  'bg-violet-500',
  'bg-amber-500',
  'bg-rose-500',
  'bg-teal-500',
  'bg-orange-400',
  'bg-indigo-500',
]

const SERIES_COLORS_DOT = [
  'bg-emerald-400',
  'bg-sky-400',
  'bg-violet-400',
  'bg-amber-400',
  'bg-rose-400',
  'bg-teal-400',
  'bg-orange-400',
  'bg-indigo-400',
]

const SERIES_COLORS_TEXT = [
  'text-emerald-400',
  'text-sky-400',
  'text-violet-400',
  'text-amber-400',
  'text-rose-400',
  'text-teal-400',
  'text-orange-400',
  'text-indigo-400',
]

// ---------------------------------------------------------------------------
// Data extraction helpers — handle all backend shapes
// ---------------------------------------------------------------------------

function extractRows(data: Record<string, unknown>): Record<string, unknown>[] {
  const rows = data['rows'] ?? data['data']
  if (Array.isArray(rows)) return rows as Record<string, unknown>[]
  return []
}

function extractSeries(data: Record<string, unknown>): { label: string; value: number }[] {
  const xKey = typeof data['xKey'] === 'string' ? data['xKey'] : null
  const yKey = typeof data['yKey'] === 'string' ? data['yKey'] : null
  const inner = data['data']

  // Shape 1: { xKey, yKey, data: [{[xKey]: label, [yKey]: value}] }
  if (xKey && yKey && Array.isArray(inner)) {
    return (inner as Record<string, unknown>[]).map((row) => ({
      label: String(row[xKey] ?? '—'),
      value: Number(row[yKey] ?? 0),
    }))
  }

  // Shape 2: { data: [{name|label, value|count|nombre}] }
  if (Array.isArray(inner)) {
    return (inner as Record<string, unknown>[]).map((row) => ({
      label: String(row['name'] ?? row['label'] ?? row['Étape'] ?? '—'),
      value: Number(row['value'] ?? row['count'] ?? row['nombre'] ?? row['Nombre'] ?? 0),
    }))
  }

  // Shape 3: flat rows with KPI/Valeur columns (from business_summary table)
  const rows = extractRows(data)
  if (rows.length > 0 && 'Indicateur' in rows[0] && 'Valeur' in rows[0]) {
    return rows.map((r) => ({
      label: String(r['Indicateur'] ?? '—'),
      value: Number(r['Valeur'] ?? 0),
    }))
  }

  return []
}

function extractKpi(data: Record<string, unknown>): { label: string; value: string; detail?: string } | null {
  if (typeof data['label'] === 'string' && data['value'] !== undefined) {
    return {
      label: String(data['label']),
      value: String(data['value']),
      detail: typeof data['detail'] === 'string' ? data['detail'] : undefined,
    }
  }
  return null
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyViz({ message }: { message: string }) {
  return (
    <p className="py-6 text-center text-xs text-slate-500 italic">
      {message}
    </p>
  )
}

// ---------------------------------------------------------------------------
// KPI card
// ---------------------------------------------------------------------------

function KpiViz({ viz }: { viz: VisualizationData }) {
  const kpi = extractKpi(viz.data)
  if (!kpi) return <EmptyViz message="Aucune donnée KPI disponible." />

  return (
    <div className="flex flex-col items-center gap-2 py-4 text-center">
      <p className="text-4xl font-black tracking-tight text-white">{kpi.value}</p>
      <p className="text-sm font-semibold text-slate-300">{kpi.label}</p>
      {kpi.detail ? (
        <p className="text-xs text-slate-500">{kpi.detail}</p>
      ) : null}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Bar chart (horizontal bars with percentage fill)
// ---------------------------------------------------------------------------

function BarChart({ viz }: { viz: VisualizationData }) {
  const series = extractSeries(viz.data)
  if (series.length === 0) return <EmptyViz message="Aucune donnée disponible." />

  const max = Math.max(...series.map((s) => s.value), 1)
  const total = series.reduce((acc, s) => acc + s.value, 0)

  return (
    <div className="space-y-3">
      {series.map((item, i) => {
        const pct = Math.round((item.value / max) * 100)
        const sharePct = total > 0 ? Math.round((item.value / total) * 100) : 0
        const bg = SERIES_COLORS_BG[i % SERIES_COLORS_BG.length]
        const txt = SERIES_COLORS_TEXT[i % SERIES_COLORS_TEXT.length]
        return (
          <div key={`${item.label}-${i}`} className="group">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="min-w-0 truncate text-xs text-slate-300">{item.label}</span>
              <div className="flex shrink-0 items-center gap-2">
                <span className={`text-xs font-bold ${txt}`}>{item.value}</span>
                <span className="text-[10px] text-slate-600">{sharePct}%</span>
              </div>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
              <div
                className={`h-full rounded-full transition-all duration-700 ease-out ${bg}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )
      })}
      <p className="pt-1 text-right text-[10px] text-slate-600">Total : {total}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pie chart (proportional legend list)
// ---------------------------------------------------------------------------

function PieChart({ viz }: { viz: VisualizationData }) {
  const series = extractSeries(viz.data)
  if (series.length === 0) return <EmptyViz message="Aucune donnée disponible." />

  const total = series.reduce((acc, s) => acc + s.value, 0)

  return (
    <div className="space-y-2.5">
      {series.map((item, i) => {
        const pct = total > 0 ? Math.round((item.value / total) * 100) : 0
        const dot = SERIES_COLORS_DOT[i % SERIES_COLORS_DOT.length]
        const bg = SERIES_COLORS_BG[i % SERIES_COLORS_BG.length]
        return (
          <div key={`${item.label}-${i}`} className="flex items-center gap-3">
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${dot}`} />
            <span className="min-w-0 flex-1 truncate text-xs text-slate-300">{item.label}</span>
            {/* Mini proportional bar */}
            <div className="hidden w-16 sm:block">
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                <div className={`h-full rounded-full ${bg}`} style={{ width: `${pct}%` }} />
              </div>
            </div>
            <span className="w-6 shrink-0 text-right text-xs font-bold text-white">{item.value}</span>
            <span className="w-9 shrink-0 text-right text-[10px] text-slate-500">{pct}%</span>
          </div>
        )
      })}
      <div className="border-t border-slate-800 pt-2 text-right text-[10px] text-slate-600">
        Total : {total}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

function TableViz({ viz }: { viz: VisualizationData }) {
  const rows = extractRows(viz.data)
  if (rows.length === 0) return <EmptyViz message="Aucune donnée disponible." />

  const columns = Object.keys(rows[0])

  return (
    <div className="overflow-x-auto rounded-lg">
      <table className="w-full min-w-full text-xs">
        <thead>
          <tr className="border-b border-slate-700/60 bg-slate-900/60">
            {columns.map((col) => (
              <th
                key={col}
                className="whitespace-nowrap px-3 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500 first:pl-4 last:pr-4"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/40">
          {rows.map((row, ri) => (
            <tr
              key={ri}
              className="transition-colors hover:bg-slate-800/30"
            >
              {columns.map((col, ci) => (
                <td
                  key={col}
                  className={`px-3 py-2.5 text-slate-300 first:pl-4 last:pr-4 ${ci === 0 ? 'font-medium text-slate-200' : ''}`}
                >
                  {String(row[col] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Rich lead table — activates when rows look like leads (Nom + Score + Statut)
// ---------------------------------------------------------------------------

function isLeadRowShape(row: Record<string, unknown>): boolean {
  const keys = Object.keys(row).map((k) => k.toLowerCase())
  return keys.includes('nom') && (keys.includes('score') || keys.includes('statut'))
}

function scoreClass(score: number): string {
  if (score >= 80) return 'text-rose-400'
  if (score >= 60) return 'text-amber-400'
  if (score >= 40) return 'text-yellow-400'
  return 'text-slate-400'
}

function statusBadgeClass(status: string): string {
  const s = status.toLowerCase()
  if (s.includes('hot') || s.includes('chaud')) return 'bg-rose-500/15 text-rose-300 border-rose-500/30'
  if (s.includes('warm') || s.includes('tiède') || s.includes('tiede')) return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
  if (s.includes('cold') || s.includes('froid')) return 'bg-sky-500/15 text-sky-300 border-sky-500/30'
  if (s.includes('new') || s.includes('nouveau')) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
  return 'bg-slate-700/40 text-slate-300 border-slate-600/40'
}

function RichLeadTable({ rows }: { rows: Record<string, unknown>[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700/60 text-[10px] uppercase tracking-wider text-slate-500">
            <th className="px-4 py-2.5 text-left font-semibold">Lead</th>
            <th className="px-4 py-2.5 text-left font-semibold">Entreprise</th>
            <th className="px-4 py-2.5 text-center font-semibold">Score</th>
            <th className="px-4 py-2.5 text-center font-semibold">Statut</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const name = String(row['Nom'] ?? '—')
            const company = String(row['Entreprise'] ?? '—')
            const score = Number(row['Score'] ?? 0)
            const status = String(row['Statut'] ?? '—')
            const action = row['Prochaine action'] != null ? String(row['Prochaine action']) : null
            return (
              <tr
                key={i}
                className="border-b border-slate-800/60 transition-colors hover:bg-slate-800/30"
              >
                <td className="px-4 py-3">
                  <div className="font-medium text-slate-100">{name}</div>
                  {action ? (
                    <div className="mt-0.5 text-[11px] text-slate-500">{action}</div>
                  ) : null}
                </td>
                <td className="px-4 py-3 text-slate-300">{company}</td>
                <td className="px-4 py-3 text-center">
                  <span className={`text-base font-bold ${scoreClass(score)}`}>{score}</span>
                  <span className="text-[10px] text-slate-600">/100</span>
                </td>
                <td className="px-4 py-3 text-center">
                  <span
                    className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${statusBadgeClass(status)}`}
                  >
                    {status}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Deduplicate visualizations by normalized title.
// Backend sometimes returns the same metric as both pie + bar — keep one.
// ---------------------------------------------------------------------------

function normalizeTitle(title: string): string {
  return title
    .toLowerCase()
    .replace(/\s*\(barres?\)/g, '')
    .replace(/\s*\(r[ée]partition\)/g, '')
    .replace(/\s*\(pie\)/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function dedupeByTitle(visualizations: VisualizationData[]): VisualizationData[] {
  const seen = new Set<string>()
  const out: VisualizationData[] = []
  for (const viz of visualizations) {
    const key = normalizeTitle(viz.title)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(viz)
  }
  return out
}

// ---------------------------------------------------------------------------
// Visualization card (one chart/table/kpi)
// ---------------------------------------------------------------------------

function VisualizationCard({ viz }: { viz: VisualizationData }) {
  const isKpi = viz.type === 'kpi'
  const isTable = viz.type === 'table'

  // Detect rich lead-table shape
  let useRichLeadTable = false
  if (isTable) {
    const rows = extractRows(viz.data)
    if (rows.length > 0 && isLeadRowShape(rows[0])) {
      useRichLeadTable = true
    }
  }

  return (
    <div
      className={`flex h-full flex-col overflow-hidden rounded-xl border bg-slate-900/70 ${
        isKpi ? 'border-emerald-500/25 bg-emerald-950/10' : 'border-slate-700/60'
      }`}
    >
      <div
        className={`shrink-0 border-b px-4 py-3 ${
          isKpi ? 'border-emerald-500/20' : 'border-slate-700/60'
        }`}
      >
        <p
          className={`text-xs font-semibold uppercase tracking-[0.12em] ${
            isKpi ? 'text-emerald-300' : 'text-slate-200'
          }`}
        >
          {viz.title}
        </p>
        {viz.description ? (
          <p className="mt-0.5 text-[10px] leading-4 text-slate-500">{viz.description}</p>
        ) : null}
      </div>
      <div className={isTable ? 'flex-1' : 'flex-1 p-4'}>
        {viz.type === 'kpi' ? (
          <KpiViz viz={viz} />
        ) : viz.type === 'bar_chart' || viz.type === 'line_chart' ? (
          <BarChart viz={viz} />
        ) : viz.type === 'pie_chart' ? (
          <PieChart viz={viz} />
        ) : isTable ? (
          useRichLeadTable ? (
            <RichLeadTable rows={extractRows(viz.data)} />
          ) : (
            <TableViz viz={viz} />
          )
        ) : (
          <EmptyViz message="Type de visualisation non supporté." />
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main renderer with smart layout:
//   - KPIs first, on their own row
//   - 1 chart + 1 table  → side-by-side (md+)
//   - other combinations → single column
// ---------------------------------------------------------------------------

type AssistantChartRendererProps = {
  visualizations: VisualizationData[]
}

function AssistantChartRenderer({ visualizations }: AssistantChartRendererProps) {
  if (visualizations.length === 0) return null

  const unique = dedupeByTitle(visualizations)
  const kpis = unique.filter((v) => v.type === 'kpi')
  const tables = unique.filter((v) => v.type === 'table')
  const charts = unique.filter((v) => v.type !== 'kpi' && v.type !== 'table')

  const sideBySide = charts.length === 1 && tables.length === 1

  return (
    <div className="space-y-3">
      {kpis.length > 0 ? (
        <div className={`grid gap-3 ${kpis.length >= 2 ? 'sm:grid-cols-2' : ''}`}>
          {kpis.map((viz, i) => (
            <VisualizationCard key={`kpi-${i}`} viz={viz} />
          ))}
        </div>
      ) : null}

      {sideBySide ? (
        <div className="grid gap-3 md:grid-cols-2">
          <VisualizationCard viz={charts[0]} />
          <VisualizationCard viz={tables[0]} />
        </div>
      ) : (
        <>
          {charts.map((viz, i) => (
            <VisualizationCard key={`chart-${i}`} viz={viz} />
          ))}
          {tables.map((viz, i) => (
            <VisualizationCard key={`table-${i}`} viz={viz} />
          ))}
        </>
      )}
    </div>
  )
}

export default AssistantChartRenderer
