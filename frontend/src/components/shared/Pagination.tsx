import * as React from 'react';

import { useLanguage } from '@/app/LanguageContext';

/**
 * Client-side pagination for a list/card view (as opposed to `DataTable`, which paginates
 * a table). Slices `items` into pages of `pageSize` and resets to page 0 whenever the
 * underlying item count changes (e.g. after a filter or a refetch).
 */
export function usePagination<T>(items: T[], pageSize = 5) {
  const [page, setPage] = React.useState(0);

  React.useEffect(() => {
    setPage(0);
  }, [items.length]);

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const pageItems = items.slice(safePage * pageSize, safePage * pageSize + pageSize);

  return { page: safePage, setPage, totalPages, pageItems, totalCount: items.length };
}

interface PaginationControlsProps {
  page: number;
  totalPages: number;
  totalCount: number;
  onPageChange: (page: number) => void;
  className?: string;
}

/** Footer with "page X of Y · N total" plus Previous/Next — mirrors `DataTable`'s pagination UI. */
export function PaginationControls({ page, totalPages, totalCount, onPageChange, className }: PaginationControlsProps) {
  const { t } = useLanguage();

  if (totalPages <= 1) return null;

  return (
    <div className={`flex items-center justify-between text-xs text-muted-foreground ${className ?? ''}`}>
      <span className="num-tabular">{t('common.pageOf', { page: page + 1, total: totalPages, count: totalCount })}</span>
      <div className="flex gap-1">
        <button
          type="button"
          disabled={page === 0}
          onClick={() => onPageChange(Math.max(0, page - 1))}
          className="rounded-md border border-border px-2 py-1 transition-colors hover:bg-accent/40 disabled:opacity-40 disabled:hover:bg-transparent"
        >
          {t('common.previous')}
        </button>
        <button
          type="button"
          disabled={page >= totalPages - 1}
          onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
          className="rounded-md border border-border px-2 py-1 transition-colors hover:bg-accent/40 disabled:opacity-40 disabled:hover:bg-transparent"
        >
          {t('common.next')}
        </button>
      </div>
    </div>
  );
}
