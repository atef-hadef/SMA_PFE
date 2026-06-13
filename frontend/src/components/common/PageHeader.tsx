import type { ReactNode } from 'react'
import StatusBadge, { type StatusType } from './StatusBadge'

type PageHeaderProps = {
  eyebrow?: string
  title: string
  subtitle: string
  statusLabel?: string
  statusTone?: StatusType
  actions?: ReactNode
}

function PageHeader({
  eyebrow = 'FlowPilot AI',
  title,
  subtitle,
  statusLabel,
  statusTone = 'info',
  actions,
}: PageHeaderProps) {
  return (
    <section className="flex flex-col gap-4 rounded-xl border border-slate-800 bg-linear-to-br from-slate-900 via-slate-900 to-slate-950 p-6 shadow-xl shadow-slate-950/30 lg:flex-row lg:items-center lg:justify-between">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
          {eyebrow}
        </p>
        <h1 className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">
          {title}
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">{subtitle}</p>
      </div>
      <div className="flex flex-col items-start gap-3 lg:items-end">
        {statusLabel ? <StatusBadge label={statusLabel} status={statusTone} /> : null}
        {actions ? <div>{actions}</div> : null}
      </div>
    </section>
  )
}

export default PageHeader
