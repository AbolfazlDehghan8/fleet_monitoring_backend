import { ArrowLeft, Gauge, MapPin, Pencil, Trash2 } from 'lucide-react';
import * as React from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { usePagination, PaginationControls } from '@/components/shared/Pagination';
import { SeverityBadge } from '@/components/shared/SeverityBadge';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/use-toast';
import { ROLES } from '@/constants/roles';
import { useAlerts } from '@/features/alerts/hooks';
import { useAuth } from '@/features/auth/AuthContext';
import { TelemetryChart } from '@/features/telemetry/TelemetryChart';
import { useTelemetry } from '@/features/telemetry/hooks';
import { useDeleteVehicle, useVehicle, useVehicleStatus } from '@/features/vehicles/hooks';
import type { Alert } from '@/types/alerts';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';
import {
  formatDateTime,
  formatFuel,
  formatOdometer,
  formatRelativeTime,
  formatSpeed,
  formatTemperature,
  formatVehicleYear,
  formatVoltage,
} from '@/utils/formatters';

export function VehicleDetailPage() {
  const { t, language } = useLanguage();
  const params = useParams<{ id: string }>();
  const vehicleId = Number(params.id);
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === ROLES.ADMIN;

  const vehicleQuery = useVehicle(vehicleId);
  const statusQuery = useVehicleStatus(vehicleId);
  const telemetryQuery = useTelemetry(vehicleQuery.data?.vehicle_id);
  const alertsQuery = useAlerts();
  const deleteMutation = useDeleteVehicle();
  const [confirmDelete, setConfirmDelete] = React.useState(false);

  async function handleDelete() {
    try {
      await deleteMutation.mutateAsync(vehicleId);
      toast({ title: t('vehicles.deleted'), variant: 'success' });
      navigate('/vehicles');
    } catch (error) {
      toast({
        title: t('vehicles.failedToDelete'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  if (vehicleQuery.isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full rounded-xl" />
        <Skeleton className="h-72 w-full rounded-xl" />
      </div>
    );
  }

  if (vehicleQuery.isError || !vehicleQuery.data) {
    return <ErrorState onRetry={() => void vehicleQuery.refetch()} title={t('vehicleDetail.unableToLoad')} />;
  }

  const vehicle = vehicleQuery.data;
  const live = statusQuery.data?.live_telemetry;
  const relatedAlerts = (alertsQuery.data ?? []).filter((a) => a.vehicle_id === vehicle.vehicle_id);
  const na = t('common.notAvailable');

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2 -ms-2 text-muted-foreground">
          <Link to="/vehicles">
            <ArrowLeft className="size-3.5" />
            {t('vehicleDetail.backToVehicles')}
          </Link>
        </Button>
        <PageHeader
          title={vehicle.vehicle_id}
          description={`${vehicle.make} ${vehicle.model} ${formatVehicleYear(vehicle.year, language) ? `(${formatVehicleYear(vehicle.year, language)})` : ''} · ${vehicle.license_plate}`}
          actions={
            <div className="flex items-center gap-2">
              <StatusBadge status={vehicle.status} className="text-sm" />
              <Button variant="outline" size="sm" onClick={() => navigate(`/vehicles/${vehicleId}/edit`)}>
                <Pencil className="size-3.5" />
                {t('common.edit')}
              </Button>
              {isAdmin && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() => setConfirmDelete(true)}
                >
                  <Trash2 className="size-3.5" />
                  {t('common.delete')}
                </Button>
              )}
            </div>
          }
        />
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={t('vehicles.deleteTitle')}
        description={t('vehicleDetail.deleteConfirmDesc')}
        confirmLabel={t('common.delete')}
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => void handleDelete()}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label={t('vehicleDetail.speed')} value={formatSpeed(live?.speed)} icon={Gauge} />
        <MetricCard label={t('vehicleDetail.fuelLevel')} value={formatFuel(live?.fuel_level)} icon={Gauge} />
        <MetricCard
          label={t('vehicleDetail.engineTemp')}
          value={formatTemperature(live?.engine_temperature)}
          icon={Gauge}
        />
        <MetricCard label={t('vehicleDetail.battery')} value={formatVoltage(live?.battery_voltage)} icon={Gauge} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">
              {t('vehicleDetail.speedHistory')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <TelemetryChart
              data={telemetryQuery.data ?? []}
              metric="speed"
              label={t('vehicleDetail.speed')}
              unit=" km/h"
              color="hsl(var(--primary))"
              isLoading={telemetryQuery.isLoading}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">
              {t('vehicleDetail.vehicleProfile')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <ProfileRow label={t('vehicleDetail.vin')} value={vehicle.vin ?? na} mono />
            <ProfileRow label={t('vehicleDetail.driver')} value={vehicle.driver?.full_name ?? t('vehicleDetail.unassigned')} />
            <ProfileRow label={t('vehicleDetail.driverPhone')} value={vehicle.driver?.phone_number ?? na} />
            <ProfileRow label={t('vehicleDetail.manager')} value={vehicle.assigned_manager_username ?? na} />
            <ProfileRow label={t('vehicleDetail.obuSerial')} value={vehicle.obu?.serial_number ?? na} mono />
            <ProfileRow label={t('vehicleDetail.firmware')} value={vehicle.obu?.firmware_version ?? na} />
            <ProfileRow label={t('vehicleDetail.odometer')} value={formatOdometer(live?.odometer)} />
            <ProfileRow
              label={t('vehicleDetail.location')}
              value={live ? `${live.latitude.toFixed(4)}, ${live.longitude.toFixed(4)}` : na}
              icon={MapPin}
            />
            <ProfileRow label={t('vehicleDetail.lastSeen')} value={formatRelativeTime(live?.last_seen)} />
            <ProfileRow label={t('vehicleDetail.added')} value={formatDateTime(vehicle.created_at)} />
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">
              {t('vehicleDetail.engineTemperature')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <TelemetryChart
              data={telemetryQuery.data ?? []}
              metric="engine_temperature"
              label={t('vehicleDetail.engineTemp')}
              unit="°C"
              color="hsl(var(--warning))"
              isLoading={telemetryQuery.isLoading}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">
              {t('vehicleDetail.fuelLevelChart')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <TelemetryChart
              data={telemetryQuery.data ?? []}
              metric="fuel_level"
              label={t('vehicleDetail.fuelLevel')}
              unit="%"
              color="hsl(var(--success))"
              isLoading={telemetryQuery.isLoading}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">
            {t('vehicleDetail.relatedAlerts')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {relatedAlerts.length > 0 ? (
            <RelatedAlertsList alerts={relatedAlerts} />
          ) : (
            <EmptyState title={t('vehicleDetail.noAlerts')} description={t('vehicleDetail.noAlertsDesc')} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function RelatedAlertsList({ alerts }: { alerts: Alert[] }) {
  const { page, setPage, totalPages, pageItems, totalCount } = usePagination(alerts, 5);

  return (
    <div className="space-y-1">
      <ul className="divide-y divide-border">
        {pageItems.map((alert) => (
          <li key={alert.id}>
            <Link
              to={`/alerts/${alert.id}`}
              className="flex items-center justify-between gap-3 py-3 transition-colors hover:text-primary"
            >
              <div className="min-w-0 space-y-0.5">
                <p className="truncate text-sm font-medium">{alert.rule_name}</p>
                <p className="text-xs text-muted-foreground">{formatRelativeTime(alert.created_at)}</p>
              </div>
              <SeverityBadge severity={alert.severity} />
            </Link>
          </li>
        ))}
      </ul>
      <PaginationControls page={page} totalPages={totalPages} totalCount={totalCount} onPageChange={setPage} className="pt-3" />
    </div>
  );
}

function MetricCard({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Gauge }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="num-tabular text-xl font-semibold">{value}</p>
        </div>
        <Icon className="size-5 text-muted-foreground" />
      </CardContent>
    </Card>
  );
}

function ProfileRow({
  label,
  value,
  mono,
  icon: Icon,
}: {
  label: string;
  value: string;
  mono?: boolean;
  icon?: typeof MapPin;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className={`flex items-center gap-1.5 text-end ${mono ? 'font-mono text-xs' : ''}`}>
        {Icon && <Icon className="size-3.5 text-muted-foreground" />}
        {value}
      </span>
    </div>
  );
}
