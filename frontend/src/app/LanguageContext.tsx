import * as React from 'react';

import { translations, type TranslationKey } from '@/i18n/translations';

export type Language = 'en' | 'fa';

interface LanguageContextValue {
  language: Language;
  dir: 'ltr' | 'rtl';
  toggleLanguage: () => void;
  setLanguage: (lang: Language) => void;
  /** Translate a key. Falls back to the key itself if missing. */
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string;
}

const LanguageContext = React.createContext<LanguageContextValue | undefined>(undefined);

const STORAGE_KEY = 'fleet.ui.language';

function getInitialLanguage(): Language {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'en' || stored === 'fa') return stored;
  return navigator.language?.toLowerCase().startsWith('fa') ? 'fa' : 'en';
}

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return Object.keys(vars).reduce(
    (acc, key) => acc.replace(new RegExp(`\\{${key}\\}`, 'g'), String(vars[key])),
    template,
  );
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = React.useState<Language>(getInitialLanguage);

  const dir: 'ltr' | 'rtl' = language === 'fa' ? 'rtl' : 'ltr';

  React.useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('lang', language === 'fa' ? 'fa-IR' : 'en');
    root.setAttribute('dir', dir);
    root.classList.toggle('font-fa', language === 'fa');
    localStorage.setItem(STORAGE_KEY, language);
  }, [language, dir]);

  const setLanguage = React.useCallback((lang: Language) => setLanguageState(lang), []);

  const toggleLanguage = React.useCallback(() => {
    setLanguageState((current) => (current === 'en' ? 'fa' : 'en'));
  }, []);

  const t = React.useCallback(
    (key: TranslationKey, vars?: Record<string, string | number>) => {
      const dict = translations[language] ?? translations.en;
      const value = dict[key] ?? translations.en[key] ?? key;
      return interpolate(value, vars);
    },
    [language],
  );

  const value = React.useMemo(
    () => ({ language, dir, toggleLanguage, setLanguage, t }),
    [language, dir, toggleLanguage, setLanguage, t],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage(): LanguageContextValue {
  const context = React.useContext(LanguageContext);
  if (!context) throw new Error('useLanguage must be used within a LanguageProvider');
  return context;
}
