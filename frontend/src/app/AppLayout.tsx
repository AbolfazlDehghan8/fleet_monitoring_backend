import * as React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Truck, X } from 'lucide-react';
import { Outlet, useLocation } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { Navbar } from '@/components/shared/Navbar';
import { Sidebar } from '@/components/shared/Sidebar';
import { useAuth } from '@/features/auth/AuthContext';

export function AppLayout() {
  const { user } = useAuth();
  const { t, dir } = useLanguage();
  const [mobileNavOpen, setMobileNavOpen] = React.useState(false);
  const location = useLocation();
  const drawerOffscreenX = dir === 'rtl' ? 280 : -280;

  React.useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  if (!user) return null;

  return (
    <div className="flex min-h-dvh bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-e border-border bg-sidebar lg:flex lg:flex-col">
        <div className="flex h-14 items-center gap-2 border-b border-sidebar-foreground/10 px-4 font-semibold text-sidebar-foreground">
          <Truck className="size-5 text-primary" />
          {t('app.shortName')}
        </div>
        <Sidebar role={user.role} className="flex-1" />
        <div className="border-t border-sidebar-foreground/10 px-4 py-3 text-xs text-sidebar-foreground/50">
          {t('app.version')}
        </div>
      </aside>

      {/* Mobile sidebar */}
      <AnimatePresence>
        {mobileNavOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm lg:hidden"
              onClick={() => setMobileNavOpen(false)}
            />
            <motion.aside
              initial={{ x: drawerOffscreenX }}
              animate={{ x: 0 }}
              exit={{ x: drawerOffscreenX }}
              transition={{ type: 'tween', duration: 0.25 }}
              className="fixed inset-y-0 start-0 z-50 flex w-64 flex-col bg-sidebar lg:hidden"
            >
              <div className="flex h-14 items-center justify-between border-b border-sidebar-foreground/10 px-4 font-semibold text-sidebar-foreground">
                <span className="flex items-center gap-2">
                  <Truck className="size-5 text-primary" />
                  {t('app.shortName')}
                </span>
                <button onClick={() => setMobileNavOpen(false)}>
                  <X className="size-5 text-sidebar-foreground/70" />
                </button>
              </div>
              <Sidebar role={user.role} className="flex-1" />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <Navbar onMenuClick={() => setMobileNavOpen(true)} />
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="mx-auto max-w-7xl space-y-6"
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  );
}
