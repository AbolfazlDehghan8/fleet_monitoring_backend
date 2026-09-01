import { useLanguage } from '@/app/LanguageContext';
import { Badge } from '@/components/ui/badge';
import { VEHICLE_STATUS_TONE, type VehicleStatus } from '@/constants/statuses';
import { cn } from '@/utils/cn';

export function StatusBadge({ status, className }: { status: VehicleStatus; className?: string }) {
  const { t } = useLanguage();
  const tone = VEHICLE_STATUS_TONE[status];
  return (
    <Badge variant={tone} className={cn('capitalize', className)}>
      <span
        className={cn('size-1.5 rounded-full', {
          'bg-success': tone === 'success',
          'bg-warning': tone === 'warning',
          'bg-destructive': tone === 'destructive',
          'bg-muted-foreground': tone === 'muted',
        })}
      />
      {t(`vehicleStatus.${status}`)}
    </Badge>
  );
}
