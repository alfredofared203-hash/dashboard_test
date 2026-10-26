# DCC frontend/backend boundary

The React application under `frontend/` is a presentation client. It must not communicate directly with AWS, ECS, CloudWatch, Prometheus, Loki, RDS, or ElastiCache, and must not contain provider credentials or provider-specific clients. DCC is an internal operational dashboard with no application login, account, role, token, or browser identity/session system. Its production ingress must therefore provide network-level access restriction; CORS is not an access-control boundary.

The intended request/data flow is:

```text
React Frontend
      |
      v
Django REST API
      |
      v
DCC Service / Integration Layer
      |
      +--> AWS / ECS
      +--> CloudWatch / Prometheus / Loki
      +--> RDS / ElastiCache
```

Validation, provider errors, and infrastructure access belong on the backend. React calls only approved Django API endpoints through `frontend/src/lib/api/`; feature-specific request mapping belongs within the owning feature boundary.

## API contract and providers

The API namespace is `/api/`. All operational endpoints are callable without an application login:

| Endpoint | Contract |
| --- | --- |
| `GET /api/health/` | Lightweight health response for container checks |
| `GET /api/ecs/clusters/` | Configured AWS ECS clusters only |
| `GET /api/ecs/clusters/{cluster}/services/` | Active services in a configured cluster |
| `GET /api/ecs/clusters/{cluster}/tasks/` | Live RUNNING task inventory and safe metadata |
| `GET /api/ecs/clusters/{cluster}/tasks/{task_id}/` | One live task with safe container/network metadata |
| `GET /api/ecs/clusters/{cluster}/services/{service}/tasks/` | Live RUNNING tasks for one configured service |
| `GET /api/ecs/tasks/` | Live RUNNING tasks across every configured cluster |
| `GET /api/ecs/tasks/{task_id}/` | One live task; pass `?cluster=<cluster>` when resolving duplicate task IDs |
| `GET /api/services/` | Service IDs, names, and health status |
| `GET /api/tasks/` | Task/service identity, state, health, counts, and availability |
| `GET /api/tasks/{task_id}/resources/` | CPU, memory, network baseline/current/peak values, impact deltas, and source (`mock`, `cloudwatch`, or `prometheus`) |
| `GET /api/dependencies/` | Normalized RDS/ElastiCache resource status, metrics, source, and current measurement context |
| `GET /api/logs/` | Bounded, normalized log entries with severity, service, task, source, session, and optional metadata |
| `GET /api/diagnostic-sessions/` | Current-process diagnostic session history, without owner/identity fields |
| `GET /api/diagnostic-sessions/active/` | Current active session, or `{"session": null}` |
| `GET /api/diagnostic-sessions/{session_id}/` | Session state and safe execution metadata |
| `POST /api/diagnostic-sessions/` | Starts a session after target validation and global guardrails pass |
| `POST /api/diagnostic-sessions/{session_id}/stop/` | Stops a valid running session, subject to global limits |
| `GET /api/diagnostic-impact/?session_id=<id>` | Session-associated baseline/during/post measurements, calculated deltas/classification, logs, and limitations |

There are no `/api/auth/*` endpoints. Session state is in process memory; there is no application database or user/session persistence. Only diagnostic start/stop mutate session state; other APIs are read-only.

ECS discovery is AWS-only through `AWSECSDiscoveryProvider`. Configure `AWS_REGION` and the explicit cluster allowlist `DCC_ECS_CLUSTERS`; no account-wide cluster scan or sample ECS fallback exists. The browser uses only the Django API. Missing configuration, access denied, or AWS errors produce safe unavailable responses. Task resource metrics and dependency observability default to CloudWatch (task metrics are currently configured-service aggregates); logs default to Loki. Mock metrics/logs/dependencies require explicit development/testing opt-in.

The Logs & Diagnostics screen calls `GET /api/logs/`; optional query filters include search, service, task, source, severity, time window, and diagnostic session ID. Loki query construction, bounded retrieval, response parsing, timestamp conversion, and severity normalization are confined to the backend. Optional Loki tenant/bearer credentials are backend-only provider configuration, not DCC user authentication. The browser never calls Loki, CloudWatch, or Grafana directly.

The Diagnostic Impact Report uses the backend-authoritative diagnostic session ID and measurement engine. The backend captures baseline/during/post measurements through normalized metrics/dependency services, calculates deltas and classifications, and returns explicit missing-data states. Diagnostic targets are validated against currently RUNNING ECS tasks. It does not use frontend fixture aggregation, expose provider-native data, execute API tests, or assert unsupported causality.

## Diagnostic safety boundary

`DiagnosticExecutionProvider` is the diagnostic execution boundary. It defaults to the in-memory provider for local development; an explicitly configured ECS provider may launch/stop a temporary Fargate worker. The backend validates target and session identifiers, accepts no caller-supplied ECS infrastructure settings, enforces maximum duration, global concurrent-session limits, global start/stop rate limits, optional target cooldown, safe state transitions, worker CPU/memory ceilings, and safe provider error handling.

Only `DIAGNOSTIC_SESSION_ID`, the validated `TARGET_TASK_ID`, and its discovered `TARGET_CLUSTER_ARN` are passed as worker environment overrides. AWS credentials, authorization headers, arbitrary environment overrides, and user identity are not passed to the worker. The application does not create ECS, Prometheus, Loki, or dependency infrastructure.

Metrics, logs, dependency observations, and impact reports are read-only. Missing measurements stay unavailable rather than zero, and provider failures do not fail diagnostic lifecycle operations. There are no RDS reboot/modify, ElastiCache reboot/flush/scale/failover, or infrastructure mutation endpoints.

## Browser and production boundary

The shared API client is the frontend's only DCC API transport. Production uses same-origin `/api/...`; local development may set `VITE_API_BASE_URL` when Vite and Django are separate processes. Browser requests do not send cookies or authentication tokens.

`DCC_CORS_ALLOWED_ORIGINS` is an explicit browser-origin allowlist; production values must use HTTPS and wildcard origins are rejected. Credentialed CORS is disabled. Security headers and safe API exception handling remain enabled. Because application authentication is intentionally absent, deploy only behind approved internal HTTPS ingress and do not treat CORS as protection from non-browser clients.

The deployment target is one Docker image containing the frontend build and Django backend, run in one ECS task/container. Diagnostic session, rate-limit, cooldown, and cleanup-pending state is process-local; multiple application tasks do not share it.
