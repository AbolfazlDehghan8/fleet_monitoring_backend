import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { rulesApi } from '@/api/rules';
import { queryKeys } from '@/constants/queryKeys';
import type { RuleWriteRequest } from '@/types/rules';

export function useRules(isActive?: boolean) {
  return useQuery({
    queryKey: queryKeys.rules.all(isActive),
    queryFn: () => rulesApi.list(isActive === undefined ? undefined : { is_active: isActive }),
  });
}

export function useRule(ruleId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.rules.detail(ruleId ?? -1),
    queryFn: () => rulesApi.get(ruleId as number),
    enabled: ruleId !== undefined,
  });
}

export function useCreateRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RuleWriteRequest) => rulesApi.create(payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['rules'] }),
  });
}

export function useUpdateRule(ruleId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<RuleWriteRequest>) => rulesApi.update(ruleId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['rules'] });
    },
  });
}

export function useDeleteRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ruleId: number) => rulesApi.remove(ruleId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['rules'] }),
  });
}
