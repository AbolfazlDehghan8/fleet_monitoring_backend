import { Languages } from 'lucide-react';

import { useLanguage } from '@/app/LanguageContext';
import { Button } from '@/components/ui/button';

export function LanguageToggle() {
  const { language, toggleLanguage, t } = useLanguage();

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleLanguage}
      aria-label={t('navbar.toggleLanguage')}
      title={t('navbar.toggleLanguage')}
      className="relative"
    >
      <Languages className="size-4" />
      <span className="absolute -bottom-0.5 -right-0.5 rounded bg-primary px-1 text-[9px] font-bold leading-tight text-primary-foreground">
        {language === 'en' ? 'FA' : 'EN'}
      </span>
    </Button>
  );
}
