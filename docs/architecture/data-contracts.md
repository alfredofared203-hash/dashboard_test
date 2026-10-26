# DCC conceptual data contracts

These contracts describe the React/Django boundary. Some API routes are implemented with deterministic mock data; this does not imply live infrastructure integrations. Frontend contracts and API transport code belong under `frontend/src/`; Django endpoints and backend domain code belong under `backend/`.

Some sections describe concepts for future frontend/backend coordination; implemented endpoints are called out explicitly. These contracts are not database schemas. Agree on versioning, nullability, units, pagination, and error envelopes before changing API contracts. Timestamps should be serialized as ISO 8601 with an explicit timezone (UTC recommended); identifiers should be stable opaque strings.

## API Discovery

```ts
type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface ApiService {
  id: string;
  name: string;
  description?: string;
  endpoints: ApiEndpoint[];
}

interface ApiEndpoint {
  id: string;
  serviceId: string;
  method: HttpMethod;
  path: string;
  description?: string;
  parameters: Array<{
    name: string;
    location: "path" | "query";
    required: boolean;
    description?: string;
    schema?: unknown;
  }>;
  headers: Array<{
    name: string;
    required: boolean;
    description?: string;
    schema?: unknown;
  }>;
  authentication: {
    required: boolean;
    schemes: string[];
    description?: string;
  };
  requestSchema?: unknown;
  responseSchemas?: Array<{
    statusCode: number;
    schema?: unknown;
  }>;
}
```

`unknown` denotes schema documents to be validated/interpreted by a schema-aware consumer; it is not permission to disable TypeScript checks elsewhere. Engineer 1 owns discovery and catalog metadata only.

## API Test

```ts
interface ApiTestResult {
  id: string;
  endpointId: string;
  method: HttpMethod;
  request: {
    headers: Record<string, string>;
    query: Record<string, string>;
    body?: unknown;
  };
  statusCode: number | null;
  response?: unknown;
  durationMs: number | null;
  success: boolean;
  error?: {
    code?: string;
    message: string;
  };
  timestamp: string;
}
```

Engineer 2 owns request execution and result handling. Execution policy, secrets, and target-service communication belong on the backend.

## Task

```ts
interface Task {
  id: string;
  serviceId: string;
  status: string;
  health: string | null;
  cpu: { value: number; unit: string } | null;
  memory: { value: number; unit: string } | null;
  network: {
    receivedBytes?: number;
    transmittedBytes?: number;
  } | null;
  startedAt: string | null;
  stoppedAt: string | null;
}
```

The operational task summary is derived from live configured ECS clusters. The canonical discovery APIs are `GET /api/ecs/clusters/`, `GET /api/ecs/clusters/{cluster}/services/`, `GET /api/ecs/clusters/{cluster}/services/{service}/tasks/`, `GET /api/ecs/tasks/`, and `GET /api/ecs/tasks/{task_id}/`. Task details include task definition, status, launch/CPU/memory/AZ, allowlisted container fields, and `awsvpc` network metadata; environment values and secrets are never returned. The cluster-scoped task list/detail routes remain compatible. When a task ID is not unique across configured clusters, global detail returns `409`; specify the `cluster` query parameter to resolve it. Missing cluster configuration or AWS errors return a safe unavailable response rather than sample ECS resources. Missing AWS counts and service status remain null rather than fabricated values.

`/api/tasks/{task_id}/resources/` returns CPU, memory, and network baseline/current/peak values, units, impact deltas, and a `source` (`mock`, `cloudwatch`, or `prometheus`). The frontend validates these DTOs before mapping them into workspace-specific presentation types. Metrics default to CloudWatch; mock metrics require explicit opt-in. CloudWatch provides aggregates for one configured ECS service; Prometheus uses the `task_id` label matching the discovered ECS task ID. Neither source attributes measurements to diagnostic sessions.

## Resource Test

```ts
interface ResourceTestResult {
  id: string;
  targetTaskId: string;
  targetServiceId: string;
  resourceType: string;
  metric: string;
  baseline: number;
  duringTestValue: number;
  delta: number;
  percentageChange: number | null;
  durationMs: number;
  timestamp: string;
  source: string;
  unit: string;
}
```

Define the measurement window, aggregation method, and zero-baseline behavior before computing percentage change.

## Diagnostic Operation

```ts
interface DiagnosticOperation {
  id: string;
  name: string;
  targetServiceId: string;
  status: string;
  startedAt: string;
  finishedAt: string | null;
  durationMs: number | null;
}
```

## Frontend Diagnostic Session

The UI diagnostic session is the single shared state observed across pages. The System Overview is the only UI owner of start/stop controls; consumer features receive read-only session state. Its provider hydrates from the backend session API and maps the response contract into this UI-facing shape.

```ts
type DiagnosticSessionStatus =
  | "idle"
  | "starting"
  | "running"
  | "completed"
  | "stopped"
  | "failed";

interface DiagnosticSession {
  sessionId: string | null;
  status: DiagnosticSessionStatus;
  startedAt: Date | null;
  endedAt: Date | null;
  elapsedSeconds: number;
  targetScope: {
    type: "system" | "service" | "task";
    identifier: string;
    displayName: string;
  } | null;
  startedBy: string | null;
  error: { code: string; message: string } | null;
  resultSummary: {
    overallStatus: "completed" | "warning" | "failed";
    checkedItems: number;
    passedItems: number;
    warningItems: number;
    failedItems: number;
  } | null;
}
```

The API boundary in `frontend/src/lib/api/` uses the backend's `id`, `target_task_id`, `started_at`, `stopped_at`, and `duration_seconds` fields and tolerates optional execution metadata. On page load, the provider restores an active session or the latest session returned by the backend; while a session is running, it polls the detail endpoint for terminal updates. CHECK starts a backend session for the operator-selected live ECS task; STOP stops that session. `starting` is a short UI transition while the start request is in flight. The UI-only result summary remains empty because report and execution-result integration is not part of this lifecycle.

## Backend Diagnostic Session Lifecycle

The backend separately owns an in-memory session lifecycle exposed through `/api/diagnostic-sessions/`. `POST` to the collection starts a session only for a currently running discovered ECS task; `GET /active/`, `GET /{session_id}/`, and `GET /` read the active, individual, or listed sessions. `POST /{session_id}/stop/` stops a running session exactly once. Starting another session while one is running and repeating a terminal transition return HTTP 409. Unknown session IDs return 404 and unknown target task IDs return 400.

The backend session record includes `id`, `status`, `target_task_id`, `started_at`, `stopped_at`, and `duration_seconds`, plus safe execution-provider/status metadata and an optional safe error message. ECS task ARNs and cluster references are internal and are not serialized. State, IDs, and execution handles are process-local only; they are not persisted and are lost on backend restart. The default in-memory execution provider does not run diagnostics or call external services. An explicitly configured ECS provider can launch/stop an existing Fargate task; it does not create infrastructure. Service-layer completion and failure transitions reserve lifecycle outcomes for future orchestration but have no public mutation endpoints.

## Diagnostic Log Entry

```ts
type LogSeverity = "DEBUG" | "INFO" | "WARN" | "ERROR";

interface DiagnosticLogEntry {
  id: string;
  timestamp: string;
  severity: LogSeverity;
  service: string;
  taskId: string;
  source: string;
  message: string;
  diagnosticSessionId: string;
  traceId?: string;
  metadata?: Record<string, string | number | boolean | null>;
}
```

The `/logs` frontend consumes `GET /api/logs/` through the shared API client. Backend `DCC_LOGS_PROVIDER` defaults to Loki; mock logs require explicit opt-in. The API response stays a list of normalized log entries; trace ID and metadata are optional, and existing workspace filtering remains client-side. Optional API filters are `search`, `service`, `task_id`, `source`, `severity`, `since_minutes` (5/15/30/60), and `diagnostic_session_id`. Loki queries are bounded to the latest hour and 500 entries. Its stream labels `service`, `task_id`, and `source` map to existing DCC fields; structured JSON line fields may also provide those values. The feature cannot create or control diagnostic sessions.

## Diagnostic Impact

`GET /api/diagnostic-impact/?session_id=<backend-session-id>` returns a backend-generated report for that process-local session. Without the query parameter, the backend selects the active or most recently created session. Unknown sessions return 404. The React page requests this endpoint through the shared API client and does not aggregate frontend task/API/log samples.

```ts
type ImpactPhaseStatus =
  | "captured" | "partial" | "unavailable" | "not_configured" | "not_captured";

interface PhaseMeasurement {
  status: ImpactPhaseStatus;
  captured_at: string | null;
  source: "mock" | "cloudwatch" | "prometheus" | null;
  metrics: Partial<Record<"cpu" | "memory" | "network", {
    value: number;
    peak: number;
    unit: string;
  }>>;
  sample_count: number;
  detail?: string;
}

interface DiagnosticImpactMetric {
  unit: string;
  baseline: number | null;
  during: number | null;
  post: number | null;
  peak_during: number | null;
  during_delta: {
    status: "available" | "unavailable";
    absolute_delta: number | null;
    percentage_delta: number | null;
    reason: string | null;
  };
  post_delta: DiagnosticImpactMetric["during_delta"];
}

interface DiagnosticImpactReport {
  session: {
    id: string; status: "running" | "stopped" | "completed" | "failed";
    target_task_id: string; started_at: string; stopped_at: string | null;
    duration_seconds: number; error: string | null;
  };
  target: { task_id: string; name: string | null; service_id: string | null; service_name: string | null };
  measurements: {
    availability: "available" | "partial" | "unavailable";
    sources: Array<"mock" | "cloudwatch" | "prometheus">;
    phases: { baseline: PhaseMeasurement; during: PhaseMeasurement; post: PhaseMeasurement };
    metrics: Record<"cpu" | "memory" | "network", DiagnosticImpactMetric>;
  };
  impact: {
    classification: "none" | "low" | "moderate" | "high" | "unknown";
    summary: string;
    thresholds: { none_max_percent: number; low_max_percent: number; moderate_max_percent: number };
  };
  logs: {
    availability: "available" | "unavailable";
    session_correlated: DiagnosticLogEntry[];
    contextual: DiagnosticLogEntry[];
  };
  api_testing: { status: "not_provided"; message: string };
  limitations: string[];
  generated_at: string;
}
```

Baseline is captured before execution, during samples start after successful execution and are limited to 60 samples at five-second intervals, and post is best-effort on terminal transitions. During values are averages of captured readings; `peak_during` is the highest sampled current value. Percent changes are null for zero baselines, and non-zero changes from zero baselines are classified `unknown`. DCC thresholds are application reporting policy only: `none` ≤5%, `low` >5–15%, `moderate` >15–30%, and `high` >30%; they are not universal or causal thresholds. Missing phases/providers remain explicit and are never fabricated as zero.

Only logs whose `diagnostic_session_id` exactly matches the backend session ID are session-correlated. Other matching target-task logs are contextual. API Testing returns `not_provided`, because no actual API execution results are associated with diagnostic sessions. Session and report data are held in process memory and disappear on backend restart. The report is an application-level comparison, not scientific causal analysis or a complete production observability system.
