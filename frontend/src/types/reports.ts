import type { ReportStatus } from '@/constants/statuses';

/** Matches `reports_module.serializers.ReportSerializer`. All fields are read-only. */
export interface Report {
  id: number;
  requested_by: number | null;
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
