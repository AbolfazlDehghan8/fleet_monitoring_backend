import { useLanguage } from '@/app/LanguageContext';
import { Badge } from '@/components/ui/badge';
import { REPORT_STATUS_TONE, type ReportStatus } from '@/constants/statuses';

export function ReportStatusBadge({ status }: { status: ReportStatus }) {
  const { t } = useLanguage();
  return <Badge variant={REPORT_STATUS_TONE[status]}>{t(`reportStatus.${status}`)}</Badge>;
}
