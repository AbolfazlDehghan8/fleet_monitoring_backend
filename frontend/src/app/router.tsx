import * as React from 'react';
import { Route, Routes } from 'react-router-dom';

import { OPERATOR_ROLES, ROLES } from '@/constants/roles';

import { AppLayout } from './AppLayout';
import { RequireAuth } from './RequireAuth';

const LoginPage = React.lazy(() => import('@/features/auth/LoginPage').then((m) => ({ default: m.LoginPage })));
const RegisterPage = React.lazy(() =>
  import('@/features/auth/RegisterPage').then((m) => ({ default: m.RegisterPage })),
);
const DashboardPage = React.lazy(() =>
  import('@/features/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })),
);
const VehiclesListPage = React.lazy(() =>
  import('@/features/vehicles/VehiclesListPage').then((m) => ({ default: m.VehiclesListPage })),
);
const VehicleDetailPage = React.lazy(() =>
  import('@/features/vehicles/VehicleDetailPage').then((m) => ({ default: m.VehicleDetailPage })),
);
const VehicleFormPage = React.lazy(() =>
  import('@/features/vehicles/VehicleFormPage').then((m) => ({ default: m.VehicleFormPage })),
);
const MyVehicleDetailPage = React.lazy(() =>
  import('@/features/vehicles/MyVehicleDetailPage').then((m) => ({ default: m.MyVehicleDetailPage })),
);
const DriversListPage = React.lazy(() =>
  import('@/features/drivers/DriversListPage').then((m) => ({ default: m.DriversListPage })),
);
const DriverFormPage = React.lazy(() =>
  import('@/features/drivers/DriverFormPage').then((m) => ({ default: m.DriverFormPage })),
);
const AdminUsersListPage = React.lazy(() =>
  import('@/features/admin/AdminUsersListPage').then((m) => ({ default: m.AdminUsersListPage })),
);
const AdminUserFormPage = React.lazy(() =>
  import('@/features/admin/AdminUserFormPage').then((m) => ({ default: m.AdminUserFormPage })),
);
const TelemetryPage = React.lazy(() =>
  import('@/features/telemetry/TelemetryPage').then((m) => ({ default: m.TelemetryPage })),
);
const AlertsListPage = React.lazy(() =>
  import('@/features/alerts/AlertsListPage').then((m) => ({ default: m.AlertsListPage })),
);
const MyAlertsListPage = React.lazy(() =>
  import('@/features/alerts/MyAlertsListPage').then((m) => ({ default: m.MyAlertsListPage })),
);
const AlertDetailPage = React.lazy(() =>
  import('@/features/alerts/AlertDetailPage').then((m) => ({ default: m.AlertDetailPage })),
);
const RulesListPage = React.lazy(() =>
  import('@/features/rules/RulesListPage').then((m) => ({ default: m.RulesListPage })),
);
const RuleFormPage = React.lazy(() =>
  import('@/features/rules/RuleFormPage').then((m) => ({ default: m.RuleFormPage })),
);
const ReportsListPage = React.lazy(() =>
  import('@/features/reports/ReportsListPage').then((m) => ({ default: m.ReportsListPage })),
);
const ReportDetailPage = React.lazy(() =>
  import('@/features/reports/ReportDetailPage').then((m) => ({ default: m.ReportDetailPage })),
);
const NotFoundPage = React.lazy(() =>
  import('@/features/misc/NotFoundPage').then((m) => ({ default: m.NotFoundPage })),
);
const UnauthorizedPage = React.lazy(() =>
  import('@/features/misc/UnauthorizedPage').then((m) => ({ default: m.UnauthorizedPage })),
);

function Suspended({ children }: { children: React.ReactNode }) {
  return (
    <React.Suspense
      fallback={
        <div className="flex min-h-40 items-center justify-center text-sm text-muted-foreground">Loading…</div>
      }
    >
      {children}
    </React.Suspense>
  );
}

export function AppRouter() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <Suspended>
            <LoginPage />
          </Suspended>
        }
      />
      <Route
        path="/register"
        element={
          <Suspended>
            <RegisterPage />
          </Suspended>
        }
      />
      <Route
        path="/403"
        element={
          <Suspended>
            <UnauthorizedPage />
          </Suspended>
        }
      />

      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route
            index
            element={
              <Suspended>
                <DashboardPage />
              </Suspended>
            }
          />

          <Route element={<RequireAuth allowedRoles={[ROLES.DRIVER]} />}>
            <Route
              path="my-vehicle/:id"
              element={
                <Suspended>
                  <MyVehicleDetailPage />
                </Suspended>
              }
            />
            <Route
              path="my-alerts"
              element={
                <Suspended>
                  <MyAlertsListPage />
                </Suspended>
              }
            />
            <Route
              path="my-alerts/:id"
              element={
                <Suspended>
                  <AlertDetailPage backTo="/my-alerts" backLabelKey="alertDetail.backToMyAlerts" />
                </Suspended>
              }
            />
          </Route>

          <Route element={<RequireAuth allowedRoles={OPERATOR_ROLES} />}>
            <Route
              path="vehicles"
              element={
                <Suspended>
                  <VehiclesListPage />
                </Suspended>
              }
            />
            <Route
              path="vehicles/new"
              element={
                <Suspended>
                  <VehicleFormPage />
                </Suspended>
              }
            />
            <Route
              path="vehicles/:id"
              element={
                <Suspended>
                  <VehicleDetailPage />
                </Suspended>
              }
            />
            <Route
              path="vehicles/:id/edit"
              element={
                <Suspended>
                  <VehicleFormPage />
                </Suspended>
              }
            />
            <Route
              path="drivers"
              element={
                <Suspended>
                  <DriversListPage />
                </Suspended>
              }
            />
            <Route
              path="drivers/new"
              element={
                <Suspended>
                  <DriverFormPage />
                </Suspended>
              }
            />
            <Route
              path="drivers/:id/edit"
              element={
                <Suspended>
                  <DriverFormPage />
                </Suspended>
              }
            />
            <Route
              path="telemetry"
              element={
                <Suspended>
                  <TelemetryPage />
                </Suspended>
              }
            />
            <Route
              path="alerts"
              element={
                <Suspended>
                  <AlertsListPage />
                </Suspended>
              }
            />
            <Route
              path="alerts/:id"
              element={
                <Suspended>
                  <AlertDetailPage />
                </Suspended>
              }
            />
            <Route
              path="reports"
              element={
                <Suspended>
                  <ReportsListPage />
                </Suspended>
              }
            />
            <Route
              path="reports/:id"
              element={
                <Suspended>
                  <ReportDetailPage />
                </Suspended>
              }
            />
          </Route>

          <Route element={<RequireAuth allowedRoles={[ROLES.ADMIN]} />}>
            <Route
              path="rules"
              element={
                <Suspended>
                  <RulesListPage />
                </Suspended>
              }
            />
            <Route
              path="rules/new"
              element={
                <Suspended>
                  <RuleFormPage />
                </Suspended>
              }
            />
            <Route
              path="rules/:id/edit"
              element={
                <Suspended>
                  <RuleFormPage />
                </Suspended>
              }
            />
            <Route
              path="admin/users"
              element={
                <Suspended>
                  <AdminUsersListPage />
                </Suspended>
              }
            />
            <Route
              path="admin/users/new"
              element={
                <Suspended>
                  <AdminUserFormPage />
                </Suspended>
              }
            />
            <Route
              path="admin/users/:id/edit"
              element={
                <Suspended>
                  <AdminUserFormPage />
                </Suspended>
              }
            />
          </Route>
        </Route>
      </Route>

      <Route
        path="*"
        element={
          <Suspended>
            <NotFoundPage />
          </Suspended>
        }
      />
    </Routes>
  );
}
