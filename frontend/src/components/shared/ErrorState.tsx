import { AlertTriangle, RotateCw } from 'lucide-react';

import { useLanguage } from '@/app/LanguageContext';
import { Button } from '@/components/ui/button';

interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
}

export function ErrorState({ title, description, onRetry }: ErrorStateProps) {
  const { t } = useLanguage();
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-destructive/30 bg-destructive/5 py-16 text-center animate-in fade-in-0">
      <div className="flex size-12 items-center justify-center rounded-full bg-destructive/10">
        <AlertTriangle className="size-5 text-destructive" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium">{title ?? t('common.somethingWrong')}</p>
        <p className="max-w-sm text-sm text-muted-foreground">{description ?? t('common.couldNotLoad')}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw className="size-3.5" />
          {t('common.retry')}
        </Button>
      )}
    </div>
  );
}
