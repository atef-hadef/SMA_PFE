type LifecycleStage = {
  key: string
  label: string
}

type LifecycleStepperProps = {
  stages: LifecycleStage[]
  currentKey: string
  completedKeys?: string[]
}

function LifecycleStepper({
  stages,
  currentKey,
  completedKeys = [],
}: LifecycleStepperProps) {
  const completedSet = new Set(completedKeys)

  return (
    <ol className="flex flex-wrap items-start justify-between gap-y-4">
      {stages.map((stage, index) => {
        const isCurrent = stage.key === currentKey
        const isDone = completedSet.has(stage.key)
        const style = isCurrent
          ? 'bg-emerald-500 text-slate-950 border-emerald-400 shadow-lg shadow-emerald-500/20'
          : isDone
            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
            : 'bg-slate-900 text-slate-500 border-slate-800'

        const connectorStyle =
          isDone || isCurrent ? 'bg-emerald-500/40' : 'bg-slate-800'

        return (
          <li
            key={stage.key}
            className="flex items-center gap-2"
          >
            <div className="flex flex-col items-center text-center">
              <span
                className={`flex h-9 w-9 items-center justify-center rounded-full border text-xs font-bold transition ${style}`}
              >
                {isDone && !isCurrent ? '✓' : index + 1}
              </span>
              <span className="mt-2 w-20 text-center text-[11px] font-semibold leading-4 text-slate-300">
                {stage.label}
              </span>
            </div>
            {index < stages.length - 1 ? (
              <span className={`h-0.5 w-8 shrink-0 sm:w-12 ${connectorStyle}`} />
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}

export type { LifecycleStage }
export default LifecycleStepper
