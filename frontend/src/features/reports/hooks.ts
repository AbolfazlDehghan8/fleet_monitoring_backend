import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { reportsApi } from '@/api/reports';
import { queryKeys } from '@/constants/queryKeys';
import type { ReportQueryParams } from '@/types/reports';

export function useReports() {
  return useQuery({
    queryKey: queryKeys.reports.all,
    queryFn: reportsApi.list,
  });
}

export function useReport(reportId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.reports.detail(reportId ?? -1),
    queryFn: () => reportsApi.get(reportId as number),
    enabled: reportId !== undefined,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'pending' || status === 'running' ? 4000 : false;
    },
  });
}

export function useGenerateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params?: ReportQueryParams) => reportsApi.generate(params),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.reports.all }),
  });
}

export function useFleetSummary(params: ReportQueryParams, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.reports.fleetSummary(JSON.stringify(params)),
    queryFn: () => reportsApi.fleetSummary(params),
    enabled,
  });
}

export function useExportReportCsv() {
  return useMutation({
    mutationFn: (reportId: number) => reportsApi.exportCsv(reportId),
  });
}
