import type { ReportStatus } from '@/constants/statuses';

/** Matches `reports_module.serializers.ReportSerializer`. All fields are read-only. */
export interface Report {
  id: number;
  /** Gap-free per-user display number (oldest = 1) — use this in the UI instead of `id`.
   * Computed server-side by ReportService.attach_sequence_number(s); shifts down for the
   * remaining reports whenever an earlier one is deleted. */
  sequence_number: number;
  requested_by: number | null;
  /** Null for system-generated (scheduled) reports. Lets an admin — who sees every
   * report, not just their own — tell their own reports apart from fleet managers'. */
  requested_by_username: string | null;
  requested_by_role: 'admin' | 'fleet_manager' | 'driver' | null;
  vehicle_id: string;
  period_start: string | null;
  period_end: string | null;
  status: ReportStatus;
  result: FleetSummaryResult | null;
  error_message: string;
  created_at: string;
  completed_at: string | null;
}

export interface ReportQueryParams {
  start_date?: string;
  end_date?: string;
  vehicle_id?: string;
}

/** Matches the payload built by `ReportService.generate_fleet_summary`. */
export interface FleetSummaryResult {
  period: { start: string; end: string };
  vehicle_count: number;
  vehicles_by_status: Record<string, number>;
  telemetry: {
    total_readings: number;
    avg_speed: number | null;
    avg_fuel_level: number | null;
    distance_traveled_km: number;
  };
  alerts: {
    total: number;
    by_severity: Record<string, number>;
    acknowledged: number;
    unacknowledged: number;
    avg_acknowledgment_time_seconds: number | null;
  };
}
