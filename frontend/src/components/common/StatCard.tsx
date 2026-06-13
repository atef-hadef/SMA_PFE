import Icon, { type IconName } from './Icon'

type StatCardProps = {
  label: string
  value: string
  trend?: string
  icon?: IconName
}

function StatCard({ label, value, trend, icon }: StatCardProps) {
  return (
    <article className="rounded-xl border border-slate-800 bg-linear-to-br from-slate-900 to-slate-950 p-5 shadow-xl shadow-slate-950/30">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-slate-400">{label}</p>
          <p className="mt-3 text-3xl font-black tracking-tight text-white">{value}</p>
        </div>
        {icon ? (
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-linear-to-br from-emerald-500 to-emerald-600 text-white shadow-md shadow-emerald-500/20">
            <Icon name={icon} size={18} />
          </span>
        ) : null}
      </div>
      {trend ? (
        <p className="mt-3 inline-flex rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-200">
          {trend}
        </p>
      ) : null}
    </article>
  )
}

export default StatCard
