type StatusType = 'success' | 'warning' | 'danger' | 'info' | 'neutral'

type StatusBadgeProps = {
  label: string
  status?: StatusType
  size?: 'sm' | 'md'
}

const styles: Record<StatusType, string> = {
  success: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  warning: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  danger: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  info: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  neutral: 'bg-slate-700/40 text-slate-300 border-slate-600/60',
}

function StatusBadge({ label, status = 'info', size = 'md' }: StatusBadgeProps) {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs'
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-md border font-semibold ${sizeClasses} ${styles[status]}`}
    >
      {label}
    </span>
  )
}

export type { StatusType }
export default StatusBadge
