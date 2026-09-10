import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { authApi } from '@/api/auth';
import { queryKeys } from '@/constants/queryKeys';
import type { ChangePasswordRequest, ProfileUpdateRequest } from '@/types/auth';

export function useProfile() {
  return useQuery({
    queryKey: queryKeys.profile,
    queryFn: () => authApi.getProfile(),
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProfileUpdateRequest) => authApi.updateProfile(payload),
    onSuccess: (profile) => {
      queryClient.setQueryData(queryKeys.profile, profile);
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (payload: ChangePasswordRequest) => authApi.changePassword(payload),
  });
}
