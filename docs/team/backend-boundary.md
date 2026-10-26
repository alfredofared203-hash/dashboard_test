# Backend session lifecycle boundary

The Django backend owns diagnostic-session lifecycle and AWS ECS discovery. The browser calls the backend's `/api/ecs/...` routes; only the AWS provider uses boto3. ECS inventory is AWS-only and limited to explicitly configured clusters. Missing AWS configuration or AWS access returns an error rather than substituting sample resources. DCC has no application accounts, login, roles, browser sessions, or user-based API permissions; operational APIs are anonymous and production exposure must be restricted at the network boundary.

## API

All routes are under `/api/diagnostic-sessions/`:

| Method | Route | Behavior |
| --- | --- | --- |
| `GET` | `/` | List sessions created in this backend process |
| `POST` | `/` | Start a session with `{"target_task_id":"<running ECS task ID>"}`; returns 201 |
| `GET` | `/active/` | Return `{"session": <session>}` or `{"session": null}` |
| `GET` | `/{session_id}/` | Retrieve a session; unknown ID returns 404 |
| `POST` | `/{session_id}/stop/` | Stop a running session once; returns the updated session |

Sessions use `running`, `stopped`, `completed`, or `failed` states. Only `running` can transition to a terminal state. A second active session and repeated/invalid terminal transitions return HTTP 409 with a JSON `detail`; an unknown or no-longer-running target task is rejected, and an unknown session returns 404. Targets are checked against the configured live ECS task inventory before any diagnostic provider is invoked.

## ECS discovery API

| Method | Route | Behavior |
| --- | --- | --- |
| `GET` | `/api/ecs/clusters/` | Describes only configured cluster names/ARNs |
| `GET` | `/api/ecs/clusters/{cluster}/services/` | Lists active services and counts for a configured cluster |
| `GET` | `/api/ecs/clusters/{cluster}/tasks/` | Lists live tasks whose desired status is `RUNNING`, including safe container/network metadata |
| `GET` | `/api/ecs/clusters/{cluster}/tasks/{task_id}/` | Returns one currently running task |

Set `AWS_REGION` and comma-separated `DCC_ECS_CLUSTERS`. The provider calls `DescribeClusters`, `ListServices`/`DescribeServices`, `ListTasks`/`DescribeTasks`, and `DescribeTaskDefinition`; it does not enumerate arbitrary account clusters. AWS environment overrides, secrets, and task-role credentials are never mapped into API responses. Discovery failures return safe `503` errors; unconfigured cluster selectors return `404`.

## Lifecycle and limitations

- `apps/diagnostics/services.py` owns validation, uniqueness of the active session, transitions, timing, and lookup.
- `apps/diagnostics/impact.py` captures normalized resource measurements for each backend session and calculates the read-only impact report. It does not call AWS, Prometheus, or Loki APIs directly.
- `apps/diagnostics/providers.py` defines the `DiagnosticExecutionProvider` protocol, in-memory implementation, and single provider factory.
- `apps/api/ecs_discovery.py` is the read-only `AWSECSDiscoveryProvider`; it owns boto3 discovery calls and maps allowlisted response fields only. `apps/api/ecs_views.py` handles HTTP behavior and does not call boto3.
- `apps/diagnostics/ecs_provider.py` owns ECS `RunTask`/`StopTask` execution for the separately configured diagnostic worker. It is distinct from read-only workload discovery.
- `apps/diagnostics/serializers.py` owns request and public session response shapes. The response exposes provider and status only; the ECS task ARN and cluster reference stay internal.
- `apps/diagnostics/models.py` contains typed in-memory domain dataclasses, not Django database models.
- Session records and execution references are process-local and disappear on backend restart. There is no persistence or cross-process coordination.
- `DCC_DIAGNOSTIC_PROVIDER` defaults to `inmemory`. ECS is disabled by default in local development, and selecting ECS never silently falls back to the mock.
- The frontend API client lives in `frontend/src/lib/api/`, defaults to `http://localhost:8000`, requests inventory through `/api/ecs/...`, and validates task/session responses. The operator selects a currently running discovered task before CHECK.
- CORS uses an explicit API-path allowlist and approved-origin list. The default allowlist covers Vite's localhost origins; set `DCC_CORS_ALLOWED_ORIGINS` to a comma-separated list for other approved origins. CORS is not an access-control boundary.
- ECS discovery requires `AWS_REGION` and `DCC_ECS_CLUSTERS`. Diagnostic worker execution additionally requires `DCC_ECS_CLUSTER`, `DCC_ECS_TASK_DEFINITION`, `DCC_ECS_SUBNETS`, and `DCC_ECS_CONTAINER_NAME`. `DCC_ECS_SECURITY_GROUPS` is optional; `DCC_ECS_ASSIGN_PUBLIC_IP` defaults to false.
- Task resource metrics use the shared `TaskMetricsProvider` boundary. `DCC_METRICS_PROVIDER` defaults to `cloudwatch`; explicit `mock` remains a non-production development/testing choice. CloudWatch configuration uses `DCC_CLOUDWATCH_REGION` (or `AWS_REGION`), `DCC_CLOUDWATCH_CLUSTER_NAME`, `DCC_CLOUDWATCH_SERVICE_NAME`, `DCC_CLOUDWATCH_ECS_NAMESPACE`, and `DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE`; boto3 uses the ECS task role's standard credential chain.
- CloudWatch currently returns CPU/memory utilization and network throughput aggregates for its configured ECS service; it does not attribute those metrics to an individual running task or diagnostic session. Task inventory itself comes from live ECS discovery. Missing configuration, missing metrics, or AWS failures return a safe 503 and never silently switch to mock metrics. Tests use mocked AWS clients.
- Prometheus is configured with backend-only `DCC_PROMETHEUS_URL`. Its provider sends bounded `/api/v1/query_range` requests and owns all PromQL and response parsing. The Prometheus endpoint must expose `dcc_task_cpu_utilization_percent`, `dcc_task_memory_utilization_percent`, `dcc_task_network_receive_bytes_total`, and `dcc_task_network_transmit_bytes_total` metrics with a `task_id` label matching the DCC task ID. It assumes CPU/memory gauges are percentages and network metrics are byte counters. Mocked HTTP responses are used in tests; no Prometheus server is needed. The provider has no Prometheus endpoint authentication support; use an appropriately network-protected endpoint.
- Logs use a separate `LogsProvider` selected by `DCC_LOGS_PROVIDER`, which defaults to `loki`; deterministic mock logs require explicit opt-in. Configure the backend-only `DCC_LOKI_URL`; optional `DCC_LOKI_BEARER_TOKEN` and `DCC_LOKI_TENANT_ID` are sent only as server-side request headers. Loki calls use its `query_range` HTTP API with a one-hour window and a maximum of 500 entries. The provider expects a `service` stream label and maps `task_id` and `source` labels (or matching structured JSON line fields) into the existing log contract; other filters continue client-side. Severity labels/fields are normalized to the DCC set, with unknown levels falling back to `INFO`; missing metadata remains absent. Tests mock HTTP responses and make no network calls. Loki integration does not deploy/configure a production logging stack.
- `GET /api/diagnostic-impact/?session_id=<id>` returns a session-associated backend report; if the ID is omitted, the active or latest in-process session is selected. Baseline is captured before execution, during sampling is initially captured after execution starts then limited to 60 five-second samples, and post is best-effort on terminal transitions. Reports remain available for the process lifetime and disappear on restart.
- Impact calculations use normalized metric values, preserve missing phases as unavailable, return null percentage deltas for zero baselines, and report `unknown` when a non-zero change cannot be classified safely. DCC's `none`/`low`/`moderate`/`high` thresholds are application-specific, not universal. Only logs with an exact diagnostic session ID are correlated; other task logs are contextual. API test results are explicitly not provided. The report is not scientific causal analysis or complete production observability; tests use mocked providers and do not require AWS, Prometheus, Loki, or network access.
- ECS discovery provides current cluster/service/task/container/network metadata; it does not provision Container Insights or expose historical task inventory.
- The worker receives `DIAGNOSTIC_SESSION_ID`, `TARGET_TASK_ID`, and the discovered `TARGET_CLUSTER_ARN` as container environment overrides.
- boto3 uses the standard credential chain. Deployment should use an IAM task role; local development may use a standard AWS profile. Never add AWS credentials to application source or frontend `VITE_*` values.
- Provider launch/stop failures are translated to HTTP 502 with safe messages. The session becomes `failed` and retains a safe error; AWS exceptions and raw response data are not returned or logged.
- The application does not create ECS infrastructure. It only launches/stops an already configured task definition on an already configured cluster/network. No ECS service, VPC, subnet, security group, IAM role, cluster, or task definition is created here.
- Prometheus, Loki, RDS, ElastiCache, worker implementation, API test attribution, and session persistence remain out of scope. DCC application login and user authorization are intentionally absent. CloudWatch/Prometheus metrics and Loki logs are opt-in provider foundations; they do not complete production observability. The diagnostic execution provider abstraction permits future execution implementations without changing the public API contract.
