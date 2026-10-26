# Engineer 3 handoff — Tasks & Resources Testing

## Scope and responsibilities

Own ECS task and resource test results: task status, health and running/stopped state; task CPU, memory and network usage; resource utilization during tests; resource consumption caused by diagnostic operations; baseline-versus-test comparison; resource impact calculation; test duration, results, and errors.

Feature boundary: `frontend/src/features/tasks-resources-testing/`. Task/resource presentation types, the API adapter, state hook, impact display, and feature UI live here. ECS task inventory is loaded from the backend's AWS-only discovery APIs; there is no sample task fallback.

## Non-responsibilities

- Do not own overall AWS architecture, credentials, or shared AWS integration design.
- Do not implement API Discovery or API Testing.
- Do not implement core diagnostic orchestration or Diagnostic Impact. Coordinate with the Project Owner where diagnostic-operation measurements are needed.
- Do not change the shared shell, global state, or another engineer's domain without coordination.

## Route ownership

Engineer 3 owns `/tasks-resources`, registered in the shared route table with one sidebar entry. `/resources` remains the existing Project Owner-owned Resource Metrics placeholder and is not renamed or repurposed.

## Expected inputs

- The page reads clusters, services, and live task detail from `/api/ecs/...`, then requests resources from `GET /api/tasks/{task_id}/resources/`.
- Task DTOs include ECS task/service identity, status, health, counts, task definition, launch type, CPU/memory, AZ, container, and safe network metadata.
- Resource DTOs include baseline/current/peak values, units, and backend-provided impact deltas.
- Resource metrics include a `source` value (`mock`, `cloudwatch`, or `prometheus`) that the UI must use when identifying the data.
- ECS inventory is AWS-backed only. Missing cluster configuration, unavailable credentials, and AWS errors produce safe unavailable states. CloudWatch is the default metrics provider and currently returns configured-service aggregates, not per-task diagnostic execution results.
- The page reads the shared backend-backed `DiagnosticSession` state; it cannot start, stop, complete, fail, or reset the session.
- Explicit handling of missing metrics, measurement errors, and unsupported task states.

## Expected outputs

- Task health/state and available backend resource aggregates, with the source explicitly identified.
- Baseline, current, peak, returned impact deltas, units, and explicit source/availability labeling.
- Explicit unavailable state for time-series history and execution results not supplied by the API.

## API integration boundary

The UI uses the task/resource API functions in `frontend/src/lib/api/tasksResources.ts` through the feature adapter in `services/apiTasksResourcesProvider.ts`. The shared API client owns HTTP transport and safe errors. ECS/CloudWatch collection and credentials belong in the backend integration layer. CloudWatch service aggregates are labeled as such and are not represented as task-specific or diagnostic-session measurements.

## Diagnostic state boundary

The Project Owner owns the shared `DiagnosticSessionProvider` and its contract in `frontend/src/app/providers/` and `frontend/src/types/diagnosticSession.ts`. System Overview owns CHECK/STOP; this feature consumes the shared session read-only and displays its session ID, scope, status, start/end time, and elapsed duration. It must not implement its own diagnostic state or controls.

## Shared dependencies

Use the existing React, TypeScript, React Router, Lucide, Tailwind/shadcn, and approved task/resource and diagnostic-operation contracts. Coordinate route, shared type, dependency, and integration changes with the Project Owner. See `docs/architecture/data-contracts.md`.

## Must not modify

- Engineer 1's API Discovery or Engineer 2's API Testing.
- Overall AWS architecture, credentials, cloud clients, or shared backend integration layer.
- Core diagnostics, Diagnostic Impact, System Overview, shell, or global state.
- Shared components to add task/resource-testing business logic.
- Existing `/resources` route or package/configuration files without coordination.
