import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { LucideIcon } from 'lucide-react';

export interface TimelineEvent {
  id: string;
  title: string;
  description?: string;
  timestamp: Date;
  icon?: LucideIcon;
  type: 'action' | 'system' | 'approval' | 'info';
}

interface ActivityTimelineProps {
  events: TimelineEvent[];
  title?: string;
  emptyMessage?: string;
}

const typeColors = {
  action: 'bg-blue-100 text-blue-700 border-blue-300',
  system: 'bg-slate-100 text-slate-700 border-slate-300',
  approval: 'bg-emerald-100 text-emerald-700 border-emerald-300',
  info: 'bg-amber-100 text-amber-700 border-amber-300',
};

export const ActivityTimeline: React.FC<ActivityTimelineProps> = ({
  events,
  title = 'Activité récente',
  emptyMessage = 'Aucune activité',
}) => {
  if (events.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-slate-500">{emptyMessage}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {events.map((event, index) => {
            const Icon = event.icon;
            return (
              <div key={event.id} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-full border-2 ${typeColors[event.type]}`}
                  >
                    {Icon ? (
                      <Icon className="h-4 w-4" />
                    ) : (
                      <div className="h-2 w-2 rounded-full bg-current" />
                    )}
                  </div>
                  {index < events.length - 1 && <div className="my-2 h-8 w-1 bg-slate-200" />}
                </div>
                <div className="pb-4 pt-1">
                  <p className="text-sm font-medium text-slate-900">{event.title}</p>
                  {event.description && (
                    <p className="text-xs text-slate-600">{event.description}</p>
                  )}
                  <p className="text-xs text-slate-500">
                    {event.timestamp.toLocaleString('fr-FR', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};
