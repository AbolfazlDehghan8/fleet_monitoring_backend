import type { ApiList } from '@/types/common';
import type { Rule, RuleListParams, RuleWriteRequest } from '@/types/rules';

import { apiClient } from './client';

export const rulesApi = {
  /** Admin only. */
  list: (params?: RuleListParams) =>
    apiClient
      .get<ApiList<Rule>>('/rules/', {
        params: params?.is_active === undefined ? undefined : { is_active: params.is_active },
      })
      .then((r) => r.data),

  get: (ruleId: number) => apiClient.get<Rule>(`/rules/${ruleId}/`).then((r) => r.data),

  create: (payload: RuleWriteRequest) => apiClient.post<Rule>('/rules/', payload).then((r) => r.data),

  update: (ruleId: number, payload: Partial<RuleWriteRequest>) =>
    apiClient.patch<Rule>(`/rules/${ruleId}/`, payload).then((r) => r.data),

  remove: (ruleId: number) => apiClient.delete<void>(`/rules/${ruleId}/`).then((r) => r.data),
};
