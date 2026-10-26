# DCC AWS Test Laboratory Blueprint

## Purpose and boundaries

This document specifies a small, disposable AWS environment for validating DCC against real infrastructure. It is a design, not a deployment record. No AWS resources have been created.

The test application (`dcc-test-app`) is the primary diagnostic target. DCC is a separate control system: it discovers and observes the lab, and may launch a short-lived diagnostic worker after its safety and networking prerequisites have been verified. DCC itself is never enrolled as a target.

The target lab has no application login requirement. Keep it private and restrict workload-control endpoints to approved operator and DCC network paths. AWS IAM authenticates workloads to AWS APIs; it is not application authentication.

## Design assumptions and explicit decisions

- Use one AWS account and region for the initial laboratory. The DCC ECS service, Test API, Test Worker, and diagnostic worker will use the same dedicated VPC and private application subnets. Keep their clusters, roles, task definitions, and security groups distinct. Do not add cross-VPC networking. A later cross-account split would require an explicitly designed cross-account role-assumption flow; the current DCC provider uses the task role's normal boto3 credential chain.
- Use two Availability Zones, private ECS/data subnets, and no public IPs for tasks or databases.
- Use a fixed API service desired count of **3** and a fixed background worker service desired count of **2**. Do not add autoscaling to the initial lab; stable counts make discovery and comparisons reproducible.
- Deploy the diagnostic worker as an ECS task definition launched on demand by DCC, not as a continuously running service. It is separate from the test app's background `worker-service`.
- Enable ECS Container Insights. Use CloudWatch for infrastructure/dependency metrics and Prometheus for per-task application/resource series. DCC's current CloudWatch task-metrics provider is service-aggregate-oriented; use Prometheus when validating a specific task's impact.
- Run private Prometheus and Loki services in the lab. Prometheus may use ephemeral storage for a short test retention window. Loki should use an S3-backed single-binary configuration with short retention if persistent log correlation across restarts is required.
- Keep the lab small, schedule it off when unused, and destroy/recreate non-stoppable resources as needed. Validate current regional service availability, quotas, and prices before implementation.

## Logical architecture

```text
Approved operator network (VPN / existing private ingress)
                    |
                    v
       DCC control service (private app subnets, same VPC)
       - React + Django, one DCC image/container
       - DCC task role: read target ECS/CloudWatch
       - DCC may launch one bounded diagnostic worker
          | ECS APIs / CloudWatch APIs
          | same-VPC private task networking
          v
  +------------------- dcc-test VPC ---------------------+
  |                                                      |
  | Private application subnets (AZ-a and AZ-b)         |
  |  DCC ECS service (separate control cluster/service) |
  |  dcc-test-cluster                                    |
  |   api-service (3 x API task, primary target)         |
  |   worker-service (2 x background task)               |
  |   Prometheus (private, DCC-readable)                 |
  |   Loki (private, DCC-readable; S3 object storage)    |
  |   diagnostic-worker (ephemeral RunTask only)         |
  |         |                                            |
  |         +---- PostgreSQL (private RDS subnet group)  |
  |         +---- Redis (private cache subnet group)     |
  |                                                      |
  | Private DNS: dcc-test.internal (ECS service discovery)|
  | S3: Loki storage and optional test artifacts         |
  +------------------------------------------------------+
```

Keep DCC as a separately named ECS cluster/service and do not include it in `DCC_ECS_CLUSTERS`. The DCC runtime VPC will be created by the approved Test Lab/DCC deployment architecture: DCC and the Test Lab services share the dedicated VPC and private application subnets. Use `awsvpc`, the DCC control SG, and no public task IP; DCC-to-Test-API traffic is scoped by SG reference to the API's configured TCP port. Do not add VPC peering, Transit Gateway, VPN, PrivateLink, or public connectivity between DCC and the Test Lab. DCC operator ingress remains a separate private deployment concern; do not expose the unauthenticated DCC UI or test controls publicly. The target API needs no public ALB.

## Resource inventory and names

| Resource | Proposed name | Initial configuration |
|---|---|---|
| VPC | `dcc-test-vpc` | `10.80.0.0/16`, two AZs |
| ECS target cluster | `dcc-test-cluster` | Container Insights enabled |
| ECS DCC cluster | `dcc-control-cluster` | Separate from target cluster; DCC is not in target allowlist |
| ECR repository | `dcc-test-app` | Immutable image tags; may contain API/worker command variants |
| ECR repository | `dcc-test-diagnostic-worker` | Only if diagnostic worker has an independently versioned image |
| ECS service | `api-service` | 3 desired API tasks, private, service discovery enabled |
| ECS service | `worker-service` | 2 desired background tasks, private |
| ECS task definition | `dcc-test-api` | API and log-router containers |
| ECS task definition | `dcc-test-worker` | Background job consumer |
| ECS task definition | `dcc-test-diagnostic-worker` | On-demand DCC worker; not a target service |
| Cloud Map namespace | `dcc-test.internal` | Private DNS; register each API task IP |
| RDS instance | `dcc-test-postgres` | PostgreSQL 16, single AZ, private |
| ElastiCache cache cluster | `dcc-test-redis-001` | Redis OSS 7.x, one small node, private |
| Prometheus service | `dcc-test-prometheus` | Private, short retention, scrape API task targets |
| Loki service | `dcc-test-loki` | Private, single-binary, S3-backed storage |
| S3 bucket | `dcc-test-loki-data` | Private, encrypted, lifecycle/retention aligned |
| Security groups | `dcc-testlab-sg-*` | DCC control, diagnostic worker, Test API, Test Worker, RDS, and Redis groups with scoped same-VPC rules |

The authoritative VPC and subnet allocation is:

```text
Test Lab VPC: 10.80.0.0/16
├── Public AZ-A (eu-north-1a):             10.80.0.0/24
├── Public AZ-B (eu-north-1b):             10.80.1.0/24
├── Private Application AZ-A (eu-north-1a): 10.80.16.0/20
├── Private Application AZ-B (eu-north-1b): 10.80.32.0/20
├── Private Data AZ-A (eu-north-1a):        10.80.48.0/24
└── Private Data AZ-B (eu-north-1b):        10.80.49.0/24
```
| CloudWatch log groups | `/dcc-test/api`, `/dcc-test/worker`, `/dcc-test/telemetry` | Retention explicitly set; no indefinite default |

Use lowercase names and immutable image tags. Prefix every lab resource with `dcc-test-` except the isolated target cluster services whose canonical names (`api-service`, `worker-service`) are part of the DCC test contract.

## ECS service and task design

| Workload | Desired / min / max | Fargate task size | Network / port | Health and role |
|---|---:|---|---|---|
| `api-service` | **3 / 3 / 3** | 0.5 vCPU, 1 GiB total task memory | Private `awsvpc`, TCP 8080; no public IP | `/health/ready` container check; app container plus FireLens log router; no broad AWS API permissions |
| `worker-service` | **2 / 2 / 2** | 0.25 vCPU, 0.5 GiB | Private `awsvpc`, no inbound listener | Job-consumer health/heartbeat; only needs DB/cache access required for its job |
| `dcc-test-prometheus` | **1 / 1 / 1** | Start at 0.25 vCPU, 0.5 GiB; adjust only from observed use | Private TCP 9090; DCC ingress only after its SG/connectivity are approved | Scrapes each API task through Cloud Map; short local TSDB retention is acceptable |
| `dcc-test-loki` | **1 / 1 / 1** | Start at 0.25 vCPU, 0.5 GiB; validate memory against retention | Private TCP 3100; DCC ingress only after its SG/connectivity are approved, and log-router SG as required | Single-binary Loki, S3-backed chunks/index, finite retention |
| Diagnostic worker | **0 normally; one per approved session** | 0.25 vCPU, 0.5 GiB, within DCC-enforced ceilings | Private `awsvpc`; no public IP | Task launched/stopped only by DCC; separate task definition and role |

Fargate task CPU/memory is a task-level envelope; allocate container reservations/limits within it for the app and log router. Confirm the selected combinations are supported in the chosen region. Keep the API at three tasks during normal validation so ECS selection is non-trivial; do not introduce autoscaling until tests explicitly cover changing membership.

Enable ECS service discovery for `api-service` and publish task IP/port records in Cloud Map. The implementation should verify that the records correspond to the live ECS task IDs emitted on `/metrics`, and that deregistered/stopped tasks disappear promptly.

## Test application contract

The separate application is named `dcc-test-app`. Its workload-control and dependency-test endpoints are reachable only from approved private sources; they must not be routed through public ingress.

| Method and path | Purpose |
|---|---|
| `GET /health/live` | Process liveness only; no dependency call |
| `GET /health/ready` | Readiness with bounded dependency checks; ECS container check |
| `GET /api/products` | Read a small deterministic product set from PostgreSQL |
| `GET /api/orders` | Read a bounded list of orders and optional Redis cache |
| `POST /api/workloads` | Start one bounded workload run; schema below |
| `GET /api/workloads/{run_id}` | Read run state and counters |
| `POST /api/workloads/{run_id}/cancel` | Cancel the named in-process run; never stops arbitrary ECS tasks |
| `GET /internal/diagnostics/ping` | Private, read-only target used by the approved worker to validate reachability and confirm the responding task identity |
| `GET /metrics` | Prometheus text exposition; private scrape only |

Workload request schema:

```json
{
  "scenario": "cpu",
  "duration_seconds": 15,
  "request_id": "operator-generated-unique-id",
  "parameters": {}
}
```

Allow only enumerated scenarios, validate the duration and each scenario's parameters server-side, reject a second concurrent run on the same task, and return a run ID plus the selected task identity. Suggested hard bounds are 1–30 seconds per run, one active run per task, and one approved lab run at a time. Keep the default parameters low. Memory and network scenarios must have strict byte caps and clean up allocations/buffers on completion or cancellation. The workload endpoint must not accept shell commands, SQL text, arbitrary URLs, arbitrary file paths, or caller-selected task ARNs.

Task identity must come from the ECS task metadata endpoint available inside the container; parse the ECS task ARN to expose the same task ID format returned by the ECS discovery API. Do not accept a caller-supplied task ID as the metric identity. Do not emit environment values, connection strings, auth material, or secrets through logs, metrics, API responses, or errors.

### Required application metrics

Prometheus series must include the following names and types so they match the current DCC Prometheus provider contract:

| Metric | Type / labels | Meaning |
|---|---|---|
| `dcc_task_cpu_utilization_percent` | Gauge; `task_id`, `service` | Current task/container CPU utilization percentage derived from task-local ECS runtime stats |
| `dcc_task_memory_utilization_percent` | Gauge; `task_id`, `service` | Current task/container memory as a percentage of its configured limit |
| `dcc_task_network_receive_bytes_total` | Counter; `task_id`, `service` | Bytes received by the task network interface |
| `dcc_task_network_transmit_bytes_total` | Counter; `task_id`, `service` | Bytes transmitted by the task network interface |
| `dcc_http_requests_total` | Counter; `service`, `method`, normalized `route`, `status_class` | Request count; do not label with raw URL/query or request ID |
| `dcc_http_request_duration_seconds` | Histogram; same bounded labels | Request latency |
| `dcc_http_request_errors_total` | Counter; `service`, normalized `route`, `error_type` | Application failures |
| `dcc_db_queries_total` / `dcc_db_query_duration_seconds` | Counter / histogram; `operation` | PostgreSQL activity without query text |
| `dcc_redis_operations_total` / `dcc_redis_operation_duration_seconds` | Counter / histogram; `operation` | Redis operations without keys or values |
| `dcc_active_requests` | Gauge; `service` | Current in-flight HTTP requests |
| `dcc_workload_runs_total` | Counter; `scenario`, `result` | Completed/failed bounded workload runs |

The DCC metrics adapter currently expects the first four metric names and a `task_id` label. Determine CPU, memory, and network values from a supported in-task ECS stats source; document units and missing-data behavior. Do not synthesize values from workload inputs. Validate label cardinality and real task identity before connecting the DCC provider.

## PostgreSQL dependency

- **Engine:** Amazon RDS for PostgreSQL 16.x; at implementation time pin an AWS-supported minor/patch selected from the region's current engine catalog and apply maintenance updates through the lab change process.
- **Size:** smallest available burstable class suitable for the tests, initially `db.t4g.micro`; single AZ, 20 GiB gp3, autoscaling off or capped at a small limit.
- **Database:** `dcc_test`; schema/table names prefixed `test_`; deterministic seed data only.
- **Placement:** DB subnet group with private subnets in both AZs; instance not publicly accessible.
- **Connections:** API/worker use a small bounded connection pool; no unbounded connection per request. A request/run ID can be logged, but no SQL literals or credentials.
- **Security group:** inbound TCP 5432 only from API and worker task security groups. No DCC or public ingress rule.
- **Credentials:** generated and stored in Secrets Manager; injected at runtime through ECS secret references. No credentials in source, image, logs, or the DCC browser.
- **Expected load:** indexed reads, bounded inserts/updates in disposable test tables, connection-count changes, optional short repeated-query runs. Do not use unbounded table growth or destructive database stress.
- **DCC observations:** CloudWatch `AWS/RDS` metrics for `CPUUtilization`, `DatabaseConnections`, `FreeStorageSpace`, `ReadIOPS`, `WriteIOPS`, `NetworkReceiveThroughput`, and `NetworkTransmitThroughput`. Configure a DCC resource entry with `resource_type=rds`, `resource_scope=db_instance`, and the actual DB instance identifier.

## Redis dependency

- **Engine:** Amazon ElastiCache for Redis OSS 7.x; pin a currently offered compatible engine version during implementation. If the region/account requires Valkey instead, verify DCC's CloudWatch metric/dimension compatibility before selecting it.
- **Size:** one small burstable cache node, initially `cache.t4g.micro`; single node and no replicas for the disposable first lab.
- **Placement:** private cache subnet group spanning both AZs; cluster itself has no public endpoint.
- **Connection pattern:** application client uses bounded connect/read timeouts, short key TTLs, and namespaced test keys (for example `dcc-test:<run_id>:...`). Never put credentials or raw PII in keys/values.
- **Security group:** inbound TCP 6379 only from API and worker task security groups.
- **Credentials:** enable in-transit encryption and an authentication token where supported by the selected node/configuration; keep it in Secrets Manager and inject at runtime.
- **Expected load:** bounded `GET`/`SET`/`INCR` operations, cache hit/miss, short-lived key churn, and an app-level latency injection. Do not flush the cache or run an unbounded key generator.
- **DCC observations:** CloudWatch `AWS/ElastiCache` `CPUUtilization`, `BytesUsedForCache`, `DatabaseMemoryUsagePercentage`, `CurrConnections`, `NetworkBytesIn`, and `NetworkBytesOut`. Configure `resource_type=elasticache`, `resource_scope=cache_cluster`, and the actual cache cluster ID (`dcc-test-redis-001` if that is the AWS-assigned identifier). Use `replication_group` and its ID only if the topology changes to a replication group.

## Metrics and logging

### Infrastructure and application metrics

- Enable ECS Container Insights on `dcc-test-cluster` for ECS service/task CPU, memory, network, and task health observations. Validate metric publication and dimensions against the AWS console/API before configuring DCC.
- Use DCC CloudWatch metrics mode as a first integration check for `api-service` with `DCC_CLOUDWATCH_CLUSTER_NAME`, `DCC_CLOUDWATCH_SERVICE_NAME`, `DCC_CLOUDWATCH_ECS_NAMESPACE=AWS/ECS`, and `DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE=ECS/ContainerInsights`. It reports service-level aggregates and must not be presented as task-specific evidence.
- Use the private Prometheus service for per-task application and task metrics. Scrape each API task through ECS Cloud Map private DNS; use a scrape interval of 15 seconds, a 7-day or shorter retention window, and the exact DCC metric names/labels above. Configure DCC with `DCC_METRICS_PROVIDER=prometheus` and `DCC_PROMETHEUS_URL=http://dcc-test-prometheus.dcc-test.internal:9090` (adjust the service DNS name if implementation chooses another).
- The current DCC runtime selects one task-metrics provider at a time. Test CloudWatch and Prometheus in separate explicitly documented deployment configurations, not by implying one response combines both.
- DCC dependency observations use `DCC_DEPENDENCIES_PROVIDER=cloudwatch` and a bounded `DCC_DEPENDENCY_RESOURCES` list. Dependency metrics are observational and do not by themselves prove diagnostic causation.

Example dependency configuration (replace IDs with the actual identifiers returned by AWS):

```json
[
  {
    "resource_type": "rds",
    "resource_id": "dcc-test-postgres",
    "resource_scope": "db_instance",
    "engine": "postgres"
  },
  {
    "resource_type": "elasticache",
    "resource_id": "dcc-test-redis-001",
    "resource_scope": "cache_cluster",
    "engine": "redis"
  }
]
```

### DCC integration settings

Configure DCC only with lab identifiers and private service URLs. Keep all tokens and passwords in Secrets Manager; none of the following settings should contain credentials.

Deploy the DCC ECS service in the Terraform `private_application_subnet_ids` and attach the `dcc_control` security-group output with public IP assignment disabled. The diagnostic `RunTask` uses the same private application subnet IDs and the `diagnostic_worker` SG output. Both reach the Test API privately using the Test API SG reference; no cross-VPC route is needed.

| DCC setting | Proposed value / phase |
|---|---|
| `AWS_REGION` | Selected lab region |
| `DCC_ECS_CLUSTERS` | ARN/name of `dcc-test-cluster` only; do not include the DCC control cluster |
| `DCC_CLOUDWATCH_REGION` | Same region |
| `DCC_CLOUDWATCH_CLUSTER_NAME` | `dcc-test-cluster` |
| `DCC_CLOUDWATCH_SERVICE_NAME` | `api-service` |
| `DCC_CLOUDWATCH_ECS_NAMESPACE` | `AWS/ECS` |
| `DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE` | `ECS/ContainerInsights` |
| `DCC_DEPENDENCIES_PROVIDER` | `cloudwatch` |
| `DCC_DEPENDENCY_RESOURCES` | The two-resource JSON example above, with actual AWS identifiers |
| `DCC_LOGS_PROVIDER` | `loki` |
| `DCC_LOKI_URL` | Private Loki base URL, for example `http://dcc-test-loki.dcc-test.internal:3100` |
| `DCC_METRICS_PROVIDER` | `cloudwatch` for the service-aggregate pass; use `prometheus` for the separate task-specific pass |
| `DCC_PROMETHEUS_URL` | Private Prometheus base URL, for example `http://dcc-test-prometheus.dcc-test.internal:9090` |
| `DCC_DIAGNOSTIC_PROVIDER` | Keep `inmemory` until the diagnostic implementation gate passes; then explicitly set `ecs` for approved lab-only runs |
| `DCC_ECS_CLUSTER` | `dcc-test-cluster`, only in the approved ECS diagnostic phase |
| `DCC_ECS_TASK_DEFINITION` | Exact active `dcc-test-diagnostic-worker:<revision>` |
| `DCC_ECS_SUBNETS` | Terraform `private_application_subnet_ids` from the same VPC |
| `DCC_ECS_SECURITY_GROUPS` | Terraform `diagnostic_worker` SG output; no public ingress |
| `DCC_ECS_CONTAINER_NAME` | Exact container name in the worker task definition |
| `DCC_DIAGNOSTIC_MAX_ACTIVE_SESSIONS` | `1` for this process-local lab validation |

Use `DCC_DIAGNOSTIC_PROVIDER=ecs` only after confirming the worker image, task definition, exact roles, private IP resolution, target port, security-group path, and cleanup behavior. The separate workload-control API remains disabled to public ingress regardless of this setting.

### Logs

```text
API / worker JSON stdout
        -> ECS FireLens (Fluent Bit log router)
        -> private Loki push endpoint
        -> S3-backed Loki storage with finite retention
        -> DCC GET /api/logs/ through private network
```

Emit one JSON object per event with `timestamp`, `level`, `service`, `task_id`, `request_id`, `trace_id`, normalized `endpoint`, `duration_ms`, `status_code`, optional `dependency`, `error_type`, and optional `diagnostic_session_id`. Include `diagnostic_session_id` only when the request is actually associated with a DCC session. Include `service` and `task_id` as Loki labels because DCC filters those fields; keep request ID, trace ID, endpoint, and other high-cardinality fields in the JSON body, not as labels.

Expected examples:

- **Normal:** `INFO` request completion and bounded DB/Redis operation durations.
- **Warning:** scenario limit reached, dependency latency elevated, cache miss, or retry; include safe run/request context.
- **Error:** intentional application error or unavailable dependency; emit normalized error type and HTTP status without stack traces containing secrets or raw connection strings.

Set short CloudWatch log group retention for infrastructure/router diagnostics. Loki must not be publicly reachable. DCC uses its backend-only `DCC_LOKI_URL` and, if required, a read-only bearer credential/tenant ID stored in Secrets Manager. Keep Loki labels low-cardinality and configure deletion/retention, not just S3 lifecycle.

## Workload scenarios

Trigger scenarios through the private `POST /api/workloads` contract. Each run uses one explicitly selected API task where possible; record the returned run ID and actual ECS task ID. Do not launch a scenario from the ECS inventory page automatically.

| Scenario | Trigger and bounds | Expected target behavior | Expected observability / DCC result |
|---|---|---|---|
| Normal | `scenario=normal`, 1–5 seconds, default parameters | Low CPU/memory, small indexed DB read and optional Redis lookup, low network | Baseline request/latency metrics and structured `INFO` log; DCC shows live task metadata and low/steady measurements |
| CPU | `scenario=cpu`, 5–30 seconds, bounded worker loop and one run at a time | CPU rises only on selected task; memory approximately stable | CPU gauge/request latency rise and return toward baseline; workload start/finish logs; DCC Prometheus per-task time series |
| Memory | `scenario=memory`, configured allocation cap (initial maximum 64 MiB) and 5–15 seconds | Memory rises on selected task within limit and is released | Memory gauge rises/falls; no OOM expected in normal case; test an explicit near-limit case only in a separate approved run |
| Database | `scenario=database`, bounded query count (initial maximum 100) | PostgreSQL connections/query activity rises; modest target CPU/network | DB counters/latencies, RDS CPU/connections/IO/network, structured dependency timings, DCC RDS dependency snapshot |
| Redis | `scenario=redis`, bounded operations/key count and TTL | Cache ops/connections/network increase; short-lived test keys expire | Redis operation metrics and ElastiCache CPU/memory/connections/network; DCC cache dependency snapshot |
| Network | `scenario=network`, fixed-size internal payloads to a private test sink, initial cap 10 MiB/run | Target network counters rise; CPU remains bounded | ECS/Prometheus task network counters, request bytes, sink-side count; no arbitrary internet target accepted |
| Error | `scenario=error`, one enumerated error mode, bounded request count | Intentional 4xx/5xx response, no task crash by default | Error counter and `ERROR`/`WARN` structured log with safe `error_type`; DCC log filter and API error surfaces |
| Dependency latency | `scenario=dependency-latency`, inject a fixed bounded delay (for example 100–500 ms) inside the app adapter only | Increased response/dependency latency without changing DB/cache configuration | Latency histogram and warning log increase; DCC dependency snapshots may show normal infrastructure, distinguishing app-injected delay |
| Dependency unavailable | App-level fail-closed adapter mode or test-only proxy returns timeout/error for a bounded number of calls | Safe fallback or 503, no destructive DB/cache action | Error counters/logs and explicit missing/unavailable measurement semantics; DCC must not convert missing data to zero |
| Combined | Named bounded preset combining CPU plus small DB/Redis/network activity; max 30 seconds | Multiple resource series rise but stay within service/task limits | Correlated run ID, task ID, metrics, logs, dependencies, and DCC impact phases; no causal claim beyond measured correlation |

Normal workload settings must be the default. The app must reject unknown modes, invalid values, excess duration/bytes/operations, and concurrent runs rather than silently substituting a different workload.

## Safe failure scenarios

| Failure to validate | Safe method | Guard |
|---|---|---|
| Task restart | Stop one non-DCC API test task through an approved operator runbook and let ECS replace it | Do not stop all tasks; confirm 2 remaining API tasks and service stability first |
| Container/application failure | Test-only feature flag makes `/health/ready` fail or an endpoint return a controlled error | Keep `/health/live` separate; auto-clear flag after a bounded test window |
| Health check failure | Toggle the readiness response on one task for a short period | Do not alter the ECS service's production deployment configuration or fail all replicas |
| Dependency timeout | Use app-level timeout injection or an isolated proxy rule for selected requests | Do not change RDS/Redis network rules or overload/stop the dependency |
| High CPU/memory/network | Use bounded workload scenarios | Enforce duration, byte, allocation and concurrency caps; abort on configured alarms |
| Latency increase | Inject delay in the app dependency adapter | Do not add latency to the shared VPC or other services |
| Dependency unavailable | Return a controlled adapter-level failure for the test run | Preserve the real database/cache; do not delete, flush, reboot, or firewall them |

All fault flags must default off, be restricted to private operator/test paths, be visible in logs, and have automatic expiry. The lab should be recoverable by re-deploying desired task definitions and recreating disposable dependencies from IaC.

## Networking

### Addressing and subnets

Use the authoritative `10.80.0.0/16` CIDR and six-subnet layout selected by Task 38 and documented in [ADR-001](../adr/ADR-001-test-lab-pre-apply-network-and-state.md). The AWS-visible `eu-north-1` VPC/subnet inventory showed only `172.31.0.0/16`; its route table has a local route and an IGW default route. No VPC peering, Transit Gateway, VPN gateway, or VPN connection was returned. The proposed range does not overlap those visible ranges. DCC and Test Lab task communication is entirely within the shared new VPC; any future connection to another network requires a separate overlap review.

| Subnet group | Example CIDRs | Placement |
|---|---|---|
| Public/egress AZ-a | `10.80.0.0/24` | NAT gateway only; no ECS task public IP |
| Public/egress AZ-b | `10.80.1.0/24` | Reserved public tier; no application/data placement |
| Private app AZ-a | `10.80.16.0/20` | API, worker, Prometheus/Loki if separately approved, diagnostic workers |
| Private app AZ-b | `10.80.32.0/20` | ECS tasks spread across AZs |
| Private data AZ-a | `10.80.48.0/24` | RDS/cache subnet group |
| Private data AZ-b | `10.80.49.0/24` | RDS/cache subnet group |

The authoritative repository layout uses the two configured AZ names `eu-north-1a` and `eu-north-1b`; verify availability/capacity in the approved account before deployment.

### Traffic rules

| Source | Destination | Rule |
|---|---|---|
| Approved private ingress/VPN | DCC service ingress | HTTPS only, to DCC ingress; no public test-control endpoint |
| DCC control SG | Test API SG | TCP 8080 only, scoped by SG reference |
| Diagnostic worker SG | API task SG | TCP 8080 only, from private worker SG |
| API/worker task SGs | PostgreSQL SG | TCP 5432 only |
| API/worker task SGs | Redis SG | TCP 6379 only |
| API task SGs | Prometheus scrape path | TCP 8080 from Prometheus SG to `/metrics` only |
| API/worker task SGs | Loki push path | TCP 3100 only from the log-router path to Loki |
| ECS tasks | AWS APIs | VPC endpoints or controlled NAT egress; only required endpoints |

No inbound internet rule should target ECS tasks, RDS, Redis, Prometheus, or Loki. Use private DNS and security-group references rather than broad VPC CIDR ingress wherever supported. Enable TLS for database/cache connections and private telemetry where supported; never route credentials over public endpoints.

Prefer a no-NAT private design with the required ECR API/ECR Docker, S3 gateway, CloudWatch Logs, CloudWatch, ECS, Secrets Manager, and STS endpoints, after validating the exact services used. VPC interface endpoints have hourly/data charges. A single NAT gateway is a simpler temporary alternative but is a significant fixed/data cost and a single-AZ dependency; do not add one without an explicit cost choice. The app and test sink require no general internet access.

### Diagnostic target resolution

The target task is selected by its actual ECS task ID and cluster identity from live discovery. Its private IP comes from the task's `awsvpc` attachment and is not user-supplied. Only a `RUNNING` task in the configured target cluster is eligible. Security groups permit the diagnostic worker to reach the selected target task's approved diagnostic endpoint; no public IP is required.

The proposed test target exposes `GET /internal/diagnostics/ping` on the private API port. It returns only a bounded response containing the actual responding task ID, service name, and timestamp; the worker compares the returned task ID with its requested target. This validates that task resolution and routing refer to the intended task, rather than merely a reachable service load balancer.

**Implementation gate:** the current DCC ECS execution provider passes `TARGET_TASK_ID` and `TARGET_CLUSTER_ARN` to the worker but does not pass the discovered private IP. Before enabling a real diagnostic, define and test how the worker resolves the task identity to the current private IP (for example, a narrowly scoped ECS `DescribeTasks` call from its task role, or a validated backend-supplied private address), and ensure it calls the selected task IP directly rather than a load-balanced service DNS name. Do not guess an IP from the task ID, use stale inventory, or grant the test app AWS credentials. Verify task replacement behavior, target port/protocol, timeout, and that the worker can reach only approved lab targets.

## IAM separation

Use separate roles and narrowly scope resource ARNs/actions where AWS supports resource-level authorization. Verify every action against the current ECS/CloudWatch/Secrets Manager service authorization documentation before applying policies. Do not use `AdministratorAccess`.

| Identity | Minimum responsibility |
|---|---|
| DCC ECS execution role | Pull DCC image from ECR; write DCC container logs; retrieve only the DCC secret references used in its task definition |
| DCC runtime task role | Read configured target cluster/service/task/task-definition inventory (`ecs:DescribeClusters`, `ListServices`, `DescribeServices`, `ListTasks`, `DescribeTasks`, `DescribeTaskDefinition` as required); read configured CloudWatch metrics (`cloudwatch:GetMetricStatistics`); read configured RDS/ElastiCache metrics; when explicitly enabled, run/stop only the diagnostic worker task in the approved cluster and `iam:PassRole` only the exact worker execution/task roles with `iam:PassedToService=ecs-tasks.amazonaws.com` |
| Diagnostic worker execution role | Standard ECR image pull, CloudWatch Logs, and only runtime secret retrieval if the worker requires an explicit secret |
| Diagnostic worker task role | Prefer no AWS permissions. If it must resolve the target task to a current private IP, permit only the minimum ECS read action(s) for the configured cluster/task; no broad discovery or mutation rights |
| Test API/worker execution role | Standard ECR pull, CloudWatch/FireLens log delivery, and retrieval of only that service's DB/cache secret references |
| Test API/worker task role | No AWS API permissions by default. App-level database/cache credentials are injected by ECS from Secrets Manager; they do not require AWS SDK credentials |
| Prometheus task role | None for Cloud Map DNS scraping; no access to the AWS account or target task mutation |
| Loki task role | S3 read/write/list scoped to the `dcc-test-loki-data` prefix/bucket, plus only the required encryption-key permissions if a customer-managed key is selected |
| Deployment identity | IaC provisioning permissions limited to the lab stack; ECR push; ECS task-definition registration/service deployment; narrowly scoped `iam:PassRole` to the lab execution/runtime roles; describe/read networking prerequisites. No routine AdministratorAccess |

If Cloud Map DNS-based discovery is replaced with AWS API discovery, add only its required read actions to the Prometheus role. If DCC's existing CloudWatch dependency provider calls `GetMetricStatistics`, do not grant write actions. Keep the role used to deploy infrastructure distinct from all runtime task roles.

## Cost-control plan

This is a laboratory, not a highly available production service:

- Three API tasks and two worker tasks are the planned steady test counts. Reduce worker desired count to zero outside worker-specific tests; scale the API, Prometheus, and Loki services down when the lab is inactive if logs/metrics retention is not required.
- At the specified task sizes, the target API, background workers, Prometheus, and Loki reserve about **2.5 vCPU and 5 GiB RAM** across four services (seven steady tasks). DCC capacity is outside this estimate because its task size/count are not specified here; one active diagnostic worker adds 0.25 vCPU and 0.5 GiB for its bounded lifetime. These are configured task envelopes, not measured utilization or a dollar quote.
- RDS and ElastiCache are the most important always-on dependency cost drivers. RDS may be stopped for short inactive periods, subject to AWS stop limits/automatic restart; snapshot and destroy/recreate for longer idle periods. ElastiCache has no simple stop/start lifecycle for a node-based cluster; snapshot if appropriate and delete/recreate when idle.
- One NAT gateway and an ALB add fixed hourly and data-processing charges. Prefer VPC endpoints/private operator access where economical; compare actual regional costs before selecting NAT/endpoints/ingress.
- Fargate cost scales with configured vCPU, memory, and run time; diagnostic worker cost should be limited by DCC duration/concurrency guards and never left running.
- CloudWatch custom Container Insights metrics, log ingestion/retention, Prometheus storage, Loki/S3 storage/requests, ECR images, snapshots, and data transfer are additional cost categories. Set log and metric retention and lifecycle policies.
- Configure budget alerts and a hard lab spend threshold before provisioning. Schedule a teardown check that confirms target ECS desired counts, temporary tasks, and disposable dependencies are removed or in their approved idle state.

Do not assert a monthly dollar estimate until the region, exact instance versions, NAT/VPC endpoint choice, log volume/retention, ingress path, and operating schedule are known. Before implementation, produce an AWS Pricing Calculator estimate for both the planned active test week and the scheduled idle profile; NAT, always-on database/cache nodes, and telemetry services are expected to dominate the idle baseline.

## DCC validation matrix

| DCC capability | Lab target / validation evidence | Important limitation |
|---|---|---|
| Cluster discovery | `dcc-test-cluster` through `GET /api/ecs/clusters/` | DCC allowlist must contain only the intended target cluster |
| Service discovery | `api-service`, `worker-service` | Compare names/counts/status to ECS |
| Running task discovery | Three API and two worker tasks | IDs/ARNs must match AWS; no sample inventory |
| Task/container/network metadata | API task definition, app/router containers, task ENI/private IP/subnet/security groups/AZ | Optional AWS metadata may be unavailable; show it as unavailable, never inferred |
| Task selection | Select one of three `api-service` task IDs | Verify task ID and cluster identity before diagnostics |
| ECS CPU/memory/network | CloudWatch Container Insights and Prometheus task series | DCC CloudWatch resource response is service aggregate; per-task impact requires valid `task_id` Prometheus series |
| Application metrics | Private Prometheus `/metrics` scrape | DCC currently consumes only its fixed CPU/memory/network metric names for resource observations; other series validate in Prometheus |
| Logs/structured correlation | FireLens to Loki; query by service/task/session labels | Do not claim session correlation unless session ID is present and exact |
| PostgreSQL observability | RDS CloudWatch metrics and test app queries | CloudWatch metrics are delayed/periodic; no SQL text is exposed |
| Redis observability | ElastiCache CloudWatch metrics and bounded operations | Verify chosen Redis/Valkey topology emits the expected metric dimensions |
| Diagnostic worker launch/stop | DCC launches only `dcc-test-diagnostic-worker` | Requires IAM PassRole/RunTask/StopTask scope and worker cleanup proof |
| Diagnostic target networking | Worker to the selected API task private address and `/internal/diagnostics/ping` | DCC worker private-IP resolution and direct-to-task request are implementation gates |
| Session lifecycle | One bounded session at a time, normal stop and timeout/cleanup test | State is process-local; use one DCC worker process/task for deterministic validation |
| Impact measurement | Baseline/during/post Prometheus snapshots and task logs | Correlation is not causal proof; missing samples remain unavailable |
| Error diagnostics | Controlled API error and dependency adapter failures | No destructive database/cache faults |
| Failure/recovery | One-task replacement/readiness failure/timeout injection | Never fail every replica or target production resources |
| Security boundary | IAM simulation/review, SG review, secret scan, private route checks | CORS is not access control; DCC/test controls are unauthenticated at app layer |

### Capabilities not fully proven by this lab

- Production-scale autoscaling, multi-account isolation, cross-region discovery, high availability, and large-volume telemetry are out of scope.
- Current DCC CloudWatch task metrics are service aggregates; task-specific impact attribution is only validated through the Prometheus path.
- DCC's in-memory diagnostic lifecycle is not durable or coordinated across replicas/restarts; keep one DCC runtime process/task during lab execution.
- CloudWatch metric publication can lag test actions; short workload scenarios may be visible in Prometheus/logs before CloudWatch.
- Real-world diagnostic causal attribution is not proven by before/during/after correlation alone.
- The foundation creates the same-VPC DCC SG boundary but does not create the DCC ECS service or its separate operator ingress.

## Implementation sequence for follow-up tasks

1. **Approve environment assumptions and cost envelope.** Select account, region, two AZs, VPC CIDR, private DCC operator ingress, budget, retention, and whether a no-NAT endpoint design is acceptable.
2. **Implement shared-VPC IaC.** Create the VPC/subnets/routes, DCC and Test Lab security groups, private DNS, IAM roles/policies, log groups, and reviewed outputs. No cross-VPC path or DCC app changes in this step.
3. **Implement `dcc-test-app`.** Add bounded endpoints/scenarios, health routes, PostgreSQL/Redis clients, task identity, matching Prometheus metrics, structured logs, and unit/integration tests. Keep workload-control endpoints private.
4. **Create disposable dependencies and secrets.** Provision RDS/Redis with private groups and runtime secret references. Confirm app connects with TLS and bounded pools.
5. **Deploy target ECS services.** Push immutable images; deploy `api-service` at 3 tasks and `worker-service` at 2 tasks; verify metadata and Cloud Map registration.
6. **Deploy telemetry.** Configure Container Insights, Prometheus scraping per task, Loki S3 retention, and FireLens; compare sample metrics/logs with source truth.
7. **Configure DCC read-only discovery/metrics/dependencies/logs.** Start with discovery and safe read-only providers. Confirm DCC task role and configured cluster/service/resource IDs. Run CloudWatch and Prometheus provider checks as separate configurations.
8. **Resolve the diagnostic networking gate.** Implement/verify worker target-IP resolution, ingress to one target, bounded diagnostic image/task definition, exact IAM role passing, and cleanup. Do not enable DCC ECS execution before this is approved.
9. **Run the safe validation matrix.** Execute normal first, then bounded workload and failure cases one at a time. Capture AWS task IDs, metric timestamps, logs, session IDs, and cleanup evidence.
10. **Add schedule/teardown automation.** Define an operator-approved schedule, snapshot policy, dependency teardown/recreation, retention, and rollback procedure. Confirm no orphaned diagnostic worker tasks remain.

## Open decisions before provisioning

1. AWS account, region, allowed two AZs, and confirmation that the proposed CIDR does not overlap the visible regional VPC ranges.
2. Private DCC operator ingress; no public unauthenticated endpoint is authorized.
3. No-NAT VPC endpoints versus the planned single NAT gateway, based on required AWS APIs and a regional cost comparison.
4. Exact RDS PostgreSQL 16.x minor/class and Redis OSS 7.x version/node supported in the target region.
5. Whether the test lab needs durable Prometheus data; Loki storage/retention remains S3-backed for useful log history.
6. The DCC diagnostic worker's exact target-IP resolution mechanism and diagnostic protocol/port. This is a hard gate, not a guessed configuration.
7. Whether API workload-control endpoints are protected by private security groups alone or an additional operator-only test harness. Do not rely on CORS as protection.
8. Whether the current DCC metrics and dependency providers can cover all desired test views without code changes; document gaps before expanding scope.

## Task 31 status

This blueprint remains a proposed design. Task 38 confirms DCC and Test Lab workloads are intended to share the dedicated VPC and private application subnets. Read-only inspection of the configured AWS identity and `eu-north-1` network inventory did not modify AWS resources. No infrastructure was deployed by this documentation update, no DCC application code was changed, and the test application was not implemented by this blueprint.
