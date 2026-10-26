import json
import os
import platform
import socket
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter

from api.config import get_settings
from api.dependencies import dependency_status


router = APIRouter(prefix="/api/diagnostics")
METADATA_TIMEOUT_SECONDS = 0.3
MAX_METADATA_BYTES = 65_536


def _ecs_task_identity() -> tuple[str | None, str | None]:
    metadata_uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4", "")
    parsed = urlparse(metadata_uri)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "169.254.170.2"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None, None
    request = Request(
        f"{metadata_uri.rstrip('/')}/task",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=METADATA_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_METADATA_BYTES + 1)
        if len(body) > MAX_METADATA_BYTES:
            return None, None
        payload = json.loads(body)
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    task_arn = payload.get("TaskARN")
    service_name = payload.get("ServiceName")
    task_id = task_arn.rsplit("/", 1)[-1] if isinstance(task_arn, str) else None
    if task_id == task_arn or not task_id or len(task_id) > 128:
        task_id = None
    if not isinstance(service_name, str) or len(service_name) > 128:
        service_name = None
    return task_id, service_name


@router.get("/info")
def diagnostics_info() -> dict[str, object]:
    settings = get_settings()
    task_id, ecs_service_name = _ecs_task_identity()
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "service": settings.service_name,
        "hostname": socket.gethostname(),
        "process_id": os.getpid(),
        "python_version": platform.python_version(),
        "task_id": task_id,
        "ecs_service_name": ecs_service_name,
        "dependencies": {
            "postgresql": dependency_status("postgres"),
            "redis": dependency_status("redis"),
        },
    }
