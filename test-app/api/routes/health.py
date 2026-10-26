from fastapi import APIRouter, HTTPException, status

from api.config import get_settings
from api.dependencies import dependency_status


router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "application": get_settings().app_name}


@router.get("/ready")
def ready() -> dict[str, object]:
    settings = get_settings()
    dependencies = {
        "postgresql": dependency_status("postgres"),
        "redis": dependency_status("redis"),
    }
    is_ready = all(
        dependency["status"] == "available"
        for dependency in dependencies.values()
    )
    result: dict[str, object] = {
        "status": "ready" if is_ready else "not_ready",
        "application": settings.app_name,
        "dependencies": dependencies,
    }
    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result,
        )
    return result
