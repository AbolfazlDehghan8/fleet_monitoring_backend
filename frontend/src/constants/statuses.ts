/**
 * Mirrors `vehicles_module.models.Vehicle.Status` exactly.
 */
export const VEHICLE_STATUSES = {
  ACTIVE: 'active',
  MAINTENANCE: 'maintenance',
  INACTIVE: 'inactive',
  DECOMMISSIONED: 'decommissioned',
} as const;

export type VehicleStatus = (typeof VEHICLE_STATUSES)[keyof typeof VEHICLE_STATUSES];

export const VEHICLE_STATUS_LABELS: Record<VehicleStatus, string> = {
  active: 'Active',
  maintenance: 'Maintenance',
  inactive: 'Inactive',
  decommissioned: 'Decommissioned',
};

/** Tailwind-friendly semantic tone per status, consumed by <StatusBadge />. */
export const VEHICLE_STATUS_TONE: Record<VehicleStatus, 'success' | 'warning' | 'muted' | 'destructive'> = {
  active: 'success',
  maintenance: 'warning',
  inactive: 'muted',
  decommissioned: 'destructive',
};

/**
 * Mirrors `reports_module.models.Report.Status` exactly.
 */
export const REPORT_STATUSES = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
} as const;

export type ReportStatus = (typeof REPORT_STATUSES)[keyof typeof REPORT_STATUSES];

export const REPORT_STATUS_LABELS: Record<ReportStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
};

export const REPORT_STATUS_TONE: Record<ReportStatus, 'success' | 'warning' | 'muted' | 'destructive'> = {
  pending: 'muted',
  running: 'warning',
  completed: 'success',
  failed: 'destructive',
};

/**
 * Mirrors `rules_module.models.RULE_SEVERITY_CHOICES` / used on Alert.severity too.
 */
export const SEVERITIES = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical',
} as const;

export type Severity = (typeof SEVERITIES)[keyof typeof SEVERITIES];

export const SEVERITY_LABELS: Record<Severity, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
};

export const SEVERITY_TONE: Record<Severity, 'muted' | 'warning' | 'destructive'> = {
  low: 'muted',
  medium: 'warning',
  high: 'destructive',
  critical: 'destructive',
};

/**
 * Mirrors `rules_module.models.RULE_METRIC_CHOICES` exactly.
 */
export const RULE_METRICS = [
  { value: 'speed', label: 'Speed (km/h)' },
  { value: 'engine_temperature', label: 'Engine Temperature (°C)' },
  { value: 'battery_voltage', label: 'Battery Voltage (V)' },
  { value: 'fuel_level', label: 'Fuel Level (%)' },
  { value: 'odometer', label: 'Odometer (km)' },
] as const;

export type RuleMetric = (typeof RULE_METRICS)[number]['value'];

/**
 * Mirrors `rules_module.models.RULE_OPERATOR_CHOICES` exactly.
 */
export const RULE_OPERATORS = [
  { value: 'gt', label: '>' },
  { value: 'gte', label: '≥' },
  { value: 'lt', label: '<' },
  { value: 'lte', label: '≤' },
  { value: 'eq', label: '=' },
] as const;

export type RuleOperator = (typeof RULE_OPERATORS)[number]['value'];
