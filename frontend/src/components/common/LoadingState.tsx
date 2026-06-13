type LoadingStateProps = {
  message?: string
  fullHeight?: boolean
}

function LoadingState({ message = 'Chargement...', fullHeight = false }: LoadingStateProps) {
  return (
    <div
      className={`${fullHeight ? 'flex h-full min-h-60 items-center justify-center' : ''}`}
    >
      <div className="inline-flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-sm font-medium text-slate-200 shadow-md">
        <span className="inline-flex gap-1">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          <span
            className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400"
            style={{ animationDelay: '120ms' }}
          />
          <span
            className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400"
            style={{ animationDelay: '240ms' }}
          />
        </span>
        {message}
      </div>
    </div>
  )
}

export default LoadingState
