from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import math
from typing import Any

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.api.dependencies import DependencyType
from apps.api.cloudwatch_metrics_provider import create_cloudwatch_client


logger = logging.getLogger(__name__)

METRIC_WINDOW = timedelta(minutes=15)
METRIC_PERIOD_SECONDS = 60
MAX_CONFIGURED_RESOURCES = 20
DEPENDENCY_CLIENT_CONFIG = Config(
    connect_timeout=3,
    read_timeout=5,
    retries={"max_attempts": 1},
)
METRIC_NAMES = {
    "rds": {
        "cpu_utilization": ("CPUUtilization", "percent", "Average", "Maximum"),
        "database_connections": ("DatabaseConnections", "count", "Average", "Maximum"),
        "free_storage": ("FreeStorageSpace", "bytes", "Average", "Maximum"),
        "read_iops": ("ReadIOPS", "count_per_second", "Average", "Maximum"),
        "write_iops": ("WriteIOPS", "count_per_second", "Average", "Maximum"),
        "network_receive": ("NetworkReceiveThroughput", "bytes_per_second", "Average", "Maximum"),
        "network_transmit": ("NetworkTransmitThroughput", "bytes_per_second", "Average", "Maximum"),
    },
    "elasticache": {
        "cpu_utilization": ("CPUUtilization", "percent", "Average", "Maximum"),
        "memory_usage_bytes": ("BytesUsedForCache", "bytes", "Average", "Maximum"),
        "memory_usage_percent": ("DatabaseMemoryUsagePercentage", "percent", "Average", "Maximum"),
        "connections": ("CurrConnections", "count", "Average", "Maximum"),
        "network_receive": ("NetworkBytesIn", "bytes_per_second", "Sum", "Maximum"),
        "network_transmit": ("NetworkBytesOut", "bytes_per_second", "Sum", "Maximum"),
    },
}


@dataclass(frozen=True)
class DependencyResourceConfig:
    resource_id: str
    resource_type: DependencyType
    resource_scope: str
    engine: str
    dimension_name: str


@dataclass(frozen=True)
class CloudWatchDependenciesConfig:
    region: str
    resources: tuple[DependencyResourceConfig, ...]

    @classmethod
    def from_settings(cls) -> "CloudWatchDependenciesConfig":
        region = settings.DCC_CLOUDWATCH_REGION or settings.AWS_REGION
        if not region:
            raise ImproperlyConfigured("AWS region is required for dependency metrics.")
        try:
            resource_definitions = json.loads(settings.DCC_DEPENDENCY_RESOURCES)
        except (TypeError, json.JSONDecodeError):
            raise ImproperlyConfigured("DCC_DEPENDENCY_RESOURCES must be valid JSON.") from None
        if not isinstance(resource_definitions, list):
            raise ImproperlyConfigured("DCC_DEPENDENCY_RESOURCES must be a JSON array.")
        if len(resource_definitions) > MAX_CONFIGURED_RESOURCES:
            raise ImproperlyConfigured("Too many dependency resources are configured.")

        resources: list[DependencyResourceConfig] = []
        identifiers: set[tuple[str, str]] = set()
        for item in resource_definitions:
            if not isinstance(item, dict):
                raise ImproperlyConfigured("A dependency resource definition is invalid.")
            resource_type = item.get("resource_type")
            resource_id = item.get("resource_id")
            engine = item.get("engine", "unknown")
            resource_scope = item.get(
                "resource_scope",
                "db_instance" if resource_type == "rds" else "cache_cluster",
            )
            expected_scopes = (
                {"db_instance"} if resource_type == "rds"
                else {"cache_cluster", "replication_group"}
            )
            if (
                resource_type not in {"rds", "elasticache"}
                or not isinstance(resource_id, str)
                or not resource_id.strip()
                or len(resource_id) > 128
                or not isinstance(engine, str)
                or not engine.strip()
                or len(engine) > 64
                or not isinstance(resource_scope, str)
                or resource_scope not in expected_scopes
            ):
                raise ImproperlyConfigured("A dependency resource definition is invalid.")
            resource_id = resource_id.strip()
            identity = (resource_type, resource_id)
            if identity in identifiers:
                raise ImproperlyConfigured("Dependency resource identifiers must be unique by type.")
            identifiers.add(identity)
            dimension_name = {
                "db_instance": "DBInstanceIdentifier",
                "cache_cluster": "CacheClusterId",
                "replication_group": "ReplicationGroupId",
            }[resource_scope]
            resources.append(DependencyResourceConfig(
                resource_id=resource_id,
                resource_type=resource_type,
                resource_scope=resource_scope,
                engine=engine.strip(),
                dimension_name=dimension_name,
            ))
        return cls(region=region, resources=tuple(resources))


class CloudWatchDependencyObservabilityProvider:
    name = "cloudwatch"

    def __init__(self, config: CloudWatchDependenciesConfig, client: Any | None = None) -> None:
        self._config = config
        self._client = client

    @classmethod
    def from_settings(cls) -> "CloudWatchDependencyObservabilityProvider":
        return cls(CloudWatchDependenciesConfig.from_settings())

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = create_cloudwatch_client(
                self._config.region,
                config=DEPENDENCY_CLIENT_CONFIG,
            )
        return self._client

    def _metric(
        self,
        resource: DependencyResourceConfig,
        metric_key: str,
    ) -> dict[str, Any]:
        metric_name, unit, statistic, peak_statistic = METRIC_NAMES[
            resource.resource_type
        ][metric_key]
        try:
            response = self._get_client().get_metric_statistics(
                Namespace=(
                    "AWS/RDS" if resource.resource_type == "rds"
                    else "AWS/ElastiCache"
                ),
                MetricName=metric_name,
                Dimensions=[{
                    "Name": resource.dimension_name,
                    "Value": resource.resource_id,
                }],
                StartTime=datetime.now(timezone.utc) - METRIC_WINDOW,
                EndTime=datetime.now(timezone.utc),
                Period=METRIC_PERIOD_SECONDS,
                Statistics=list({statistic, peak_statistic}),
            )
            datapoints = response.get("Datapoints")
            if not isinstance(datapoints, list):
                raise ValueError("Invalid CloudWatch data points.")
            values = [
                (
                    point["Timestamp"],
                    self._number(point[statistic]),
                    self._number(point[peak_statistic]),
                )
                for point in datapoints
            ]
        except (AttributeError, KeyError, TypeError, ValueError):
            logger.warning(
                "CloudWatch dependency metric response was invalid (type=%s, metric=%s).",
                resource.resource_type,
                metric_key,
            )
            return {
                "current": None,
                "peak": None,
                "unit": unit,
                "status": "unavailable",
            }
        except (BotoCoreError, ClientError):
            logger.warning(
                "CloudWatch dependency metric request failed (type=%s, metric=%s).",
                resource.resource_type,
                metric_key,
            )
            return {
                "current": None,
                "peak": None,
                "unit": unit,
                "status": "unavailable",
            }
        except Exception:
            logger.warning(
                "CloudWatch dependency metric request failed (type=%s, metric=%s).",
                resource.resource_type,
                metric_key,
            )
            return {
                "current": None,
                "peak": None,
                "unit": unit,
                "status": "unavailable",
            }
        if not values:
            return {
                "current": None,
                "peak": None,
                "unit": unit,
                "status": "unavailable",
            }
        values.sort(key=lambda point: point[0])
        scale = (
            1 / METRIC_PERIOD_SECONDS
            if resource.resource_type == "elasticache"
            and metric_key in {"network_receive", "network_transmit"}
            else 1
        )
        return {
            "current": values[-1][1] * scale,
            "peak": max(point[2] for point in values) * scale,
            "unit": unit,
            "status": "available",
        }

    @staticmethod
    def _number(value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Invalid CloudWatch number.")
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Invalid CloudWatch number.")
        return result

    def list_dependencies(
        self,
        resource_type: DependencyType | None = None,
    ) -> list[dict[str, Any]]:
        return self._list_dependencies(resource_type, impact_only=False)

    def list_impact_dependencies(self) -> list[dict[str, Any]]:
        return self._list_dependencies(None, impact_only=True)

    def _list_dependencies(
        self,
        resource_type: DependencyType | None,
        *,
        impact_only: bool,
    ) -> list[dict[str, Any]]:
        resources: list[dict[str, Any]] = []
        for resource in self._config.resources:
            if resource_type is not None and resource.resource_type != resource_type:
                continue
            metric_definitions = METRIC_NAMES[resource.resource_type]
            if impact_only:
                metric_keys = (
                    ("cpu_utilization", "database_connections")
                    if resource.resource_type == "rds"
                    else ("cpu_utilization", "memory_usage_bytes", "memory_usage_percent")
                )
            else:
                metric_keys = tuple(metric_definitions)
            metrics = {
                key: self._metric(resource, key)
                for key in metric_keys
            }
            available_metrics = [
                metric for metric in metrics.values()
                if metric["status"] == "available"
            ]
            resources.append({
                "resource_id": resource.resource_id,
                "resource_type": resource.resource_type,
                "resource_scope": resource.resource_scope,
                "engine": resource.engine,
                "status": "unknown",
                "availability": "available" if available_metrics else "unavailable",
                "source": self.name,
                "metrics": metrics,
            })
        return resources
