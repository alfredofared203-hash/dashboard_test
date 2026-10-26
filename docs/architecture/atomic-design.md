# DCC frontend architecture

The React application in `frontend/` organizes shared presentation components using Atomic Design while keeping route-level screens, feature logic, and mock data outside the shared component layers. Django code is kept in the separate `backend/` tree.

## Layers and locations

- `frontend/src/components/atoms/`: focused reusable primitives such as status badges and severity marks.
- `frontend/src/components/molecules/`: small combinations such as metric cards, section headings, and page titles.
- `frontend/src/components/organisms/`: complete interface sections such as navigation, resource charts, and service tables.
- `frontend/src/components/templates/`: shared page framing, responsive shell, and route outlet. Templates accept page content and do not own page-specific data.
- `frontend/src/pages/`: one component per route. Pages compose templates and organisms; unfinished destinations use a labeled placeholder.
- `frontend/src/features/`: domain-specific logic and UI. Keep a hook or type inside its feature when it is not genuinely shared.
- `frontend/src/hooks/`: only hooks that are reusable across unrelated features.
- `frontend/src/lib/`: shared framework-independent helpers. `utils.ts` contains the class-name helper used by shadcn/ui primitives; `time.ts` contains shared duration formatting.
- `frontend/src/types/`: types shared across separate features. Feature-specific types stay with their feature.
- `frontend/src/mocks/`: demonstration fixtures shared by unrelated features. Feature-specific fixtures stay inside their owning feature.
- `frontend/src/routes/`: route paths and navigation metadata; sidebar navigation is generated from the same configuration.
- `frontend/src/lib/api/`: shared Django API transport and validated endpoint contracts. Do not place mock behavior here.
- `frontend/src/styles/`: global Tailwind layers and project-wide styles.
- `frontend/src/app/`: application composition and providers.
- `frontend/src/app/providers/DiagnosticSessionProvider.tsx`: Project Owner-controlled shared diagnostic session state, hydrated and mutated through the backend API; consumers use its read-only state hook unless they own core diagnostic controls.
- `frontend/src/types/diagnosticSession.ts`: shared diagnostic session contract used across route-level features.
- `frontend/src/components/ui/`: shadcn/ui-compatible primitives as expected by the shadcn CLI. This is a deliberate convention exception: primitives here are imported by atoms and other lower-level shared components and must not depend on organisms, templates, or pages.
- `frontend/src/features/diagnostics/components/`: diagnostic-session-specific UI, including its CHECK/STOP control panel. Feature-owned UI should stay with its feature instead of making shared components depend on feature business contracts.
- `frontend/src/features/logs-diagnostics/`: Logs & Diagnostics types, legacy fixtures used by the mock Diagnostic Impact report, API-backed provider, read-only session hook, page, and log detail UI.
- `frontend/src/features/diagnostic-impact/`: Diagnostic Impact report contract, aggregation provider, hook, page, and report-specific presentation components.

## Dependency direction

Atoms depend only on platform and utility code. Molecules may compose atoms; organisms may compose atoms and molecules; templates may compose organisms and lower layers; pages may compose templates and feature modules. Shared UI must not import page-specific code. Route configuration contains metadata only and does not import page components. Keep imports one-way and avoid circular references.

Dashboard organisms receive datasets and callbacks through typed props. Mock fixtures are selected/composed at the page boundary rather than imported by reusable presentation components. Feature-specific state, types, and interface components remain within their feature boundary. The shared diagnostic provider is a core-state exception owned by the Project Owner; downstream feature hooks can observe it but must not add controls or duplicate session state. The sidebar may consume route metadata to render navigation; route configuration must not import UI components.

Logs UI consumes the feature-local `LogsProvider` through its hook; the workspace uses the backend logs API while the separate Diagnostic Impact report retains its explicit mock-only log provider. The Logs feature may read shared diagnostic session state, but it does not mutate or control it.

The Diagnostic Impact page consumes a feature-local report provider. That provider composes the shared diagnostic session and explicit public read-only entry points from Tasks & Resources, API Testing, and Logs. Report presentation does not import feature-private fixtures or mutate any source feature.

Prefer named exports and focused modules over large barrels. Do not add a folder or abstraction for a future concern until it has a real first use.

## Adding shared UI and shadcn/ui

Before implementing a primitive, check whether an existing `frontend/src/components/ui/` shadcn component already covers it. Add or update shadcn primitives in that directory using the configured `components.json`; compose those primitives from the Atomic Design layers instead of duplicating their behavior. Keep `cn` in `frontend/src/lib/utils.ts`.

Place a genuinely reusable small composition in `molecules/` and a larger self-contained section in `organisms/`. Components with domain-specific behavior belong in the matching `features/<domain>/` module rather than shared UI.

## Mock data and Django API

Keep feature-specific demo fixtures inside the owning feature and reserve `frontend/src/mocks/` for fixtures that are intentionally shared. Do not imply that mock values are live metrics. Shared JSON transport and API operations live in `frontend/src/lib/api/`; keep API transport and loading/error state out of presentational components.

## Adding a page

1. Add a route path, label, and navigation icon to `frontend/src/routes/navigation.ts`.
2. Create a focused page under `frontend/src/pages/`.
3. Register the route in `frontend/src/routes/AppRoutes.tsx`; the shared template already owns the shell.
4. Compose existing organisms and molecules before introducing new shared UI.
5. Add domain-specific state and types to a feature module if required.
6. Run `npm run typecheck` and `npm run build` from `frontend/`.

The System Overview reads live service/task inventory and provider-backed telemetry from the backend; unavailable AWS/provider data is shown as unavailable rather than replaced by samples. Diagnostic session controls use the backend-owned lifecycle. Unimplemented destinations remain placeholders until their own milestone. Logs & Diagnostics uses the backend logs API, which defaults to Loki; Diagnostic Impact reads a backend-generated session report through the shared API client.

For team ownership, route assignments, future feature boundaries, and conceptual contracts, see `docs/team/ownership.md` and `docs/architecture/data-contracts.md`. Frontend-to-backend restrictions are documented in `docs/architecture/backend-boundary.md`.
Team-wide collaboration and code-quality rules are documented in `docs/team/development-rules.md`.
