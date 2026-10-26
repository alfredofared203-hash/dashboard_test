import logging
import time
from typing import Callable

from api.config import get_settings
from api.dependencies import DependencyUnavailable
from api.logging_config import log_event
from api.metrics import WORKER_ERRORS, WORKER_JOB_DURATION, WORKER_JOBS
from api.services.database_service import readiness_database_probe
from api.services.redis_service import worker_heartbeat


logger = logging.getLogger(__name__)
MAX_RETRIES = 3
MAX_BACKOFF_SECONDS = 4


def _retry(operation: str, callback: Callable[[], object]) -> bool:
    settings = get_settings()
    for attempt in range(MAX_RETRIES):
        try:
            callback()
            return True
        except DependencyUnavailable as error:
            if attempt + 1 < MAX_RETRIES:
                time.sleep(min(2**attempt, MAX_BACKOFF_SECONDS))
            else:
                WORKER_ERRORS.labels(settings.service_name, operation).inc()
                log_event(
                    logger,
                    logging.WARNING,
                    "worker_dependency_unavailable",
                    service=settings.service_name,
                    operation=operation,
                    status="unavailable",
                    error_type=type(error).__name__,
                )
    return False


def run_cycle() -> bool:
    settings = get_settings()
    started = time.perf_counter()
    database_ok = _retry("postgresql", readiness_database_probe)
    redis_ok = _retry("redis", worker_heartbeat)
    success = database_ok and redis_ok
    elapsed = time.perf_counter() - started
    WORKER_JOBS.labels(
        settings.service_name,
        "success" if success else "partial_failure",
    ).inc()
    WORKER_JOB_DURATION.labels(settings.service_name).observe(elapsed)
    log_event(
        logger,
        logging.INFO if success else logging.WARNING,
        "worker_cycle_completed",
        service=settings.service_name,
        job="dependency_heartbeat",
        duration_ms=elapsed * 1000,
        status="success" if success else "partial_failure",
    )
    return success
