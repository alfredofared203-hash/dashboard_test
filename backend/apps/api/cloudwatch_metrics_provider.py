from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import math
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.api.metrics import MetricsProviderError
from apps.api.providers import get_tasks


logger = logging.getLogger(__name__)

METRIC_WINDOW = timedelta(minutes=15)
METRIC_PERIOD_SECONDS = 60


def create_cloudwatch_client(region: str, *, config: Any | None = None) -> Any:
    options = {"config": config} if config is not None else {}
    return boto3.client("cloudwatch", region_name=region, **options)


@dataclass(frozen=True)
class CloudWatchMetricsConfig:
    region: str
    cluster_name: str
    service_name: str
    ecs_namespace: str
    container_insights_namespace: str

    @classmethod
    def from_settings(cls) -> "CloudWatchMetricsConfig":
        required = {
            "DCC_CLOUDWATCH_REGION": settings.DCC_CLOUDWATCH_REGION,
            "DCC_CLOUDWATCH_CLUSTER_NAME": settings.DCC_CLOUDWATCH_CLUSTER_NAME,
            "DCC_CLOUDWATCH_SERVICE_NAME": settings.DCC_CLOUDWATCH_SERVICE_NAME,
            "DCC_CLOUDWATCH_ECS_NAMESPACE": settings.DCC_CLOUDWATCH_ECS_NAMESPACE,
            "DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE": (
                settings.DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE
            ),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ImproperlyConfigured(
                "CloudWatch task metrics configuration is incomplete."
            )

        return cls(
            region=settings.DCC_CLOUDWATCH_REGION,
            cluster_name=settings.DCC_CLOUDWATCH_CLUSTER_NAME,
            service_name=settings.DCC_CLOUDWATCH_SERVICE_NAME,
            ecs_namespace=settings.DCC_CLOUDWATCH_ECS_NAMESPACE,
            container_insights_namespace=(
                settings.DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE
            ),
        )


class CloudWatchTaskMetricsProvider:
    name = "cloudwatch"

    def __init__(self, config: CloudWatchMetricsConfig, client: Any | None = None) -> None:
        self._config = config
        self._client = client

    @classmethod
    def from_settings(cls) -> "CloudWatchTaskMetricsProvider":
        return cls(CloudWatchMetricsConfig.from_settings())

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = create_cloudwatch_client(self._config.region)
        return self._client

    def _datapoints(self, namespace: str, metric_name: str) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        response = self._get_client().get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=[
                {"Name": "ClusterName", "Value": self._config.cluster_name},
                {"Name": "ServiceName", "Value": self._config.service_name},
            ],
            StartTime=now - METRIC_WINDOW,
            EndTime=now,
            Period=METRIC_PERIOD_SECONDS,
            Statistics=(
                ["Sum"]
                if metric_name in {"NetworkRxBytes", "NetworkTxBytes"}
                else ["Average", "Maximum"]
            ),
        )
        datapoints = response.get("Datapoints")
        if not isinstance(datapoints, list):
            raise MetricsProviderError(
                "CloudWatch returned an invalid task metrics response."
            )
        return datapoints

    @staticmethod
    def _number(datapoint: dict[str, Any], key: str) -> float:
        value = datapoint.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MetricsProviderError(
                "CloudWatch returned invalid task metric values."
            )
        number = float(value)
        if not math.isfinite(number):
            raise MetricsProviderError(
                "CloudWatch returned invalid task metric values."
            )
        return number

    def _utilization(self, metric_name: str) -> dict[str, Any]:
        datapoints = self._datapoints(self._config.ecs_namespace, metric_name)
        if not datapoints:
            raise MetricsProviderError(
                "CloudWatch has no resource metrics available for the configured ECS service."
            )
        try:
            ordered = sorted(datapoints, key=lambda point: point["Timestamp"])
            averages = [self._number(point, "Average") for point in ordered]
            maxima = [self._number(point, "Maximum") for point in ordered]
        except (KeyError, TypeError):
            raise MetricsProviderError(
                "CloudWatch returned invalid task metric values."
            ) from None
        return {
            "baseline": averages[0],
            "current": averages[-1],
            "peak": max(maxima),
            "unit": "percent",
        }

    def _network(self) -> dict[str, float | str]:
        received = self._datapoints(
            self._config.container_insights_namespace, "NetworkRxBytes"
        )
        transmitted = self._datapoints(
            self._config.container_insights_namespace, "NetworkTxBytes"
        )
        if not received or not transmitted:
            raise MetricsProviderError(
                "CloudWatch has no network metrics available for the configured ECS service."
            )

        try:
            received_by_time = {
                point["Timestamp"]: self._number(point, "Sum") for point in received
            }
            transmitted_by_time = {
                point["Timestamp"]: self._number(point, "Sum")
                for point in transmitted
            }
            timestamps = sorted(received_by_time.keys() & transmitted_by_time.keys())
            if not timestamps:
                raise MetricsProviderError(
                    "CloudWatch has no matching network metrics for the configured ECS service."
                )
            mbps = [
                (received_by_time[timestamp] + transmitted_by_time[timestamp])
                * 8
                / METRIC_PERIOD_SECONDS
                / 1_000_000
                for timestamp in timestamps
            ]
        except (KeyError, TypeError):
            raise MetricsProviderError(
                "CloudWatch returned invalid network metric values."
            ) from None
        return {
            "baseline": mbps[0],
            "current": mbps[-1],
            "peak": max(mbps),
            "unit": "mbps",
        }

    def get_task_resources(self, task_id: str) -> dict[str, Any] | None:
        if not any(task["id"] == task_id for task in get_tasks()):
            return None
        try:
            cpu = self._utilization("CPUUtilization")
            memory = self._utilization("MemoryUtilization")
            network = self._network()
        except MetricsProviderError:
            raise
        except (BotoCoreError, ClientError):
            logger.warning(
                "CloudWatch task metrics request failed (task_id=%s).",
                task_id,
            )
            raise MetricsProviderError(
                "CloudWatch could not return task resource metrics."
            ) from None

        cpu_delta = cpu["current"] - cpu["baseline"]
        memory_delta = memory["current"] - memory["baseline"]
        network_delta = network["current"] - network["baseline"]
        return {
            "task_id": task_id,
            "cpu": cpu,
            "memory": memory,
            "network": network,
            "impact": {
                "status": "unknown",
                "cpu_delta": cpu_delta,
                "memory_delta": memory_delta,
                "network_delta": network_delta,
            },
            "source": self.name,
        }
