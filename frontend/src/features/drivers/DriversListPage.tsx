import * as React from 'react';
import { Pencil, Plus, Trash2, Users } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { FilterBar } from '@/components/shared/FilterBar';
import { useLanguage } from '@/app/LanguageContext';
import { PageHeader } from '@/components/shared/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { ROLES } from '@/constants/roles';
import { useAuth } from '@/features/auth/AuthContext';
import { useDeleteDriver, useDrivers } from '@/features/vehicles/hooks';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';
import type { Driver } from '@/types/vehicles';

export function DriversListPage() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const navigate = useNavigate();
  const driversQuery = useDrivers();
  const deleteMutation = useDeleteDriver();
  const isAdmin = user?.role === ROLES.ADMIN;

  const [search, setSearch] = React.useState('');
  const [pendingDeleteId, setPendingDeleteId] = React.useState<number | null>(null);

  const filtered = React.useMemo(() => {
    const data = driversQuery.data ?? [];
    return data.filter((driver) => {
      const haystack = `${driver.full_name} ${driver.username} ${driver.email} ${driver.license_number}`.toLowerCase();
      return !search || haystack.includes(search.toLowerCase());
    });
  }, [driversQuery.data, search]);

  async function handleDelete() {
    if (pendingDeleteId === null) return;
    try {
      await deleteMutation.mutateAsync(pendingDeleteId);
      toast({ title: t('drivers.deleted'), variant: 'success' });
      setPendingDeleteId(null);
    } catch (error) {
      toast({
        title: t('drivers.failedToDelete'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  const columns: DataTableColumn<Driver>[] = [
    {
      id: 'name',
      header: t('drivers.colDriver'),
      sortAccessor: (row) => row.full_name,
      cell: (row) => (
        <div>
          <p className="text-sm font-medium">{row.full_name}</p>
          <p className="text-xs text-muted-foreground">{row.username}</p>
        </div>
      ),
    },
    {
      id: 'license_number',
      header: t('drivers.colLicense'),
      sortAccessor: (row) => row.license_number,
      cell: (row) => <span className="font-mono text-sm">{row.license_number}</span>,
    },
    {
      id: 'phone_number',
      header: t('drivers.colPhone'),
      cell: (row) => <span className="text-sm text-muted-foreground">{row.phone_number || t('common.notAvailable')}</span>,
    },
    {
      id: 'is_active',
      header: t('common.status'),
      sortAccessor: (row) => (row.is_active ? 1 : 0),
      cell: (row) => (
        <Badge variant={row.is_active ? 'success' : 'muted'}>
          {row.is_active ? t('common.active') : t('vehicleStatus.inactive')}
        </Badge>
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
              navigate(`/drivers/${row.id}/edit`);
            }}
          >
            <Pencil className="size-4" />
          </Button>
          {isAdmin && (
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
          )}
        </div>
      ),
      className: 'text-end',
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('drivers.title')}
        description={t('drivers.description')}
        actions={
          <Button size="sm" onClick={() => navigate('/drivers/new')}>
            <Plus className="size-4" />
            {t('drivers.newProfile')}
          </Button>
        }
      />

      <FilterBar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('drivers.searchPlaceholder')}
        hasActiveFilters={Boolean(search)}
        onClear={() => setSearch('')}
      />

      {driversQuery.isError ? (
        <ErrorState onRetry={() => void driversQuery.refetch()} />
      ) : (
        <DataTable
          columns={columns}
          data={filtered}
          getRowId={(row) => row.id}
          isLoading={driversQuery.isLoading}
          onRowClick={(row) => navigate(`/drivers/${row.id}/edit`)}
          emptyTitle={t('drivers.noProfiles')}
          emptyDescription={t('drivers.noProfilesDesc')}
          emptyIcon={Users}
        />
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        onOpenChange={(open) => !open && setPendingDeleteId(null)}
        title={t('drivers.deleteTitle')}
        description={t('drivers.deleteDesc')}
        confirmLabel={t('common.delete')}
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => void handleDelete()}
      />
    </div>
  );
}
