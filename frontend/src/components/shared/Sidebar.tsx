import {
  AlertTriangle,
  FileBarChart,
  LayoutDashboard,
  ListChecks,
  Radio,
  ShieldCheck,
  Truck,
  Users,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { ROLES, type Role } from '@/constants/roles';
import type { TranslationKey } from '@/i18n/translations';
import { cn } from '@/utils/cn';

interface NavItem {
  to: string;
  labelKey: TranslationKey;
  icon: typeof LayoutDashboard;
  roles?: Role[];
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', labelKey: 'nav.dashboard', icon: LayoutDashboard },
  { to: '/vehicles', labelKey: 'nav.vehicles', icon: Truck, roles: [ROLES.ADMIN, ROLES.FLEET_MANAGER] },
  { to: '/drivers', labelKey: 'nav.drivers', icon: Users, roles: [ROLES.ADMIN, ROLES.FLEET_MANAGER] },
  { to: '/telemetry', labelKey: 'nav.telemetry', icon: Radio, roles: [ROLES.ADMIN, ROLES.FLEET_MANAGER] },
  { to: '/alerts', labelKey: 'nav.alerts', icon: AlertTriangle, roles: [ROLES.ADMIN, ROLES.FLEET_MANAGER] },
  { to: '/my-alerts', labelKey: 'nav.alerts', icon: AlertTriangle, roles: [ROLES.DRIVER] },
  { to: '/rules', labelKey: 'nav.rules', icon: ListChecks, roles: [ROLES.ADMIN] },
  { to: '/reports', labelKey: 'nav.reports', icon: FileBarChart, roles: [ROLES.ADMIN, ROLES.FLEET_MANAGER] },
  { to: '/admin/users', labelKey: 'nav.users', icon: ShieldCheck, roles: [ROLES.ADMIN] },
];

export function Sidebar({ role, className }: { role: Role; className?: string }) {
  const { t } = useLanguage();
  const items = NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(role));

  return (
    <nav className={cn('flex flex-col gap-1 px-3 py-4', className)}>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-sidebar-foreground/10 text-sidebar-foreground'
                : 'text-sidebar-foreground/60 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground',
            )
          }
        >
          <item.icon className="size-4 shrink-0" />
          {t(item.labelKey)}
        </NavLink>
      ))}
    </nav>
  );
}
