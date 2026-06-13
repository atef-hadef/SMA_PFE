/**
 * Lightweight, dependency-free SVG charts for the analytics dashboard.
 * Dark-theme, responsive (viewBox-based), no external charting library.
 */

export const CHART_COLORS = [
  '#34d399', // emerald
  '#38bdf8', // sky
  '#a78bfa', // violet
  '#fbbf24', // amber
  '#fb7185', // rose
  '#2dd4bf', // teal
  '#fb923c', // orange
  '#818cf8', // indigo
]

export type ChartDatum = {
  label: string
  value: number
  color?: string
}

function isEmpty(data: ChartDatum[]): boolean {
  return data.length === 0 || data.every((d) => !d.value || d.value <= 0)
}

function EmptyChart({ message = 'Aucune donnée disponible' }: { message?: string }) {
  return (
    <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-slate-800 text-xs text-slate-500">
      {message}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Donut chart with centred total + legend
// ---------------------------------------------------------------------------
export function DonutChart({
  data,
  centerLabel,
  thickness = 14,
}: {
  data: ChartDatum[]
  centerLabel?: string
  thickness?: number
}) {
  if (isEmpty(data)) return <EmptyChart />

  const total = data.reduce((sum, d) => sum + Math.max(0, d.value), 0)
  const size = 120
  const r = (size - thickness) / 2
  const c = 2 * Math.PI * r
  let offset = 0

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:gap-6">
      <div className="relative shrink-0">
        <svg viewBox={`0 0 ${size} ${size}`} className="h-36 w-36 -rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" className="stroke-slate-800" strokeWidth={thickness} />
          {data.map((d, i) => {
            const value = Math.max(0, d.value)
            const dash = (value / total) * c
            const color = d.color ?? CHART_COLORS[i % CHART_COLORS.length]
            const circle = (
              <circle
                key={d.label}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={color}
                strokeWidth={thickness}
                strokeDasharray={`${dash} ${c - dash}`}
                strokeDashoffset={-offset}
                strokeLinecap="round"
              />
            )
            offset += dash
            return circle
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-black text-white">{total}</span>
          {centerLabel ? <span className="text-[10px] uppercase tracking-wider text-slate-500">{centerLabel}</span> : null}
        </div>
      </div>
      <ul className="flex w-full flex-col gap-2">
        {data.map((d, i) => {
          const color = d.color ?? CHART_COLORS[i % CHART_COLORS.length]
          const pct = total > 0 ? Math.round((d.value / total) * 100) : 0
          return (
            <li key={d.label} className="flex items-center justify-between gap-3 text-sm">
              <span className="flex items-center gap-2 text-slate-300">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                {d.label}
              </span>
              <span className="font-semibold text-white">
                {d.value} <span className="text-xs font-normal text-slate-500">({pct}%)</span>
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Vertical bar chart with value labels (pixel heights = always renders)
// ---------------------------------------------------------------------------
export function BarChart({ data }: { data: ChartDatum[] }) {
  if (isEmpty(data)) return <EmptyChart />

  const max = Math.max(...data.map((d) => d.value), 1)
  const PLOT = 180
  const BAR_MAX = PLOT - 28 // leave room for the value label above the bar

  return (
    <div>
      <div className="flex items-end gap-3 sm:gap-5" style={{ height: PLOT }}>
        {data.map((d, i) => {
          const color = d.color ?? CHART_COLORS[i % CHART_COLORS.length]
          const barHeight = Math.max(6, Math.round((d.value / max) * BAR_MAX))
          return (
            <div key={d.label} className="flex min-w-0 flex-1 flex-col items-center justify-end gap-2">
              <span className="text-sm font-bold text-white">{d.value}</span>
              <div
                className="w-full max-w-18 rounded-t-lg shadow-lg transition-all"
                style={{ height: barHeight, background: `linear-gradient(to top, ${color}, ${color}aa)` }}
              />
            </div>
          )
        })}
      </div>
      <div className="mt-2 flex gap-3 border-t border-slate-800 pt-2.5 sm:gap-5">
        {data.map((d) => (
          <span
            key={d.label}
            className="min-w-0 flex-1 truncate text-center text-[11px] font-medium text-slate-400"
            title={d.label}
          >
            {d.label}
          </span>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Area / line trend chart (time series)
// ---------------------------------------------------------------------------
export function AreaChart({
  data,
  color = CHART_COLORS[0],
  height = 200,
}: {
  data: ChartDatum[]
  color?: string
  height?: number
}) {
  if (data.length < 2) return <EmptyChart message="Pas assez de points pour une tendance" />

  const width = 600
  const padX = 8
  const padY = 24
  const max = Math.max(...data.map((d) => d.value), 1)
  const stepX = (width - padX * 2) / (data.length - 1)
  const scaleY = (v: number) => height - padY - (v / max) * (height - padY * 2)

  const points = data.map((d, i) => ({ x: padX + i * stepX, y: scaleY(d.value), datum: d }))
  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  const area = `${line} L${points[points.length - 1].x.toFixed(1)},${height - padY} L${points[0].x.toFixed(1)},${height - padY} Z`
  const gradId = `area-grad-${color.replace('#', '')}`

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((g) => (
          <line key={g} x1={padX} x2={width - padX} y1={padY + g * (height - padY * 2)} y2={padY + g * (height - padY * 2)} className="stroke-slate-800" strokeWidth={1} />
        ))}
        <path d={area} fill={`url(#${gradId})`} />
        <path d={line} fill="none" stroke={color} strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
        {points.map((p) => (
          <circle key={p.datum.label} cx={p.x} cy={p.y} r={3} className="fill-slate-900" stroke={color} strokeWidth={2} />
        ))}
      </svg>
      <div className="mt-1 flex justify-between px-1 text-[10px] text-slate-500">
        {data.map((d) => (
          <span key={d.label} className="flex-1 truncate text-center">
            {d.label}
          </span>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Funnel chart (conversion stages)
// ---------------------------------------------------------------------------
export function FunnelChart({ data }: { data: ChartDatum[] }) {
  if (isEmpty(data)) return <EmptyChart />

  const top = data[0]?.value || 1

  return (
    <div className="flex flex-col items-center gap-1 py-1">
      {data.map((d, i) => {
        const color = d.color ?? CHART_COLORS[i % CHART_COLORS.length]
        const widthPct = Math.max(16, Math.round((d.value / top) * 100))
        const ofTotal = top > 0 ? Math.round((d.value / top) * 100) : 0
        const prev = i > 0 ? data[i - 1].value : null
        const conv = prev && prev > 0 ? Math.round((d.value / prev) * 100) : null
        return (
          <div key={d.label} className="flex w-full flex-col items-center">
            {conv !== null ? (
              <span className="py-1.5 text-[11px] font-semibold text-slate-500">↓ {conv}% de conversion</span>
            ) : null}
            <div
              className="flex items-center justify-between gap-3 rounded-lg px-5 py-3.5 shadow-lg transition-all"
              style={{
                width: `${widthPct}%`,
                minWidth: '150px',
                background: `linear-gradient(135deg, ${color}, ${color}aa)`,
              }}
            >
              <span className="text-sm font-semibold text-[#0b1220]">{d.label}</span>
              <span className="flex items-baseline gap-1.5">
                <span className="text-lg font-black text-[#0b1220]">{d.value}</span>
                <span className="text-[11px] font-semibold text-[#0b1220]/70">{ofTotal}%</span>
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
