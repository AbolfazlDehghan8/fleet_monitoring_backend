/** Matches `telemetry_module.serializers.TelemetryLogSerializer`. */
export interface TelemetryLog {
  id: number;
  vehicle_id: string;
  obu_serial: string;
  timestamp: string;
  speed: number;
  engine_temperature: number;
  battery_voltage: number;
  fuel_level: number;
  latitude: number;
  longitude: number;
  odometer: number;
  received_at: string;
}

export interface TelemetryListParams {
  /** The backend filters by the human-readable `vehicle_id` string, not the numeric pk. */
  vehicle_id?: string;
}

/** Matches `telemetry_module.serializers.TelemetryIngestSerializer`. Used to simulate an
 * OBU packet for manual testing of the rule engine / alerting pipeline. */
export interface TelemetryIngestRequest {
  vehicle_id: string;
  obu_serial: string;
  timestamp: string;
  speed: number;
  engine_temperature: number;
  battery_voltage: number;
  fuel_level: number;
  latitude: number;
  longitude: number;
  odometer: number;
}

export interface TelemetryIngestResponse {
  dispatch_id: string;
}
