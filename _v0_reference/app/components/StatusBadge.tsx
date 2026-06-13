import React from 'react';
import { Badge } from '@/components/ui/badge';

export type StatusType = 'pending' | 'approved' | 'rejected' | 'processing' | 'completed' | 'draft';
export type PriorityType = 'low' | 'medium' | 'high' | 'urgent';

interface StatusBadgeProps {
  status: StatusType;
  label?: string;
}

interface PriorityBadgeProps {
  priority: PriorityType;
  label?: string;
}

const statusConfig: Record<StatusType, { label: string; variant: any }> = {
  pending: { label: 'En attente', variant: 'secondary' },
  approved: { label: 'Approuvé', variant: 'default' },
  rejected: { label: 'Rejeté', variant: 'destructive' },
  processing: { label: 'En traitement', variant: 'outline' },
  completed: { label: 'Complété', variant: 'secondary' },
  draft: { label: 'Brouillon', variant: 'secondary' },
};

const priorityConfig: Record<PriorityType, { label: string; className: string }> = {
  low: { label: 'Basse', className: 'bg-blue-100 text-blue-800' },
  medium: { label: 'Moyenne', className: 'bg-amber-100 text-amber-800' },
  high: { label: 'Haute', className: 'bg-orange-100 text-orange-800' },
  urgent: { label: 'Urgente', className: 'bg-red-100 text-red-800' },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label }) => {
  const config = statusConfig[status];
  return (
    <Badge variant={config.variant} className="whitespace-nowrap">
      {label || config.label}
    </Badge>
  );
};

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority, label }) => {
  const config = priorityConfig[priority];
  return (
    <span className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${config.className}`}>
      {label || config.label}
    </span>
  );
};
