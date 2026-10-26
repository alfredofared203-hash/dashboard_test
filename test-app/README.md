# Standalone Test Laboratory Service

Version: see [`VERSION`](./VERSION). This directory is a portable Python service containing an HTTP API and a separate background worker. It can be copied out of its current host repository and developed/deployed independently.

The service provides a small realistic workload target: safe PostgreSQL reads, fixed-key Redis operations, bounded CPU/latency/memory workloads, a controlled error, JSON logs, Prometheus metrics, and health/readiness/diagnostic metadata. It does not contain a business-critical domain model.

## Architecture

```text
API process (FastAPI/Uvicorn, port 8080)
  ├── PostgreSQL (DATABASE_URL)
  ├── Redis (REDIS_URL)
  ├── JSON stdout logs
  └── Prometheus /metrics

Worker process (python -m worker.main)
  ├── periodic PostgreSQL SELECT 1
  ├── periodic Redis heartbeat
  ├── JSON stdout logs
  └── Prometheus metrics (port 9101)
```

The same Docker image supports both commands, but the API and worker are separate OS processes and should run as separate services/tasks. Neither process requires AWS.

## Standalone boundary

This service has its own `requirements.txt`, configuration, Dockerfile, Compose project, tests, version, and documentation. It does not import or call any host application's code, API, database, or identity/authentication system. Its source contains no AWS SDK calls and requires no AWS environment variables or credentials.

It is independent of its host repository. Use [`INTEGRATION.md`](./INTEGRATION.md) as the extraction and deployment contract.

## Local startup

Requires Python 3.12+ for local mode, or Docker Engine with Compose for the complete database/cache lab.

### Compose (API, worker, PostgreSQL, Redis)

Run these commands from `test-app/`:

```powershell
Copy-Item .env.example .env
# Edit .env and set POSTGRES_PASSWORD to a URL-safe local value.
# Compose builds the API DATABASE_URL from POSTGRES_USER and POSTGRES_PASSWORD.
docker compose up --build
```

API: `http://localhost:8080`. Worker metrics: `http://localhost:9101/metrics`. PostgreSQL uses a named local volume; Redis is reachable only within the Compose network. `GET /health` is available without dependency checks. Readiness becomes healthy after PostgreSQL and Redis answer their probes.

To reset local PostgreSQL data, run `docker compose down --volumes` from this directory. This deletes only the Compose-owned local database volume.

### Local Python API

Start PostgreSQL and Redis separately, then from `test-app/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "postgresql://test_lab:<url-safe-local-password>@localhost:5432/test_lab"
$env:REDIS_URL = "redis://localhost:6379/0"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8080
```

Run the worker in another terminal/process:

```powershell
$env:WORKER_ENABLED = "true"
$env:SERVICE_NAME = "worker-service"
python -m worker.main
```

Use `.env.example` as the configuration reference. The application intentionally does not load a `.env` file itself; supply environment variables through the shell, Compose, or the deployment runtime.

## Configuration

| Variable | Meaning | Default / validation |
|---|---|---|
| `APP_NAME` | Application display/service identity | `standalone-test-laboratory` |
| `APP_VERSION` | Independently versioned application release | `0.1.0` |
| `ENVIRONMENT` | Environment label | `local` |
| `LOG_LEVEL` | JSON log threshold | `INFO`; DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `SERVICE_NAME` | Service label | `api-service` |
| `HOST`, `PORT` | API bind settings | `0.0.0.0`, `8080` |
| `REQUEST_TIMEOUT_MS` | PostgreSQL statement/connect and Redis socket timeout bound | 3000 ms; hard maximum 30000 ms |
| `DATABASE_URL` | PostgreSQL URL | Optional for process startup; data/readiness operations report unavailable if not set |
| `REDIS_URL` | Redis URL | Optional for process startup; Redis/readiness operations report unavailable if not set |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Local Compose PostgreSQL initialization | Local-only; choose a URL-safe password for the sample connection URL |
| `WORKER_ENABLED` | Enable the separate worker loop | `false`; Compose explicitly enables worker service |
| `WORKER_INTERVAL_SECONDS` | Delay between worker cycles | 10; range 1–300 seconds |
| `WORKER_METRICS_PORT` | Worker-only Prometheus HTTP port | 9101 |
| `MAX_CPU_WORK_MS` | Configured CPU duration ceiling | 1000 ms; absolute max 5000 ms |
| `MAX_LATENCY_MS` | Configured artificial delay ceiling | 1000 ms; absolute max 5000 ms |
| `MAX_MEMORY_MB` | Configured memory allocation ceiling | 32 MiB; absolute max 64 MiB |

Invalid URLs, booleans, log levels, ports, and out-of-range values fail configuration rather than silently falling back.

## HTTP API

| Method/path | Purpose |
|---|---|
| `GET /health` | Liveness only; does not call dependencies |
| `GET /ready` | Structured PostgreSQL and Redis status; 503 unless both are available |
| `GET /metrics` | Prometheus text metrics for the API process |
| `GET /api/diagnostics/info` | Safe app/version/environment/hostname/PID/Python/dependency/task identity |
| `GET /api/products?limit=10` | Bounded parameterized PostgreSQL SELECT |
| `GET /api/orders?limit=10` | Bounded parameterized PostgreSQL SELECT |
| `GET /api/redis` | GET the fixed lab value key |
| `POST /api/redis` | JSON `{"value":"example"}` SET to a fixed key; empty body increments a fixed counter |
| `POST /api/work/cpu` | JSON `{"duration_ms":500}` |
| `POST /api/work/latency` | JSON `{"delay_ms":500}` |
| `POST /api/work/memory` | JSON `{"megabytes":16,"duration_ms":500}` |
| `POST /api/work/mixed` | JSON `{"cpu_ms":100,"delay_ms":100}` plus best-effort PostgreSQL and Redis operations |
| `GET /api/work/error` | Intentional safe HTTP 500 for error/log/metric validation |

Every request receives an `X-Request-ID`; a syntactically safe caller-provided ID is preserved, otherwise the service generates a UUID. API errors never expose stack traces or connection details.

## Workload safety

- CPU duration: 1 ms to configured ceiling, which cannot exceed 5000 ms.
- Latency duration: 1 ms to configured ceiling, which cannot exceed 5000 ms.
- Memory: 1 MiB to configured ceiling, which cannot exceed 64 MiB; allocation is released before return.
- Only two concurrent synthetic workloads per process; excess requests return 429.
- Query row limit: 1–25.
- Redis values: 1–128 characters; service-controlled keys expire after 24 hours.
- No arbitrary shell, SQL, Redis command, path, URL, or task identity input is accepted.
- The service has no built-in authentication. Keep workload endpoints behind trusted private network controls; do not expose them publicly.

## PostgreSQL and Redis

PostgreSQL uses `psycopg` and `DATABASE_URL`. The first products/orders read idempotently creates two minimal tables and seeds two small deterministic rows in each. All SQL statements are fixed and caller data is never used as SQL text.

Redis uses `redis-py` and `REDIS_URL`. Only service-owned fixed keys are used for GET, SET, INCR, and expiring worker heartbeat operations. Both clients use bounded timeouts. Failures are recorded safely and return explicit unavailable statuses/errors.

Neither dependency is required just to start the process or answer liveness. Both are required for a successful readiness response.

## Worker

`python -m worker.main` runs independently from Uvicorn. When enabled, each cycle runs a PostgreSQL `SELECT 1` and increments a fixed TTL-limited Redis heartbeat. Each operation retries at most three times with exponential backoff up to two seconds; failures do not enter a tight retry loop. The loop then waits `WORKER_INTERVAL_SECONDS`. SIGINT/SIGTERM stops it cleanly. Worker metrics are exposed independently at `WORKER_METRICS_PORT` (default 9101); Prometheus state is process-local and not shared with the API.

## Metrics and logging

API `/metrics` exposes:

- `http_requests_total`, `http_request_duration_seconds`, `http_errors_total`
- `workload_executions_total`, `workload_duration_seconds`
- `database_operations_total`, `database_operation_duration_seconds`
- `redis_operations_total`, `redis_operation_duration_seconds`
- `intentional_errors_total`, `application_info`

Worker `/metrics` exposes `worker_jobs_total`, `worker_job_duration_seconds`, and `worker_errors_total`. Labels are bounded service/method/route/status/workload/operation/result values. Request IDs are not metric labels. This version does not invent per-task CPU, memory, or network measurements.

Logs are JSON lines to stdout with timestamp, level, service, version, environment, event, request ID, hostname, and appropriate bounded operation, duration, status, workload/job, run ID, or error type fields. Never log passwords, tokens, authorization headers, connection URLs, request bodies, SQL literals, Redis values, or arbitrary environment variables. Output is suitable for Docker logging, CloudWatch collection, or Loki ingestion.

## Docker and Compose

Build the standalone image from this directory:

```powershell
docker build -t standalone-test-laboratory:0.1.0 .
```

Run API mode (supply DB/cache URLs as needed):

```powershell
docker run --rm -p 8080:8080 -e DATABASE_URL="<private-postgres-url>" -e REDIS_URL="<private-redis-url>" standalone-test-laboratory:0.1.0
```

Run worker mode as a different container using the same image:

```powershell
docker run --rm -e WORKER_ENABLED=true -e SERVICE_NAME=worker-service -e DATABASE_URL="<private-postgres-url>" -e REDIS_URL="<private-redis-url>" standalone-test-laboratory:0.1.0 python -m worker.main
```

The Dockerfile uses a non-root runtime user. Do not pass real passwords on interactive command lines in shared environments; use local secret injection/Compose environment and approved runtime secret stores.

## Tests

From `test-app/`, install development requirements and run:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

Unit/API tests use mocks and `TestClient`; no AWS, database, Redis server, Prometheus, or Loki is needed.

## Versioning and integration

The independent semantic version is stored in `VERSION` and surfaced as `APP_VERSION`/diagnostic metadata. Use SemVer: patch for compatible fixes, minor for backward-compatible features, major for breaking API/config/metric changes. Tag container images with an immutable version/revision; retain the previous image for rollback.

See [`INTEGRATION.md`](./INTEGRATION.md) for extraction, infrastructure, environment, API compatibility, health, network, secrets, ECS, Prometheus, logging, sizing, and troubleshooting contracts. No AWS resources are created here; AWS deployment is a separate future operation.
