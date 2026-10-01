import * as React from 'react';
import { ListChecks, Pencil, Plus, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { FilterBar } from '@/components/shared/FilterBar';
import { PageHeader } from '@/components/shared/PageHeader';
import { SeverityBadge } from '@/components/shared/SeverityBadge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { toast } from '@/components/ui/use-toast';
import { RULE_METRICS } from '@/constants/statuses';
import type { TranslationKey } from '@/i18n/translations';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';
import type { Rule } from '@/types/rules';

import { useDeleteRule, useRules, useUpdateRule } from './hooks';

function RuleToggle({ rule }: { rule: Rule }) {
  const { t } = useLanguage();
  const updateMutation = useUpdateRule(rule.id);

  async function handleToggle(checked: boolean) {
    try {
      await updateMutation.mutateAsync({ is_active: checked });
    } catch (error) {
      toast({
        title: t('rules.failedToUpdate'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  return (
    <Switch
      checked={rule.is_active}
      onCheckedChange={(checked) => void handleToggle(checked)}
      disabled={updateMutation.isPending}
      onClick={(e) => e.stopPropagation()}
    />
  );
}

export function RulesListPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const rulesQuery = useRules();
  const deleteMutation = useDeleteRule();

  const [search, setSearch] = React.useState('');
  const [metricFilter, setMetricFilter] = React.useState('');
  const [pendingDeleteId, setPendingDeleteId] = React.useState<number | null>(null);

  const filtered = React.useMemo(() => {
    const data = rulesQuery.data ?? [];
    return data.filter((rule) => {
      const matchesMetric = !metricFilter || rule.metric === metricFilter;
      const haystack = `${rule.name} ${rule.description}`.toLowerCase();
      const matchesSearch = !search || haystack.includes(search.toLowerCase());
      return matchesMetric && matchesSearch;
    });
  }, [rulesQuery.data, search, metricFilter]);

  async function handleDelete() {
    if (pendingDeleteId === null) return;
    try {
      await deleteMutation.mutateAsync(pendingDeleteId);
      toast({ title: t('rules.deleted'), variant: 'success' });
      setPendingDeleteId(null);
    } catch (error) {
      toast({
        title: t('rules.failedToDelete'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  const columns: DataTableColumn<Rule>[] = [
    {
      id: 'name',
      header: t('rules.colRule'),
      sortAccessor: (row) => row.name,
      cell: (row) => (
        <div>
          <p className="text-sm font-medium">{row.name}</p>
          {row.description && <p className="text-xs text-muted-foreground">{row.description}</p>}
        </div>
      ),
    },
    {
      id: 'condition',
      header: t('rules.colCondition'),
      cell: (row) => (
        <span className="font-mono text-xs text-muted-foreground">
          {row.metric} {row.operator} {row.threshold}
        </span>
      ),
    },
    {
      id: 'severity',
      header: t('alerts.colSeverity'),
      sortAccessor: (row) => row.severity,
      cell: (row) => <SeverityBadge severity={row.severity} />,
    },
    {
      id: 'is_active',
      header: t('rules.colEnabled'),
      sortAccessor: (row) => (row.is_active ? 1 : 0),
      cell: (row) => <RuleToggle rule={row} />,
    },
    {
      id: 'created_by',
      header: t('rules.colCreatedBy'),
      cell: (row) => (
        <span className="text-sm text-muted-foreground">{row.created_by_username ?? t('common.notAvailable')}</span>
      ),
    },
    {
      id: 'actions',
      header: '',
      cell: (row) => (
        <div className="flex justify-end gap-1">
          <Button
            size="icon"
            variant="ghost"
            className="text-muted-foreground hover:text-foreground"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/rules/${row.id}/edit`);
            }}
          >
            <Pencil className="size-4" />
          </Button>
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
        </div>
      ),
      className: 'text-end',
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('rules.title')}
        description={t('rules.description')}
        actions={
          <Button size="sm" onClick={() => navigate('/rules/new')}>
            <Plus className="size-4" />
            {t('rules.newRule')}
          </Button>
        }
      />

      <FilterBar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('rules.searchPlaceholder')}
        selects={[
          {
            key: 'metric',
            label: t('alertDetail.metric'),
            value: metricFilter,
            onChange: setMetricFilter,
            options: RULE_METRICS.map((m) => ({ value: m.value, label: t(`ruleMetric.${m.value}` as TranslationKey) })),
          },
        ]}
        hasActiveFilters={Boolean(search || metricFilter)}
        onClear={() => {
          setSearch('');
          setMetricFilter('');
        }}
      />

      {rulesQuery.isError ? (
        <ErrorState onRetry={() => void rulesQuery.refetch()} />
      ) : (
        <DataTable
          columns={columns}
          data={filtered}
          getRowId={(row) => row.id}
          isLoading={rulesQuery.isLoading}
          onRowClick={(row) => navigate(`/rules/${row.id}/edit`)}
          emptyTitle={t('rules.noRules')}
          emptyDescription={t('rules.noRulesDesc')}
          emptyIcon={ListChecks}
        />
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        onOpenChange={(open) => !open && setPendingDeleteId(null)}
        title={t('rules.deleteTitle')}
        description={t('rules.deleteDesc')}
        confirmLabel={t('common.delete')}
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => void handleDelete()}
      />
    </div>
  );
}
