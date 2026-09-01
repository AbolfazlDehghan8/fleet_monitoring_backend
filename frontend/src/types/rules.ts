import type { RuleMetric, RuleOperator, Severity } from '@/constants/statuses';

/** Matches `rules_module.serializers.RuleSerializer`. */
export interface Rule {
  id: number;
  name: string;
  description: string;
  metric: RuleMetric;
  operator: RuleOperator;
  threshold: number;
  severity: Severity;
  is_active: boolean;
  created_by_username: string | null;
  created_at: string;
  updated_at: string;
}

/** Matches `rules_module.serializers.RuleWriteSerializer`. */
export interface RuleWriteRequest {
  name: string;
  description?: string;
  metric: RuleMetric;
  operator: RuleOperator;
  threshold: number;
  severity: Severity;
  is_active: boolean;
}

export interface RuleListParams {
  is_active?: boolean;
}
