type BadgeTone = 'green' | 'orange' | 'red' | 'blue' | 'slate' | 'purple'

type PriorityBadgeProps = {
  label: string
  tone?: BadgeTone
  withDot?: boolean
  size?: 'sm' | 'md'
}

const toneClasses: Record<BadgeTone, string> = {
  green: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  orange: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  red: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  blue: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  slate: 'bg-slate-700/40 text-slate-300 border-slate-600/60',
  purple: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
}

const dotClasses: Record<BadgeTone, string> = {
  green: 'bg-emerald-400',
  orange: 'bg-amber-400',
  red: 'bg-rose-400',
  blue: 'bg-sky-400',
  slate: 'bg-slate-400',
  purple: 'bg-violet-400',
}

function PriorityBadge({
  label,
  tone = 'blue',
  withDot = false,
  size = 'md',
}: PriorityBadgeProps) {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs'
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border font-semibold ${sizeClasses} ${toneClasses[tone]}`}
    >
      {withDot ? (
        <span className={`h-1.5 w-1.5 rounded-full ${dotClasses[tone]}`} />
      ) : null}
      {label}
    </span>
  )
}

export type { BadgeTone }
export default PriorityBadge
