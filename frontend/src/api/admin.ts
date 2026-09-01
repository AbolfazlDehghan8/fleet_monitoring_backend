import type {
  AdminUser,
  AdminUserCreateRequest,
  AdminUserListParams,
  AdminUserUpdateRequest,
} from '@/types/admin';

import { apiClient } from './client';

export const adminUsersApi = {
  /** Admin only. Optionally filtered by role (e.g. to pick a fleet manager to
   * assign a vehicle to, or a driver-role user to link a driver profile to). */
  list: (params?: AdminUserListParams) =>
    apiClient.get<AdminUser[]>('/admin/users/', { params }).then((r) => r.data),

  get: (userId: number) => apiClient.get<AdminUser>(`/admin/users/${userId}/`).then((r) => r.data),

  create: (payload: AdminUserCreateRequest) =>
    apiClient.post<AdminUser>('/admin/users/', payload).then((r) => r.data),

  update: (userId: number, payload: AdminUserUpdateRequest) =>
    apiClient.patch<AdminUser>(`/admin/users/${userId}/`, payload).then((r) => r.data),

  remove: (userId: number) => apiClient.delete<void>(`/admin/users/${userId}/`).then((r) => r.data),
};
