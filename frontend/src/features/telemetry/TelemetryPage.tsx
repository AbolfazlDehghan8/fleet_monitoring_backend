import * as React from 'react';
import { Radio } from 'lucide-react';

import { useLanguage } from '@/app/LanguageContext';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useVehicles } from '@/features/vehicles/hooks';
import { formatDateTime, formatFuel, formatSpeed, formatTemperature, formatVoltage } from '@/utils/formatters';

import { SimulateTelemetryDialog } from './SimulateTelemetryDialog';
import { TelemetryChart } from './TelemetryChart';
import { useTelemetry } from './hooks';

export function TelemetryPage() {
  const { t } = useLanguage();
  const vehiclesQuery = useVehicles();
  const [selectedVehicleId, setSelectedVehicleId] = React.useState<string>('');

  React.useEffect(() => {
    if (!selectedVehicleId && vehiclesQuery.data && vehiclesQuery.data.length > 0) {
      setSelectedVehicleId(vehiclesQuery.data[0].vehicle_id);
    }
  }, [vehiclesQuery.data, selectedVehicleId]);

  const telemetryQuery = useTelemetry(selectedVehicleId || undefined);
  const latest = telemetryQuery.data?.[0];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('telemetry.title')}
        description={t('telemetry.description')}
        actions={
          vehiclesQuery.data && vehiclesQuery.data.length > 0 ? (
            <SimulateTelemetryDialog vehicles={vehiclesQuery.data} defaultVehicleId={selectedVehicleId} />
          ) : undefined
        }
      />

      {vehiclesQuery.isLoading ? (
        <Skeleton className="h-9 w-64" />
      ) : vehiclesQuery.isError ? (
        <ErrorState onRetry={() => void vehiclesQuery.refetch()} />
      ) : vehiclesQuery.data && vehiclesQuery.data.length > 0 ? (
        <Select value={selectedVehicleId} onValueChange={setSelectedVehicleId}>
          <SelectTrigger className="w-full sm:w-72">
            <SelectValue placeholder={t('telemetry.selectVehicle')} />
          </SelectTrigger>
          <SelectContent>
            {vehiclesQuery.data.map((vehicle) => (
              <SelectItem key={vehicle.id} value={vehicle.vehicle_id}>
                {vehicle.vehicle_id} · {vehicle.make} {vehicle.model}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <EmptyState icon={Radio} title={t('telemetry.noVehicles')} description={t('telemetry.noVehiclesDesc')} />
      )}

      {selectedVehicleId && (
        <>
          {latest && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <SnapshotCard label={t('telemetry.speed')} value={formatSpeed(latest.speed)} />
              <SnapshotCard label={t('telemetry.fuelLevel')} value={formatFuel(latest.fuel_level)} />
              <SnapshotCard label={t('telemetry.engineTemp')} value={formatTemperature(latest.engine_temperature)} />
              <SnapshotCard label={t('telemetry.battery')} value={formatVoltage(latest.battery_voltage)} />
            </div>
          )}

          {telemetryQuery.isError ? (
            <ErrorState onRetry={() => void telemetryQuery.refetch()} />
          ) : (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base font-semibold text-foreground">{t('telemetry.speed')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <TelemetryChart
                    data={telemetryQuery.data ?? []}
                    metric="speed"
                    label={t('telemetry.speed')}
                    unit=" km/h"
                    color="hsl(var(--primary))"
                    isLoading={telemetryQuery.isLoading}
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base font-semibold text-foreground">
                    {t('telemetry.fuelLevel')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <TelemetryChart
                    data={telemetryQuery.data ?? []}
                    metric="fuel_level"
                    label={t('telemetry.fuelLevel')}
                    unit="%"
                    color="hsl(var(--success))"
                    isLoading={telemetryQuery.isLoading}
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base font-semibold text-foreground">
                    {t('telemetry.engineTemperature')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <TelemetryChart
                    data={telemetryQuery.data ?? []}
                    metric="engine_temperature"
                    label={t('telemetry.engineTemp')}
                    unit="°C"
                    color="hsl(var(--warning))"
                    isLoading={telemetryQuery.isLoading}
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base font-semibold text-foreground">
                    {t('telemetry.batteryVoltage')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <TelemetryChart
                    data={telemetryQuery.data ?? []}
                    metric="battery_voltage"
                    label={t('telemetry.battery')}
                    unit="V"
                    color="hsl(var(--destructive))"
                    isLoading={telemetryQuery.isLoading}
                  />
                </CardContent>
              </Card>
            </div>
          )}

          {latest && (
            <p className="text-xs text-muted-foreground">
              {t('telemetry.showingReadings', { time: formatDateTime(latest.received_at) })}
            </p>
          )}
        </>
      )}
    </div>
  );
}

function SnapshotCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="num-tabular text-xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  );
}
