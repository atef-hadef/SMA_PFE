import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon,
  title,
  description,
  action,
}) => {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center gap-4 py-12 text-center">
        {Icon && <Icon className="h-12 w-12 text-slate-300" />}
        <div>
          <h3 className="font-semibold text-slate-900">{title}</h3>
          {description && <p className="text-sm text-slate-600 mt-1">{description}</p>}
        </div>
        {action && (
          <button
            onClick={action.onClick}
            className="text-xs font-semibold text-blue-600 hover:text-blue-700 underline"
          >
            {action.label}
          </button>
        )}
      </CardContent>
    </Card>
  );
};
