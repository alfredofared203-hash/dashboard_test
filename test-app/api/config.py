from dataclasses import dataclass
from functools import lru_cache
import os
from urllib.parse import urlparse


HARD_MAX_CPU_WORK_MS = 5_000
HARD_MAX_LATENCY_MS = 5_000
HARD_MAX_MEMORY_MB = 64
HARD_MAX_WORKER_INTERVAL_SECONDS = 300
HARD_MAX_REQUEST_TIMEOUT_MS = 30_000


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw_value = os.environ.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _validate_url(name: str, value: str, schemes: set[str]) -> None:
    if not value:
        return
    parsed = urlparse(value)
    try:
        parsed.port
    except ValueError as error:
        raise ValueError(f"{name} must be a valid URL.") from error
    if (
        parsed.scheme not in schemes
        or not parsed.hostname
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{name} must be a valid connection URL.")


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    environment: str
    log_level: str
    service_name: str
    host: str
    port: int
    request_timeout_ms: int
    database_url: str
    redis_url: str
    worker_enabled: bool
    worker_interval_seconds: int
    worker_metrics_port: int
    max_cpu_work_ms: int
    max_latency_ms: int
    max_memory_mb: int

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.environ.get("DATABASE_URL", "").strip()
        redis_url = os.environ.get("REDIS_URL", "").strip()
        _validate_url("DATABASE_URL", database_url, {"postgres", "postgresql"})
        _validate_url("REDIS_URL", redis_url, {"redis", "rediss"})

        worker_enabled_value = os.environ.get("WORKER_ENABLED", "false").strip().lower()
        if worker_enabled_value not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError("WORKER_ENABLED must be a boolean value.")
        log_level = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be a supported logging level.")

        return cls(
            app_name=os.environ.get("APP_NAME", "standalone-test-laboratory").strip(),
            app_version=os.environ.get("APP_VERSION", "0.1.0").strip(),
            environment=os.environ.get("ENVIRONMENT", "local").strip(),
            log_level=log_level,
            service_name=os.environ.get("SERVICE_NAME", "api-service").strip(),
            host=os.environ.get("HOST", "0.0.0.0").strip(),
            port=_bounded_int("PORT", 8080, 1, 65_535),
            request_timeout_ms=_bounded_int(
                "REQUEST_TIMEOUT_MS",
                3_000,
                1,
                HARD_MAX_REQUEST_TIMEOUT_MS,
            ),
            database_url=database_url,
            redis_url=redis_url,
            worker_enabled=worker_enabled_value in {"true", "1", "yes"},
            worker_interval_seconds=_bounded_int(
                "WORKER_INTERVAL_SECONDS",
                10,
                1,
                HARD_MAX_WORKER_INTERVAL_SECONDS,
            ),
            worker_metrics_port=_bounded_int("WORKER_METRICS_PORT", 9101, 1, 65_535),
            max_cpu_work_ms=_bounded_int(
                "MAX_CPU_WORK_MS",
                1_000,
                1,
                HARD_MAX_CPU_WORK_MS,
            ),
            max_latency_ms=_bounded_int(
                "MAX_LATENCY_MS",
                1_000,
                1,
                HARD_MAX_LATENCY_MS,
            ),
            max_memory_mb=_bounded_int(
                "MAX_MEMORY_MB",
                32,
                1,
                HARD_MAX_MEMORY_MB,
            ),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_environment()
