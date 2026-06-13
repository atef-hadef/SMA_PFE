import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { AlertCircle } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  fullHeight?: boolean;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Erreur',
  message = 'Une erreur est survenue. Veuillez réessayer.',
  onRetry,
  fullHeight = false,
}) => {
  return (
    <div className={fullHeight ? 'flex h-screen items-center justify-center' : 'p-8'}>
      <Card className="w-full max-w-md border-red-200 bg-red-50">
        <CardContent className="flex flex-col items-center gap-4 pt-8 pb-8">
          <AlertCircle className="h-12 w-12 text-red-600" />
          <div className="text-center">
            <h3 className="font-semibold text-red-900">{title}</h3>
            <p className="text-sm text-red-700 mt-2">{message}</p>
          </div>
          {onRetry && (
            <Button onClick={onRetry} variant="outline" size="sm" className="w-full">
              Réessayer
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
