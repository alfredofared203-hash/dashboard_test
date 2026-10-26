import type { DiagnosticLogEntry } from "../types/logs";

interface MockLogDefinition {
  id: string;
  minutesAgo: number;
  severity: DiagnosticLogEntry["severity"];
  service: string;
  taskId: string;
  source: string;
  message: string;
  sessionGroup: "current" | "previous" | "older";
  traceId?: string;
  metadata?: DiagnosticLogEntry["metadata"];
}

const mockLogDefinitions: MockLogDefinition[] = [
  {
    id: "log-demo-001",
    minutesAgo: 2,
    severity: "INFO",
    service: "gateway-service",
    taskId: "task-demo-gateway-01",
    source: "RequestRouter",
    message: "Diagnostic health route completed successfully.",
    sessionGroup: "current",
    traceId: "trace-demo-7fa21",
    metadata: { route: "/health", statusCode: 200, durationMs: 18 },
  },
  {
    id: "log-demo-002",
    minutesAgo: 3,
    severity: "DEBUG",
    service: "catalog-service",
    taskId: "task-demo-catalog-02",
    source: "DependencyProbe",
    message: "Dependency probe started for the catalog read path.",
    sessionGroup: "current",
    metadata: { probe: "catalog-read", attempt: 1 },
  },
  {
    id: "log-demo-003",
    minutesAgo: 5,
    severity: "WARN",
    service: "worker-service",
    taskId: "task-demo-worker-01",
    source: "QueueConsumer",
    message: "Queue acknowledgement took longer than the demo threshold.",
    sessionGroup: "current",
    traceId: "trace-demo-184bc",
    metadata: { queue: "demo-events", durationMs: 940 },
  },
  {
    id: "log-demo-004",
    minutesAgo: 8,
    severity: "ERROR",
    service: "catalog-service",
    taskId: "task-demo-catalog-02",
    source: "DatabaseHealthCheck",
    message: "Simulated database health check timed out; no production system was contacted.",
    sessionGroup: "current",
    traceId: "trace-demo-82d11",
    metadata: { check: "read-only-health", timeoutMs: 1200, simulated: true },
  },
  {
    id: "log-demo-005",
    minutesAgo: 12,
    severity: "INFO",
    service: "worker-service",
    taskId: "task-demo-worker-02",
    source: "TaskMonitor",
    message: "Worker task reported ready for the diagnostic sample.",
    sessionGroup: "current",
    metadata: { health: "healthy", sample: true },
  },
  {
    id: "log-demo-006",
    minutesAgo: 18,
    severity: "DEBUG",
    service: "gateway-service",
    taskId: "task-demo-gateway-02",
    source: "ConnectionPool",
    message: "Connection pool sample recorded with two idle connections.",
    sessionGroup: "current",
    metadata: { idleConnections: 2, activeConnections: 4 },
  },
  {
    id: "log-demo-007",
    minutesAgo: 26,
    severity: "WARN",
    service: "billing-service",
    taskId: "task-demo-billing-01",
    source: "RetryPolicy",
    message: "A simulated downstream retry was scheduled after a transient response.",
    sessionGroup: "previous",
    traceId: "trace-demo-3c0aa",
    metadata: { retry: 2, backoffMs: 250 },
  },
  {
    id: "log-demo-008",
    minutesAgo: 34,
    severity: "INFO",
    service: "catalog-service",
    taskId: "task-demo-catalog-01",
    source: "CacheAdapter",
    message: "Mock cache lookup completed with a miss.",
    sessionGroup: "previous",
    metadata: { cache: "demo-catalog", result: "miss" },
  },
  {
    id: "log-demo-009",
    minutesAgo: 43,
    severity: "ERROR",
    service: "billing-service",
    taskId: "task-demo-billing-01",
    source: "InvoiceWorker",
    message: "An illustrative invoice job failed validation and was not submitted.",
    sessionGroup: "previous",
    traceId: "trace-demo-55d2e",
    metadata: { validation: "demo-only", submitted: false },
  },
  {
    id: "log-demo-010",
    minutesAgo: 51,
    severity: "DEBUG",
    service: "gateway-service",
    taskId: "task-demo-gateway-01",
    source: "HeaderNormalizer",
    message: "Normalized three non-sensitive demo request headers.",
    sessionGroup: "older",
    metadata: { headerCount: 3 },
  },
  {
    id: "log-demo-011",
    minutesAgo: 67,
    severity: "INFO",
    service: "worker-service",
    taskId: "task-demo-worker-01",
    source: "Scheduler",
    message: "The scheduled mock worker cycle completed.",
    sessionGroup: "older",
    metadata: { cycle: "demo-cycle-14", completed: true },
  },
  {
    id: "log-demo-012",
    minutesAgo: 91,
    severity: "WARN",
    service: "catalog-service",
    taskId: "task-demo-catalog-02",
    source: "ResponseCache",
    message: "A mock cache entry was skipped because its sample age exceeded the limit.",
    sessionGroup: "older",
    metadata: { sampleAgeSeconds: 481 },
  },
];

const demonstrationSessionIds = {
  current: "dcc-demo-session-current",
  previous: "dcc-demo-session-previous",
  older: "dcc-demo-session-older",
} as const;

export function createMockLogs(currentSessionId: string | null): DiagnosticLogEntry[] {
  const now = Date.now();

  return mockLogDefinitions.map((definition) => ({
    id: definition.id,
    timestamp: new Date(now - definition.minutesAgo * 60_000).toISOString(),
    severity: definition.severity,
    service: definition.service,
    taskId: definition.taskId,
    source: definition.source,
    message: definition.message,
    diagnosticSessionId: definition.sessionGroup === "current" && currentSessionId
      ? currentSessionId
      : demonstrationSessionIds[definition.sessionGroup],
    ...(definition.traceId ? { traceId: definition.traceId } : {}),
    ...(definition.metadata ? { metadata: definition.metadata } : {}),
  }));
}
