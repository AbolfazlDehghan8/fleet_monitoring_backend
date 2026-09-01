import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';

import { cn } from '@/utils/cn';

import { dismissToast, useToast } from './use-toast';

const ICONS = {
  default: Info,
  success: CheckCircle2,
  destructive: AlertTriangle,
};

export function Toaster() {
  const { toasts } = useToast();

  return (
    <div className="pointer-events-none fixed bottom-4 end-4 z-[100] flex w-full max-w-sm flex-col gap-2">
      <AnimatePresence initial={false}>
        {toasts.map((t) => {
          const Icon = ICONS[t.variant ?? 'default'];
          return (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 12, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40, scale: 0.96 }}
              transition={{ duration: 0.2 }}
              className={cn(
                'pointer-events-auto flex items-start gap-3 rounded-lg border border-border bg-card p-4 shadow-lg',
                t.variant === 'destructive' && 'border-destructive/40',
                t.variant === 'success' && 'border-success/40',
              )}
            >
              <Icon
                className={cn(
                  'mt-0.5 size-4 shrink-0',
                  t.variant === 'destructive' && 'text-destructive',
                  t.variant === 'success' && 'text-success',
                  (!t.variant || t.variant === 'default') && 'text-primary',
                )}
              />
              <div className="flex-1 space-y-0.5">
                {t.title && <p className="text-sm font-medium">{t.title}</p>}
                {t.description && <p className="text-xs text-muted-foreground">{t.description}</p>}
              </div>
              <button
                onClick={() => dismissToast(t.id)}
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                <X className="size-3.5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
