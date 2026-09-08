import type * as React from 'react';

import { ArrowLeft, CheckCircle2 } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { SeverityBadge } from '@/components/shared/SeverityBadge';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/use-toast';
import { useAcknowledgeAlert, useAlert } from '@/features/alerts/hooks';
import { formatDateTime } from '@/utils/formatters';
import { ApiError } from '@/types/common';

/**
 * Shared alert detail view. The underlying `/alerts/:id/` and `/alerts/:id/acknowledge/`
 * endpoints scope-check server-side (Admin/Fleet Manager/Driver each see only what they're
 * allowed to), so this same page serves the driver's own-alert detail too — only the back
 * link needs to point at the caller's list page (`/alerts` for operators, `/my-alerts` for
 * drivers).
 */
export function AlertDetailPage({
  backTo = '/alerts',
  backLabelKey = 'alertDetail.backToAlerts',
}: {
  backTo?: string;
  backLabelKey?: 'alertDetail.backToAlerts' | 'alertDetail.backToMyAlerts';
}) {
  const { t } = useLanguage();
  const params = useParams<{ id: string }>();
  const alertId = Number(params.id);

  const alertQuery = useAlert(alertId);
  const acknowledgeMutation = useAcknowledgeAlert();

  async function handleAcknowledge() {
    try {
      await acknowledgeMutation.mutateAsync(alertId);
      toast({ title: t('alerts.alertAcknowledged'), variant: 'success' });
    } catch (error) {
      toast({
        title: t('alerts.failedToAcknowledge'),
        description: error instanceof ApiError ? ApiError.extractMessage(error.body) : undefined,
        variant: 'destructive',
      });
    }
  }

  if (alertQuery.isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-56 w-full rounded-xl" />
      </div>
    );
  }

  if (alertQuery.isError || !alertQuery.data) {
    return <ErrorState onRetry={() => void alertQuery.refetch()} title={t('alertDetail.unableToLoad')} />;
  }

  const alert = alertQuery.data;

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2 -ms-2 text-muted-foreground">
          <Link to={backTo}>
            <ArrowLeft className="size-3.5" />
            {t(backLabelKey)}
          </Link>
        </Button>
        <PageHeader
          title={alert.rule_name}
          description={t('alertDetail.triggeredOn', {
            vehicle: alert.vehicle_id,
            time: formatDateTime(alert.created_at),
          })}
          actions={
            !alert.acknowledged ? (
              <Button onClick={() => void handleAcknowledge()} disabled={acknowledgeMutation.isPending}>
                <CheckCircle2 className="size-4" />
                {acknowledgeMutation.isPending
                  ? t('alertDetail.acknowledging')
                  : t('alertDetail.acknowledgeAlert')}
              </Button>
            ) : (
              <Badge variant="success" className="text-sm">
                {t('alerts.acknowledged')}
              </Badge>
            )
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">
              {t('alertDetail.alertDetails')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label={t('alerts.colSeverity')} value={<SeverityBadge severity={alert.severity} />} />
            <Row label={t('alerts.colVehicle')} value={<span className="font-mono">{alert.vehicle_id}</span>} />
            <Row label={t('alertDetail.metric')} value={alert.metric} />
            <Row label={t('alertDetail.threshold')} value={String(alert.threshold)} />
            <Row label={t('alertDetail.recordedValue')} value={String(alert.value)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">
              {t('alertDetail.triggeringRule')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label={t('alertDetail.ruleName')} value={alert.rule_name} />
            <Row label={t('alertDetail.metricMonitored')} value={alert.metric} />
            <Row label={t('alertDetail.threshold')} value={String(alert.threshold)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">
              {t('alertDetail.acknowledgment')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label={t('common.status')} value={alert.acknowledged ? t('alerts.acknowledged') : t('alerts.open')} />
            <Row label={t('alertDetail.acknowledgedBy')} value={alert.acknowledged_by_username ?? t('common.notAvailable')} />
            <Row label={t('alertDetail.acknowledgedAt')} value={formatDateTime(alert.acknowledged_at)} />
            <Row label={t('alertDetail.createdAt')} value={formatDateTime(alert.created_at)} />
          </CardContent>
        </Card>
      </div>
    </div>
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
