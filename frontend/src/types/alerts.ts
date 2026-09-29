import type { Severity } from '@/constants/statuses';

/**
 * Matches `alerts_module.serializers.AlertSerializer`. All fields are read-only.
 * `acknowledged*` describe the *current user's* own acknowledgment only (per-user, not shared across roles).
 */
export interface Alert {
  id: number;
  vehicle_id: string;
  rule_name: string;
  metric: string;
  threshold: number;
  value: number;
  severity: Severity;
  acknowledged: boolean;
  acknowledged_by_username: string | null;
  acknowledged_at: string | null;
  created_at: string;
}
