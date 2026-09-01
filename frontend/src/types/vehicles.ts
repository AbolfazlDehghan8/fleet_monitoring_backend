import type { VehicleStatus } from '@/constants/statuses';

/** Matches `vehicles_module.serializers.OBUSerializer`. */
export interface OBU {
  serial_number: string;
  firmware_version: string;
  is_active: boolean;
  installed_at: string;
}

/** Matches `vehicles_module.serializers.DriverSerializer`. */
export interface Driver {
  id: number;
  user: number;
  username: string;
  email: string;
  full_name: string;
  license_number: string;
  phone_number: string;
  is_active: boolean;
  created_at: string;
}

export interface DriverCreateRequest {
  user: number;
  license_number: string;
  phone_number?: string;
}

export interface DriverUpdateRequest {
  license_number?: string;
  phone_number?: string;
  is_active?: boolean;
}

/** Matches `vehicles_module.serializers.VehicleSerializer`. */
export interface Vehicle {
  id: number;
  vehicle_id: string;
  license_plate: string;
  vin: string | null;
  make: string;
  model: string;
  year: number | null;
  status: VehicleStatus;
  driver: Driver | null;
  assigned_manager: number | null;
  assigned_manager_username: string | null;
  obu: OBU | null;
  created_at: string;
  updated_at: string;
}

export interface VehicleCreateRequest {
  vehicle_id: string;
  license_plate: string;
  vin?: string | null;
  make?: string;
  model?: string;
  year?: number | null;
  status?: VehicleStatus;
  driver?: number | null;
  assigned_manager?: number | null;
  obu_serial_number?: string;
  obu_firmware_version?: string;
}

/** PATCH payload — same shape whether the actor is Admin or Fleet Manager; the
 * backend silently drops `assigned_manager` for a Fleet Manager actor. */
export type VehicleUpdateRequest = Partial<Omit<VehicleCreateRequest, 'vehicle_id'>>;

/** Matches the cached payload from `VehicleService.get_vehicle_status`. */
export interface VehicleStatusPayload {
  vehicle_id: number;
  vehicle_identifier: string;
  status: VehicleStatus;
  updated_at: string;
  live_telemetry?: {
    vehicle_id: string;
    status: VehicleStatus;
    speed: number;
    engine_temperature: number;
    battery_voltage: number;
    fuel_level: number;
    latitude: number;
    longitude: number;
    odometer: number;
    last_seen: string;
  };
}

/** Matches `VehicleService.get_dashboard_stats`. */
export interface DashboardStats {
  total_vehicles: number;
  vehicles_by_status: Record<VehicleStatus, number>;
  unacknowledged_alerts: number;
  generated_at: string;
}
