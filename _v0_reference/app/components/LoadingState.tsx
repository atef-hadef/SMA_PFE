import React from 'react';
import { Card, CardContent } from '@/components/ui/card';

interface LoadingStateProps {
  message?: string;
  fullHeight?: boolean;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Chargement...',
  fullHeight = false,
}) => {
  return (
    <div className={fullHeight ? 'flex h-screen items-center justify-center' : 'p-8'}>
      <Card className="w-full max-w-md">
        <CardContent className="flex flex-col items-center gap-4 pt-8 pb-8">
          <div className="flex gap-1">
            <div className="h-3 w-3 rounded-full bg-slate-400 animate-pulse"></div>
            <div className="h-3 w-3 rounded-full bg-slate-400 animate-pulse" style={{ animationDelay: '0.1s' }}></div>
            <div className="h-3 w-3 rounded-full bg-slate-400 animate-pulse" style={{ animationDelay: '0.2s' }}></div>
          </div>
          <p className="text-sm text-slate-600">{message}</p>
        </CardContent>
      </Card>
    </div>
  );
};
