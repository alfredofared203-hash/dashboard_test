# DCC frontend development rules

- **Feature ownership:** Keep feature implementation within its assigned feature directory. Coordinate before changing another domain, shared state, routes, or shared UI.
- **Public contracts:** Cross-feature consumers import only the owning feature's `public.ts` read-only API. Avoid importing another feature's internal components, hooks, providers, or fixtures.
- **Diagnostic session:** The shared diagnostic provider is the single lifecycle owner. System Overview controls CHECK/STOP; other workspaces consume the session read-only.
- **Providers:** Pages and components depend on typed provider contracts. Providers reject on retrieval/execution errors; show loading, empty, and error states rather than silently substituting success data.
- **Backend boundary:** Future backend access belongs behind the approved Django REST API/provider boundary. The browser must not access infrastructure services directly.
- **Mock data:** Keep feature-specific fixtures within their feature. Label all mock values clearly and never present them as live telemetry or actual execution history.
- **Security:** Never commit real credentials, tokens, secrets, customer data, or sensitive infrastructure identifiers.
- **Dependencies:** Reuse existing packages and shared UI before adding dependencies or duplicate components.
- **Atomic Design:** Preserve one-way dependencies: pages → templates → organisms → molecules → atoms. Shared UI must not depend on feature business logic.
- **Validation:** Run `npm run typecheck` and `npm run build` from `frontend/` for frontend changes. Run `python manage.py check` from `backend/` for backend changes. Do not add test or lint frameworks without an agreed need.
