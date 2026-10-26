# Standalone Test Laboratory Integration Contract

This guide is for an engineer who receives only this directory and has never seen its source repository. It defines the service boundary and deployment contract without assuming a specific host application.

## 1. What this service provides

The Test Laboratory is an independent Python service with:

- a FastAPI HTTP API for health/readiness, safe runtime metadata, PostgreSQL and Redis checks, and bounded workloads;
- a separate periodic worker process for database/cache activity;
- Prometheus-compatible API and worker metrics;
- JSON logs to stdout suitable for container logging;
- a Docker image that supports API and worker commands;
- a local Docker Compose environment with PostgreSQL and Redis.

The service is intended to generate controlled, observable behavior for integration and diagnostics testing. It is not a production business application.

## 2. What it does not depend on

The service does not depend on the repository that hosts it, any host application's code/API/database/authentication, AWS credentials or APIs, ECS SDKs, or a specific monitoring control plane. It has no application login/authentication. It does not provision infrastructure, expose arbitrary shell/SQL/Redis commands, or perform task-management operations.

To extract it, copy the complete `test-app/` directory. Build and run from that directory. No source changes should be required; configure endpoints and limits through the environment variables in `.env.example`.

## 3. Required infrastructure

For an API deployment with all integration paths enabled:

- a container runtime/orchestrator and private network;
- PostgreSQL accessible from API and, optionally, worker tasks;
- Redis accessible from API and, optionally, worker tasks;
- a secret/configuration mechanism to inject connection URLs securely.

Prometheus and log aggregation are optional external consumers. They are not bundled in the application image or local Compose stack. No AWS resources are created by this service.

## 4. Environment variables

All service configuration is environment-driven. Never commit actual URLs/passwords.

| Variable | Required | Default / contract |
|---|---:|---|
| `APP_NAME` | No | `standalone-test-laboratory` |
| `APP_VERSION` | No | `0.1.0`; should match the image/release version |
| `ENVIRONMENT` | No | `local`; non-secret label |
| `LOG_LEVEL` | No | `INFO`; `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `SERVICE_NAME` | No | `api-service`; set independently per deployed service |
| `HOST` | No | `0.0.0.0` in containers |
| `PORT` | No | API port `8080`, range 1–65535 |
| `REQUEST_TIMEOUT_MS` | No | 3000 ms; hard maximum 30000 ms |
| `DATABASE_URL` | For DB endpoints | PostgreSQL URL; credentials must come from secret injection |
| `REDIS_URL` | For Redis endpoints | `redis://` or `rediss://` URL; credentials must come from secret injection |
| `WORKER_ENABLED` | No | `false`; worker service must explicitly set true |
| `WORKER_INTERVAL_SECONDS` | No | 10 seconds; range 1–300 |
| `WORKER_METRICS_PORT` | No | 9101; reachable only by approved scraper/network |
| `MAX_CPU_WORK_MS` | No | 1000 ms; hard maximum 5000 |
| `MAX_LATENCY_MS` | No | 1000 ms; hard maximum 5000 |
| `MAX_MEMORY_MB` | No | 32 MiB; hard maximum 64 |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Compose only | Local database initialization; not consumed by the API except the assembled URL |

Unknown/invalid URL schemes, logging levels, boolean values, or values outside hard limits fail configuration. Do not define AWS account IDs, AWS regions, or AWS-specific settings for this service.

## 5. API service configuration

Run the API process:

```text
uvicorn api.main:app --host 0.0.0.0 --port 8080
```

Set `SERVICE_NAME` to an operator-chosen API service label, `WORKER_ENABLED=false`, and the dependency URLs that this deployment is permitted to reach. The same image can run a different API version/limit set only by changing its immutable image tag and environment; do not bake credentials into the image.

## 6. Worker service configuration

Run separately from the API:

```text
python -m worker.main
```

Set `SERVICE_NAME=worker-service`, `WORKER_ENABLED=true`, `WORKER_INTERVAL_SECONDS`, `DATABASE_URL`, and/or `REDIS_URL` as needed. Worker cycles check PostgreSQL with `SELECT 1` and increment one service-owned expiring Redis key. Each dependency attempt is bounded to three tries with capped backoff; the configured cycle interval prevents tight loops. SIGINT/SIGTERM requests graceful shutdown.

Worker Prometheus metrics are process-local and available on the configured `WORKER_METRICS_PORT`. The worker's metric state is not merged into the API `/metrics` registry.

## 7. PostgreSQL requirements

- PostgreSQL 14+ is recommended; validate the selected managed engine/driver combination.
- Provide a database and least-privilege application user through `DATABASE_URL`.
- Permit API tasks and optionally worker tasks to connect to the database port (normally TCP 5432); do not expose it publicly.
- The app creates only `products` and `orders` tables lazily on the first read and inserts a few deterministic rows idempotently. This is a demo/test schema, not a migration framework.
- Reads use fixed parameterized statements and a caller limit of 1–25. No endpoint accepts SQL text.
- Connection and statement timeouts use `REQUEST_TIMEOUT_MS`.
- For disposable test environments, seed data can be recreated by dropping only this app's schema/tables under an approved reset procedure.

## 8. Redis requirements

- Redis-compatible server is recommended; validate authentication/TLS settings for the selected provider.
- Provide a `redis://` or `rediss://` connection URL with credentials via runtime secret injection if required.
- Permit API/worker tasks to access TCP 6379 (or the configured endpoint port) privately only.
- The app uses fixed keys under `test-laboratory:*`, sets a 24-hour TTL, and exposes no arbitrary key or command API.
- Operations and socket connect/read waits use bounded timeouts.

## 9. Network requirements

- API ingress is TCP 8080 from approved clients/scrapers only. It has no built-in authentication, so private routing/security policy is mandatory; do not publish workload-control endpoints to the public internet.
- Worker has no inbound application listener. If scraping worker metrics, allow TCP 9101 only from the approved Prometheus/scraper.
- API/worker egress is limited to the configured PostgreSQL/Redis endpoints and approved log/metrics infrastructure.
- No public IP is required by the application itself.
- `/api/diagnostics/info` optionally reads ECS task metadata only when the runtime supplies the standard ECS metadata URI; local and non-ECS environments return null task identity. It exposes no credentials or private IP.

## 10. Ports

| Port | Process | Use |
|---:|---|---|
| 8080 | API | HTTP API, liveness/readiness, `/metrics` |
| 9101 | Worker | Worker Prometheus metrics only |
| 5432 | PostgreSQL default | API/worker to DB |
| 6379 | Redis default | API/worker to cache |

Only publish application ports that are required by the deployment. Local Compose binds 8080 and 9101 to host loopback only and keeps DB/cache internal to its network.

## 11. Health and readiness

- `GET /health` is the process liveness check. It does not contact PostgreSQL or Redis and should be the orchestrator restart health check.
- `GET /ready` probes PostgreSQL and Redis separately and returns a structured status for each. It returns HTTP 200 only when both are available; otherwise HTTP 503 with values `unavailable` or `not_configured`.
- Probe requests use bounded dependency timeouts. Do not use `/ready` as a liveness check: a dependency outage should not cause endless application restarts.
- Container health-check example:

```text
python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
```

## 12. Prometheus integration

Scrape the API endpoint at `GET /metrics` on port 8080. Scrape the worker endpoint on port 9101 only if worker metrics are required. The application exposes HTTP counters/latency/errors, workload execution/duration, PostgreSQL and Redis operation counts/durations, intentional error count, worker job/duration/error metrics, and an application-info gauge.

Labels are bounded to service, method, registered route template, status class, workload, operation, and result. Request IDs, arbitrary user input, raw URLs, SQL statements, Redis values, and credentials are not metric labels. This service does not synthesize CPU/memory/network telemetry; use real runtime/container metrics from the chosen platform collector if required.

Set scrape intervals and retention outside the application. Prometheus is not a runtime dependency; API operation continues when it is unavailable.

## 13. Loki and log integration

Application and worker logs are newline-delimited JSON written to stdout. A runtime log driver/agent may forward them to CloudWatch, Loki, or another sink. Useful fields include `timestamp`, `level`, `service`, `version`, `environment`, `event`, `request_id`, `hostname`, `operation`, `duration_ms`, `status`, `error_type`, workload/job and run ID.

If ingesting to Loki, keep labels low-cardinality (for example `service` and `environment`) and leave request/run IDs and operation details in the JSON body. Do not add credentials, connection strings, auth headers, request bodies, SQL text, Redis keys/values, or environment dumps to logs.

## 14. Docker deployment

Build from the extracted directory:

```sh
docker build -t standalone-test-laboratory:0.1.0 .
```

Use one immutable image digest/tag for separately configured API and worker services. API command:

```text
uvicorn api.main:app --host 0.0.0.0 --port 8080
```

Worker command:

```text
python -m worker.main
```

The Dockerfile uses a slim Python base, installs only this directory's runtime requirements, copies only API/worker/version files, and runs as a non-root user. It contains no AWS credentials, DB passwords, or host-application code.

### DCC Test Lab ECR image

The Task 46 Test Lab image was built from this directory as `linux/amd64`, tested, and pushed to the existing immutable-tag repository:

```text
366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-testlab-app:test-20261025-235129
```

Image digest:

```text
sha256:e1fcf841446fa2a34a27c066846d66bdddc6934c7d5c2c9a350c3f00ed419162
```

Use the pinned digest or immutable tag for both separate ECS services. API command: `uvicorn api.main:app --host 0.0.0.0 --port 8080`; Worker command: `python -m worker.main`.

## 15. ECS deployment model

This describes a possible deployment shape only; this guide does not deploy AWS infrastructure or prescribe a control-center deployment.

```text
ECS cluster (chosen by the consuming environment)
├── test-laboratory-api-service
│   └── same image, API command, port 8080
└── test-laboratory-worker-service
    └── same image, worker command, no inbound app port
```

Use separate ECS task definitions/service configuration or an explicit container command override to select runtime mode. Set desired counts, networking, secret references, logging and scaling according to the consuming environment's requirements. The app does not discover ECS resources, launch tasks, stop tasks, or call AWS APIs.

## 16. Security group requirements

Use the orchestrator/network platform's equivalent controls:

- API inbound: port 8080 from explicit approved application/operator clients and metrics scraper only.
- Worker inbound: none, except optional port 9101 from the metrics scraper.
- PostgreSQL inbound: database port only from API/worker identities that need SQL.
- Redis inbound: cache port only from API/worker identities that need Redis.
- Egress: only required DB/cache plus approved log/scrape/telemetry paths.
- No public access to workload endpoints, database, or cache.

## 17. Secrets management

Inject `DATABASE_URL` and `REDIS_URL` at runtime using the deployment platform's secret facility. Avoid plaintext task definitions, shell history, build arguments, image layers, logs, support bundles, and source control. Rotate credentials using the managed dependency's supported process. The application never prints URLs or credential values.

## 18. Resource sizing guidance

Start with a small API container (for example 0.5 vCPU / 1 GiB) and worker container (0.25 vCPU / 0.5 GiB), then measure under the capped scenarios. These are initial test estimates, not a promise of supported capacity or production sizing. Include memory margin for the Python runtime and at most 64 MiB per active memory scenario. Database/cache sizes and replica counts are selected by the consuming environment; scale down/destroy disposable resources when idle.

At most two synthetic workloads run concurrently per API process. More than one API replica means the concurrency cap applies per replica, not globally; use desired count and ingress controls appropriate to the test. It is not a distributed lock.

## 19. Workload safety limits

Configured maxima cannot exceed 5 seconds for CPU, 5 seconds for artificial latency, and 64 MiB for memory. Mixed workload caps CPU and delay independently and executes at most one small DB read and one fixed-key Redis increment. Error mode returns only a controlled message. Excess simultaneous workload requests return 429.

These limits control each request but do not replace private network isolation, platform CPU/memory limits, operator approval, or monitoring. Run workloads only against disposable test environments.

## 20. Communication contract

Other applications can call stable HTTP endpoints through private network routes:

| Endpoint | Integration use |
|---|---|
| `GET /health` | Liveness |
| `GET /ready` | Dependency readiness |
| `GET /api/diagnostics/info` | Identify responding service/runtime; task ID may be null outside ECS |
| `GET /api/products`, `GET /api/orders` | Exercise PostgreSQL reads |
| `GET /api/redis`, `POST /api/redis` | Exercise fixed Redis value/counter operations |
| `POST /api/work/cpu`, `/latency`, `/memory`, `/mixed` | Trigger bounded test workload |
| `GET /api/work/error` | Controlled error case |
| `GET /metrics` | Prometheus scrape |

Clients may send `X-Request-ID` using 1–128 ASCII letters/digits/dot/underscore/hyphen. The service returns the accepted/generated ID in the response header and includes it in JSON logs. Do not pass secrets in request IDs.

## 21. Troubleshooting

| Symptom | Check |
|---|---|
| `/health` fails | Process, port binding, container health check and application logs |
| `/ready` returns 503 | Read each `dependencies` status; check DNS, security rules, credentials injection and endpoint reachability without printing URLs |
| Data endpoint returns 503 | Dependency operation metric/log; verify URL scheme, availability, timeout and schema initialization |
| Worker repeatedly reports dependency unavailable | Check the worker's independent environment and network routes; it retries three times per dependency and waits for the configured cycle interval |
| `/metrics` missing series | Trigger the relevant request/operation; counters are process-local and appear after first observation |
| Diagnostic task ID is null | Runtime may not expose ECS metadata URI or metadata endpoint is unavailable; local/non-ECS null is expected |
| Logs lack request ID | Confirm request reached the service and check `X-Request-ID` response; service generates one when absent/invalid |
| Compose refuses to start | Confirm Docker Engine is running and `POSTGRES_PASSWORD` is set in the local `.env` file |

Never troubleshoot by printing full connection strings, dumping environment variables, enabling arbitrary command access, or making the service public.

## 22. Versioning and upgrades

`VERSION` is independent of any hosting repository. `APP_VERSION` may override its runtime label but should match the release. Follow SemVer:

- patch: backward-compatible fixes;
- minor: backward-compatible endpoints, metrics, or configuration;
- major: breaking HTTP payloads, behavior, metric names/labels, or environment contract.

Tag images with immutable version plus build revision. Before upgrading, run the included unit/API tests, build the image, exercise health/readiness and sample endpoints against disposable dependencies, compare OpenAPI/metric changes, then deploy to a non-production environment. Retain the previous image tag for rollback. Do not assume database migrations are supported: the current schema initialization is only for two simple test tables.
