import type { ApiList } from '@/types/common';
import type { FleetSummaryResult, Report, ReportQueryParams } from '@/types/reports';

import { apiClient } from './client';

export const reportsApi = {
  list: () => apiClient.get<ApiList<Report>>('/reports/').then((r) => r.data),

  get: (reportId: number) => apiClient.get<Report>(`/reports/${reportId}/`).then((r) => r.data),

  /** Synchronous, ad-hoc summary — computed and returned immediately. */
  fleetSummary: (params?: ReportQueryParams) =>
    apiClient.get<FleetSummaryResult>('/reports/fleet-summary/', { params }).then((r) => r.data),

  /** Queues an async report; poll `get(id)` until status is completed/failed. */
  generate: (params?: ReportQueryParams) =>
    apiClient.post<Report>('/reports/generate/', params).then((r) => r.data),

  /** Returns a CSV Blob — only valid once the report's status is `completed`. */
  exportCsv: (reportId: number) =>
    apiClient
      .get<Blob>(`/reports/${reportId}/export/`, { responseType: 'blob' })
      .then((r) => r.data),
};
