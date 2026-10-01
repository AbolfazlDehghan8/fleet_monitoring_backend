import * as React from 'react';
import { FileBarChart, Plus, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { ReportStatusBadge } from '@/components/shared/ReportStatusBadge';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from '@/components/ui/use-toast';
import { ROLES } from '@/constants/roles';
import { useAuth } from '@/features/auth/AuthContext';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';
import type { Report } from '@/types/reports';
import { formatDateTime } from '@/utils/formatters';

import { useDeleteReport, useGenerateReport, useReports } from './hooks';

type RequesterFilter = 'all' | 'mine' | 'system';

export function ReportsListPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { user } = useAuth();
  const reportsQuery = useReports();
  const generateMutation = useGenerateReport();
  const deleteMutation = useDeleteReport();

  const [pendingDeleteId, setPendingDeleteId] = React.useState<number | null>(null);
  const [requesterFilter, setRequesterFilter] = React.useState<RequesterFilter>('all');

  // Reports are private per role: the backend only returns the caller's own reports,
  // plus — for admins only — system-generated (scheduled) reports. Fleet managers
  // therefore never see admin/system reports and admins never see managers' reports.
  // The filter/column below only exist to tell an admin's own reports from system ones.
  const isAdmin = user?.role === ROLES.ADMIN;

  const filteredReports = React.useMemo(() => {
    const data = reportsQuery.data ?? [];
    if (!isAdmin || requesterFilter === 'all') return data;
    if (requesterFilter === 'mine') return data.filter((r) => r.requested_by === user?.id);
    return data.filter((r) => r.requested_by === null);
  }, [reportsQuery.data, requesterFilter, isAdmin, user?.id]);

  async function handleGenerate() {
    try {
      const report = await generateMutation.mutateAsync(undefined);
      toast({ title: t('reports.generationStarted'), variant: 'success' });
      navigate(`/reports/${report.id}`);
    } catch (error) {
      toast({
        title: t('reports.failedToStart'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  async function handleDelete() {
    if (pendingDeleteId === null) return;
    try {
      await deleteMutation.mutateAsync(pendingDeleteId);
      toast({ title: t('reports.deleted'), variant: 'success' });
      setPendingDeleteId(null);
    } catch (error) {
      toast({
        title: t('reports.failedToDelete'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  const columns: DataTableColumn<Report>[] = [
    {
      id: 'sequence_number',
      header: t('reports.colReport'),
      sortAccessor: (row) => row.sequence_number,
      cell: (row) => <span className="font-mono text-sm">#{row.sequence_number}</span>,
    },
    ...(isAdmin
      ? [
          {
            id: 'requested_by',
            header: t('reports.colRequestedBy'),
            sortAccessor: (row) => row.requested_by_username ?? '',
            cell: (row) => {
              if (row.requested_by === null) {
                return <Badge variant="muted">{t('reports.requesterSystem')}</Badge>;
              }
              return <Badge>{t('reports.requesterMe')}</Badge>;
            },
          } satisfies DataTableColumn<Report>,
        ]
      : []),
    {
      id: 'vehicle_id',
      header: t('reports.colScope'),
      cell: (row) => <span className="text-sm">{row.vehicle_id || t('reports.entireFleet')}</span>,
    },
    {
      id: 'period',
      header: t('reports.colPeriod'),
      cell: (row) => {
        // Reports created without explicit dates store null period_start/end; the
        // backend resolves the default window (last 30 days) at run time and
        // records it in result.period, so fall back to that before giving up.
        const start = row.period_start ?? row.result?.period?.start;
        const end = row.period_end ?? row.result?.period?.end;
        return start && end ? (
          <span className="text-xs text-muted-foreground">
            {formatDateTime(start)} → {formatDateTime(end)}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">{t('common.notAvailable')}</span>
        );
      },
    },
    {
      id: 'status',
      header: t('common.status'),
      sortAccessor: (row) => row.status,
      cell: (row) => <ReportStatusBadge status={row.status} />,
    },
    {
      id: 'created_at',
      header: t('reports.colRequested'),
      sortAccessor: (row) => new Date(row.created_at).getTime(),
      cell: (row) => <span className="text-sm text-muted-foreground">{formatDateTime(row.created_at)}</span>,
    },
    {
      id: 'actions',
      header: '',
      cell: (row) => (
        <Button
          size="icon"
          variant="ghost"
          className="text-muted-foreground hover:text-destructive"
          onClick={(e) => {
            e.stopPropagation();
            setPendingDeleteId(row.id);
          }}
        >
          <Trash2 className="size-4" />
        </Button>
      ),
      className: 'text-end',
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('reports.title')}
        description={t('reports.description')}
        actions={
          <Button size="sm" onClick={() => void handleGenerate()} disabled={generateMutation.isPending}>
            <Plus className="size-4" />
            {generateMutation.isPending ? t('reports.starting') : t('reports.generateReport')}
          </Button>
        }
      />

      {isAdmin && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">{t('reports.filterByRequester')}</span>
          <Select value={requesterFilter} onValueChange={(v) => setRequesterFilter(v as RequesterFilter)}>
            <SelectTrigger className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('reports.filterAll')}</SelectItem>
              <SelectItem value="mine">{t('reports.filterMine')}</SelectItem>
              <SelectItem value="system">{t('reports.filterSystem')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      {reportsQuery.isError ? (
        <ErrorState onRetry={() => void reportsQuery.refetch()} />
      ) : (
        <DataTable
          columns={columns}
          data={filteredReports}
          getRowId={(row) => row.id}
          isLoading={reportsQuery.isLoading}
          onRowClick={(row) => navigate(`/reports/${row.id}`)}
          emptyTitle={t('reports.noReports')}
          emptyDescription={t('reports.noReportsDesc')}
          emptyIcon={FileBarChart}
        />
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        onOpenChange={(open) => !open && setPendingDeleteId(null)}
        title={t('reports.deleteTitle')}
        description={t('reports.deleteDesc')}
        confirmLabel={t('common.delete')}
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => void handleDelete()}
      />
    </div>
  );
}
