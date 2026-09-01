import { motion } from 'framer-motion';
import { Home, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { Button } from '@/components/ui/button';

export function UnauthorizedPage() {
  const { t } = useLanguage();
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-background px-4 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="flex size-20 items-center justify-center rounded-3xl bg-destructive/10 text-destructive"
      >
        <ShieldAlert className="size-9" />
      </motion.div>
      <div className="space-y-2">
        <p className="text-6xl font-bold tracking-tight text-destructive/80">403</p>
        <h1 className="text-xl font-semibold">{t('misc.unauthorizedTitle')}</h1>
        <p className="max-w-sm text-sm text-muted-foreground">{t('misc.unauthorizedDesc')}</p>
      </div>
      <Button asChild variant="outline">
        <Link to="/">
          <Home className="size-4" />
          {t('misc.backToDashboard')}
        </Link>
      </Button>
    </div>
  );
}
