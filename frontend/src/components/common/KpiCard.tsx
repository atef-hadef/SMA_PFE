import type { ReactNode } from 'react'
import Icon, { type IconName } from './Icon'

type KpiTone = 'emerald' | 'sky' | 'violet' | 'amber' | 'rose' | 'slate'

type KpiCardProps = {
  label: string
  value: ReactNode
  trend?: string
  trendDirection?: 'up' | 'down' | 'flat'
  helper?: string
  tone?: KpiTone
  icon?: IconName
}

const gradientByTone: Record<KpiTone, string> = {
  emerald: 'from-emerald-500 to-emerald-600',
  sky: 'from-sky-500 to-blue-600',
  violet: 'from-violet-500 to-indigo-600',
  amber: 'from-amber-500 to-orange-500',
  rose: 'from-rose-500 to-red-600',
  slate: 'from-slate-500 to-slate-600',
}

const trendIconByDirection: Record<
  NonNullable<KpiCardProps['trendDirection']>,
  IconName
> = {
  up: 'trending-up',
  down: 'trending-down',
  flat: 'activity',
}

function KpiCard({
  label,
  value,
  trend,
  trendDirection = 'up',
  helper,
  tone = 'emerald',
  icon,
}: KpiCardProps) {
  const gradient = gradientByTone[tone]

  return (
    <article className="rounded-xl border border-slate-800 bg-linear-to-br from-slate-900 to-slate-950 p-5 shadow-xl shadow-slate-950/30 transition hover:border-slate-700">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-400">{label}</p>
          <p className="mt-3 text-3xl font-black tracking-tight text-white">{value}</p>
          {helper ? <p className="mt-2 text-xs leading-5 text-slate-500">{helper}</p> : null}
        </div>
        {icon ? (
          <span
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-linear-to-br text-white shadow-lg ${gradient}`}
          >
            <Icon name={icon} size={18} />
          </span>
        ) : null}
      </div>
      {trend ? (
        <div className="mt-4 flex items-center">
          <span
            className={`inline-flex items-center gap-1 rounded-lg bg-linear-to-br px-2.5 py-1 text-xs font-semibold text-white shadow-sm ${gradient}`}
          >
            <Icon name={trendIconByDirection[trendDirection]} size={14} />
            {trend}
          </span>
        </div>
      ) : null}
    </article>
  )
}

export type { KpiTone }
export default KpiCard
