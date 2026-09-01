# Fleet Monitoring Console

A production-grade fleet operations console — the React frontend for the Fleet Monitoring Django REST API. Operators sign in, monitor live vehicle status, review telemetry history, manage alert rules, acknowledge alerts, and generate reports.

> **Backend contract note:** This frontend was built directly against the backend's source (`auth_module`, `vehicles_module`, `telemetry_module`, `rules_module`, `alerts_module`, `reports_module`) rather than a generated OpenAPI schema, since none was reachable during development. Endpoint paths, field names, and enum values below match the backend exactly as of this build. If the backend changes, update `src/types/` and `src/api/` first — everything else is typed against those.

## Features

- **Authentication** — JWT login, automatic access-token refresh via an Axios interceptor, protected routes, and role-aware UI (Admin / Fleet Manager / Driver).
- **Dashboard** — fleet-wide stat cards, vehicle status grid, recent alerts feed.
- **Vehicles** — searchable/filterable list, detail page with driver, OBU, live telemetry snapshot, historical charts, and related alerts.
- **Telemetry** — per-vehicle time-series charts for speed, fuel, engine temperature, and battery voltage, polling for near-real-time updates.
- **Rules** *(Admin only)* — create, edit, enable/disable, and delete threshold-based alert rules.
- **Alerts** — filterable list with severity/status filters and one-click acknowledgment.
- **Reports** — trigger fleet summary generation, poll until complete, view breakdowns, export CSV.

## Tech Stack

React 19 · Vite · TypeScript (strict) · Tailwind CSS · shadcn/ui-style primitives (Radix UI) · React Router 7 · TanStack Query 5 · Axios · Framer Motion · Recharts · React Hook Form + Zod · date-fns

## Architecture

Feature-based structure — each feature folder owns its pages, hooks, and (where relevant) components:

```
src/
  app/            router, layout shell, auth guard, providers, theme context
  api/            Axios instance + interceptors, typed service functions per module
  types/          TypeScript types mirroring backend serializers exactly
  constants/      roles, statuses, severities, query keys — matching backend enums
  features/
    auth/         login page, auth context
    dashboard/    home dashboard
    vehicles/     list, detail, hooks
    telemetry/    chart component, standalone page, hooks
    rules/        list, create/edit form, hooks
    alerts/       list, detail, hooks
    reports/      list, detail, hooks
    misc/         404 / 403 pages
  components/
    ui/           shadcn-style primitives (button, card, dialog, table, ...)
    shared/       DataTable, FilterBar, StatCard, StatusBadge, Sidebar, Navbar, ...
  hooks/          shared reusable hooks
  utils/          formatters, cn()
  styles/         Tailwind + design tokens
```

### State & data layer

- **TanStack Query** owns all server state — vehicles, telemetry, alerts, rules, reports. No manual `useEffect` + `fetch` chains. Live-feeling views use `refetchInterval` polling, structured so it can later be swapped for a WebSocket/Channels push with minimal changes (the query functions are the only thing that would move).
- **React Context** is used only for auth/session state (`AuthContext`) and UI-only state (`ThemeContext`) — never for server data.
- Query keys are centralized in `src/constants/queryKeys.ts` for consistent invalidation per feature.

### API contract details worth knowing

- The backend's list endpoints return **plain JSON arrays**, not a paginated envelope — `DEFAULT_PAGINATION_CLASS` is configured in Django but unused by these `APIView`-based endpoints. Vehicles, drivers, and rules are returned in full; telemetry is capped server-side at 500 rows and reports at 200.
- The **only server-side filter** is telemetry's `?vehicle_id=<string>`. Everything else (vehicle status, alert severity/status, rule metric) is filtered **client-side** in this frontend — see `FilterBar` usage in each list page.
- **Rules management is Admin-only** — Fleet Managers cannot view or edit rules, per backend RBAC.
- Reports has two flows: `GET /reports/fleet-summary/` computes and returns a summary synchronously; `POST /reports/generate/` queues an async report that the UI polls (`GET /reports/:id/`) until `status` is `completed` or `failed`, then offers a CSV export.

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

```
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_POLL_INTERVAL_MS=15000
```

## Installation

```bash
npm install
```

## Running the Project

```bash
npm run dev
```

The app runs at `http://localhost:5173` and expects the Django backend at `VITE_API_BASE_URL`.

## Build

```bash
npm run build    # type-checks then builds to dist/
npm run preview  # serve the production build locally
```

## Other scripts

```bash
npm run lint       # ESLint
npm run format     # Prettier (writes)
npm run typecheck  # tsc --noEmit
```

Husky + lint-staged run ESLint and Prettier on staged files automatically on commit (set up via `npm run prepare`, wired through the `prepare` script).

## Connecting to the Backend

1. Start the Django backend and note its base URL (e.g. `http://localhost:8000`).
2. Set `VITE_API_BASE_URL` to `<backend-url>/api/v1` in `.env`.
3. Log in with credentials provisioned by an administrator — this app does not support self-registration, matching the backend's admin-provisioned user model.

All request/response shapes in `src/types/` and endpoint calls in `src/api/` are written directly against the backend's serializers and views. If you update the backend, search for the corresponding type/service file before touching UI code.

## Screenshots

_Add screenshots of the Dashboard, Vehicle Detail, Alerts, and Reports views here before publishing._

## License

MIT
