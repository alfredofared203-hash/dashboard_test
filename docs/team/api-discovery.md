# Engineer 1 handoff — API Discovery

## Scope and responsibilities

Own discovery of services and API endpoints: catalog entries, service-to-endpoint relationships, HTTP methods and paths, endpoint descriptions, parameters, headers, authentication requirements, and discovered request/response schemas.

Feature boundary: `frontend/src/features/api-discovery/`. Discovery domain types, demonstration fixtures, provider interface, loading/error state, and catalog UI live in this feature.

## Non-responsibilities

- Do not execute API requests or implement GET/POST/PUT/PATCH/DELETE testing workflows.
- Do not build response viewers, test execution, test history, or API test results. These belong to Engineer 2.
- Do not implement AWS integration architecture, credentials, or backend services.
- Do not change the shared shell, existing route definitions, global state, or another engineer's feature without coordination.

## Route ownership

Engineer 1 owns the mock-backed API Discovery experience at `/api-discovery`. The previous `/api-explorer` path redirects to preserve existing links. The sidebar has one API Discovery entry. The future Django-backed provider is not implemented. Do not add API Testing navigation or change the route without coordinating with the Project Owner.

## Expected inputs

- Approved backend discovery response or a typed adapter over an agreed contract.
- Service identifiers and descriptive metadata.
- Endpoint method, path, description, parameter/header metadata, authentication requirements, and schema metadata.
- Explicit loading, empty, and discovery-error states.

Use the existing demonstration provider during this frontend-only phase. Keep future fixtures inside this feature rather than shared components.

## Expected outputs

- A service/API catalog with stable identifiers and endpoint relationships.
- Discoverable, typed endpoint metadata and schemas.
- UI states that distinguish discovered metadata from unavailable or failed discovery.
- Feature-local types, UI, hooks, and tests; no test-request execution.

## Future backend integration point

Consume approved Django REST Framework endpoints through `frontend/src/api/` shared request configuration and feature-local API functions under `frontend/src/features/api-discovery/`. The React client must never connect directly to AWS, ECS, CloudWatch, Prometheus, Loki, RDS, or ElastiCache.

## Shared dependencies

Use the existing React, TypeScript, React Router, Lucide, Tailwind/shadcn, and shared typed API configuration when available. Coordinate any dependency, navigation, shared type, or route changes with the Project Owner. See `docs/architecture/data-contracts.md`.

## Must not modify

- Engineer 2's API-testing feature, its execution lifecycle, or test results.
- Engineer 3's tasks/resources-testing feature.
- Shared dashboard shell, overview, diagnostics, global state, or backend architecture.
- Shared components to add discovery-specific business logic.
- Existing routes or package/configuration files without coordination.
