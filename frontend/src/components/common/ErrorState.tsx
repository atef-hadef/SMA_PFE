import Icon from './Icon'

type ErrorStateProps = {
  title?: string
  message: string
  actionLabel?: string
  onAction?: () => void
  tone?: 'danger' | 'warning'
}

function ErrorState({
  title = 'Action impossible',
  message,
  actionLabel,
  onAction,
  tone = 'danger',
}: ErrorStateProps) {
  const toneClasses =
    tone === 'warning'
      ? 'border-amber-500/30 bg-amber-500/10 text-amber-100'
      : 'border-rose-500/30 bg-rose-500/10 text-rose-100'

  const iconToneClasses =
    tone === 'warning' ? 'text-amber-300' : 'text-rose-300'

  return (
    <div className={`rounded-xl border p-4 text-sm ${toneClasses}`}>
      <div className="flex items-start gap-3">
        <Icon name="alert" size={20} className={iconToneClasses} />
        <div>
          <p className="font-semibold">{title}</p>
          <p className="mt-1 leading-6 opacity-90">{message}</p>
          {actionLabel && onAction ? (
            <button
              type="button"
              onClick={onAction}
              className={`mt-3 inline-flex items-center rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                tone === 'warning'
                  ? 'border-amber-400/40 text-amber-100 hover:bg-amber-400/10'
                  : 'border-rose-400/40 text-rose-100 hover:bg-rose-400/10'
              }`}
            >
              {actionLabel}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export default ErrorState
