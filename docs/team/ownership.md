# DCC team ownership and architecture freeze

This document establishes feature boundaries for parallel implementation. The React dashboard under `frontend/` is the shared baseline and remains independently runnable; the Django foundation under `backend/` is a separate source tree.

## Ownership

### Engineer 1 — API Discovery

Owns API discovery only: service and endpoint discovery, catalog metadata, methods, paths, parameters, headers, authentication requirements, request/response schema discovery, and service-to-endpoint relationships.

Must not implement API request execution or API testing.

### Engineer 2 — API Testing

Owns API request execution and test results only: GET, POST, PUT, PATCH, DELETE, request headers/query/body, response viewer, status, duration, errors, execution, and results.

Must not implement API or service endpoint discovery.

### Engineer 3 — Tasks & Resources Testing

Owns ECS task and resource testing only: task status/health/state, CPU, memory and network use, test-time resource utilization, diagnostic-operation consumption, baseline comparison, impact calculation, duration, results, and errors.

Does not own overall AWS architecture, API Discovery, or API Testing.

### Project Owner — Core DCC

Owns all remaining work: System Overview, application shell, CHECK/STOP and the shared diagnostic session state/orchestration, Diagnostic Impact, Logs & Diagnostics, AWS/ECS/CloudWatch/Prometheus/Loki/RDS/ElastiCache integration architecture, Django and Django REST Framework, authentication, security, Docker/ECS deployment, CI/CD, global state, shared infrastructure, project settings, cross-feature contracts, and final integration.

## Route ownership

Current registered routes are defined centrally in `frontend/src/routes/AppRoutes.tsx`; sidebar metadata is in `frontend/src/routes/navigation.ts`.

| Current route | Current screen | Ownership / handoff |
| --- | --- | --- |
| `/` | System Overview | Project Owner |
| `/resources` | Resource Metrics placeholder | Project Owner owns the existing route and dashboard section. Engineer 3's future test work belongs at `/tasks-resources`; coordinate before changing or reusing `/resources`. |
| `/logs` | Logs & Diagnostics backend-mock log investigation workspace | Project Owner |
| `/api-discovery` | API Discovery catalog | Engineer 1 |
| `/api-explorer` | Redirect to `/api-discovery` | Legacy alias retained for links; Engineer 1 owns the destination experience. |
| `/diagnostic-impact` | Diagnostic Impact Report mock workspace | Project Owner |
| `/settings` | Settings & Integrations placeholder | Project Owner |
| `/api-testing` | API Testing mock workspace | Engineer 2; local request simulation only, no backend or target-service calls. |
| `/tasks-resources` | Tasks & Resources Testing AWS ECS workspace | Engineer 3; live configured ECS inventory with CloudWatch service aggregates by default. |

API Discovery is implemented as a mock-backed catalog at `/api-discovery`; API Testing is a mock-backed request workspace at `/api-testing`; Tasks & Resources Testing reads live AWS ECS discovery APIs at `/tasks-resources`. The existing `/resources` route remains the separate Resource Metrics placeholder owned by the Project Owner.

The Project Owner owns the `/logs` workspace, API-backed provider, filters, and detail view. The backend defaults to Loki and reports unavailable when it is not configured; deterministic mock entries require explicit opt-in. The workspace reads shared diagnostic session state without controlling it.

The Project Owner owns the `/diagnostic-impact` report aggregation, its provider contract, and its read-only integration with public feature data sources. Reports are backend-generated from the configured providers; metrics/logs/dependencies use real CloudWatch/Loki sources by default, with mock data requiring explicit development/testing opt-in.

## Parallel work rules

- Work only within the assigned domain and its documented route/feature boundary.
- Do not modify another engineer's domain without prior coordination with that owner and the Project Owner.
- Shared components, routes, global state, package configuration, shared types, and backend contracts are Project Owner-controlled. Propose changes before editing them.
- The shared diagnostic session contract/provider is Project Owner-owned. Feature pages may consume it read-only; only the System Overview diagnostic controls may start or stop a session. CHECK is rejected while a session is starting/running; STOP transitions that session to stopped. Backend state is process-local; reloading the page restores the active or latest session still available from that backend process.
- Keep feature-specific UI, hooks, types, and orchestration inside the owning feature. Shared components receive data and callbacks through typed props.
- Do not change the frozen dashboard shell, System Overview behavior, or existing routes as a side effect of feature work.
- Agree on API changes through `docs/architecture/data-contracts.md` before parallel frontend/backend implementation. The contracts are conceptual until approved and versioned.
- Keep this handoff documentation aligned with any approved ownership or route changes.

## Feature directories

No empty directories are created for unstarted features. When work is approved, use:

- `frontend/src/features/api-discovery/` — Engineer 1
- `frontend/src/features/api-testing/` — Engineer 2
- `frontend/src/features/tasks-resources-testing/` — Engineer 3
- `frontend/src/features/diagnostics/` — Project Owner
- `frontend/src/features/diagnostic-impact/` — Project Owner

The directory name alone does not grant ownership of shared infrastructure or another domain.
