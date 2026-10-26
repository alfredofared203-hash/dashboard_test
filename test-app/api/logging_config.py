from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import socket
from typing import Any

from api.config import get_settings


request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
_EXTRA_FIELDS = (
    "event",
    "operation",
    "duration_ms",
    "status",
    "error_type",
    "workload",
    "job",
    "run_id",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        settings = get_settings()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", settings.service_name),
            "version": settings.app_version,
            "environment": settings.environment,
            "event": getattr(record, "event", record.getMessage()),
            "request_id": getattr(record, "request_id", request_id_context.get()),
            "hostname": socket.gethostname(),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def configure_logging() -> None:
    root = logging.getLogger()
    settings = get_settings()
    if getattr(root, "_standalone_test_logging", False):
        root.setLevel(settings.log_level)
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(settings.log_level)
        root._standalone_test_logging = True

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    service: str,
    operation: str | None = None,
    duration_ms: float | None = None,
    status: str | None = None,
    error_type: str | None = None,
    workload: str | None = None,
    job: str | None = None,
    run_id: str | None = None,
) -> None:
    logger.log(
        level,
        event,
        extra={
            "service": service,
            "event": event,
            "request_id": request_id_context.get(),
            "operation": operation,
            "duration_ms": duration_ms,
            "status": status,
            "error_type": error_type,
            "workload": workload,
            "job": job,
            "run_id": run_id,
        },
    )
