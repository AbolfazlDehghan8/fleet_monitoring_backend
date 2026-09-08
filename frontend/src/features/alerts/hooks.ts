import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { alertsApi } from '@/api/alerts';
import { queryKeys } from '@/constants/queryKeys';

const POLL_INTERVAL_MS = Number(import.meta.env.VITE_POLL_INTERVAL_MS ?? 15000);

export function useAlerts() {
  return useQuery({
    queryKey: queryKeys.alerts.all,
    queryFn: alertsApi.list,
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useAlert(alertId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.alerts.detail(alertId ?? -1),
    queryFn: () => alertsApi.get(alertId as number),
    enabled: alertId !== undefined,
  });
}

export function useMyAlerts() {
  return useQuery({
    queryKey: queryKeys.alerts.mine,
    queryFn: alertsApi.listMine,
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alertId: number) => alertsApi.acknowledge(alertId),
    onSuccess: (_data, alertId) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.alerts.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.alerts.detail(alertId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
    },
  });
}

export function useAcknowledgeMyAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alertId: number) => alertsApi.acknowledgeMine(alertId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.alerts.mine });
    },
  });
}
