from contextlib import contextmanager
from http import HTTPStatus
import logging
import threading
import time
from typing import Iterator
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StrictInt

from api.config import get_settings
from api.dependencies import DependencyUnavailable
from api.logging_config import log_event
from api.metrics import INTENTIONAL_ERRORS, WORKLOAD_DURATION, WORKLOAD_EXECUTIONS
from api.services.database_service import list_products
from api.services.redis_service import increment_counter
from api.services.workload_service import cpu_work, latency_work, memory_work


router = APIRouter(prefix="/api/work")
logger = logging.getLogger(__name__)
_ACTIVE_WORKLOADS = threading.BoundedSemaphore(2)


class CPUWorkRequest(BaseModel):
    duration_ms: StrictInt = Field(ge=1, le=5_000)


class LatencyWorkRequest(BaseModel):
    delay_ms: StrictInt = Field(ge=1, le=5_000)


class MixedWorkRequest(BaseModel):
    cpu_ms: StrictInt = Field(default=100, ge=1, le=1_000)
    delay_ms: StrictInt = Field(default=100, ge=1, le=1_000)


class MemoryWorkRequest(BaseModel):
    megabytes: StrictInt = Field(ge=1, le=64)
    duration_ms: StrictInt = Field(default=500, ge=1, le=5_000)


@contextmanager
def measure_workload(workload: str) -> Iterator[str]:
    settings = get_settings()
    run_id = str(uuid4())
    started = time.perf_counter()
    result = "success"
    try:
        yield run_id
    except Exception:
        result = "error"
        WORKLOAD_EXECUTIONS.labels(settings.service_name, workload, "error").inc()
        raise
    finally:
        elapsed = time.perf_counter() - started
        WORKLOAD_DURATION.labels(settings.service_name, workload).observe(elapsed)
        if result == "success":
            WORKLOAD_EXECUTIONS.labels(settings.service_name, workload, "success").inc()
        log_event(
            logger,
            logging.INFO if result == "success" else logging.WARNING,
            "workload_completed",
            service=settings.service_name,
            workload=workload,
            duration_ms=elapsed * 1000,
            status=result,
            run_id=run_id,
        )


@contextmanager
def workload_slot(workload: str) -> Iterator[None]:
    if not _ACTIVE_WORKLOADS.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The workload concurrency limit has been reached.",
        )
    try:
        with measure_workload(workload):
            yield
    finally:
        _ACTIVE_WORKLOADS.release()


def _configured_limit(value: int, maximum: int, name: str) -> None:
    if value > maximum:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f"{name} exceeds the configured maximum of {maximum}.",
        )


@router.post("/cpu")
def cpu_workload(payload: CPUWorkRequest) -> dict[str, object]:
    settings = get_settings()
    _configured_limit(payload.duration_ms, settings.max_cpu_work_ms, "duration_ms")
    with workload_slot("cpu"):
        actual_duration = cpu_work(payload.duration_ms)
    return {"workload": "cpu", "duration_ms": actual_duration}


@router.post("/latency")
def latency_workload(payload: LatencyWorkRequest) -> dict[str, object]:
    settings = get_settings()
    _configured_limit(payload.delay_ms, settings.max_latency_ms, "delay_ms")
    with workload_slot("latency"):
        actual_duration = latency_work(payload.delay_ms)
    return {"workload": "latency", "duration_ms": actual_duration}


@router.post("/memory")
def memory_workload(payload: MemoryWorkRequest) -> dict[str, object]:
    settings = get_settings()
    _configured_limit(payload.megabytes, settings.max_memory_mb, "megabytes")
    _configured_limit(payload.duration_ms, settings.max_latency_ms, "duration_ms")
    with workload_slot("memory"):
        allocated_bytes, actual_duration = memory_work(
            payload.megabytes,
            payload.duration_ms,
        )
    return {
        "workload": "memory",
        "allocated_bytes": allocated_bytes,
        "duration_ms": actual_duration,
    }


@router.post("/mixed")
def mixed_workload(payload: MixedWorkRequest) -> dict[str, object]:
    settings = get_settings()
    _configured_limit(payload.cpu_ms, settings.max_cpu_work_ms, "cpu_ms")
    _configured_limit(payload.delay_ms, settings.max_latency_ms, "delay_ms")
    with workload_slot("mixed"):
        cpu_duration = cpu_work(payload.cpu_ms)
        delay_duration = latency_work(payload.delay_ms)
        try:
            products = list_products(1)
            database_status = "executed"
        except DependencyUnavailable:
            products = []
            database_status = "unavailable"
        try:
            counter = increment_counter()
            redis_status = "executed"
        except DependencyUnavailable:
            counter = None
            redis_status = "unavailable"
    return {
        "workload": "mixed",
        "components": {
            "cpu": {"status": "executed", "duration_ms": cpu_duration},
            "latency": {"status": "executed", "duration_ms": delay_duration},
            "postgresql": {
                "status": database_status,
                "rows_read": len(products),
            },
            "redis": {"status": redis_status, "counter": counter},
        },
    }


@router.get("/error")
def intentional_error() -> None:
    service = get_settings().service_name
    INTENTIONAL_ERRORS.labels(service).inc()
    log_event(
        logger,
        logging.WARNING,
        "intentional_test_error",
        service=service,
        workload="intentional_error",
        status="error",
        error_type="intentional",
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Intentional test error.",
    )
