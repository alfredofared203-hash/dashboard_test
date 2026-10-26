# DevOps Control Center

DCC is organized as a React frontend and a Django REST Framework backend. ECS cluster, service, and running-task inventory is read from AWS ECS by a backend-only boto3 provider. The browser never calls AWS directly, and discovery never falls back to fabricated ECS data.

## Repository structure

```text
project-root/
├── frontend/   React + TypeScript + Vite application
├── backend/    Django + Django REST Framework project
├── docs/       Architecture and team handoff documentation
├── Dockerfile
├── docker-entrypoint.sh
└── .dockerignore
```

Frontend and backend source code are physically separated. Development uses two independent processes; the intended deployment packages the frontend build and Django backend into **one Docker image**, later run in **one ECS task**. This does not mean separate frontend/backend images, containers, or ECS services.

## Deployment documentation

- [Production runtime contract](./docs/deployment/runtime.md)
- [AWS ECS deployment guide](./docs/deployment/aws-ecs.md)
- [ECS task definition template](./deploy/ecs/task-definition.template.json)
- [DCC AWS test laboratory blueprint](./docs/deployment/aws-test-lab.md)

## Development

### Frontend

```bash
cd frontend
npm install
npm run dev
```

In development the frontend API client targets port 8000 on the same hostname used for Vite. In production the API client uses the same origin (`/api/...`). Copy `frontend/.env.example` to `frontend/.env.local` to override `VITE_API_BASE_URL` when the frontend and backend run separately. Vite environment values are public and must not contain secrets.

For local browser requests, the backend allows the Vite origins `http://localhost:5173` and `http://127.0.0.1:5173` on the operational API routes. `DCC_CORS_ALLOWED_ORIGINS` remains an explicit origin allowlist; production requires HTTPS entries. Credentialed CORS and CSRF are disabled because the DCC does not use browser identity or session cookies.

Run frontend checks from `frontend/`:

```bash
npm run typecheck
npm run build
```

### Production Docker runtime

The repository builds a single multi-stage Docker image for both the React frontend and the Django API. The frontend is compiled during the image build, copied into the Python runtime image, and then served by Django from the same origin. `GET /` serves the SPA, `GET /api/...` serves the backend, and `GET /assets/...` serves the compiled frontend bundle.

```bash
docker build -t dcc:local .
docker run --rm -p 8000:8000 -e DJANGO_SECRET_KEY=replace-me -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 -e DCC_CORS_ALLOWED_ORIGINS=https://localhost:5173 dcc:local
```

The same-origin frontend API client uses `/api/` in production; the backend must be mounted as a single app container and must not rely on a separate Vite dev server.

### Backend

Use Python 3.12 or later. From `backend/`, create and activate a virtual environment, install the pinned requirements, and run Django:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py runserver
```

DRF endpoints are available under `/api/`: `GET /health/`, `GET /services/`, `GET /tasks/`, `GET /tasks/{task_id}/resources/`, `GET /dependencies/`, `GET /logs/`, `GET /diagnostic-impact/?session_id=<id>`, and the diagnostic session lifecycle:

```text
GET  /diagnostic-sessions/
POST /diagnostic-sessions/                 {"target_task_id": "<running ECS task ID>"}
GET  /diagnostic-sessions/active/
GET  /diagnostic-sessions/{session_id}/
POST /diagnostic-sessions/{session_id}/stop/
```

Read-only ECS discovery routes are also available:

```text
GET /api/ecs/clusters/
GET /api/ecs/clusters/{cluster}/services/
GET /api/ecs/clusters/{cluster}/tasks/
GET /api/ecs/clusters/{cluster}/tasks/{task_id}/
```

Set `AWS_REGION` and the comma-separated `DCC_ECS_CLUSTERS` allowlist before calling these routes. Cluster names and ARNs are supported; DCC only queries configured clusters. Missing configuration and AWS failures return safe `503` responses, never sample inventory. Grant the DCC task role read-only ECS discovery permissions for those clusters. A local setup without AWS credentials or cluster configuration can still run the application, but ECS-backed APIs report unavailable rather than showing invented resources.

All operational API routes are available without a DCC login, account, role, token, or user session. The API is intended for an internally network-restricted deployment; CORS is not an access-control boundary. `GET /api/health/` remains lightweight and public. Diagnostic start/stop requests are controlled by backend target validation, global concurrency/rate limits, duration limits, cooldown, state-transition checks, ECS resource ceilings, and safe provider handling.

Starting a session validates the target against live configured ECS clusters and only allows a currently running task. A target no longer present in the live inventory is rejected. Session state is process-local, is not persisted, and is lost when the backend restarts. The response exposes safe execution metadata only; the execution worker ARN remains internal. Failed starts/stops mark the session `failed`, retain a safe error message, and return HTTP 502 without exposing AWS SDK details. `GET /diagnostic-sessions/` lists sessions created during the current process. `GET /diagnostic-sessions/active/` returns `{"session": null}` if no session is running.

The provider abstraction is `DiagnosticExecutionProvider`, selected by `DCC_DIAGNOSTIC_PROVIDER`. The default is `inmemory`, so ordinary local development and tests do not require AWS configuration or make AWS calls. Set it to `ecs` to use the Fargate ECS `RunTask`/`StopTask` provider. The ECS provider passes the selected live task ID and cluster ARN with the diagnostic session ID to the configured worker container as restricted environment overrides and stores the worker task ARN privately in process memory.

Task resource metrics use a `TaskMetricsProvider` abstraction selected by `DCC_METRICS_PROVIDER`, defaulting to CloudWatch; mock metrics are only available when explicitly selected for development/testing. The CloudWatch provider returns aggregates for its configured ECS service, not task-specific or diagnostic-session measurements. The `prometheus` provider uses the Prometheus HTTP range-query API and requires matching real `task_id` labels. Missing configuration and unavailable metrics return safe API errors and never silently fall back to sample values. The DCC task inventory is independently verified against AWS ECS before metrics are returned.

Dependency observability is exposed through the read-only `GET /api/dependencies/` endpoint and the Dependency Observability workspace. Its separate `DependencyObservabilityProvider` uses `DCC_DEPENDENCIES_PROVIDER=cloudwatch` by default; deterministic mock examples require explicit `DCC_DEPENDENCIES_PROVIDER=mock` opt-in. Configure the region and `DCC_DEPENDENCY_RESOURCES` with real resource IDs for CloudWatch, for example:

```json
[{"resource_type":"rds","resource_id":"orders-db","engine":"postgres"},
 {"resource_type":"elasticache","resource_id":"sessions-cache","engine":"redis","resource_scope":"cache_cluster"}]
```

Entries require `resource_type` (`rds` or `elasticache`) and `resource_id`; `engine` and `resource_scope` are optional (`rds` defaults to `db_instance`; ElastiCache defaults to `cache_cluster`, with `replication_group` also supported). At most 20 resources are accepted. The backend uses boto3's normal credential chain; provide IAM credentials through the deployment's normal secret/role mechanism, never in source or `VITE_*` variables. The provider only reads CloudWatch metrics: RDS CPU, connections, free storage, read/write IOPS and network throughput; ElastiCache CPU, memory bytes/percentage, connections and network throughput. ElastiCache network-byte sums are normalized over the provider's 60-second metric period to bytes per second. CloudWatch does not provide status through these metric queries, so live resource status is `unknown`; empty or missing datapoints are `unavailable`/null, never zero. The list response marks ordinary telemetry `current_health`, or identifies the backend diagnostic session when one is active. The impact report stores separate baseline, during and best-effort post dependency snapshots; dependency deltas are shown separately from ECS target impact and do not change the ECS impact classification or imply causality. This integration is read-only and has no resource mutation controls. Dependency failures do not fail diagnostic lifecycle. Tests mock boto3/CloudWatch and need no AWS credentials or network access.

CloudWatch and Prometheus are integration foundations, not complete production observability. They do not provision their infrastructure, enumerate real DCC tasks, attribute measurements to diagnostic executions, or provide an application history API. The Prometheus endpoint must be reachable by the backend and currently has no application-level authentication support.

Logs use a separate backend `LogsProvider`, selected by `DCC_LOGS_PROVIDER` and defaulting to `loki`. Configure `DCC_LOKI_URL` to use Loki's HTTP `query_range` API; no fake log data is substituted when Loki is unavailable. Loki access is backend-only; optional `DCC_LOKI_BEARER_TOKEN` and `DCC_LOKI_TENANT_ID` are sent as request headers and must be supplied as backend secrets/configuration. The provider retrieves at most 500 entries from the latest hour and returns the existing normalized `/api/logs/` list; current UI filters remain client-side over that bounded result. The endpoint optionally accepts `search`, `service`, `task_id`, `source`, `severity`, `since_minutes` (5/15/30/60), and `diagnostic_session_id` filters. Loki streams are expected to carry `service`, `task_id`, and `source` labels (structured JSON lines may provide these instead), with optional severity/session/trace fields. Unrecognized severities normalize to `INFO`, and absent metadata stays absent. Backend tests mock all Loki HTTP calls. This does not deploy or fully configure the production observability stack.

Diagnostic Impact reports use the backend-owned session and metrics/log services. The backend captures baseline, bounded during-session samples, and a best-effort post-session sample; `GET /api/diagnostic-impact/?session_id=<id>` returns normalized deltas, DCC application-level classification, phase availability, and limitations. If omitted, the endpoint selects the active or most recently created session. Metrics and logs default to CloudWatch and Loki; their APIs report unavailable until configured rather than silently substituting samples. Only logs with an exact backend session ID are classified as session-correlated, and API Testing results are explicitly not provided. Session/report data remains process-local, and the impact classification is not causal analysis or full production observability. See [the Diagnostic Impact report notes](docs/features/diagnostic-impact.md) for sampling bounds, zero-baseline handling, and thresholds.

ECS discovery always uses AWS and requires `AWS_REGION` plus `DCC_ECS_CLUSTERS`. The following additional configuration is required only when the diagnostic execution provider is set to `ecs`:

| Environment variable | Purpose |
| --- | --- |
| `AWS_REGION` | AWS region for ECS discovery and the ECS API client |
| `DCC_ECS_CLUSTERS` | Required comma-separated allowlist of existing workload cluster names or ARNs for discovery |
| `DCC_ECS_CLUSTER` | Existing ECS cluster name or ARN where the diagnostic worker runs |
| `DCC_ECS_TASK_DEFINITION` | Existing diagnostic worker task definition family/revision or ARN |
| `DCC_ECS_SUBNETS` | Comma-separated existing subnet IDs for Fargate `awsvpc` networking |
| `DCC_ECS_SECURITY_GROUPS` | Optional comma-separated existing security group IDs |
| `DCC_ECS_CONTAINER_NAME` | Existing container name to receive worker input overrides |
| `DCC_ECS_ASSIGN_PUBLIC_IP` | Whether Fargate networking assigns a public IP; defaults to `false` |
| `DCC_ECS_MAX_TASK_CPU` | Maximum configured task CPU units; defaults to `1024` |
| `DCC_ECS_MAX_TASK_MEMORY_MIB` | Maximum configured task memory; defaults to `2048` MiB |
| `DCC_DIAGNOSTIC_PROVIDER` | `inmemory` (default) or `ecs` |

**ECS discovery is AWS-only and requires `AWS_REGION` plus `DCC_ECS_CLUSTERS`.** Missing configuration or AWS access returns a safe unavailable response, never sample ECS resources. Diagnostic worker execution separately defaults to `inmemory` locally; set `DCC_DIAGNOSTIC_PROVIDER=ecs` and provide its worker/task/network settings to run a real worker. boto3 uses the standard AWS credential provider chain. Use an IAM task role in deployment and a standard local AWS profile for development; do not put AWS credentials in source, Vite variables, or `.env.example`.

The DCC backend does not create ECS infrastructure. It discovers only the explicitly configured workload clusters using read-only ECS APIs. Diagnostic execution launches and stops an already configured ECS task definition using the configured worker cluster/network configuration. Before launch it describes the worker task definition, validates its configured container and enforces `DCC_ECS_MAX_TASK_CPU` and `DCC_ECS_MAX_TASK_MEMORY_MIB`; the request body cannot override ECS settings. No VPC, subnet, security group, IAM role, cluster, task definition, or ECS service is created by this application. No worker implementation or automatic retry is included. Task inventory is live AWS ECS; metrics and dependencies default to CloudWatch and logs to Loki. Their data remains unavailable until real provider settings/permissions are supplied. The frontend uses backend APIs for diagnostic session lifecycle, ECS discovery, Tasks & Resources, Logs, and Diagnostic Impact.

Diagnostic execution limits, request/target validation, global process-local rate limits, timeout cleanup limitations, safe exception responses, security headers, and least-privilege AWS permission categories are documented in [Diagnostic safety and operational guardrails](docs/architecture/diagnostic-security.md).

DCC does not configure a database or persist application, user, or browser-session data. Django serves the compiled React application and static assets from the production image.

Backend configuration uses `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, and `DJANGO_ALLOWED_HOSTS`. The development-only key fallback is used only with debug enabled; production must provide a secret and set debug off. `VITE_*` values are bundled into public frontend assets and must never contain backend secrets.

## Production deployment model

```text
Development:  frontend process + backend process (separate, local)
Deployment:   frontend build + Django backend -> ONE Docker image
Target:       ONE Docker image -> ONE ECS task
```

The root Dockerfile uses the repository root as its build context. Build the prepared image with:

```bash
docker build -t dcc .
```

The Dockerfile packages the production frontend build and Django project into one image. Django serves the frontend SPA, static assets, and `/api/*` from the same origin. The container exposes port `8000` and has a lightweight `/api/health/` check. See [Production runtime contract](docs/deployment/runtime.md) and [AWS ECS deployment guide](docs/deployment/aws-ecs.md).

## Architecture and team handoff

- [Atomic Design and frontend architecture](docs/architecture/atomic-design.md)
- [Frontend/backend boundary](docs/architecture/backend-boundary.md)
- [Conceptual data contracts](docs/architecture/data-contracts.md)
- [Team ownership and routes](docs/team/ownership.md)
- [API Discovery handoff](docs/team/api-discovery.md)
- [API Testing handoff](docs/team/api-testing.md)
- [Tasks & Resources Testing handoff](docs/team/tasks-resources-testing.md)
