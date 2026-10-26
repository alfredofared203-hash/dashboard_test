# Engineer 2 handoff — API Testing

## Scope and responsibilities

Own API request execution and test results: GET, POST, PUT, PATCH, DELETE; request headers, query parameters, and body; response viewing; status codes; duration; errors; test execution and results.

Feature boundary: `frontend/src/features/api-testing/`. The UI, request state, types, and mock execution provider live within this feature.

## Non-responsibilities

- Do not discover services or endpoints, curate the API catalog, or infer endpoint schemas. These belong to Engineer 1.
- Do not implement AWS integrations, backend services, task testing, or diagnostic orchestration.
- Do not change the shared shell, route configuration, global state, or another engineer's domain without coordination.

## Route ownership

Engineer 2 owns `/api-testing`, registered in the shared route table with one sidebar entry. `/api-explorer` remains a compatibility redirect to `/api-discovery` and must not be repurposed.

## Expected inputs

- A selected, discovered endpoint identifier and its approved method/path/schema metadata from Engineer 1's catalog contract.
- User-provided request headers, query parameters, and body.
- The selected endpoint and its public Discovery contract, plus user-provided URL path, query parameters, headers, and JSON body.
- Approved Django REST Framework execution endpoint and explicit loading/error behavior when backend execution is introduced.

Do not duplicate discovery data or provide a second independently maintained endpoint catalog.

## Expected outputs

- Execution result associated with an endpoint and request.
- HTTP status, response payload/headers as approved, duration, success/failure, error details, and timestamp.
- Feature-local request/response types, UI, execution state, and session-only history.
- Current development execution uses deterministic local mock scenarios only and never sends target requests.
- Diagnostic Impact may consume the explicitly mock-only summary contract from `frontend/src/features/api-testing/public.ts`; it is an aggregate illustration, not API execution history.

## Future backend integration point

The feature consumes endpoint metadata through `frontend/src/features/api-discovery/public.ts`, without importing Discovery internals. Current execution uses `frontend/src/features/api-testing/services/apiTestProvider.ts`; replace its mock provider with approved Django REST Framework execution via shared `frontend/src/api/` configuration when that backend is available. Actual target-request execution and policy enforcement belong on the backend, not in direct calls from React.

## Shared dependencies

Use existing React, TypeScript, React Router, Lucide, Tailwind/shadcn, and the approved API Discovery contract. Coordinate dependencies, shared request behavior, routes, and common contract changes with the Project Owner. See `docs/architecture/data-contracts.md`.

## Must not modify

- Engineer 1's service/endpoint discovery or catalog behavior.
- Engineer 3's tasks/resources testing.
- Shared dashboard shell, System Overview, diagnostic lifecycle, global state, or backend integration architecture.
- Shared components to add API-testing business logic.
- Existing routes or package/configuration files without coordination.
