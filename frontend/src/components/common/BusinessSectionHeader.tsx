import type { ReactNode } from 'react'

type BusinessSectionHeaderProps = {
  title: string
  description?: string
  actions?: ReactNode
  eyebrow?: string
}

function BusinessSectionHeader({
  title,
  description,
  actions,
  eyebrow,
}: BusinessSectionHeaderProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
            {eyebrow}
          </p>
        ) : null}
        <h2 className="mt-1 text-xl font-bold text-white">{title}</h2>
        {description ? (
          <p className="mt-1 max-w-3xl text-sm text-slate-400">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </div>
  )
}

export default BusinessSectionHeader
