import * as React from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, type LucideIcon } from 'lucide-react';

import { useLanguage } from '@/app/LanguageContext';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/utils/cn';

import { EmptyState } from './EmptyState';
import { TableSkeleton } from './LoadingSkeleton';

export interface DataTableColumn<T> {
  id: string;
  header: string;
  /** Render the cell. Receives the row. */
  cell: (row: T) => React.ReactNode;
  /** Enables client-side sort using this accessor. Omit for non-sortable columns. */
  sortAccessor?: (row: T) => string | number | null;
  className?: string;
  headerClassName?: string;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  getRowId: (row: T) => string | number;
  isLoading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyIcon?: LucideIcon;
  onRowClick?: (row: T) => void;
  /** Optional highlight predicate — used for the "new alert just arrived" pulse. */
  isRowHighlighted?: (row: T) => boolean;
  pageSize?: number;
}

type SortDirection = 'asc' | 'desc' | null;

export function DataTable<T>({
  columns,
  data,
  getRowId,
  isLoading,
  emptyTitle,
  emptyDescription,
  emptyIcon,
  onRowClick,
  isRowHighlighted,
  pageSize = 25,
}: DataTableProps<T>) {
  const { t } = useLanguage();
  const [sortColumnId, setSortColumnId] = React.useState<string | null>(null);
  const [sortDirection, setSortDirection] = React.useState<SortDirection>(null);
  const [page, setPage] = React.useState(0);

  React.useEffect(() => {
    setPage(0);
  }, [data.length]);

  const sortedData = React.useMemo(() => {
    if (!sortColumnId || !sortDirection) return data;
    const column = columns.find((c) => c.id === sortColumnId);
    if (!column?.sortAccessor) return data;

    const copy = [...data];
    copy.sort((a, b) => {
      const av = column.sortAccessor!(a);
      const bv = column.sortAccessor!(b);
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      const comparison = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv));
      return sortDirection === 'asc' ? comparison : -comparison;
    });
    return copy;
  }, [data, sortColumnId, sortDirection, columns]);

  const totalPages = Math.max(1, Math.ceil(sortedData.length / pageSize));
  const paginated = sortedData.slice(page * pageSize, page * pageSize + pageSize);

  function toggleSort(columnId: string) {
    if (sortColumnId !== columnId) {
      setSortColumnId(columnId);
      setSortDirection('asc');
      return;
    }
    if (sortDirection === 'asc') {
      setSortDirection('desc');
      return;
    }
    setSortColumnId(null);
    setSortDirection(null);
  }

  if (isLoading) {
    return <TableSkeleton columns={columns.length} />;
  }

  if (data.length === 0) {
    return (
      <EmptyState
        title={emptyTitle ?? t('common.noRecordsFound')}
        description={emptyDescription ?? t('common.adjustFilters')}
        icon={emptyIcon}
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-border">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {columns.map((column) => (
                <TableHead key={column.id} className={column.headerClassName}>
                  {column.sortAccessor ? (
                    <button
                      onClick={() => toggleSort(column.id)}
                      className="inline-flex items-center gap-1 transition-colors hover:text-foreground"
                    >
                      {column.header}
                      {sortColumnId === column.id ? (
                        sortDirection === 'asc' ? (
                          <ArrowUp className="size-3" />
                        ) : (
                          <ArrowDown className="size-3" />
                        )
                      ) : (
                        <ArrowUpDown className="size-3 opacity-40" />
                      )}
                    </button>
                  ) : (
                    column.header
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginated.map((row) => (
              <TableRow
                key={getRowId(row)}
                onClick={() => onRowClick?.(row)}
                className={cn(
                  onRowClick && 'cursor-pointer',
                  isRowHighlighted?.(row) && 'animate-pulse-ring bg-primary/5',
                )}
              >
                {columns.map((column) => (
                  <TableCell key={column.id} className={column.className}>
                    {column.cell(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="num-tabular">
            {t('common.pageOf', { page: page + 1, total: totalPages, count: sortedData.length })}
          </span>
          <div className="flex gap-1">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="rounded-md border border-border px-2 py-1 disabled:opacity-40"
            >
              {t('common.previous')}
            </button>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              className="rounded-md border border-border px-2 py-1 disabled:opacity-40"
            >
              {t('common.next')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
