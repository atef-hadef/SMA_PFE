import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

interface TechnicalDetailsProps {
  title?: string;
  children: React.ReactNode;
}

export const TechnicalDetails: React.FC<TechnicalDetailsProps> = ({
  title = 'Détails techniques',
  children,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="border-t pt-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-xs font-semibold text-slate-600 hover:text-slate-900 transition"
      >
        <ChevronDown
          className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
        {title}
      </button>
      {isOpen && <div className="mt-4 space-y-2 text-xs text-slate-600">{children}</div>}
    </div>
  );
};
