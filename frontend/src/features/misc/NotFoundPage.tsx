import { motion } from 'framer-motion';
import { Compass, Home } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { Button } from '@/components/ui/button';

export function NotFoundPage() {
  const { t } = useLanguage();
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-background px-4 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="flex size-20 items-center justify-center rounded-3xl bg-primary/10 text-primary"
      >
        <Compass className="size-9" />
      </motion.div>
      <div className="space-y-2">
        <p className="text-6xl font-bold tracking-tight text-primary/80">404</p>
        <h1 className="text-xl font-semibold">{t('misc.notFoundTitle')}</h1>
        <p className="max-w-sm text-sm text-muted-foreground">{t('misc.notFoundDesc')}</p>
      </div>
      <Button asChild>
        <Link to="/">
          <Home className="size-4" />
          {t('misc.backToDashboard')}
        </Link>
      </Button>
    </div>
  );
}
