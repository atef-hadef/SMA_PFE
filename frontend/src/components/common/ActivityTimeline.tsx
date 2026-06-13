import type { ReactNode } from 'react'

type TimelineTone = 'green' | 'orange' | 'red' | 'blue' | 'slate' | 'purple'

type ActivityTimelineItem = {
  id: string
  title: string
  description?: string
  time?: string
  tone?: TimelineTone
  meta?: ReactNode
}

type ActivityTimelineProps = {
  items: ActivityTimelineItem[]
  emptyTitle?: string
  emptyDescription?: string
}

const dotClasses: Record<TimelineTone, string> = {
  green: 'bg-emerald-400',
  orange: 'bg-amber-400',
  red: 'bg-rose-400',
  blue: 'bg-sky-400',
  slate: 'bg-slate-400',
  purple: 'bg-violet-400',
}

function ActivityTimeline({
  items,
  emptyTitle = 'Aucune activité récente',
  emptyDescription = 'Les nouveaux événements apparaîtront ici.',
}: ActivityTimelineProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-700 bg-slate-950/40 p-5 text-center">
        <p className="font-semibold text-white">{emptyTitle}</p>
        <p className="mt-1 text-sm text-slate-400">{emptyDescription}</p>
      </div>
    )
  }

  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li
          key={item.id}
          className="flex items-start justify-between gap-3 border-b border-slate-800 pb-3 last:border-0 last:pb-0"
        >
          <div className="flex min-w-0 items-start gap-3">
            <span
              className={`mt-2 h-2 w-2 shrink-0 rounded-full ${dotClasses[item.tone ?? 'blue']}`}
            />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{item.title}</p>
              {item.description ? (
                <p className="mt-0.5 text-xs leading-5 text-slate-400">{item.description}</p>
              ) : null}
              {item.meta ? <div className="mt-2">{item.meta}</div> : null}
            </div>
          </div>
          {item.time ? (
            <span className="shrink-0 text-xs text-slate-500">{item.time}</span>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

export type { ActivityTimelineItem, TimelineTone }
export default ActivityTimeline
