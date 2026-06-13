import type { ReactNode } from 'react'

type ActionButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'urgent'

type ActionButtonProps = {
  label: ReactNode
  onClick?: () => void
  variant?: ActionButtonVariant
  disabled?: boolean
  title?: string
  type?: 'button' | 'submit' | 'reset'
  fullWidth?: boolean
  size?: 'sm' | 'md'
}

const variantClasses: Record<ActionButtonVariant, string> = {
  primary:
    'border border-emerald-400 bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20 hover:bg-emerald-400 disabled:bg-slate-700 disabled:text-slate-400 disabled:border-slate-700',
  secondary:
    'border border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700 disabled:text-slate-500',
  ghost:
    'border border-transparent text-slate-300 hover:bg-slate-800/60 hover:text-white disabled:text-slate-600',
  danger:
    'border border-rose-500/50 bg-rose-500/15 text-rose-200 hover:bg-rose-500/25 disabled:text-slate-500',
  urgent:
    'border border-amber-300 bg-amber-400 text-slate-950 shadow-md shadow-amber-500/30 hover:bg-amber-300 disabled:bg-slate-700 disabled:text-slate-400 disabled:border-slate-700',
}

function ActionButton({
  label,
  onClick,
  variant = 'primary',
  disabled = false,
  title,
  type = 'button',
  fullWidth = false,
  size = 'md',
}: ActionButtonProps) {
  const sizeClasses = size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm'
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg font-semibold transition disabled:cursor-not-allowed ${sizeClasses} ${variantClasses[variant]} ${fullWidth ? 'w-full' : ''}`}
    >
      {label}
    </button>
  )
}

export type { ActionButtonVariant }
export default ActionButton
