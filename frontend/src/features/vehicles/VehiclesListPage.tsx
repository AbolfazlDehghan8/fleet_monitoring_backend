import * as React from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { FilterBar } from '@/components/shared/FilterBar';
import { PageHeader } from '@/components/shared/PageHeader';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { ROLES } from '@/constants/roles';
import { VEHICLE_STATUSES, type VehicleStatus } from '@/constants/statuses';
import { useAuth } from '@/features/auth/AuthContext';
import { useDeleteVehicle, useVehicles } from '@/features/vehicles/hooks';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';
import type { Vehicle } from '@/types/vehicles';
import { formatVehicleYear } from '@/utils/formatters';

export function VehiclesListPage() {
  const { t, language } = useLanguage();
  const { user } = useAuth();
  const navigate = useNavigate();
  const vehiclesQuery = useVehicles();
  const deleteMutation = useDeleteVehicle();

  const [search, setSearch] = React.useState('');
  const [statusFilter, setStatusFilter] = React.useState('');
  const [pendingDeleteId, setPendingDeleteId] = React.useState<number | null>(null);

  const isAdmin = user?.role === ROLES.ADMIN;

  const filtered = React.useMemo(() => {
    const data = vehiclesQuery.data ?? [];
    return data.filter((vehicle) => {
      const matchesStatus = !statusFilter || vehicle.status === statusFilter;
      const haystack = `${vehicle.vehicle_id} ${vehicle.license_plate} ${vehicle.make} ${vehicle.model} ${vehicle.driver?.full_name ?? ''}`.toLowerCase();
      const matchesSearch = !search || haystack.includes(search.toLowerCase());
      return matchesStatus && matchesSearch;
    });
  }, [vehiclesQuery.data, search, statusFilter]);

  async function handleDelete() {
    if (pendingDeleteId === null) return;
    try {
      await deleteMutation.mutateAsync(pendingDeleteId);
      toast({ title: t('vehicles.deleted'), variant: 'success' });
      setPendingDeleteId(null);
    } catch (error) {
      toast({
        title: t('vehicles.failedToDelete'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  const columns: DataTableColumn<Vehicle>[] = [
    {
      id: 'vehicle_id',
      header: t('vehicles.colVehicle'),
      sortAccessor: (row) => row.vehicle_id,
      cell: (row) => (
        <div>
          <p className="font-mono text-sm font-medium">{row.vehicle_id}</p>
          <p className="text-xs text-muted-foreground">
            {row.make} {row.model} {formatVehicleYear(row.year, language) ? `(${formatVehicleYear(row.year, language)})` : ''}
          </p>
        </div>
      ),
    },
    {
      id: 'license_plate',
      header: t('vehicles.colPlate'),
      sortAccessor: (row) => row.license_plate,
      cell: (row) => <span className="font-mono text-sm">{row.license_plate}</span>,
    },
    {
      id: 'driver',
      header: t('vehicles.colDriver'),
      sortAccessor: (row) => row.driver?.full_name ?? null,
      cell: (row) => <span className="text-sm">{row.driver?.full_name ?? t('common.notAvailable')}</span>,
    },
    {
      id: 'status',
      header: t('common.status'),
      sortAccessor: (row) => row.status,
      cell: (row) => <StatusBadge status={row.status} />,
    },
    {
      id: 'manager',
      header: t('vehicles.colManager'),
      cell: (row) => (
        <span className="text-sm text-muted-foreground">
          {row.assigned_manager_username ?? t('common.notAvailable')}
        </span>
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
              navigate(`/vehicles/${row.id}/edit`);
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
        title={t('vehicles.title')}
        description={t('vehicles.description')}
        actions={
          <Button size="sm" onClick={() => navigate('/vehicles/new')}>
            <Plus className="size-4" />
            {t('vehicles.addVehicle')}
          </Button>
        }
      />

      <FilterBar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('vehicles.searchPlaceholder')}
        selects={[
          {
            key: 'status',
            label: t('common.status'),
            value: statusFilter,
            onChange: setStatusFilter,
            options: Object.values(VEHICLE_STATUSES).map((status: VehicleStatus) => ({
              value: status,
              label: t(`vehicleStatus.${status}`),
            })),
          },
        ]}
        hasActiveFilters={Boolean(search || statusFilter)}
        onClear={() => {
          setSearch('');
          setStatusFilter('');
        }}
      />

      {vehiclesQuery.isError ? (
        <ErrorState onRetry={() => void vehiclesQuery.refetch()} />
      ) : (
        <DataTable
          columns={columns}
          data={filtered}
          getRowId={(row) => row.id}
          isLoading={vehiclesQuery.isLoading}
          onRowClick={(row) => navigate(`/vehicles/${row.id}`)}
          emptyTitle={t('vehicles.noMatch')}
          emptyDescription={t('vehicles.noMatchDesc')}
        />
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        onOpenChange={(open) => !open && setPendingDeleteId(null)}
        title={t('vehicles.deleteTitle')}
        description={t('vehicles.deleteDesc')}
        confirmLabel={t('common.delete')}
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => void handleDelete()}
      />
    </div>
  );
}
