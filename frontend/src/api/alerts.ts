import type { ApiList } from '@/types/common';
import type { Alert } from '@/types/alerts';

import { apiClient } from './client';

export const alertsApi = {
  /** Admin sees all alerts; Fleet Manager sees alerts for assigned vehicles. */
  list: () => apiClient.get<ApiList<Alert>>('/alerts/').then((r) => r.data),

  get: (alertId: number) => apiClient.get<Alert>(`/alerts/${alertId}/`).then((r) => r.data),

  /** Acknowledges for the caller only; other users/roles still see the alert as open. */
  acknowledge: (alertId: number) =>
    apiClient.post<Alert>(`/alerts/${alertId}/acknowledge/`).then((r) => r.data),

  /** Removes the alert from the caller's own lists only; other users still see it. */
  remove: (alertId: number) => apiClient.delete(`/alerts/${alertId}/`).then(() => undefined),

  /** Driver-role only. */
  listMine: () => apiClient.get<ApiList<Alert>>('/alerts/me/').then((r) => r.data),

  acknowledgeMine: (alertId: number) =>
    apiClient.post<Alert>('/alerts/me/acknowledge/', { alert_id: alertId }).then((r) => r.data),
};
