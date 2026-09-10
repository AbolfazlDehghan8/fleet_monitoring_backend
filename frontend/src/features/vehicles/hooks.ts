import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { driversApi, vehiclesApi } from '@/api/vehicles';
import { queryKeys } from '@/constants/queryKeys';
import type { DriverCreateRequest, DriverUpdateRequest, VehicleCreateRequest, VehicleUpdateRequest } from '@/types/vehicles';

const POLL_INTERVAL_MS = Number(import.meta.env.VITE_POLL_INTERVAL_MS ?? 15000);

export function useVehicles() {
  return useQuery({
    queryKey: queryKeys.vehicles.all,
    queryFn: vehiclesApi.list,
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useVehicle(vehicleId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.vehicles.detail(vehicleId ?? -1),
    queryFn: () => vehiclesApi.get(vehicleId as number),
    enabled: vehicleId !== undefined,
  });
}

export function useVehicleStatus(vehicleId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.vehicles.status(vehicleId ?? -1),
    queryFn: () => vehiclesApi.getStatus(vehicleId as number),
    enabled: vehicleId !== undefined,
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useDashboardStats() {
  return useQuery({
    queryKey: queryKeys.dashboardStats,
    queryFn: vehiclesApi.getDashboardStats,
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useMyVehicles() {
  return useQuery({
    queryKey: queryKeys.vehicles.mine,
    queryFn: vehiclesApi.getMine,
  });
}

export function useCreateVehicle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: VehicleCreateRequest) => vehiclesApi.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.vehicles.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
      // A driver may have moved from the free pool onto this vehicle.
      void queryClient.invalidateQueries({ queryKey: queryKeys.drivers.assignable });
    },
  });
}

export function useUpdateVehicle(vehicleId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: VehicleUpdateRequest) => vehiclesApi.update(vehicleId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.vehicles.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.vehicles.detail(vehicleId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
      // A driver may have been (re)assigned to or freed from this vehicle.
      void queryClient.invalidateQueries({ queryKey: queryKeys.drivers.assignable });
    },
  });
}

export function useDeleteVehicle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (vehicleId: number) => vehiclesApi.remove(vehicleId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.vehicles.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
    },
  });
}

/** Roster view (Admin: all; Fleet Manager: assigned only) — for the /drivers list page. */
export function useDrivers() {
  return useQuery({
    queryKey: queryKeys.drivers.all,
    queryFn: driversApi.list,
  });
}

/** Driver-role users with no driver profile yet — for the driver-creation form's
 * "linked user" picker. Available to Admin and Fleet Manager alike. */
export function useLinkableDriverUsers() {
  return useQuery({
    queryKey: queryKeys.drivers.linkableUsers,
    queryFn: driversApi.listLinkableUsers,
  });
}

/** Drivers eligible for assignment to a vehicle the current actor manages — for
 * the vehicle form's driver dropdown. Includes not-yet-assigned drivers, unlike
 * `useDrivers`, so a freshly created driver profile is actually selectable. */
export function useAssignableDrivers() {
  return useQuery({
    queryKey: queryKeys.drivers.assignable,
    queryFn: driversApi.listAssignable,
  });
}

export function useCreateDriver() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DriverCreateRequest) => driversApi.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.drivers.all });
      // The new driver leaves the "linkable users" pool and enters the "assignable" one.
      void queryClient.invalidateQueries({ queryKey: queryKeys.drivers.linkableUsers });
      void queryClient.invalidateQueries({ queryKey: queryKeys.drivers.assignable });
    },
  });
}

export function useUpdateDriver(driverId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DriverUpdateRequest) => driversApi.update(driverId, payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.drivers.all }),
  });
}

export function useDriver(driverId: number | undefined) {
  return useQuery({
    queryKey: ['drivers', driverId ?? -1] as const,
    queryFn: () => driversApi.get(driverId as number),
    enabled: driverId !== undefined,
  });
}

/** Admin only — the backend rejects this for Fleet Manager actors. */
export function useDeleteDriver() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (driverId: number) => driversApi.remove(driverId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.drivers.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.vehicles.all });
      // The linked user becomes "linkable" again; the driver leaves the assignable pool.
      void queryClient.invalidateQueries({ queryKey: queryKeys.drivers.linkableUsers });
      void queryClient.invalidateQueries({ queryKey: queryKeys.drivers.assignable });
    },
  });
}
