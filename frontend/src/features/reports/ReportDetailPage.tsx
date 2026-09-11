import type * as React from 'react';

import { ArrowLeft, Download, Loader2 } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { ReportStatusBadge } from '@/components/shared/ReportStatusBadge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/use-toast';
import type { TranslationKey } from '@/i18n/translations';
import { ApiError } from '@/types/common';
import { formatDateTime, formatNumber } from '@/utils/formatters';

import { useExportReportCsv, useReport } from './hooks';

export function ReportDetailPage() {
  const { t } = useLanguage();
  const params = useParams<{ id: string }>();
  const reportId = Number(params.id);

  const reportQuery = useReport(reportId);
  const exportMutation = useExportReportCsv();

  async function handleExport() {
    try {
      const blob = await exportMutation.mutateAsync(reportId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `fleet-report-${reportId}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast({
        title: t('reportDetail.exportFailed'),
        description: error instanceof ApiError ? ApiError.extractMessage(error.body) : undefined,
        variant: 'destructive',
      });
    }
  }

  if (reportQuery.isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-56 w-full rounded-xl" />
      </div>
    );
  }

  if (reportQuery.isError || !reportQuery.data) {
    return <ErrorState onRetry={() => void reportQuery.refetch()} title={t('reportDetail.unableToLoad')} />;
  }

  const report = reportQuery.data;
  const summary = report.result;

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2 -ms-2 text-muted-foreground">
          <Link to="/reports">
            <ArrowLeft className="size-3.5" />
            {t('reportDetail.backToReports')}
          </Link>
        </Button>
        <PageHeader
          title={t('reportDetail.reportNumber', { id: report.id })}
          description={
            report.vehicle_id
              ? t('reportDetail.scopedTo', { vehicle: report.vehicle_id })
              : t('reports.entireFleet')
          }
          actions={
            <div className="flex items-center gap-2">
              <ReportStatusBadge status={report.status} />
              {report.status === 'completed' && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void handleExport()}
                  disabled={exportMutation.isPending}
                >
                  {exportMutation.isPending ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Download className="size-4" />
                  )}
                  {t('reportDetail.exportCsv')}
                </Button>
              )}
            </div>
          }
        />
      </div>

      {(report.status === 'pending' || report.status === 'running') && (
        <Card>
          <CardContent className="flex items-center gap-3 p-6 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            {t('reportDetail.generating')}
          </CardContent>
        </Card>
      )}

      {report.status === 'failed' && (
        <ErrorState
          title={t('reportDetail.generationFailed')}
          description={report.error_message || t('reportDetail.unknownError')}
        />
      )}

      {summary && (
        <>
          {/*
           * Defense-in-depth: the backend now always sends `telemetry` and the full
           * `alerts` shape (see reports_module.services.ReportService._build_summary),
           * but we still fall back to safe defaults here in case an older report row,
           * or any future report source, ever sends a partial payload — a missing
           * field should degrade to "—" / 0, not crash the whole page.
           */}
          {(() => {
            const telemetry = summary.telemetry ?? {
              total_readings: 0,
              avg_speed: null,
              avg_fuel_level: null,
              distance_traveled_km: 0,
            };
            const alerts = summary.alerts ?? {
              total: 0,
              by_severity: {},
              acknowledged: 0,
              unacknowledged: 0,
              avg_acknowledgment_time_seconds: null,
            };

            return (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <MetricCard label={t('reportDetail.vehicles')} value={formatNumber(summary.vehicle_count)} />
                  <MetricCard
                    label={t('reportDetail.telemetryReadings')}
                    value={formatNumber(telemetry.total_readings)}
                  />
                  <MetricCard
                    label={t('reportDetail.distanceTraveled')}
                    value={`${formatNumber(telemetry.distance_traveled_km, 1)} km`}
                  />
                  <MetricCard label={t('reportDetail.totalAlerts')} value={formatNumber(alerts.total)} />
                </div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base font-semibold text-foreground">
                        {t('reportDetail.telemetrySummary')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      <Row label={t('reportDetail.periodStart')} value={formatDateTime(summary.period?.start)} />
                      <Row label={t('reportDetail.periodEnd')} value={formatDateTime(summary.period?.end)} />
                      <Row
                        label={t('reportDetail.avgSpeed')}
                        value={`${formatNumber(telemetry.avg_speed ?? 0, 1)} km/h`}
                      />
                      <Row
                        label={t('reportDetail.avgFuelLevel')}
                        value={`${formatNumber(telemetry.avg_fuel_level ?? 0, 1)}%`}
                      />
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base font-semibold text-foreground">
                        {t('reportDetail.alertSummary')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      <Row label={t('reportDetail.acknowledged')} value={formatNumber(alerts.acknowledged)} />
                      <Row label={t('reportDetail.unacknowledged')} value={formatNumber(alerts.unacknowledged)} />
                      {alerts.avg_acknowledgment_time_seconds !== null &&
                        alerts.avg_acknowledgment_time_seconds !== undefined && (
                          <Row
                            label={t('reportDetail.avgAckTime')}
                            value={`${formatNumber(alerts.avg_acknowledgment_time_seconds / 60, 1)} min`}
                          />
                        )}
                      {Object.entries(alerts.by_severity ?? {}).map(([severity, count]) => (
                        <Row
                          key={severity}
                          label={t('reportDetail.severityCount', {
                            severity: t(`severity.${severity}` as TranslationKey),
                          })}
                          value={formatNumber(count)}
                        />
                      ))}
                    </CardContent>
                  </Card>
                </div>
              </>
            );
          })()}
        </>
      )}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="num-tabular text-xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-end font-medium">{value}</span>
    </div>
  );
}
