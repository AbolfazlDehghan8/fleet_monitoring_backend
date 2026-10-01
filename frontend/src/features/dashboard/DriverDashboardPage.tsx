import * as React from 'react';
import { AlertTriangle, CheckCircle2, ChevronRight, Gauge, MapPin, Trash2, Truck } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { CardGridSkeleton, TableSkeleton } from '@/components/shared/LoadingSkeleton';
import { usePagination, PaginationControls } from '@/components/shared/Pagination';
import { SeverityBadge } from '@/components/shared/SeverityBadge';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from '@/components/ui/use-toast';
import { PageHeader } from '@/components/shared/PageHeader';
import { useAcknowledgeMyAlert, useDeleteAlert, useMyAlerts } from '@/features/alerts/hooks';
import { useMyVehicles, useVehicleStatus } from '@/features/vehicles/hooks';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';
import type { Alert } from '@/types/alerts';
import type { Vehicle } from '@/types/vehicles';
import {
  formatFuel,
  formatRelativeTime,
  formatSpeed,
  formatTemperature,
  formatVehicleYear,
  formatVoltage,
} from '@/utils/formatters';

export function DriverDashboardPage() {
  const { t } = useLanguage();
  const vehiclesQuery = useMyVehicles();
  const alertsQuery = useMyAlerts();

  return (
    <div className="space-y-6">
      <PageHeader title={t('dashboard.title')} description={t('dashboard.driverDescription')} />

      <div className="space-y-3">
        <h2 className="text-base font-semibold text-foreground">{t('dashboard.myVehicle')}</h2>
        {vehiclesQuery.isLoading ? (
          <CardGridSkeleton count={1} />
        ) : vehiclesQuery.isError ? (
          <ErrorState onRetry={() => void vehiclesQuery.refetch()} />
        ) : vehiclesQuery.data && vehiclesQuery.data.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {vehiclesQuery.data.map((vehicle) => (
              <MyVehicleCard key={vehicle.id} vehicle={vehicle} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Truck}
            title={t('dashboard.noVehicleAssigned')}
            description={t('dashboard.noVehicleAssignedDesc')}
          />
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">{t('dashboard.myAlerts')}</CardTitle>
        </CardHeader>
        <CardContent>
          {alertsQuery.isLoading ? (
            <TableSkeleton rows={4} columns={2} />
          ) : alertsQuery.isError ? (
            <ErrorState onRetry={() => void alertsQuery.refetch()} />
          ) : alertsQuery.data && alertsQuery.data.length > 0 ? (
            <MyAlertsList alerts={alertsQuery.data} />
          ) : (
            <EmptyState
              icon={CheckCircle2}
              title={t('dashboard.noAlerts')}
              description={t('dashboard.noAlertsDriverDesc')}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function MyAlertsList({ alerts }: { alerts: Alert[] }) {
  const { page, setPage, totalPages, pageItems, totalCount } = usePagination(alerts, 5);

  return (
    <div className="space-y-3">
      <ul className="space-y-3">
        {pageItems.map((alert) => (
          <MyAlertRow key={alert.id} alertId={alert.id} />
        ))}
      </ul>
      <PaginationControls page={page} totalPages={totalPages} totalCount={totalCount} onPageChange={setPage} />
    </div>
  );
}

function MyVehicleCard({ vehicle }: { vehicle: Vehicle }) {
  const { t, language } = useLanguage();
  const statusQuery = useVehicleStatus(vehicle.id);
  const live = statusQuery.data?.live_telemetry;
  const na = t('common.notAvailable');

  return (
    <Card className="glass">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base font-semibold text-foreground">
          <span className="font-mono">{vehicle.vehicle_id}</span>
        </CardTitle>
        <StatusBadge status={vehicle.status} />
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {vehicle.make} {vehicle.model} {formatVehicleYear(vehicle.year, language) ? `(${formatVehicleYear(vehicle.year, language)})` : ''} · {vehicle.license_plate}
        </p>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricTile label={t('vehicleDetail.speed')} value={formatSpeed(live?.speed)} icon={Gauge} />
          <MetricTile label={t('vehicleDetail.fuelLevel')} value={formatFuel(live?.fuel_level)} icon={Gauge} />
          <MetricTile
            label={t('vehicleDetail.engineTemp')}
            value={formatTemperature(live?.engine_temperature)}
            icon={Gauge}
          />
          <MetricTile label={t('vehicleDetail.battery')} value={formatVoltage(live?.battery_voltage)} icon={Gauge} />
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <MapPin className="size-3.5" />
            {live ? `${live.latitude.toFixed(4)}, ${live.longitude.toFixed(4)}` : na}
          </span>
          <span>{t('vehicleDetail.lastSeen')}: {formatRelativeTime(live?.last_seen)}</span>
        </div>

        <Button asChild variant="outline" size="sm" className="w-full">
          <Link to={`/my-vehicle/${vehicle.id}`}>
            {t('dashboard.viewDetails')}
            <ChevronRight className="size-3.5" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function MetricTile({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Gauge }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border p-2.5">
      <Icon className="size-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0">
        <p className="truncate text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="num-tabular truncate text-sm font-semibold">{value}</p>
      </div>
    </div>
  );
}

function MyAlertRow({ alertId }: { alertId: number }) {
  const { t } = useLanguage();
  const alertsQuery = useMyAlerts();
  const acknowledgeMutation = useAcknowledgeMyAlert();
  const deleteMutation = useDeleteAlert();
  const [confirmDeleteOpen, setConfirmDeleteOpen] = React.useState(false);
  const alert = alertsQuery.data?.find((a) => a.id === alertId);
  if (!alert) return null;

  async function handleAcknowledge() {
    try {
      await acknowledgeMutation.mutateAsync(alertId);
      toast({ title: t('alerts.alertAcknowledged'), variant: 'success' });
    } catch (error) {
      toast({
        title: t('alerts.failedToAcknowledge'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  async function handleDelete() {
    try {
      await deleteMutation.mutateAsync(alertId);
      toast({ title: t('alerts.alertDeleted'), variant: 'success' });
      setConfirmDeleteOpen(false);
    } catch (error) {
      toast({
        title: t('alerts.failedToDelete'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  return (
    <>
      <li className="flex items-start justify-between gap-3 rounded-lg border border-border p-3">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-3.5 shrink-0 text-muted-foreground" />
            <p className="truncate text-sm font-medium">{alert.rule_name}</p>
          </div>
          <p className="truncate text-xs text-muted-foreground">
            {alert.vehicle_id} · {formatRelativeTime(alert.created_at)}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <SeverityBadge severity={alert.severity} />
          {alert.acknowledged ? (
            <span className="text-xs font-medium text-success">{t('alerts.acknowledged')}</span>
          ) : (
            <Button
              size="sm"
              variant="outline"
              onClick={() => void handleAcknowledge()}
              disabled={acknowledgeMutation.isPending}
            >
              {t('alerts.acknowledge')}
            </Button>
          )}
          <Button
            size="icon"
            variant="ghost"
            className="size-8 text-muted-foreground hover:text-destructive"
            aria-label={t('alerts.delete')}
            title={t('alerts.delete')}
            onClick={() => setConfirmDeleteOpen(true)}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      </li>
      <ConfirmDialog
        open={confirmDeleteOpen}
        onOpenChange={setConfirmDeleteOpen}
        title={t('alerts.deleteTitle')}
        description={t('alerts.deleteDesc')}
        confirmLabel={t('common.delete')}
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => void handleDelete()}
      />
    </>
  );
}