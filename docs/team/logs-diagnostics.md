# Logs & Diagnostics handoff

## Scope

The Project Owner owns the read-only `/logs` workspace for investigating diagnostic log entries. The frontend supports search, filtering, sorting, session context, result counts, refresh, and log details using normalized entries returned by the backend API.

## Responsibilities

- Keep the route at `/logs`.
- Maintain the feature-local `LogsProvider` contract and replaceable provider boundary.
- Own log entry types, mock fixtures, filtering, result states, and log detail presentation.
- Consume shared diagnostic session state read-only, including session ID, status, target scope, start time, and elapsed duration.
- Consume `GET /api/logs/` through `frontend/src/lib/api/logs.ts`; filtering stays client-side.
- Keep the data source boundary explicit: Loki is the backend default; mock logs require explicit development/testing opt-in.

## Non-responsibilities

- No Loki, Grafana, CloudWatch Logs, AWS, ECS, or other infrastructure integration in the frontend.
- No new Django/DRF business logic, database, authentication, persistence, polling, or live streaming.
- No CHECK/STOP controls or mutations to diagnostic session state.

## Suggested feature directory

`frontend/src/features/logs-diagnostics/` owns its `types/`, `mocks/`, `services/`, `hooks/`, `components/`, and `pages/`. `frontend/src/pages/LogsDiagnosticsPage.tsx` is the route-level adapter and `frontend/src/routes/AppRoutes.tsx` retains route registration.

## Route ownership

The Project Owner owns `/logs`. It remains a single route and does not replace or rename another destination.

## Expected inputs

- A read-only `DiagnosticSession` from the shared application provider.
- `LogsProvider.getLogs()` retrieves all endpoint entries; session scope is applied client-side using the shared session ID.
- Each log entry includes an ID, timestamp, severity, service, task ID, source/component, message, diagnostic session ID, and optional trace ID and metadata.

## Expected outputs

- A responsive searchable and filterable log list.
- Explicit loading, no-session, empty, no-match, and provider-error states.
- Counts and a session-scoped log summary based only on provider data.
- A keyboard-accessible detail dialog for the selected entry.
- A refresh action that invokes the provider without introducing polling or live streaming.

## Backend integration boundary

The feature provider uses the shared API client in `frontend/src/lib/api/`. The endpoint defaults to the backend Loki provider selected by `DCC_LOGS_PROVIDER`; no sample logs are substituted when Loki is unavailable. Loki requests, query construction, credentials, response parsing, and provider errors belong in the backend; the browser must not contact Loki. Loki retrieval is limited to the latest hour and 500 entries; the current workspace continues applying its filters client-side. The API optionally accepts `search`, `service`, `task_id`, `source`, `severity`, `since_minutes` (5/15/30/60), and `diagnostic_session_id`. Loki is expected to expose `service`, `task_id`, and `source` stream labels or equivalent structured log fields; those mappings are backend-owned.

## Shared dependencies

- `DiagnosticSessionProvider` and the contract in `frontend/src/types/diagnosticSession.ts`, read-only.
- Shared `ActionButton`, application shell, and global focus behavior.
- The conceptual logs contract in `docs/architecture/data-contracts.md` and backend boundary in `docs/architecture/backend-boundary.md`.

## What the engineer must NOT modify

- Do not change System Overview CHECK/STOP or the shared diagnostic session provider.
- Do not modify API Discovery, API Testing, Tasks & Resources Testing, shared dashboard navigation, or unrelated shared components without coordination.
- Do not add direct browser calls to Loki, Grafana, CloudWatch, AWS, or other infrastructure.
- Do not include real credentials, tokens, production identifiers, or production log content in fixtures.
