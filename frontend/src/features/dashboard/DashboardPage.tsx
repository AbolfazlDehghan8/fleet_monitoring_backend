import { motion } from 'framer-motion';
import { AlertTriangle, ArrowRight, CheckCircle2, ShieldAlert, Truck } from 'lucide-react';
import { Link } from 'react-router-dom';

import { StatCard } from '@/components/shared/StatCard';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { SeverityBadge } from '@/components/shared/SeverityBadge';
import { useLanguage } from '@/app/LanguageContext';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { CardGridSkeleton, TableSkeleton } from '@/components/shared/LoadingSkeleton';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { VehicleStatus } from '@/constants/statuses';
import { useAlerts } from '@/features/alerts/hooks';
import { useDashboardStats, useVehicles } from '@/features/vehicles/hooks';
import { formatRelativeTime } from '@/utils/formatters';

export function DashboardPage() {
  const { t } = useLanguage();
  const statsQuery = useDashboardStats();
  const vehiclesQuery = useVehicles();
  const alertsQuery = useAlerts();

  const recentAlerts = [...(alertsQuery.data ?? [])]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 6);

  const activeVehicleCount = statsQuery.data?.vehicles_by_status.active ?? 0;
  const violatedVehicleCount = new Set((alertsQuery.data ?? []).filter((a) => !a.acknowledged).map((a) => a.vehicle_id))
    .size;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('dashboard.title')}
        description={t('dashboard.description')}
      />

      {statsQuery.isLoading ? (
        <CardGridSkeleton />
      ) : statsQuery.isError ? (
        <ErrorState onRetry={() => void statsQuery.refetch()} />
      ) : statsQuery.data ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label={t('dashboard.totalVehicles')}
            value={statsQuery.data.total_vehicles}
            icon={Truck}
            delay={0}
          />
          <StatCard
            label={t('dashboard.activeVehicles')}
            value={activeVehicleCount}
            icon={CheckCircle2}
            tone="success"
            delay={0.05}
          />
          <StatCard
            label={t('dashboard.openAlerts')}
            value={statsQuery.data.unacknowledged_alerts}
            icon={AlertTriangle}
            tone={statsQuery.data.unacknowledged_alerts > 0 ? 'warning' : 'default'}
            delay={0.1}
          />
          <StatCard
            label={t('dashboard.vehiclesWithViolations')}
            value={violatedVehicleCount}
            icon={ShieldAlert}
            tone={violatedVehicleCount > 0 ? 'destructive' : 'default'}
            delay={0.15}
          />
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base font-semibold text-foreground">
              {t('dashboard.fleetStatusOverview')}
            </CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link to="/vehicles">
                {t('dashboard.viewAll')}
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {vehiclesQuery.isLoading ? (
              <TableSkeleton rows={4} columns={3} />
            ) : vehiclesQuery.isError ? (
              <ErrorState onRetry={() => void vehiclesQuery.refetch()} />
            ) : vehiclesQuery.data && vehiclesQuery.data.length > 0 ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {vehiclesQuery.data.slice(0, 9).map((vehicle, index) => (
                  <motion.div
                    key={vehicle.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25, delay: index * 0.03 }}
                    whileHover={{ scale: 1.015 }}
                  >
                    <Link
                      to={`/vehicles/${vehicle.id}`}
                      className="flex flex-col gap-2 rounded-lg border border-border p-3 transition-colors hover:border-primary/40 hover:bg-accent/40"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-sm font-medium">{vehicle.vehicle_id}</span>
                        <StatusBadge status={vehicle.status} />
                      </div>
                      <p className="truncate text-xs text-muted-foreground">
                        {vehicle.make} {vehicle.model} · {vehicle.license_plate}
                      </p>
                    </Link>
                  </motion.div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={Truck}
                title={t('dashboard.noVehiclesYet')}
                description={t('dashboard.noVehiclesYetDesc')}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base font-semibold text-foreground">
              {t('dashboard.recentAlerts')}
            </CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link to="/alerts">
                {t('dashboard.viewAll')}
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {alertsQuery.isLoading ? (
              <TableSkeleton rows={4} columns={2} />
            ) : alertsQuery.isError ? (
              <ErrorState onRetry={() => void alertsQuery.refetch()} />
            ) : recentAlerts.length > 0 ? (
              <ul className="space-y-3">
                {recentAlerts.map((alert) => (
                  <li key={alert.id}>
                    <Link
                      to={`/alerts/${alert.id}`}
                      className="flex items-start justify-between gap-3 rounded-lg border border-border p-3 transition-colors hover:border-primary/40 hover:bg-accent/40"
                    >
                      <div className="min-w-0 space-y-1">
                        <p className="truncate text-sm font-medium">{alert.rule_name}</p>
                        <p className="truncate text-xs text-muted-foreground">
                          {alert.vehicle_id} · {formatRelativeTime(alert.created_at)}
                        </p>
                      </div>
                      <SeverityBadge severity={alert.severity} />
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState icon={CheckCircle2} title={t('dashboard.noAlerts')} description={t('dashboard.noAlertsDesc')} />
            )}
          </CardContent>
        </Card>
      </div>

      {statsQuery.data && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">
              {t('dashboard.vehiclesByStatus')}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-6">
            {(Object.entries(statsQuery.data.vehicles_by_status) as [VehicleStatus, number][]).map(
              ([status, count]) => (
                <div key={status} className="flex items-center gap-2">
                  <StatusBadge status={status} />
                  <span className="num-tabular text-sm text-muted-foreground">
                    {count} {t(`vehicleStatus.${status}`)}
                  </span>
                </div>
              ),
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
