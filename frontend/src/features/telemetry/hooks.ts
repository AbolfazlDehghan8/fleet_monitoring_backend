import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { telemetryApi } from '@/api/telemetry';
import { queryKeys } from '@/constants/queryKeys';
import type { TelemetryIngestRequest } from '@/types/telemetry';

const POLL_INTERVAL_MS = Number(import.meta.env.VITE_POLL_INTERVAL_MS ?? 15000);

export function useTelemetry(vehicleId?: string) {
  return useQuery({
    queryKey: queryKeys.telemetry.list(vehicleId),
    queryFn: () => telemetryApi.list(vehicleId ? { vehicle_id: vehicleId } : undefined),
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useMyTelemetry() {
  return useQuery({
    queryKey: queryKeys.telemetry.mine,
    queryFn: telemetryApi.listMine,
    refetchInterval: POLL_INTERVAL_MS,
  });
}

/** Submits a manual/simulated telemetry reading — see `telemetryApi.ingest`. */
export function useIngestTelemetry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TelemetryIngestRequest) => telemetryApi.ingest(payload),
    onSuccess: (_data, variables) => {
      // The worker persists the row asynchronously — give it a moment, then
      // refresh whatever telemetry/alert views are open.
      setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: queryKeys.telemetry.list(variables.vehicle_id) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.telemetry.list(undefined) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.alerts.all });
        void queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
      }, 1500);
    },
  });
}
