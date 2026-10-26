from dataclasses import replace

from api.config import get_settings
from api.dependencies import DependencyUnavailable
from worker import main as worker_main
from worker.worker_service import run_cycle


def test_disabled_worker_exits_without_starting_server(monkeypatch) -> None:
    monkeypatch.setattr(
        "worker.main.get_settings",
        lambda: replace(get_settings(), worker_enabled=False),
    )
    monkeypatch.setattr(
        "worker.main.start_http_server",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("disabled worker must not start metrics server")
        ),
    )
    worker_main.main()


def test_worker_retries_dependencies_with_bounded_backoff(monkeypatch) -> None:
    attempts = {"postgres": 0, "redis": 0}

    def failed_probe() -> None:
        attempts["postgres"] += 1
        raise DependencyUnavailable("postgres")

    def successful_redis() -> int:
        attempts["redis"] += 1
        return 1

    monkeypatch.setattr("worker.worker_service.readiness_database_probe", failed_probe)
    monkeypatch.setattr("worker.worker_service.worker_heartbeat", successful_redis)
    monkeypatch.setattr("worker.worker_service.time.sleep", lambda _: None)
    assert run_cycle() is False
    assert attempts == {"postgres": 3, "redis": 1}
