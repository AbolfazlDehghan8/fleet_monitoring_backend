/**
 * Mirrors `auth_module.models.User.Role` exactly.
 * Do not rename — these values are sent to / received from the API verbatim.
 */
export const ROLES = {
  ADMIN: 'admin',
  FLEET_MANAGER: 'fleet_manager',
  DRIVER: 'driver',
} as const;

export type Role = (typeof ROLES)[keyof typeof ROLES];

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Admin',
  fleet_manager: 'Fleet Manager',
  driver: 'Driver',
};

/** Admin and Fleet Manager both reach the operations console (vehicles, alerts, reports). */
export const OPERATOR_ROLES: Role[] = [ROLES.ADMIN, ROLES.FLEET_MANAGER];
