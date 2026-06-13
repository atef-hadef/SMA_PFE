type ProcessStepStatus = 'done' | 'active' | 'pending' | 'blocked'

type ProcessStep = {
  label: string
  description?: string
  status?: ProcessStepStatus
}

type ProcessStepperProps = {
  steps: ProcessStep[]
  orientation?: 'vertical' | 'horizontal'
}

const statusClasses: Record<ProcessStepStatus, string> = {
  done: 'border-emerald-500/40 bg-emerald-500/20 text-emerald-300',
  active: 'border-sky-500/40 bg-sky-500/20 text-sky-300',
  pending: 'border-slate-700 bg-slate-900 text-slate-500',
  blocked: 'border-rose-500/40 bg-rose-500/20 text-rose-300',
}

const connectorClasses: Record<ProcessStepStatus, string> = {
  done: 'bg-emerald-500/40',
  active: 'bg-sky-500/30',
  pending: 'bg-slate-800',
  blocked: 'bg-rose-500/30',
}

function ProcessStepper({ steps, orientation = 'vertical' }: ProcessStepperProps) {
  if (orientation === 'horizontal') {
    return (
      <ol className="flex items-center gap-1 overflow-x-auto pb-2">
        {steps.map((step, index) => {
          const status = step.status ?? 'pending'
          return (
            <li key={`${step.label}-${index}`} className="flex min-w-0 items-center gap-2">
              <div className="flex flex-col items-center text-center">
                <span
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-xs font-bold ${statusClasses[status]}`}
                >
                  {status === 'done' ? '✓' : index + 1}
                </span>
                <span className="mt-2 w-28 truncate text-[11px] font-medium text-slate-300">
                  {step.label}
                </span>
              </div>
              {index < steps.length - 1 ? (
                <span className={`h-0.5 w-10 shrink-0 ${connectorClasses[status]}`} />
              ) : null}
            </li>
          )
        })}
      </ol>
    )
  }

  return (
    <ol className="space-y-3">
      {steps.map((step, index) => {
        const status = step.status ?? 'pending'
        return (
          <li
            key={`${step.label}-${index}`}
            className="flex gap-3 rounded-lg border border-slate-800 bg-slate-900/50 p-3"
          >
            <span
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-bold ${statusClasses[status]}`}
            >
              {status === 'done' ? '✓' : index + 1}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white">{step.label}</p>
              {step.description ? (
                <p className="mt-1 text-xs leading-5 text-slate-400">{step.description}</p>
              ) : null}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

export type { ProcessStep, ProcessStepStatus }
export default ProcessStepper
