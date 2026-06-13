import type { ReactNode } from 'react'

type AppCardTone = 'default' | 'muted' | 'success' | 'warning' | 'danger' | 'info'

type AppCardProps = {
  children: ReactNode
  title?: string
  eyebrow?: string
  description?: string
  actions?: ReactNode
  className?: string
  bodyClassName?: string
  tone?: AppCardTone
}

const toneClasses: Record<AppCardTone, string> = {
  default:
    'border-slate-800 bg-linear-to-br from-slate-900 to-slate-950 shadow-slate-950/30',
  muted: 'border-slate-800 bg-slate-950/60 shadow-slate-950/20',
  success: 'border-emerald-500/30 bg-emerald-950/20 shadow-emerald-950/10',
  warning: 'border-amber-500/30 bg-amber-950/20 shadow-amber-950/10',
  danger: 'border-rose-500/30 bg-rose-950/20 shadow-rose-950/10',
  info: 'border-sky-500/30 bg-sky-950/20 shadow-sky-950/10',
}

function AppCard({
  children,
  title,
  eyebrow,
  description,
  actions,
  className = '',
  bodyClassName = '',
  tone = 'default',
}: AppCardProps) {
  const hasHeader = title || eyebrow || description || actions

  return (
    <section
      className={`overflow-hidden rounded-xl border shadow-xl ${toneClasses[tone]} ${className}`}
    >
      {hasHeader ? (
        <div className="flex flex-col gap-3 border-b border-slate-800 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            {eyebrow ? (
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
                {eyebrow}
              </p>
            ) : null}
            {title ? (
              <h2 className="mt-1 text-lg font-semibold text-white">{title}</h2>
            ) : null}
            {description ? (
              <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
                {description}
              </p>
            ) : null}
          </div>
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      ) : null}
      <div className={bodyClassName || 'p-5'}>{children}</div>
    </section>
  )
}

export type { AppCardTone }
export default AppCard
