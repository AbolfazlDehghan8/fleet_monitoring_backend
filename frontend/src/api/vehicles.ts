import type { ApiList } from '@/types/common';
import type {
  DashboardStats,
  Driver,
  DriverCreateRequest,
  DriverUpdateRequest,
  LinkableUser,
  Vehicle,
  VehicleCreateRequest,
  VehicleStatusPayload,
  VehicleUpdateRequest,
} from '@/types/vehicles';

import { apiClient } from './client';

export const vehiclesApi = {
  /** Admin sees every vehicle; Fleet Manager sees only vehicles assigned to them. */
  list: () => apiClient.get<ApiList<Vehicle>>('/vehicles/').then((r) => r.data),

  get: (vehicleId: number) => apiClient.get<Vehicle>(`/vehicles/${vehicleId}/`).then((r) => r.data),

  create: (payload: VehicleCreateRequest) =>
    apiClient.post<Vehicle>('/vehicles/', payload).then((r) => r.data),

  update: (vehicleId: number, payload: VehicleUpdateRequest) =>
    apiClient.patch<Vehicle>(`/vehicles/${vehicleId}/`, payload).then((r) => r.data),

  remove: (vehicleId: number) => apiClient.delete<void>(`/vehicles/${vehicleId}/`).then((r) => r.data),

  getStatus: (vehicleId: number) =>
    apiClient.get<VehicleStatusPayload>(`/vehicles/${vehicleId}/status/`).then((r) => r.data),

  getDashboardStats: () =>
    apiClient.get<DashboardStats>('/vehicles/dashboard-stats/').then((r) => r.data),

  /** Driver-role only: the authenticated driver's own assigned vehicle(s). */
  getMine: () => apiClient.get<ApiList<Vehicle>>('/vehicles/me/').then((r) => r.data),
};

export const driversApi = {
  /** Roster view — Admin sees every driver; Fleet Manager sees only drivers
   * already assigned to their vehicles (per the Access Control Matrix). */
  list: () => apiClient.get<ApiList<Driver>>('/vehicles/drivers/').then((r) => r.data),

  /** Driver-role users with no driver profile yet. Populates the "linked user"
   * picker on the driver-profile creation form for Admin AND Fleet Manager. */
  listLinkableUsers: () =>
    apiClient.get<ApiList<LinkableUser>>('/vehicles/drivers/linkable-users/').then((r) => r.data),

  /** Drivers eligible for assignment to a vehicle this actor manages: Admin sees
   * all; Fleet Manager sees drivers on their own vehicles PLUS drivers not yet
   * linked to any vehicle. Use this (not `list`) to populate the vehicle-form
   * driver dropdown, otherwise a freshly created driver can never be selected. */
  listAssignable: () =>
    apiClient.get<ApiList<Driver>>('/vehicles/drivers/assignable/').then((r) => r.data),

  get: (driverId: number) => apiClient.get<Driver>(`/vehicles/drivers/${driverId}/`).then((r) => r.data),

  create: (payload: DriverCreateRequest) =>
    apiClient.post<Driver>('/vehicles/drivers/', payload).then((r) => r.data),

  update: (driverId: number, payload: DriverUpdateRequest) =>
    apiClient.patch<Driver>(`/vehicles/drivers/${driverId}/`, payload).then((r) => r.data),

  remove: (driverId: number) =>
    apiClient.delete<void>(`/vehicles/drivers/${driverId}/`).then((r) => r.data),
};
