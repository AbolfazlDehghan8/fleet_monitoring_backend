import type { Role } from '@/constants/roles';

/** Matches `auth_module.serializers.UserSerializer`. */
export interface User {
  id: number;
  username: string;
  email: string;
  role: Role;
  first_name: string;
  last_name: string;
  is_active: boolean;
  created_at: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
  first_name?: string;
  last_name?: string;
}

/** Self-registration always returns a driver-role account — see
 * `AuthService.register_user`. No tokens are issued; the user must log in
 * separately afterwards. */
export type RegisterResponse = User;

export interface LoginRequest {
  username: string;
  password: string;
}

/** Matches the payload built by `AuthService.login_user`. */
export interface LoginResponse {
  user: {
    id: number;
    username: string;
    email: string;
    role: Role;
    first_name: string;
    last_name: string;
  };
  access_token: string;
  refresh_token: string;
}

export interface RefreshResponse {
  access_token: string;
  refresh_token: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
  new_password_confirm: string;
}

export interface ProfileUpdateRequest {
  first_name?: string;
  last_name?: string;
  email?: string;
}

/** Matches `UserService.get_user_profile`. */
export interface Profile extends User {
  role_display: string;
  full_name: string;
  updated_at: string;
}
