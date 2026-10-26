# Diagnostic safety and operational guardrails

## Access model

DCC has no application login, user accounts, roles, credentials, identity tokens, or user sessions. Operational endpoints are anonymous at the application layer. Production access must therefore be restricted by the approved internal network/HTTPS ingress; CORS is a browser policy and is not an access-control boundary.

Diagnostic actions are protected by backend-enforced target validation, input validation, global concurrency and rate limits, target cooldown, maximum duration, state-transition checks, ECS resource ceilings, and provider-specific safety checks. These controls are independent of user identity and must remain enabled even though the API has no application authentication.

## Backend-enforced execution limits

Diagnostic limits are enforced by `DiagnosticSessionService` before execution reaches the provider. Defaults are:

| Setting | Default | Behavior |
| --- | ---: | --- |
| `DCC_DIAGNOSTIC_MAX_DURATION_SECONDS` | `900` | Maximum session age before it is marked failed and cleanup is attempted |
| `DCC_DIAGNOSTIC_MAX_ACTIVE_SESSIONS` | `1` | Maximum globally active sessions in this backend process |
| `DCC_DIAGNOSTIC_START_RATE_LIMIT` | `3` | Global start attempts within the start window |
| `DCC_DIAGNOSTIC_START_RATE_WINDOW_SECONDS` | `3600` | Sliding window for start attempts |
| `DCC_DIAGNOSTIC_STOP_RATE_LIMIT` | `10` | Global stop attempts within the stop window |
| `DCC_DIAGNOSTIC_STOP_RATE_WINDOW_SECONDS` | `60` | Sliding window for stop attempts |
| `DCC_DIAGNOSTIC_TARGET_COOLDOWN_SECONDS` | `0` | Optional minimum delay before starting another session for the same target |

Exceeding concurrency returns `409`; exceeding a rate limit or target cooldown returns `429`. Limits use a lock-protected in-memory store. They are process-local and reset on restart; multiple backend processes do not share limits. The configured default allows one global running session, preserving the current single-active-session UI/API behavior.

### Maximum duration and cleanup limitation

The backend checks duration before session reads, lists, impact reports, starts, and stops. At the configured maximum it attempts to stop the execution provider, records `failed` with `Diagnostic session exceeded the configured maximum duration.`, and captures a best-effort terminal measurement. This is request/session-access enforcement, not an independent timer: if the backend receives no further requests, it cannot guarantee that an ECS worker is stopped at the exact deadline. A backend process crash or failed ECS `StopTask` can likewise leave a worker running. The API reports safe terminal status/error information and logs only safe correlation data; AWS-side monitoring/cleanup is still required for those infrastructure-dependent failure cases. No Celery, Redis, scheduler, or persistent store is used.

## Target and request validation

`POST /api/diagnostic-sessions/` accepts only a JSON object with `target_task_id`. The identifier is limited to 128 ASCII letters, digits, dots, underscores, colons, and hyphens. It must resolve to a live task with `lastStatus=RUNNING` in one of the explicitly configured `DCC_ECS_CLUSTERS`; otherwise the backend returns `400` for malformed/unknown targets or `409` for a known but ineligible task. If ECS discovery is unconfigured or unavailable, the API returns a safe `503` and does not start an execution provider.

Session IDs are server-generated UUIDv4 values. Malformed IDs are rejected as not found before lookup. Session transitions are centralized; terminal sessions cannot be stopped or restarted. Session state has no owner or identity metadata. No client-provided session state or infrastructure configuration is accepted.

## ECS execution boundary

Worker cluster, task definition, subnets, security groups, container, public-IP choice, and resource ceilings are backend configuration; request bodies cannot provide arbitrary ECS parameters. The ECS provider validates UUID/task ID shape, calls `DescribeTaskDefinition`, requires an active configured container, and rejects task CPU/memory above `DCC_ECS_MAX_TASK_CPU`/`DCC_ECS_MAX_TASK_MEMORY_MIB` (defaults `1024` CPU units and `2048` MiB). Only `DIAGNOSTIC_SESSION_ID`, the validated `TARGET_TASK_ID`, and the server-discovered `TARGET_CLUSTER_ARN` are added to the configured container environment. AWS credentials, authorization headers, and arbitrary environment overrides are never passed in the task override.

Use boto3's normal credential chain and a task role with only required actions, scoped as narrowly as AWS supports:

- `ecs:RunTask` for the configured task definition and cluster.
- `ecs:StopTask` for tasks in the configured cluster.
- `ecs:DescribeTaskDefinition` for the configured task definition.
- `iam:PassRole` only for configured ECS task/execution roles, restricted to `ecs-tasks.amazonaws.com`.
- `cloudwatch:GetMetricStatistics` for configured metric namespaces/dimensions.

Validate resource-level permissions against the AWS service authorization reference and actual deployment. This repository creates no IAM policy or infrastructure. Do not grant broad ECS, IAM, EC2, RDS, or ElastiCache mutation permissions.

## API, errors, logs, and observability

All operational APIs are available without an application login:

| Route | Access and behavior |
| --- | --- |
| `GET /api/health/` | Lightweight public health check |
| `GET /api/ecs/clusters/` | Read-only discovery for configured clusters only |
| `GET /api/ecs/clusters/{cluster}/services/` | Read-only active service inventory |
| `GET /api/ecs/clusters/{cluster}/tasks/` | Read-only currently RUNNING task inventory |
| `GET /api/ecs/clusters/{cluster}/tasks/{task_id}/` | Safe task, container, and network metadata |
| `GET /api/services/`, `/api/tasks/`, `/api/tasks/{task_id}/resources/` | Read-only normalized service/task data |
| `GET /api/logs/`, `/api/dependencies/`, `/api/diagnostic-impact/` | Read-only normalized provider data |
| `GET /api/diagnostic-sessions/`, `/active/`, `/{session_id}/` | Read-only in-memory session status/history |
| `POST /api/diagnostic-sessions/` | Starts only after backend validation and global safeguards pass |
| `POST /api/diagnostic-sessions/{session_id}/stop/` | Stops a valid running session, subject to global rate limit |

There are no application auth endpoints; prior `/api/auth/*` routes are removed. Requests with cookies or authorization headers do not establish an application identity.

API exception responses use safe DRF messages; unhandled API exceptions are logged with request method/path and exception type only, then return a generic JSON `500`. Provider code translates AWS and observability failures to safe messages. Diagnostic logs may include session/target identifiers and safe operation/status fields, but never secrets, credentials, raw request bodies, or provider exception details.

Metrics, logs, dependencies, and diagnostic impact are read-only. Their providers use query APIs only; missing measurements remain unavailable rather than zero, provider failures do not fail a diagnostic session, and the impact engine does not issue resource mutations. No RDS reboot/modify, ElastiCache reboot/flush/scale/failover, ECS service mutation, or infrastructure mutation endpoint is present.

## Browser security and production configuration

`DCC_CORS_ALLOWED_ORIGINS` remains an explicit browser-origin allowlist. Wildcards are rejected, and production entries must use HTTPS. Credentialed CORS is disabled because the application does not use browser credentials. Same-origin production frontend requests use `/api/...`; CORS does not prevent non-browser clients from reaching an exposed endpoint.

Django security middleware sends `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: strict-origin-when-cross-origin`. JSON API responses also receive a restrictive Content Security Policy. HSTS is not enabled here because this repository does not guarantee the deployment TLS termination path; enable it only after HTTPS is guaranteed at the deployment boundary.

The frontend handles validation, conflict (`409`), rate-limit (`429`), provider, and bounded request-timeout errors without automatic retries of diagnostic actions.

## Production recommendations and known limitations

- Restrict the production service to approved internal ingress. The anonymous API must not be exposed directly to an untrusted network.
- Configure only approved workload clusters in `DCC_ECS_CLUSTERS`; no arbitrary account-wide cluster scans are performed.
- Keep process-local active-session and rate limits conservative; they do not coordinate multiple workers/containers.
- Keep `DCC_DIAGNOSTIC_MAX_ACTIVE_SESSIONS=1` with the current single-active-session UI.
- Set `DJANGO_DEBUG=false`, provide `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and exact HTTPS `DCC_CORS_ALLOWED_ORIGINS`.
- Verify worker task-definition CPU/memory, IAM role pass-through, network configuration, task stop behavior, and least-privilege IAM against the actual AWS account.
- Timeout cleanup is request-driven and process-local. It cannot guarantee exact-time stopping after process failure or an unavailable AWS API.
