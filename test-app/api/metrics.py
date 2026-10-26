from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests handled by the test application.",
    ("service", "method", "route", "status_class"),
    registry=REGISTRY,
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("service", "method", "route"),
    registry=REGISTRY,
)
HTTP_ERRORS = Counter(
    "http_errors_total",
    "HTTP error responses produced by the test application.",
    ("service", "route", "error_type"),
    registry=REGISTRY,
)
WORKLOAD_EXECUTIONS = Counter(
    "workload_executions_total",
    "Bounded workload executions.",
    ("service", "workload", "result"),
    registry=REGISTRY,
)
WORKLOAD_DURATION = Histogram(
    "workload_duration_seconds",
    "Duration of bounded workloads.",
    ("service", "workload"),
    registry=REGISTRY,
)
DATABASE_OPERATIONS = Counter(
    "database_operations_total",
    "PostgreSQL operations by result.",
    ("service", "operation", "result"),
    registry=REGISTRY,
)
DATABASE_OPERATION_DURATION = Histogram(
    "database_operation_duration_seconds",
    "PostgreSQL operation duration in seconds.",
    ("service", "operation"),
    registry=REGISTRY,
)
REDIS_OPERATIONS = Counter(
    "redis_operations_total",
    "Redis operations by result.",
    ("service", "operation", "result"),
    registry=REGISTRY,
)
REDIS_OPERATION_DURATION = Histogram(
    "redis_operation_duration_seconds",
    "Redis operation duration in seconds.",
    ("service", "operation"),
    registry=REGISTRY,
)
INTENTIONAL_ERRORS = Counter(
    "intentional_errors_total",
    "Controlled intentional error responses.",
    ("service",),
    registry=REGISTRY,
)
WORKER_JOBS = Counter(
    "worker_jobs_total",
    "Background worker jobs by result.",
    ("service", "result"),
    registry=REGISTRY,
)
WORKER_JOB_DURATION = Histogram(
    "worker_job_duration_seconds",
    "Background worker job duration in seconds.",
    ("service",),
    registry=REGISTRY,
)
WORKER_ERRORS = Counter(
    "worker_errors_total",
    "Background worker dependency failures.",
    ("service", "dependency"),
    registry=REGISTRY,
)
APP_INFO = Gauge(
    "application_info",
    "Application build and environment information.",
    ("service", "version", "environment"),
    registry=REGISTRY,
)


def record_request(
    *,
    service: str,
    method: str,
    route: str,
    status_code: int,
    elapsed_seconds: float,
) -> None:
    status_class = f"{status_code // 100}xx"
    HTTP_REQUESTS.labels(service, method, route, status_class).inc()
    HTTP_REQUEST_DURATION.labels(service, method, route).observe(elapsed_seconds)
    if status_code >= 400:
        error_type = "intentional" if route == "/api/work/error" else status_class
        HTTP_ERRORS.labels(service, route, error_type).inc()
