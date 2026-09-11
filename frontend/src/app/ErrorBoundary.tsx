import * as React from 'react';
import { AlertTriangle, RotateCw } from 'lucide-react';

import { Button } from '@/components/ui/button';

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

const COPY = {
  en: {
    title: 'Something went wrong',
    description:
      'This page hit an unexpected error. Your data is safe — try reloading, and if it keeps happening, use the button below to report it.',
    reload: 'Reload page',
    goHome: 'Go to dashboard',
  },
  fa: {
    title: 'یک خطای غیرمنتظره رخ داد',
    description:
      'این صفحه با یک خطای غیرمنتظره مواجه شد. اطلاعات شما در امان است — دوباره صفحه را بارگذاری کنید و اگر ادامه داشت، از دکمه‌ی زیر برای گزارش استفاده کنید.',
    reload: 'بارگذاری مجدد صفحه',
    goHome: 'رفتن به داشبورد',
  },
} as const;

/**
 * Deliberately does NOT depend on LanguageContext/useLanguage: this boundary can
 * catch crashes that originate inside the providers themselves, so it reads the
 * persisted language preference directly (see app/LanguageContext.tsx STORAGE_KEY)
 * instead of relying on a context that may not have mounted successfully.
 */
function getCopy() {
  try {
    const stored = localStorage.getItem('fleet.ui.language');
    return stored === 'fa' ? COPY.fa : COPY.en;
  } catch {
    return COPY.en;
  }
}

/**
 * Top-level safety net. Without this, any uncaught render error (e.g. a report
 * whose result payload is missing an expected field) unmounts the entire React
 * tree and leaves the user staring at a blank white page with no way to recover
 * short of manually retyping the URL.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('Unhandled error caught by ErrorBoundary:', error, info.componentStack);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    const copy = getCopy();

    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center text-foreground">
        <div className="flex size-14 items-center justify-center rounded-full bg-destructive/10">
          <AlertTriangle className="size-6 text-destructive" />
        </div>
        <div className="space-y-1.5">
          <p className="text-base font-semibold">{copy.title}</p>
          <p className="max-w-sm text-sm text-muted-foreground">{copy.description}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={this.handleReload}>
            <RotateCw className="size-3.5" />
            {copy.reload}
          </Button>
          <Button size="sm" variant="outline" onClick={this.handleGoHome}>
            {copy.goHome}
          </Button>
        </div>
      </div>
    );
  }
}
