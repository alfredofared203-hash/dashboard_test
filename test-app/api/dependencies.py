from functools import lru_cache
import logging
import math
import time

import psycopg
from psycopg import Error as PostgreSQLError
from redis import Redis
from api.config import get_settings
from api.logging_config import log_event
from api.metrics import (
    DATABASE_OPERATION_DURATION,
    DATABASE_OPERATIONS,
    REDIS_OPERATION_DURATION,
    REDIS_OPERATIONS,
)


logger = logging.getLogger(__name__)


class DependencyUnavailable(Exception):
    def __init__(self, dependency: str) -> None:
        self.dependency = dependency
        super().__init__(f"{dependency} is unavailable.")


def _timeout_seconds() -> float:
    return max(0.1, get_settings().request_timeout_ms / 1000)


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    settings = get_settings()
    if not settings.redis_url:
        raise DependencyUnavailable("redis")
    timeout = _timeout_seconds()
    return Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=timeout,
        socket_timeout=timeout,
        decode_responses=True,
    )


def database_connection():
    settings = get_settings()
    if not settings.database_url:
        raise DependencyUnavailable("postgres")
    timeout_seconds = max(1, math.ceil(settings.request_timeout_ms / 1000))
    try:
        return psycopg.connect(
            settings.database_url,
            connect_timeout=timeout_seconds,
            options=f"-c statement_timeout={settings.request_timeout_ms}",
        )
    except (PostgreSQLError, OSError, TimeoutError):
        raise DependencyUnavailable("postgres") from None


def timed_database_operation(operation: str, callback):
    service = get_settings().service_name
    started = time.perf_counter()
    try:
        result = callback()
    except DependencyUnavailable:
        DATABASE_OPERATIONS.labels(service, operation, "error").inc()
        log_event(
            logger,
            logging.WARNING,
            "database_operation_failed",
            service=service,
            operation=operation,
            duration_ms=(time.perf_counter() - started) * 1000,
            status="unavailable",
            error_type="DependencyUnavailable",
        )
        raise
    except (PostgreSQLError, OSError, TimeoutError):
        DATABASE_OPERATIONS.labels(service, operation, "error").inc()
        log_event(
            logger,
            logging.WARNING,
            "database_operation_failed",
            service=service,
            operation=operation,
            duration_ms=(time.perf_counter() - started) * 1000,
            status="unavailable",
            error_type="PostgreSQLError",
        )
        raise DependencyUnavailable("postgres") from None
    duration = time.perf_counter() - started
    DATABASE_OPERATIONS.labels(service, operation, "success").inc()
    DATABASE_OPERATION_DURATION.labels(service, operation).observe(duration)
    log_event(
        logger,
        logging.INFO,
        "database_operation_completed",
        service=service,
        operation=operation,
        duration_ms=duration * 1000,
        status="success",
    )
    return result


def timed_redis_operation(operation: str, callback):
    service = get_settings().service_name
    started = time.perf_counter()
    try:
        result = callback()
    except DependencyUnavailable:
        REDIS_OPERATIONS.labels(service, operation, "error").inc()
        log_event(
            logger,
            logging.WARNING,
            "redis_operation_failed",
            service=service,
            operation=operation,
            duration_ms=(time.perf_counter() - started) * 1000,
            status="unavailable",
            error_type="DependencyUnavailable",
        )
        raise
    except (RedisError, OSError, TimeoutError):
        REDIS_OPERATIONS.labels(service, operation, "error").inc()
        log_event(
            logger,
            logging.WARNING,
            "redis_operation_failed",
            service=service,
            operation=operation,
            duration_ms=(time.perf_counter() - started) * 1000,
            status="unavailable",
            error_type="RedisError",
        )
        raise DependencyUnavailable("redis") from None
    duration = time.perf_counter() - started
    REDIS_OPERATIONS.labels(service, operation, "success").inc()
    REDIS_OPERATION_DURATION.labels(service, operation).observe(duration)
    log_event(
        logger,
        logging.INFO,
        "redis_operation_completed",
        service=service,
        operation=operation,
        duration_ms=duration * 1000,
        status="success",
    )
    return result


def dependency_status(name: str) -> dict[str, str]:
    settings = get_settings()
    if name == "postgres":
        if not settings.database_url:
            return {"status": "not_configured"}
        probe = lambda: timed_database_operation(
            "readiness",
            _probe_database,
        )
    else:
        if not settings.redis_url:
            return {"status": "not_configured"}
        probe = lambda: timed_redis_operation(
            "readiness",
            lambda: get_redis_client().ping(),
        )
    try:
        probe()
    except DependencyUnavailable:
        return {"status": "unavailable"}
    return {"status": "available"}


def _probe_database() -> None:
    with database_connection() as connection:
        connection.execute("SELECT 1").fetchone()
