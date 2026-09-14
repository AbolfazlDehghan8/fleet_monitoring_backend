import * as React from 'react';
import { CheckCircle2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { FilterBar } from '@/components/shared/FilterBar';
import { PageHeader } from '@/components/shared/PageHeader';
import { SeverityBadge } from '@/components/shared/SeverityBadge';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { SEVERITIES, type Severity } from '@/constants/statuses';
import { useAcknowledgeAlert, useAlerts } from '@/features/alerts/hooks';
import { formatDateTime } from '@/utils/formatters';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';
import type { Alert } from '@/types/alerts';

export function AlertsListPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const alertsQuery = useAlerts();
  const acknowledgeMutation = useAcknowledgeAlert();

  const [search, setSearch] = React.useState('');
  const [severityFilter, setSeverityFilter] = React.useState('');
  const [statusFilter, setStatusFilter] = React.useState('');

  const filtered = React.useMemo(() => {
    const data = alertsQuery.data ?? [];
    return data.filter((alert) => {
      const matchesSeverity = !severityFilter || alert.severity === severityFilter;
      const matchesStatus =
        !statusFilter ||
        (statusFilter === 'acknowledged' && alert.acknowledged) ||
        (statusFilter === 'unacknowledged' && !alert.acknowledged);
      const haystack = `${alert.vehicle_id} ${alert.rule_name} ${alert.metric}`.toLowerCase();
      const matchesSearch = !search || haystack.includes(search.toLowerCase());
      return matchesSeverity && matchesStatus && matchesSearch;
    });
  }, [alertsQuery.data, search, severityFilter, statusFilter]);

  async function handleAcknowledge(alert: Alert, event: React.MouseEvent) {
    event.stopPropagation();
    try {
      await acknowledgeMutation.mutateAsync(alert.id);
      toast({ title: t('alerts.alertAcknowledged'), variant: 'success' });
    } catch (error) {
      toast({
        title: t('alerts.failedToAcknowledge'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  const columns: DataTableColumn<Alert>[] = [
    {
      id: 'severity',
      header: t('alerts.colSeverity'),
      sortAccessor: (row) => row.severity,
      cell: (row) => <SeverityBadge severity={row.severity} />,
    },
    {
      id: 'rule_name',
      header: t('alerts.colRule'),
      sortAccessor: (row) => row.rule_name,
      cell: (row) => (
        <div>
          <p className="text-sm font-medium">{row.rule_name}</p>
          <p className="text-xs text-muted-foreground">
            {t('alerts.valueVsThreshold', { metric: row.metric, value: row.value, threshold: row.threshold })}
          </p>
        </div>
      ),
    },
    {
      id: 'vehicle_id',
      header: t('alerts.colVehicle'),
      sortAccessor: (row) => row.vehicle_id,
      cell: (row) => <span className="font-mono text-sm">{row.vehicle_id}</span>,
    },
    {
      id: 'created_at',
      header: t('alerts.colTriggered'),
      sortAccessor: (row) => new Date(row.created_at).getTime(),
      cell: (row) => <span className="text-sm text-muted-foreground">{formatDateTime(row.created_at)}</span>,
    },
    {
      id: 'acknowledged',
      header: t('common.status'),
      sortAccessor: (row) => (row.acknowledged ? 1 : 0),
      cell: (row) =>
        row.acknowledged ? (
          <Badge variant="success">{t('alerts.acknowledged')}</Badge>
        ) : (
          <Badge variant="warning">{t('alerts.open')}</Badge>
        ),
    },
    {
      id: 'actions',
      header: '',
      cell: (row) =>
        !row.acknowledged ? (
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => void handleAcknowledge(row, e)}
            disabled={acknowledgeMutation.isPending}
          >
            <CheckCircle2 className="size-3.5" />
            {t('alerts.acknowledge')}
          </Button>
        ) : null,
      className: 'text-end',
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t('alerts.title')} description={t('alerts.description')} />

      <FilterBar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('alerts.searchPlaceholder')}
        selects={[
          {
            key: 'severity',
            label: t('alerts.colSeverity'),
            value: severityFilter,
            onChange: setSeverityFilter,
            options: Object.values(SEVERITIES).map((s: Severity) => ({ value: s, label: t(`severity.${s}`) })),
          },
          {
            key: 'status',
            label: t('common.status'),
            value: statusFilter,
            onChange: setStatusFilter,
            options: [
              { value: 'unacknowledged', label: t('alerts.open') },
              { value: 'acknowledged', label: t('alerts.acknowledged') },
            ],
          },
        ]}
        hasActiveFilters={Boolean(search || severityFilter || statusFilter)}
        onClear={() => {
          setSearch('');
          setSeverityFilter('');
          setStatusFilter('');
        }}
      />

      {alertsQuery.isError ? (
        <ErrorState onRetry={() => void alertsQuery.refetch()} />
      ) : (
        <DataTable
          columns={columns}
          data={filtered}
          getRowId={(row) => row.id}
          isLoading={alertsQuery.isLoading}
          onRowClick={(row) => navigate(`/alerts/${row.id}`)}
          emptyTitle={t('alerts.noMatch')}
          emptyDescription={t('alerts.noMatchDesc')}
        />
      )}
    </div>
  );
}
