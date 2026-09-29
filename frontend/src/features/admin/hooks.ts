import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { adminUsersApi } from '@/api/admin';
import { queryKeys } from '@/constants/queryKeys';
import type { Role } from '@/constants/roles';
import type { AdminUserCreateRequest, AdminUserUpdateRequest } from '@/types/admin';

export function useAdminUsers(role?: Role) {
  return useQuery({
    queryKey: queryKeys.adminUsers.all(role),
    queryFn: () => adminUsersApi.list(role ? { role } : undefined),
  });
}

export function useAdminUser(userId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.adminUsers.detail(userId ?? -1),
    queryFn: () => adminUsersApi.get(userId as number),
    enabled: userId !== undefined,
  });
}

export function useCreateAdminUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdminUserCreateRequest) => adminUsersApi.create(payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
  });
}

export function useUpdateAdminUser(userId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdminUserUpdateRequest) => adminUsersApi.update(userId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.drivers.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.vehicles.all });
    },
  });
}

export function useDeleteAdminUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) => adminUsersApi.remove(userId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
  });
}
