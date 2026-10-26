from contextlib import asynccontextmanager
import logging
import time
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from api.config import get_settings
from api.logging_config import (
    configure_logging,
    log_event,
    request_id_context,
)
from api.metrics import APP_INFO, REGISTRY, record_request
from api.middleware.request_id import RequestIdMiddleware
from api.routes.database import router as database_router
from api.routes.diagnostics import router as diagnostics_router
from api.routes.health import router as health_router
from api.routes.redis import router as redis_router
from api.routes.workload import router as workload_router


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    APP_INFO.labels(
        settings.service_name,
        settings.app_version,
        settings.environment,
    ).set(1)
    yield


app = FastAPI(
    title=get_settings().app_name,
    version=get_settings().app_version,
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)
app.include_router(health_router)
app.include_router(database_router)
app.include_router(redis_router)
app.include_router(workload_router)
app.include_router(diagnostics_router)


@app.middleware("http")
async def request_metrics(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as error:
        log_event(
            logger,
            logging.ERROR,
            "unhandled_request_error",
            service=get_settings().service_name,
            operation=request.method,
            status="error",
            error_type=type(error).__name__,
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
        )
    finally:
        route = request.scope.get("route")
        route_path = getattr(route, "path", None) or "/unmatched"
        elapsed = time.perf_counter() - started
        request_id = getattr(response, "headers", {}).get("X-Request-ID", "-")
        token = request_id_context.set(request_id)
        record_request(
            service=get_settings().service_name,
            method=request.method,
            route=route_path,
            status_code=status_code,
            elapsed_seconds=elapsed,
        )
        log_event(
            logger,
            logging.INFO if status_code < 400 else logging.WARNING,
            "http_request_completed",
            service=get_settings().service_name,
            operation=f"{request.method} {route_path}",
            duration_ms=elapsed * 1000,
            status=str(status_code),
        )
        request_id_context.reset(token)
    return response


@app.exception_handler(Exception)
async def unexpected_exception_handler(_: Request, error: Exception) -> JSONResponse:
    log_event(
        logger,
        logging.ERROR,
        "unhandled_application_error",
        service=get_settings().service_name,
        status="error",
        error_type=type(error).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
