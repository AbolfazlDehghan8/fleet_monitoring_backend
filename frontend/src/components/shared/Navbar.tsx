import { LogOut, Menu, Truck, User as UserIcon } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { LanguageToggle } from '@/components/shared/LanguageToggle';
import { ThemeToggle } from '@/components/shared/ThemeToggle';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useAuth } from '@/features/auth/AuthContext';
import { initials } from '@/utils/formatters';

export function Navbar({ onMenuClick }: { onMenuClick: () => void }) {
  const { user, logout } = useAuth();
  const { t } = useLanguage();

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur-md">
      <Button variant="ghost" size="icon" className="lg:hidden" onClick={onMenuClick}>
        <Menu className="size-5" />
      </Button>

      <div className="flex items-center gap-2 font-semibold lg:hidden">
        <Truck className="size-4 text-primary" />
        {t('app.shortName')}
      </div>

      <div className="ms-auto flex items-center gap-2">
        <LanguageToggle />
        <ThemeToggle />

        {user && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="gap-2 px-2">
                <span className="flex size-7 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                  {initials(user.first_name, user.last_name, user.username[0]?.toUpperCase())}
                </span>
                <span className="hidden text-sm font-medium sm:inline">{user.username}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="space-y-0.5">
                <p className="text-sm font-medium text-foreground">
                  {user.first_name || user.last_name ? `${user.first_name} ${user.last_name}`.trim() : user.username}
                </p>
                <p className="text-xs font-normal text-muted-foreground">{t(`role.${user.role}`)}</p>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/profile">
                  <UserIcon className="size-4" />
                  {t('navbar.profile')}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => void logout()} className="text-destructive focus:text-destructive">
                <LogOut className="size-4" />
                {t('navbar.signOut')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </header>
  );
}
