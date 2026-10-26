import logging
from dataclasses import replace
import json

from fastapi.testclient import TestClient

from api import dependencies
from api.config import Settings, get_settings
from api.main import app


def test_health_does_not_probe_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.routes.health.dependency_status",
        lambda _: (_ for _ in ()).throw(AssertionError("unexpected dependency probe")),
    )
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_reports_dependencies_individually(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.routes.health.dependency_status",
        lambda name: {"status": "unavailable" if name == "redis" else "available"},
    )
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["dependencies"] == {
        "postgresql": {"status": "available"},
        "redis": {"status": "unavailable"},
    }


def test_readiness_identifies_unconfigured_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.routes.health.dependency_status",
        lambda _: {"status": "not_configured"},
    )
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["dependencies"] == {
        "postgresql": {"status": "not_configured"},
        "redis": {"status": "not_configured"},
    }


def test_request_id_is_generated() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 36


def test_request_id_is_propagated_and_invalid_value_replaced() -> None:
    client = TestClient(app)
    valid = client.get("/health", headers={"X-Request-ID": "lab-run-123"})
    invalid = client.get("/health", headers={"X-Request-ID": "bad value"})
    assert valid.headers["X-Request-ID"] == "lab-run-123"
    assert invalid.headers["X-Request-ID"] != "bad value"


def test_uvicorn_loggers_use_json_root_handler() -> None:
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        assert logger.propagate
        assert not logger.handlers


def test_http_log_uses_returned_request_id(caplog) -> None:
    response = TestClient(app).get("/health")
    request_logs = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "http_request_completed"
    ]
    assert request_logs[-1].request_id == response.headers["X-Request-ID"]


def test_metrics_endpoint_is_available() -> None:
    response = TestClient(app).get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "workload_executions_total" in response.text
    assert response.headers["content-type"].startswith("text/plain")


def test_diagnostics_response_contains_no_connection_strings(monkeypatch) -> None:
    monkeypatch.setattr("api.routes.diagnostics._ecs_task_identity", lambda: (None, None))
    monkeypatch.setattr(
        "api.routes.diagnostics.dependency_status",
        lambda _: {"status": "not_configured"},
    )
    response = TestClient(app).get("/api/diagnostics/info")
    body = json.dumps(response.json())
    assert response.status_code == 200
    assert response.json()["task_id"] is None
    assert "DATABASE_URL" not in body
    assert "REDIS_URL" not in body


def test_cpu_limit_is_enforced(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.routes.workload.get_settings",
        lambda: replace(get_settings(), max_cpu_work_ms=50),
    )
    response = TestClient(app).post("/api/work/cpu", json={"duration_ms": 51})
    assert response.status_code == 422


def test_latency_limit_is_enforced(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.routes.workload.get_settings",
        lambda: replace(get_settings(), max_latency_ms=25),
    )
    response = TestClient(app).post("/api/work/latency", json={"delay_ms": 26})
    assert response.status_code == 422


def test_memory_limit_is_enforced(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.routes.workload.get_settings",
        lambda: replace(get_settings(), max_memory_mb=2),
    )
    response = TestClient(app).post(
        "/api/work/memory",
        json={"megabytes": 3, "duration_ms": 10},
    )
    assert response.status_code == 422


def test_intentional_error_is_safe_and_counted() -> None:
    client = TestClient(app)
    response = client.get("/api/work/error")
    assert response.status_code == 500
    assert response.json() == {"detail": "Intentional test error."}
    assert "intentional_errors_total" in client.get("/metrics").text


def test_database_failure_returns_safe_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.routes.database.list_products",
        lambda _: (_ for _ in ()).throw(dependencies.DependencyUnavailable("postgres")),
    )
    response = TestClient(app).get("/api/products")
    assert response.status_code == 503
    assert response.json()["detail"] == "PostgreSQL is currently unavailable."


def test_redis_failure_returns_safe_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.routes.redis.get_value",
        lambda: (_ for _ in ()).throw(dependencies.DependencyUnavailable("redis")),
    )
    response = TestClient(app).get("/api/redis")
    assert response.status_code == 503
    assert response.json()["detail"] == "Redis is currently unavailable."


def test_configuration_rejects_invalid_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "http://invalid.example")
    try:
        Settings.from_environment()
    except ValueError as error:
        assert "DATABASE_URL" in str(error)
    else:
        raise AssertionError("invalid DATABASE_URL should be rejected")


def test_configuration_accepts_database_and_redis_credentials(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://test_user:test_password@localhost:5432/test_lab",
    )
    monkeypatch.setenv(
        "REDIS_URL",
        "redis://test_user:test_password@localhost:6379/0",
    )
    settings = Settings.from_environment()
    assert settings.database_url.startswith("postgresql://")
    assert settings.redis_url.startswith("redis://")


def test_configuration_rejects_workload_limit_above_hard_max(monkeypatch) -> None:
    monkeypatch.setenv("MAX_MEMORY_MB", "65")
    try:
        Settings.from_environment()
    except ValueError as error:
        assert "MAX_MEMORY_MB" in str(error)
    else:
        raise AssertionError("unsafe memory limit should be rejected")


def test_cpu_and_latency_workloads_return_execution_data() -> None:
    client = TestClient(app)
    cpu_response = client.post("/api/work/cpu", json={"duration_ms": 1})
    latency_response = client.post("/api/work/latency", json={"delay_ms": 1})
    assert cpu_response.status_code == 200
    assert cpu_response.json()["workload"] == "cpu"
    assert latency_response.status_code == 200
    assert latency_response.json()["workload"] == "latency"


def test_workload_rejects_boolean_duration() -> None:
    response = TestClient(app).post("/api/work/cpu", json={"duration_ms": True})
    assert response.status_code == 422
