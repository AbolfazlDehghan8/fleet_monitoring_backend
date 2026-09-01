import type {
  ChangePasswordRequest,
  LoginRequest,
  LoginResponse,
  Profile,
  ProfileUpdateRequest,
  RegisterRequest,
  RegisterResponse,
} from '@/types/auth';

import { apiClient } from './client';

export const authApi = {
  login: (payload: LoginRequest) =>
    apiClient.post<LoginResponse>('/auth/login/', payload).then((r) => r.data),

  /** Public, unauthenticated. Always creates a driver-role account —
   * elevated roles must be granted afterwards by an Admin via /admin/users/. */
  register: (payload: RegisterRequest) =>
    apiClient.post<RegisterResponse>('/auth/register/', payload).then((r) => r.data),

  logout: (refreshToken?: string) =>
    apiClient.post<{ message: string }>('/auth/logout/', { refresh_token: refreshToken }).then((r) => r.data),

  getProfile: () => apiClient.get<Profile>('/auth/profile/').then((r) => r.data),

  updateProfile: (payload: ProfileUpdateRequest) =>
    apiClient.patch<Profile>('/auth/profile/', payload).then((r) => r.data),

  changePassword: (payload: ChangePasswordRequest) =>
    apiClient.post<{ message: string }>('/auth/profile/change-password/', payload).then((r) => r.data),
};
