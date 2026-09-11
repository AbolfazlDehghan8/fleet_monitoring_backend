import { OPERATOR_ROLES, ROLES } from './roles';
import type { Role } from './roles';

/**
 * Mirrors the `allowedRoles` restrictions declared in `app/router.tsx`.
 * Used to validate a post-login redirect target (e.g. `location.state.from`)
 * against the role of the user who just logged in, so we never bounce a
 * freshly-authenticated user into a route their role can't see.
 */
const ROUTE_ACCESS: { prefix: string; roles: Role[] }[] = [
  { prefix: '/my-vehicle', roles: [ROLES.DRIVER] },
  { prefix: '/my-alerts', roles: [ROLES.DRIVER] },
  { prefix: '/vehicles', roles: OPERATOR_ROLES },
  { prefix: '/drivers', roles: OPERATOR_ROLES },
  { prefix: '/telemetry', roles: OPERATOR_ROLES },
  { prefix: '/alerts', roles: OPERATOR_ROLES },
  { prefix: '/reports', roles: OPERATOR_ROLES },
  { prefix: '/rules', roles: [ROLES.ADMIN] },
  { prefix: '/admin', roles: [ROLES.ADMIN] },
];

/** Returns true if `role` is allowed to land on `path` directly after login. */
export function canRoleAccessPath(role: Role, path: string): boolean {
  const rule = ROUTE_ACCESS.find((r) => path === r.prefix || path.startsWith(`${r.prefix}/`));
  if (!rule) return true; // unrestricted routes (/, /profile) or unknown paths
  return rule.roles.includes(role);
}

/**
 * Picks a safe redirect target after login: `requestedPath` if the role can
 * actually reach it, otherwise falls back to the dashboard.
 */
export function resolveLoginRedirect(role: Role, requestedPath: string | undefined): string {
  if (!requestedPath) return '/';
  return canRoleAccessPath(role, requestedPath) ? requestedPath : '/';
}
