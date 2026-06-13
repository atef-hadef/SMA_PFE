import type { ReactNode } from 'react'

type TechnicalDetailsPanelProps = {
  title?: string
  children: ReactNode
  className?: string
}

function TechnicalDetailsPanel({
  title = 'Détails techniques',
  children,
  className = '',
}: TechnicalDetailsPanelProps) {
  return (
    <details
      className={`group overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 ${className}`}
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold text-slate-300 transition hover:bg-slate-800/60 hover:text-white">
        <span className="inline-flex items-center gap-2">
          <span className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-slate-700 bg-slate-950 text-[11px] text-slate-400 group-open:text-emerald-200">
            i
          </span>
          {title}
        </span>
        <span className="text-slate-500 transition group-open:rotate-180">⌄</span>
      </summary>
      <div className="border-t border-slate-800 bg-slate-950/50 p-4 text-sm leading-6 text-slate-400">
        {children}
      </div>
    </details>
  )
}

export default TechnicalDetailsPanel
