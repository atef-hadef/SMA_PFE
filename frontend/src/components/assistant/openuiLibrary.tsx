/* eslint-disable react-refresh/only-export-components -- OpenUI libraries intentionally export schema objects consumed by Renderer and the prompt generator. */
import { createLibrary, defineComponent, useRenderNode, useTriggerAction } from '@openuidev/react-lang'
import type { ComponentRenderProps } from '@openuidev/react-lang'
import type { ReactNode } from 'react'
import { z } from 'zod/v4'
import { Icon } from '../common'

const primitiveValueSchema = z.union([z.string(), z.number(), z.boolean(), z.null()])
const tableCellSchema = primitiveValueSchema.optional()
const toneSchema = z.enum(['neutral', 'success', 'warning', 'danger', 'info']).default('neutral')
const chartPointSchema = z.object({
  label: z.string(),
  value: z.number(),
  secondaryValue: z.number().optional(),
})
const tableColumnSchema = z.object({
  key: z.string(),
  label: z.string(),
  align: z.enum(['left', 'center', 'right']).default('left'),
})
const tableRowSchema = z.record(z.string(), tableCellSchema)
const priorityLeadRowSchema = z.object({
  name: primitiveValueSchema,
  company: primitiveValueSchema.optional(),
  score: primitiveValueSchema.optional(),
  status: primitiveValueSchema.optional(),
  nextAction: primitiveValueSchema.optional(),
  owner: primitiveValueSchema.optional(),
})
const actionSchema = z.object({
  label: z.string(),
  actionType: z.enum([
    'navigate',
    'refresh',
    'filter',
    'open_details',
    'prepare_followups',
    'generate_email_draft',
    'create_task',
    'launch_report',
    'send_approved_email',
    'query',
  ]),
  route: z.string().optional(),
  targetId: z.string().optional(),
  message: z.string().optional(),
  requiresConfirmation: z.boolean().default(false),
})

function toneClass(tone: z.infer<typeof toneSchema>) {
  switch (tone) {
    case 'success':
      return 'border-emerald-500/25 bg-emerald-500/10 text-emerald-200'
    case 'warning':
      return 'border-amber-500/25 bg-amber-500/10 text-amber-200'
    case 'danger':
      return 'border-rose-500/25 bg-rose-500/10 text-rose-200'
    case 'info':
      return 'border-sky-500/25 bg-sky-500/10 text-sky-200'
    default:
      return 'border-slate-700/60 bg-slate-900/70 text-slate-200'
  }
}

// Rich, analytics-grade tone palette (gradient tints + solid accents).
type ToneStyle = { ring: string; grad: string; accent: string; soft: string; hex: string }
const TONE_STYLES: Record<z.infer<typeof toneSchema>, ToneStyle> = {
  neutral: { ring: 'border-slate-700/60', grad: 'from-slate-800/60 to-slate-900/40', accent: 'bg-slate-500', soft: 'text-slate-400', hex: '#94a3b8' },
  info: { ring: 'border-sky-500/30', grad: 'from-sky-500/15 to-slate-900/30', accent: 'bg-sky-500', soft: 'text-sky-300/80', hex: '#38bdf8' },
  success: { ring: 'border-emerald-500/30', grad: 'from-emerald-500/15 to-slate-900/30', accent: 'bg-emerald-500', soft: 'text-emerald-300/80', hex: '#34d399' },
  warning: { ring: 'border-amber-500/30', grad: 'from-amber-500/15 to-slate-900/30', accent: 'bg-amber-500', soft: 'text-amber-300/80', hex: '#fbbf24' },
  danger: { ring: 'border-rose-500/30', grad: 'from-rose-500/15 to-slate-900/30', accent: 'bg-rose-500', soft: 'text-rose-300/80', hex: '#fb7185' },
}
function toneStyle(tone: z.infer<typeof toneSchema>): ToneStyle {
  return TONE_STYLES[tone] ?? TONE_STYLES.neutral
}

// Categorical palette for charts (donut segments / bars).
const CHART_PALETTE = ['#34d399', '#38bdf8', '#a78bfa', '#fbbf24', '#fb7185', '#2dd4bf', '#fb923c', '#818cf8']

/** Parse a trend string ("+12 %", "-3", "stable") into a direction + colour. */
function trendMeta(trend?: string): { arrow: string; cls: string } | null {
  if (!trend) return null
  const t = trend.trim()
  if (/^[+]|↑|hausse|\bup\b/i.test(t) && !/^[+]?0(\D|$)/.test(t)) return { arrow: '↑', cls: 'text-emerald-300' }
  if (/^[-−]|↓|baisse|\bdown\b/i.test(t)) return { arrow: '↓', cls: 'text-rose-300' }
  return { arrow: '→', cls: 'text-slate-400' }
}

function alignClass(align: 'left' | 'center' | 'right') {
  if (align === 'right') return 'text-right'
  if (align === 'center') return 'text-center'
  return 'text-left'
}

function normalizeValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') return Number.isInteger(value) ? value.toString() : value.toLocaleString('fr-FR')
  if (typeof value === 'boolean') return value ? 'Oui' : 'Non'
  return String(value)
}

function formatMaybeCurrency(value: string, currency?: string | null) {
  if (!currency) return value
  return `${value} ${currency}`
}

function Shell({ children }: { children: ReactNode }) {
  return <div className="space-y-3">{children}</div>
}

export const TextBlock = defineComponent({
  name: 'TextBlock',
  description: 'Displays concise business text, facts, context, or a short explanation.',
  props: z.object({
    title: z.string().optional(),
    text: z.string(),
    tone: toneSchema,
  }),
  component: ({ props }) => (
    <div className={`rounded-xl border px-5 py-4 ${toneClass(props.tone)}`}>
      {props.title ? <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em]">{props.title}</p> : null}
      <p className="text-sm leading-6">{props.text}</p>
    </div>
  ),
})

export const KpiCard = defineComponent({
  name: 'KpiCard',
  description: 'Displays one verified KPI calculated by the backend.',
  props: z.object({
    label: z.string(),
    value: z.union([z.string(), z.number()]),
    detail: z.string().optional(),
    trend: z.string().optional(),
    currency: z.string().optional(),
    tone: toneSchema,
  }),
  component: ({ props }) => {
    const t = toneStyle(props.tone)
    const trend = trendMeta(props.trend)
    return (
      <div className={`group relative overflow-hidden rounded-2xl border bg-linear-to-br p-4 transition-all duration-300 hover:shadow-lg hover:shadow-black/20 ${t.ring} ${t.grad}`}>
        <span className={`absolute inset-y-0 left-0 w-1 ${t.accent}`} aria-hidden />
        <div className="flex items-start justify-between gap-2 pl-1.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{props.label}</p>
          {trend ? (
            <span className={`inline-flex items-center gap-0.5 rounded-full bg-slate-950/40 px-1.5 py-0.5 text-[10px] font-bold ${trend.cls}`}>
              <span aria-hidden>{trend.arrow}</span>
              {props.trend}
            </span>
          ) : null}
        </div>
        <p className="mt-2 pl-1.5 text-3xl font-black leading-none tracking-tight text-white">
          {formatMaybeCurrency(normalizeValue(props.value), props.currency)}
        </p>
        {props.detail ? <p className="mt-1.5 pl-1.5 text-xs leading-5 text-slate-400">{props.detail}</p> : null}
      </div>
    )
  },
})

export const SingleMetricCard = defineComponent({
  name: 'SingleMetricCard',
  description: 'Displays a direct answer with one verified backend metric. Use for short "how many" questions.',
  props: z.object({
    label: z.string(),
    value: z.union([z.string(), z.number()]),
    detail: z.string().optional(),
    tone: toneSchema,
    currency: z.string().optional(),
  }),
  component: ({ props }) => {
    const t = toneStyle(props.tone)
    return (
      <div className={`relative overflow-hidden rounded-2xl border bg-linear-to-br ${t.ring} ${t.grad}`}>
        <span className={`pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full opacity-20 blur-3xl ${t.accent}`} aria-hidden />
        <span className={`absolute inset-x-0 top-0 h-0.5 ${t.accent}`} aria-hidden />
        <div className="relative flex flex-col gap-3 p-6 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-300">{props.label}</p>
            {props.detail ? <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">{props.detail}</p> : null}
          </div>
          <p className="text-5xl font-black leading-none tracking-tight text-white sm:text-6xl">
            {formatMaybeCurrency(normalizeValue(props.value), props.currency)}
          </p>
        </div>
      </div>
    )
  },
})

export const KpiGrid = defineComponent({
  name: 'KpiGrid',
  description: 'Responsive grid of KPI cards. Use for 2 to 6 KPIs.',
  props: z.object({
    cards: z.array(KpiCard.ref).default([]),
  }),
  component: KpiGridRenderer,
})

function KpiGridRenderer({ props }: ComponentRenderProps<{ cards: z.infer<typeof KpiCard.ref>[] }>) {
  const renderNode = useRenderNode()
  if (props.cards.length === 0) {
    return <EmptyPanel title="Aucun KPI" message="Aucun indicateur disponible pour cette question." />
  }
  return <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{props.cards.map((card) => renderNode(card))}</div>
}

function ChartFrame({
  title,
  description,
  data,
  children,
}: {
  title: string
  description?: string
  data: z.infer<typeof chartPointSchema>[]
  children: ReactNode
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-700/60 bg-slate-900/70">
      <div className="border-b border-slate-700/60 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-200">{title}</p>
        {description ? <p className="mt-0.5 text-[10px] leading-4 text-slate-500">{description}</p> : null}
      </div>
      <div className="p-4">{data.length > 0 ? children : <EmptyPanel title="Aucune donnée" message="Aucune série disponible." />}</div>
    </div>
  )
}

export const BarChartCard = defineComponent({
  name: 'BarChartCard',
  description: 'Horizontal bar chart for distributions and comparisons.',
  props: z.object({
    title: z.string(),
    description: z.string().optional(),
    data: z.array(chartPointSchema).default([]),
  }),
  component: ({ props }) => {
    const max = Math.max(...props.data.map((item) => item.value), 1)
    const total = props.data.reduce((sum, item) => sum + item.value, 0)
    return (
      <ChartFrame title={props.title} description={props.description} data={props.data}>
        <div className="space-y-3.5">
          {props.data.map((item, index) => {
            const color = CHART_PALETTE[index % CHART_PALETTE.length]
            const share = total > 0 ? Math.round((item.value / total) * 100) : 0
            return (
              <div key={item.label}>
                <div className="mb-1.5 flex items-center justify-between gap-3 text-xs">
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: color }} />
                    <span className="truncate text-slate-300">{item.label}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    <span className="font-bold text-white">{normalizeValue(item.value)}</span>
                    <span className="w-9 text-right text-[10px] text-slate-500">{share}%</span>
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-slate-800/80">
                  <div
                    className="h-full rounded-full transition-all duration-700 ease-out"
                    style={{
                      width: `${Math.round((item.value / max) * 100)}%`,
                      background: `linear-gradient(90deg, ${color}99, ${color})`,
                    }}
                  />
                </div>
              </div>
            )
          })}
          <p className="pt-0.5 text-right text-[10px] text-slate-600">Total : {normalizeValue(total)}</p>
        </div>
      </ChartFrame>
    )
  },
})

export const LineChartCard = defineComponent({
  name: 'LineChartCard',
  description: 'Compact trend list for chronological or comparative metrics.',
  props: z.object({
    title: z.string(),
    description: z.string().optional(),
    data: z.array(chartPointSchema).default([]),
  }),
  component: ({ props }) => {
    const values = props.data.map((d) => d.value)
    const max = Math.max(...values, 1)
    const min = Math.min(...values, 0)
    const span = max - min || 1
    const n = props.data.length
    const x = (i: number) => (n <= 1 ? 50 : (i / (n - 1)) * 100)
    const y = (v: number) => 38 - ((v - min) / span) * 32 - 3
    const line = props.data.map((d, i) => `${x(i).toFixed(2)},${y(d.value).toFixed(2)}`).join(' ')
    const area = `0,38 ${line} 100,38`
    return (
      <ChartFrame title={props.title} description={props.description} data={props.data}>
        <div className="space-y-3">
          <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="h-28 w-full">
            <defs>
              <linearGradient id="lc-area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
              </linearGradient>
            </defs>
            <polygon points={area} fill="url(#lc-area)" />
            <polyline points={line} fill="none" stroke="#38bdf8" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
            {props.data.map((d, i) => (
              <circle key={d.label} cx={x(i)} cy={y(d.value)} r="1.4" fill="#0ea5e9" stroke="#0b1220" strokeWidth="0.6" vectorEffect="non-scaling-stroke" />
            ))}
          </svg>
          <div className="flex justify-between text-[10px] text-slate-500">
            {props.data.map((d) => (
              <span key={d.label} className="flex-1 truncate text-center">{d.label}</span>
            ))}
          </div>
        </div>
      </ChartFrame>
    )
  },
})

export const PieChartCard = defineComponent({
  name: 'PieChartCard',
  description: 'Legend-style pie chart for shares and status distributions.',
  props: z.object({
    title: z.string(),
    description: z.string().optional(),
    data: z.array(chartPointSchema).default([]),
  }),
  component: ({ props }) => {
    const total = props.data.reduce((sum, item) => sum + item.value, 0)
    let cumulative = 0
    return (
      <ChartFrame title={props.title} description={props.description} data={props.data}>
        <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
          <div className="relative h-36 w-36 shrink-0">
            <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
              <circle cx="18" cy="18" r="15.915" fill="none" stroke="#1e293b" strokeWidth="3.5" />
              {props.data.map((item, index) => {
                const pct = total > 0 ? (item.value / total) * 100 : 0
                const dash = `${pct} ${100 - pct}`
                const offset = 25 - cumulative
                cumulative += pct
                return (
                  <circle
                    key={item.label}
                    cx="18"
                    cy="18"
                    r="15.915"
                    fill="none"
                    stroke={CHART_PALETTE[index % CHART_PALETTE.length]}
                    strokeWidth="3.5"
                    strokeDasharray={dash}
                    strokeDashoffset={offset}
                    strokeLinecap="round"
                  />
                )
              })}
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-black leading-none text-white">{normalizeValue(total)}</span>
              <span className="text-[9px] uppercase tracking-wider text-slate-500">Total</span>
            </div>
          </div>
          <div className="w-full space-y-2">
            {props.data.map((item, index) => {
              const percent = total > 0 ? Math.round((item.value / total) * 100) : 0
              return (
                <div key={item.label} className="flex items-center gap-2.5 text-xs">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: CHART_PALETTE[index % CHART_PALETTE.length] }} />
                  <span className="min-w-0 flex-1 truncate text-slate-300">{item.label}</span>
                  <span className="font-bold text-white">{normalizeValue(item.value)}</span>
                  <span className="w-9 text-right text-slate-500">{percent}%</span>
                </div>
              )
            })}
          </div>
        </div>
      </ChartFrame>
    )
  },
})

export const FunnelChartCard = defineComponent({
  name: 'FunnelChartCard',
  description: 'Funnel visualization for conversion stages.',
  props: z.object({
    title: z.string(),
    description: z.string().optional(),
    data: z.array(chartPointSchema).default([]),
  }),
  component: ({ props }) => {
    const max = Math.max(...props.data.map((item) => item.value), 1)
    return (
      <ChartFrame title={props.title} description={props.description} data={props.data}>
        <div className="space-y-1.5">
          {props.data.map((item, index) => {
            const width = Math.max(12, Math.round((item.value / max) * 100))
            const prev = index > 0 ? props.data[index - 1].value : item.value
            const conv = prev > 0 ? Math.round((item.value / prev) * 100) : 100
            const color = CHART_PALETTE[index % CHART_PALETTE.length]
            return (
              <div key={item.label} className="flex flex-col items-center">
                <div
                  className="flex items-center justify-between rounded-lg px-3 py-2.5 text-xs transition-all"
                  style={{ width: `${width}%`, background: `linear-gradient(90deg, ${color}cc, ${color}77)` }}
                >
                  <span className="truncate font-semibold text-white">{item.label}</span>
                  <span className="ml-2 shrink-0 font-black text-white">{normalizeValue(item.value)}</span>
                </div>
                {index > 0 ? (
                  <span className="py-0.5 text-[9px] text-slate-500">▼ {conv}%</span>
                ) : null}
              </div>
            )
          })}
        </div>
      </ChartFrame>
    )
  },
})

export const SmartDataTable = defineComponent({
  name: 'SmartDataTable',
  description: 'Validated business table with columns and rows supplied by the backend. Do not include technical IDs.',
  props: z.object({
    title: z.string(),
    description: z.string().optional(),
    columns: z.array(tableColumnSchema).default([]),
    rows: z.array(tableRowSchema).default([]),
    emptyMessage: z.string().default('Aucune donnée disponible.'),
  }),
  component: ({ props }) => {
    if (props.columns.length === 0 || props.rows.length === 0) {
      return <EmptyPanel title={props.title} message={props.emptyMessage} />
    }
    return (
      <div className="overflow-hidden rounded-xl border border-slate-700/60 bg-slate-900/70">
        <div className="border-b border-slate-700/60 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-200">{props.title}</p>
          {props.description ? <p className="mt-0.5 text-[10px] leading-4 text-slate-500">{props.description}</p> : null}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700/60 bg-slate-950/40">
                {props.columns.map((column) => (
                  <th key={column.key} className={`px-3 py-2.5 font-semibold uppercase tracking-wider text-slate-500 ${alignClass(column.align)}`}>
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {props.rows.map((row, index) => (
                <tr key={index} className="hover:bg-slate-800/30">
                  {props.columns.map((column) => (
                    <td key={column.key} className={`px-3 py-2.5 text-slate-300 ${alignClass(column.align)}`}>
                      {normalizeValue(row[column.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  },
})

export const PriorityLeadTable = defineComponent({
  name: 'PriorityLeadTable',
  description: 'CRM lead table optimized for prioritized follow-up. Use only for authorized CRM lead rows.',
  props: z.object({
    title: z.string(),
    description: z.string().optional(),
    rows: z.array(priorityLeadRowSchema).default([]),
    emptyMessage: z.string().default('Aucun lead prioritaire disponible.'),
  }),
  component: ({ props }) => {
    if (props.rows.length === 0) return <EmptyPanel title={props.title} message={props.emptyMessage} />
    return (
      <div className="overflow-hidden rounded-xl border border-slate-700/60 bg-slate-900/70">
        <div className="flex flex-col gap-1 border-b border-slate-700/60 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-200">{props.title}</p>
            {props.description ? <p className="mt-0.5 text-[10px] leading-4 text-slate-500">{props.description}</p> : null}
          </div>
          <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-amber-200">
            Priorité
          </span>
        </div>
        <div className="divide-y divide-slate-800/70">
          {props.rows.map((row, index) => (
            <div key={`${normalizeValue(row.name)}-${index}`} className="grid gap-3 px-4 py-3 md:grid-cols-[1.4fr_1fr_auto] md:items-center">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{normalizeValue(row.name)}</p>
                <p className="mt-0.5 truncate text-xs text-slate-500">{normalizeValue(row.company)}</p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded-full border border-slate-700 bg-slate-800/60 px-2.5 py-1 text-slate-300">
                  Score {normalizeValue(row.score)}
                </span>
                <span className="rounded-full border border-rose-500/25 bg-rose-500/10 px-2.5 py-1 font-semibold text-rose-200">
                  {normalizeValue(row.status)}
                </span>
                {row.owner ? (
                  <span className="rounded-full border border-slate-700 bg-slate-800/60 px-2.5 py-1 text-slate-400">
                    {normalizeValue(row.owner)}
                  </span>
                ) : null}
              </div>
              <p className="text-xs leading-5 text-slate-400 md:text-right">{normalizeValue(row.nextAction)}</p>
            </div>
          ))}
        </div>
      </div>
    )
  },
})

function ListCard({
  title,
  items,
  tone = 'neutral',
  marker = 'dot',
}: {
  title: string
  items: string[]
  tone?: z.infer<typeof toneSchema>
  marker?: 'dot' | 'arrow'
}) {
  if (items.length === 0) return <EmptyPanel title={title} message="Aucun élément à afficher." />
  return (
    <div className={`rounded-xl border px-4 py-3 ${toneClass(tone)}`}>
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em]">{title}</p>
      <ul className="space-y-2.5 text-sm leading-6">
        {items.map((item) => (
          <li key={item} className="flex gap-2.5">
            {marker === 'arrow' ? (
              <span className="mt-px shrink-0 text-base font-bold leading-6 text-current opacity-80" aria-hidden>→</span>
            ) : (
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-70" aria-hidden />
            )}
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export const AlertList = defineComponent({
  name: 'AlertList',
  description: 'Displays warnings, risks, or blocking issues.',
  props: z.object({ title: z.string().default('Alertes'), items: z.array(z.string()).default([]), tone: toneSchema }),
  component: ({ props }) => <ListCard title={props.title} items={props.items} tone={props.tone} />,
})

export const InsightList = defineComponent({
  name: 'InsightList',
  description: 'Displays factual observations derived from validated backend data.',
  props: z.object({ title: z.string().default('Observations'), items: z.array(z.string()).default([]) }),
  component: ({ props }) => <ListCard title={props.title} items={props.items} tone="info" />,
})

export const RecommendationList = defineComponent({
  name: 'RecommendationList',
  description: 'Displays AI recommendations as suggestions, not certainty.',
  props: z.object({ title: z.string().default('Recommandations'), items: z.array(z.string()).default([]) }),
  component: ({ props }) => <ListCard title={props.title} items={props.items} tone="success" marker="arrow" />,
})

export const SuggestedActions = defineComponent({
  name: 'SuggestedActions',
  description: 'Displays safe suggested actions. Mutating actions must set requiresConfirmation to true.',
  props: z.object({
    title: z.string().default('Actions suggérées'),
    actions: z.array(actionSchema).default([]),
  }),
  component: SuggestedActionsRenderer,
})

function SuggestedActionsRenderer({ props }: ComponentRenderProps<{ title: string; actions: z.infer<typeof actionSchema>[] }>) {
  const triggerAction = useTriggerAction()
  if (props.actions.length === 0) return null
  return (
    <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 px-5 py-4">
      <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">{props.title}</p>
      <div className="flex flex-wrap gap-2">
        {props.actions.map((action) => (
          <button
            key={`${action.actionType}-${action.label}`}
            type="button"
            onClick={() =>
              void triggerAction(action.label, undefined, {
                type: action.actionType,
                params: {
                  label: action.label,
                  route: action.route,
                  targetId: action.targetId,
                  message: action.message,
                  requiresConfirmation: action.requiresConfirmation,
                },
              })
            }
            className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/60 px-3.5 py-2 text-sm font-medium text-slate-200 transition hover:border-emerald-500/40 hover:bg-emerald-500/10 hover:text-emerald-200"
          >
            <Icon name={action.requiresConfirmation ? 'alert' : 'chevron-right'} size={13} />
            {action.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export const WorkflowHealthCard = defineComponent({
  name: 'WorkflowHealthCard',
  description: 'Summarizes automation health without exposing raw logs or webhook internals.',
  props: z.object({
    title: z.string().default('Santé des automatisations'),
    successCount: z.number().default(0),
    failureCount: z.number().default(0),
    pendingCount: z.number().default(0),
    summary: z.string().optional(),
  }),
  component: ({ props }) => (
    <div className="rounded-xl border border-slate-700/60 bg-slate-900/70 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-200">{props.title}</p>
      {props.summary ? <p className="mt-1 text-sm leading-6 text-slate-400">{props.summary}</p> : null}
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <KpiMini label="Succès" value={props.successCount} tone="success" />
        <KpiMini label="Échecs" value={props.failureCount} tone={props.failureCount > 0 ? 'danger' : 'neutral'} />
        <KpiMini label="En attente" value={props.pendingCount} tone={props.pendingCount > 0 ? 'warning' : 'neutral'} />
      </div>
    </div>
  ),
})

function KpiMini({ label, value, tone }: { label: string; value: number; tone: z.infer<typeof toneSchema> }) {
  return (
    <div className={`rounded-lg border px-3 py-2 ${toneClass(tone)}`}>
      <p className="text-[10px] uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-1 text-lg font-black text-white">{value}</p>
    </div>
  )
}

export const SourceList = defineComponent({
  name: 'SourceList',
  description: 'Displays traceable business sources in user-friendly language.',
  props: z.object({
    sources: z.array(z.object({ label: z.string(), type: z.string().optional() })).default([]),
  }),
  component: ({ props }) =>
    props.sources.length > 0 ? (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] uppercase tracking-wider text-slate-600">Sources</span>
        {props.sources.map((source) => (
          <span key={source.label} className="inline-flex items-center gap-1.5 rounded-md border border-slate-700/60 bg-slate-800/40 px-2 py-0.5 text-[11px] text-slate-400">
            <Icon name="file" size={10} className="text-slate-500" />
            {source.label}
          </span>
        ))}
      </div>
    ) : null,
})

function EmptyPanel({ title, message }: { title: string; message: string }) {
  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-900/60 px-4 py-5 text-center">
      <p className="text-sm font-semibold text-slate-300">{title}</p>
      <p className="mt-1 text-xs text-slate-500">{message}</p>
    </div>
  )
}

export const EmptyState = defineComponent({
  name: 'EmptyState',
  description: 'Displays a clear empty-data message.',
  props: z.object({ title: z.string(), message: z.string() }),
  component: ({ props }) => <EmptyPanel title={props.title} message={props.message} />,
})

export const InsufficientDataState = defineComponent({
  name: 'InsufficientDataState',
  description: 'Explains that data volume is too low for trends while preserving factual answer.',
  props: z.object({ title: z.string(), message: z.string(), detail: z.string().optional() }),
  component: ({ props }) => (
    <div className="rounded-xl border border-amber-500/25 bg-amber-500/10 px-5 py-4 text-amber-100">
      <div className="flex items-start gap-3">
        <Icon name="alert" size={16} className="mt-0.5 shrink-0 text-amber-300" />
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.12em]">{props.title}</p>
          <p className="mt-1 text-sm leading-6">{props.message}</p>
          {props.detail ? <p className="mt-2 text-xs leading-5 text-amber-100/75">{props.detail}</p> : null}
        </div>
      </div>
    </div>
  ),
})

export const ErrorState = defineComponent({
  name: 'ErrorState',
  description: 'Displays a generic user-facing error without technical details.',
  props: z.object({ title: z.string().default('Réponse indisponible'), message: z.string() }),
  component: ({ props }) => (
    <div className={`rounded-xl border px-5 py-4 ${toneClass('danger')}`}>
      <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em]">{props.title}</p>
      <p className="text-sm leading-6">{props.message}</p>
    </div>
  ),
})

export const LoadingState = defineComponent({
  name: 'LoadingState',
  description: 'Displays an assistant loading state.',
  props: z.object({ message: z.string().default('Préparation de la visualisation...') }),
  component: ({ props }) => (
    <div className="rounded-xl border border-slate-700/60 bg-slate-900/70 px-4 py-3 text-sm text-slate-400">{props.message}</div>
  ),
})

export const DashboardSection = defineComponent({
  name: 'DashboardSection',
  description: 'Groups dashboard blocks under an optional title.',
  props: z.object({
    title: z.string().optional(),
    description: z.string().optional(),
    children: z.array(z.union([
      TextBlock.ref,
      SingleMetricCard.ref,
      KpiGrid.ref,
      BarChartCard.ref,
      LineChartCard.ref,
      PieChartCard.ref,
      FunnelChartCard.ref,
      SmartDataTable.ref,
      PriorityLeadTable.ref,
      AlertList.ref,
      InsightList.ref,
      RecommendationList.ref,
      SuggestedActions.ref,
      WorkflowHealthCard.ref,
      SourceList.ref,
      EmptyState.ref,
      InsufficientDataState.ref,
      ErrorState.ref,
      LoadingState.ref,
    ])).default([]),
  }),
  component: DashboardSectionRenderer,
})

function DashboardSectionRenderer({
  props,
}: ComponentRenderProps<{ title?: string; description?: string; children: unknown[] }>) {
  const renderNode = useRenderNode()
  return (
    <section className="space-y-3">
      {props.title ? (
        <div className="flex items-center gap-2">
          <span className="h-3 w-1 rounded-full bg-linear-to-b from-emerald-400 to-sky-500" aria-hidden />
          <h3 className="text-[11px] font-bold uppercase tracking-[0.16em] text-slate-400">{props.title}</h3>
          <span className="h-px flex-1 bg-linear-to-r from-slate-700/60 to-transparent" aria-hidden />
        </div>
      ) : null}
      {props.description ? <p className="-mt-1 text-xs leading-5 text-slate-500">{props.description}</p> : null}
      <Shell>{props.children.map((child) => renderNode(child))}</Shell>
    </section>
  )
}

export const AssistantDashboard = defineComponent({
  name: 'AssistantDashboard',
  description: 'Root component for FlowPilot AI generative dashboards.',
  props: z.object({
    title: z.string(),
    summary: z.string(),
    sections: z.array(DashboardSection.ref).default([]),
  }),
  component: AssistantDashboardRenderer,
})

// Parsed OpenUI nodes expose `typeName` (component name) + `props`.
type DashNode = { typeName: string; props: Record<string, unknown> }
function asDashNode(value: unknown): DashNode | null {
  if (value && typeof value === 'object' && 'typeName' in value && 'props' in value) {
    return value as DashNode
  }
  return null
}
// Components that read as "text/analysis" → left column.
const NARRATIVE_TYPES = new Set(['TextBlock', 'InsightList', 'RecommendationList', 'AlertList', 'InsufficientDataState', 'ErrorState'])
// Components that belong at the bottom, full width.
const FOOTER_TYPES = new Set(['SuggestedActions', 'SourceList'])

/**
 * Thesys-style split-screen: analytical text on the left (40%), visual
 * dashboard on the right (60%). Narrative components are pulled out of their
 * sections into the left column; the visual sections keep their titles on the
 * right. Actions/sources span full width underneath. On mobile the dashboard
 * is shown first, then the text.
 */
function AssistantDashboardRenderer({
  props,
}: ComponentRenderProps<{ title: string; summary: string; sections: unknown[] }>) {
  const renderNode = useRenderNode()

  const narrative: unknown[] = []
  const footer: unknown[] = []
  const visualSections: unknown[] = []

  for (const rawSection of props.sections) {
    const section = asDashNode(rawSection)
    if (!section) {
      visualSections.push(rawSection)
      continue
    }
    const children = Array.isArray(section.props.children) ? section.props.children : []
    const visualChildren: unknown[] = []
    for (const rawChild of children) {
      const typeName = asDashNode(rawChild)?.typeName ?? ''
      if (NARRATIVE_TYPES.has(typeName)) narrative.push(rawChild)
      else if (FOOTER_TYPES.has(typeName)) footer.push(rawChild)
      else visualChildren.push(rawChild)
    }
    // Keep the section (and its title) on the right, with only visual children.
    if (visualChildren.length > 0) {
      visualSections.push({ ...section, props: { ...section.props, children: visualChildren } })
    }
  }

  const header = (
    <div>
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.14em] text-emerald-300">
        <Icon name="spark" size={10} />
        Analyse IA
      </span>
      <h2 className="mt-2.5 text-lg font-black leading-tight tracking-tight text-white">{props.title}</h2>
      <p className="mt-2 text-[15px] leading-7 text-slate-300">{props.summary}</p>
    </div>
  )

  // No visual content → single-column narrative (graceful fallback).
  if (visualSections.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <span className="absolute inset-x-0 top-0 h-0.5 bg-linear-to-r from-emerald-500 via-sky-500 to-violet-500" aria-hidden />
        {header}
        {narrative.length > 0 ? <div className="mt-4 space-y-3">{narrative.map((node) => renderNode(node))}</div> : null}
        {footer.length > 0 ? <div className="mt-4 space-y-3">{footer.map((node) => renderNode(node))}</div> : null}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-[2fr_3fr]">
        {/* LEFT — analytical text (mobile: below the dashboard) */}
        <div className="relative order-2 flex flex-col gap-3 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60 p-4 md:order-1 md:max-h-[78vh] md:overflow-y-auto">
          <span className="absolute inset-x-0 top-0 h-0.5 bg-linear-to-r from-emerald-500 via-sky-500 to-violet-500" aria-hidden />
          {header}
          {narrative.length > 0 ? <div className="space-y-3">{narrative.map((node) => renderNode(node))}</div> : null}
        </div>

        {/* RIGHT — visual dashboard (mobile: on top) */}
        <div className="order-1 flex flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-950/50 p-4 md:order-2 md:max-h-[78vh] md:overflow-y-auto">
          {visualSections.map((section) => renderNode(section))}
        </div>
      </div>

      {/* Actions + sources span full width underneath. */}
      {footer.length > 0 ? <div className="space-y-3">{footer.map((node) => renderNode(node))}</div> : null}
    </div>
  )
}

export const flowPilotOpenUILibrary = createLibrary({
  root: 'AssistantDashboard',
  components: [
    AssistantDashboard,
    DashboardSection,
    TextBlock,
    SingleMetricCard,
    KpiGrid,
    KpiCard,
    BarChartCard,
    LineChartCard,
    PieChartCard,
    FunnelChartCard,
    SmartDataTable,
    PriorityLeadTable,
    AlertList,
    InsightList,
    RecommendationList,
    SuggestedActions,
    WorkflowHealthCard,
    SourceList,
    EmptyState,
    InsufficientDataState,
    ErrorState,
    LoadingState,
  ],
  componentGroups: [
    { name: 'Layout', components: ['AssistantDashboard', 'DashboardSection', 'TextBlock'] },
    { name: 'Metrics', components: ['SingleMetricCard', 'KpiGrid', 'KpiCard', 'BarChartCard', 'LineChartCard', 'PieChartCard', 'FunnelChartCard'] },
    { name: 'Data', components: ['SmartDataTable', 'PriorityLeadTable', 'WorkflowHealthCard', 'SourceList'] },
    { name: 'Guidance', components: ['AlertList', 'InsightList', 'RecommendationList', 'SuggestedActions', 'EmptyState', 'InsufficientDataState', 'ErrorState', 'LoadingState'] },
  ],
})

export const flowPilotOpenUIPrompt = flowPilotOpenUILibrary.prompt({
  preamble: 'You generate FlowPilot AI business dashboards with OpenUI Lang.',
  additionalRules: [
    'Always respond in the same language as the user.',
    'Use only values present in the provided validated backend payload.',
    'Never invent, recalculate, round, or modify KPI values.',
    'Never include SQL, JSON payloads, webhook names, internal IDs, workflow_execution_id, or agent_run_id.',
    'Use AssistantDashboard as root and keep dashboards concise.',
    'Use SingleMetricCard for short count questions and PriorityLeadTable for CRM hot leads.',
    'Use InsufficientDataState when the data volume is too low for trends.',
    'Use EmptyState when arrays are empty.',
    'Mutating actions must set requiresConfirmation to true.',
  ],
  examples: [
    'root = AssistantDashboard("Résumé CRM", "Le pipeline contient 12 leads.", [DashboardSection("Indicateurs", null, [KpiGrid([KpiCard("Leads", 12, "Total PostgreSQL", null, null, "info")])])])',
    'root = AssistantDashboard("Hot leads", "Deux leads nécessitent une action.", [DashboardSection("Priorités", null, [PriorityLeadTable("Leads prioritaires", "Liste validée", [{name: "Client A", company: "Société", score: 92, status: "hot"}], "Aucun lead prioritaire.")])])',
  ],
  toolCalls: false,
  bindings: false,
})
