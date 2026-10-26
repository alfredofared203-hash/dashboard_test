from typing import Any

from apps.api.ecs_discovery import get_ecs_discovery_provider

def get_services() -> list[dict[str, Any]]:
    provider = get_ecs_discovery_provider()
    services = [
        service
        for cluster in provider.list_clusters()
        for service in provider.list_services(cluster["cluster_arn"])
    ]
    return [
        {
            "id": service["service_arn"],
            "name": service["service_name"],
            "status": (
                "unknown"
                if service["running_count"] is None or service["desired_count"] is None
                else "healthy"
                if service["running_count"] >= service["desired_count"]
                else "warning"
                if service["running_count"] > 0
                else "critical"
            ),
        }
        for service in services
    ]


def get_tasks() -> list[dict[str, Any]]:
    provider = get_ecs_discovery_provider()
    return [
        {
            "id": task["task_id"],
            "service_id": task["service_arn"] or task["service_name"] or "standalone",
            "name": task["task_definition_family"],
            "status": task["last_status"].lower(),
            "health": (
                "healthy"
                if task["health_status"] == "HEALTHY"
                else "unknown"
                if task["health_status"] in {"UNKNOWN", "NONE"}
                else "warning"
            ),
            "desired_count": task["desired_count"],
            "current_count": task["current_count"],
            "availability": (
                "available" if task["last_status"] == "RUNNING" else "unavailable"
            ),
        }
        for task in provider.list_all_running_tasks()
    ]


def get_task_resources(task_id: str) -> dict[str, Any] | None:
    task_ids = {task["id"] for task in get_tasks()}
    if task_id not in task_ids:
        return None
    return {
        "task_id": task_id,
        "cpu": {"baseline": 20, "current": 24, "peak": 31, "unit": "percent"},
        "memory": {"baseline": 40, "current": 44, "peak": 51, "unit": "percent"},
        "network": {"baseline": 100, "current": 112, "peak": 140, "unit": "mbps"},
        "impact": {
            "status": "warning",
            "cpu_delta": 4,
            "memory_delta": 4,
            "network_delta": 12,
        },
    }


def get_logs() -> list[dict[str, Any]]:
    return [
        {
            "id": "log-001",
            "timestamp": "2026-01-01T10:00:00Z",
            "severity": "INFO",
            "service": "Orders Service",
            "task_id": "task-001",
            "source": "orders-worker",
            "message": "Worker started successfully.",
            "diagnostic_session_id": "session-001",
            "trace_id": "trace-demo-001",
            "metadata": {"attempt": 1, "mock": True},
        },
        {
            "id": "log-002",
            "timestamp": "2026-01-01T10:00:21Z",
            "severity": "WARN",
            "service": "Payments Service",
            "task_id": "task-002",
            "source": "payments-worker",
            "message": "Payment provider response exceeded the sample threshold.",
            "diagnostic_session_id": "session-001",
            "trace_id": None,
            "metadata": {"duration_ms": 840, "mock": True},
        },
        {
            "id": "log-003",
            "timestamp": "2026-01-01T10:00:42Z",
            "severity": "ERROR",
            "service": "Payments Service",
            "task_id": "task-002",
            "source": "payments-worker",
            "message": "Sample retry limit reached; no live request was made.",
            "diagnostic_session_id": "session-001",
            "trace_id": "trace-demo-003",
            "metadata": {"retries": 3, "mock": True},
        },
    ]
