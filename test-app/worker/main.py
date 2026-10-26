import logging
import signal
from threading import Event

from prometheus_client import start_http_server

from api.config import get_settings
from api.logging_config import configure_logging, log_event
from api.metrics import REGISTRY
from worker.worker_service import run_cycle


configure_logging()
logger = logging.getLogger(__name__)
stop_event = Event()


def _request_stop(_: int, __: object) -> None:
    stop_event.set()


def main() -> None:
    settings = get_settings()
    if not settings.worker_enabled:
        log_event(
            logger,
            logging.INFO,
            "worker_disabled",
            service=settings.service_name,
            status="disabled",
        )
        return

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)
    start_http_server(
        settings.worker_metrics_port,
        addr="0.0.0.0",
        registry=REGISTRY,
    )
    log_event(
        logger,
        logging.INFO,
        "worker_started",
        service=settings.service_name,
        job="dependency_heartbeat",
        status="running",
    )
    while not stop_event.is_set():
        run_cycle()
        stop_event.wait(settings.worker_interval_seconds)
    log_event(
        logger,
        logging.INFO,
        "worker_stopped",
        service=settings.service_name,
        status="stopped",
    )


if __name__ == "__main__":
    main()
