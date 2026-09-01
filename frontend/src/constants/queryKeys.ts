/** Centralized TanStack Query key factory — keeps invalidation consistent per feature. */
export const queryKeys = {
  profile: ['profile'] as const,
  dashboardStats: ['dashboard', 'stats'] as const,
  vehicles: {
    all: ['vehicles'] as const,
    detail: (id: number) => ['vehicles', id] as const,
    status: (id: number) => ['vehicles', id, 'status'] as const,
    mine: ['vehicles', 'mine'] as const,
  },
  drivers: {
    all: ['drivers'] as const,
  },
  adminUsers: {
    all: (role?: string) => ['admin', 'users', role ?? 'all'] as const,
    detail: (id: number) => ['admin', 'users', id] as const,
  },
  telemetry: {
    list: (vehicleId?: string) => ['telemetry', vehicleId ?? 'all'] as const,
    mine: ['telemetry', 'mine'] as const,
  },
  rules: {
    all: (isActive?: boolean) => ['rules', isActive ?? 'all'] as const,
    detail: (id: number) => ['rules', id] as const,
  },
  alerts: {
    all: ['alerts'] as const,
    detail: (id: number) => ['alerts', id] as const,
    mine: ['alerts', 'mine'] as const,
  },
  reports: {
    all: ['reports'] as const,
    detail: (id: number) => ['reports', id] as const,
    fleetSummary: (params: string) => ['reports', 'fleet-summary', params] as const,
  },
};
