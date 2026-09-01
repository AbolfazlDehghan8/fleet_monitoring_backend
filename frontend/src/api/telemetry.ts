import type { ApiList } from '@/types/common';
import type {
  TelemetryIngestRequest,
  TelemetryIngestResponse,
  TelemetryListParams,
  TelemetryLog,
} from '@/types/telemetry';

import { apiClient } from './client';

export const telemetryApi = {
  /**
   * Admin sees all logs, Fleet Manager sees logs for assigned vehicles.
   * The backend caps this endpoint at the 500 most recent rows and only
   * supports filtering by the vehicle's human-readable `vehicle_id`.
   */
  list: (params?: TelemetryListParams) =>
    apiClient.get<ApiList<TelemetryLog>>('/telemetry/', { params }).then((r) => r.data),

  /** Driver-role only: telemetry for the authenticated driver's own vehicle(s). */
  listMine: () => apiClient.get<ApiList<TelemetryLog>>('/telemetry/me/').then((r) => r.data),

  /**
   * Submits a single telemetry packet as if it came from an OBU device.
   * Any authenticated user may call this — it exists so the ingestion → RabbitMQ →
   * Celery → rule-evaluation → alert pipeline can be exercised manually without
   * real hardware. Returns 202 with a dispatch_id; the row appears in `list()`
   * shortly after once the async worker persists it.
   */
  ingest: (payload: TelemetryIngestRequest) =>
    apiClient.post<TelemetryIngestResponse>('/telemetry/', payload).then((r) => r.data),
};
