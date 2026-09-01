import { useLanguage } from '@/app/LanguageContext';
import { Badge } from '@/components/ui/badge';
import { SEVERITY_TONE, type Severity } from '@/constants/statuses';

export function SeverityBadge({ severity }: { severity: Severity }) {
  const { t } = useLanguage();
  return <Badge variant={SEVERITY_TONE[severity]}>{t(`severity.${severity}`)}</Badge>;
}
