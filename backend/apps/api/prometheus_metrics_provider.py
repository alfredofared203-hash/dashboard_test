from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
import json
import logging
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.api.metrics import MetricsProviderError
from apps.api.providers import get_tasks


logger = logging.getLogger(__name__)


METRIC_WINDOW = timedelta(minutes=15)
METRIC_STEP_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class PrometheusMetricsConfig:
    base_url: str

    @classmethod
    def from_settings(cls) -> "PrometheusMetricsConfig":
        base_url = settings.DCC_PROMETHEUS_URL.rstrip("/")
        try:
            parsed = urlparse(base_url)
            parsed.port
        except ValueError:
            raise ImproperlyConfigured("DCC_PROMETHEUS_URL is invalid.") from None
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ImproperlyConfigured("DCC_PROMETHEUS_URL is invalid.")
        return cls(base_url=base_url)


class PrometheusTaskMetricsProvider:
    name = "prometheus"

    def __init__(self, config: PrometheusMetricsConfig) -> None:
        self._config = config

    @classmethod
    def from_settings(cls) -> "PrometheusTaskMetricsProvider":
        return cls(PrometheusMetricsConfig.from_settings())

    @staticmethod
    def _prometheus_string(value: str) -> str:
        return json.dumps(value)

    def _query(self, expression: str) -> list[tuple[float, float]]:
        end = datetime.now(timezone.utc)
        params = urlencode(
            {
                "query": expression,
                "start": (end - METRIC_WINDOW).timestamp(),
                "end": end.timestamp(),
                "step": METRIC_STEP_SECONDS,
            }
        )
        endpoint = urljoin(f"{self._config.base_url}/", "api/v1/query_range")
        request = Request(
            f"{endpoint}?{params}",
            headers={"Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError:
            logger.warning("Prometheus metrics request returned an HTTP error.")
            raise MetricsProviderError(
                "Prometheus could not return task resource metrics."
            ) from None
        except (URLError, TimeoutError, OSError, HTTPException, ValueError):
            logger.warning("Prometheus metrics endpoint could not return a response.")
            raise MetricsProviderError(
                "Prometheus could not return task resource metrics."
            ) from None

        if len(body) > MAX_RESPONSE_BYTES:
            raise MetricsProviderError(
                "Prometheus returned an oversized task metrics response."
            )
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise MetricsProviderError(
                "Prometheus returned an invalid task metrics response."
            ) from None
        if (
            not isinstance(payload, dict)
            or payload.get("status") != "success"
            or not isinstance(payload.get("data"), dict)
            or payload["data"].get("resultType") != "matrix"
            or not isinstance(payload["data"].get("result"), list)
        ):
            raise MetricsProviderError(
                "Prometheus returned an invalid task metrics response."
            )

        values: list[tuple[float, float]] = []
        for series in payload["data"]["result"]:
            if not isinstance(series, dict) or not isinstance(series.get("values"), list):
                raise MetricsProviderError(
                    "Prometheus returned invalid task metric values."
                )
            for sample in series["values"]:
                if not isinstance(sample, list) or len(sample) != 2:
                    raise MetricsProviderError(
                        "Prometheus returned invalid task metric values."
                    )
                timestamp, raw_value = sample
                try:
                    timestamp_value = float(timestamp)
                    metric_value = float(raw_value)
                except (TypeError, ValueError):
                    raise MetricsProviderError(
                        "Prometheus returned invalid task metric values."
                    ) from None
                if not math.isfinite(timestamp_value) or not math.isfinite(metric_value):
                    raise MetricsProviderError(
                        "Prometheus returned invalid task metric values."
                    )
                values.append((timestamp_value, metric_value))

        return sorted(values)

    def _resource_metric(
        self,
        expression: str,
        *,
        unit: str,
    ) -> dict[str, float | str]:
        samples = self._query(expression)
        if not samples:
            raise MetricsProviderError(
                "Prometheus has no resource metrics available for the requested task."
            )
        metric_values = [value for _, value in samples]
        return {
            "baseline": metric_values[0],
            "current": metric_values[-1],
            "peak": max(metric_values),
            "unit": unit,
        }

    def get_task_resources(self, task_id: str) -> dict[str, Any] | None:
        if not any(task["id"] == task_id for task in get_tasks()):
            return None

        task_label = self._prometheus_string(task_id)
        cpu_query = f'avg(dcc_task_cpu_utilization_percent{{task_id={task_label}}})'
        memory_query = f'avg(dcc_task_memory_utilization_percent{{task_id={task_label}}})'
        network_query = (
            f'(sum(rate(dcc_task_network_receive_bytes_total{{task_id={task_label}}}[5m])) '
            f'+ sum(rate(dcc_task_network_transmit_bytes_total{{task_id={task_label}}}[5m]))) '
            '* 8 / 1000000'
        )

        try:
            cpu = self._resource_metric(cpu_query, unit="percent")
            memory = self._resource_metric(memory_query, unit="percent")
            network = self._resource_metric(network_query, unit="mbps")
        except MetricsProviderError:
            raise

        return {
            "task_id": task_id,
            "cpu": cpu,
            "memory": memory,
            "network": network,
            "impact": {
                "status": "unknown",
                "cpu_delta": cpu["current"] - cpu["baseline"],
                "memory_delta": memory["current"] - memory["baseline"],
                "network_delta": network["current"] - network["baseline"],
            },
            "source": self.name,
        }
