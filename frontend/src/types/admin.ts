import type { Role } from '@/constants/roles';
import type { User } from '@/types/auth';

/** Matches `auth_module.serializers.AdminUserCreateSerializer`. Admin only —
 * unlike public registration this may create admin/fleet_manager accounts. */
export interface AdminUserCreateRequest {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
  role: Role;
  first_name?: string;
  last_name?: string;
}

/** Matches `auth_module.serializers.AdminUserUpdateSerializer`. */
export interface AdminUserUpdateRequest {
  first_name?: string;
  last_name?: string;
  email?: string;
  role?: Role;
  is_active?: boolean;
}

export interface AdminUserListParams {
  role?: Role;
}

export type AdminUser = User;
