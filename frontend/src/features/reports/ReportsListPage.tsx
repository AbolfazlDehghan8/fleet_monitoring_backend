import * as React from 'react';
import { FileBarChart, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { ReportStatusBadge } from '@/components/shared/ReportStatusBadge';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { ApiError } from '@/types/common';
import type { Report } from '@/types/reports';
import { formatDateTime } from '@/utils/formatters';

import { useGenerateReport, useReports } from './hooks';

export function ReportsListPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const reportsQuery = useReports();
  const generateMutation = useGenerateReport();

  async function handleGenerate() {
    try {
      const report = await generateMutation.mutateAsync(undefined);
      toast({ title: t('reports.generationStarted'), variant: 'success' });
      navigate(`/reports/${report.id}`);
    } catch (error) {
      toast({
        title: t('reports.failedToStart'),
        description: error instanceof ApiError ? ApiError.extractMessage(error.body) : undefined,
        variant: 'destructive',
      });
    }
  }

  const columns: DataTableColumn<Report>[] = [
    {
      id: 'id',
      header: t('reports.colReport'),
      sortAccessor: (row) => row.id,
      cell: (row) => <span className="font-mono text-sm">#{row.id}</span>,
    },
    {
      id: 'vehicle_id',
      header: t('reports.colScope'),
      cell: (row) => <span className="text-sm">{row.vehicle_id || t('reports.entireFleet')}</span>,
    },
    {
      id: 'period',
      header: t('reports.colPeriod'),
      cell: (row) =>
        row.period_start && row.period_end ? (
          <span className="text-xs text-muted-foreground">
            {formatDateTime(row.period_start)} → {formatDateTime(row.period_end)}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">{t('common.notAvailable')}</span>
        ),
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

      {reportsQuery.isError ? (
        <ErrorState onRetry={() => void reportsQuery.refetch()} />
      ) : (
        <DataTable
          columns={columns}
          data={reportsQuery.data ?? []}
          getRowId={(row) => row.id}
          isLoading={reportsQuery.isLoading}
          onRowClick={(row) => navigate(`/reports/${row.id}`)}
          emptyTitle={t('reports.noReports')}
          emptyDescription={t('reports.noReportsDesc')}
          emptyIcon={FileBarChart}
        />
      )}
    </div>
  );
}
