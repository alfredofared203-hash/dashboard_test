from copy import deepcopy
from typing import Any

from apps.api.dependencies import DependencyType


class MockDependencyObservabilityProvider:
    name = "mock"

    def list_dependencies(
        self,
        resource_type: DependencyType | None = None,
    ) -> list[dict[str, Any]]:
        resources = [
            {
                "resource_id": "dcc-orders-db",
                "resource_type": "rds",
                "resource_scope": "db_instance",
                "engine": "postgres",
                "status": "available",
                "availability": "available",
                "source": self.name,
                "metrics": {
                    "cpu_utilization": {
                        "current": 28.4,
                        "peak": 35.2,
                        "unit": "percent",
                        "status": "available",
                    },
                    "database_connections": {
                        "current": 24,
                        "peak": 31,
                        "unit": "count",
                        "status": "available",
                    },
                    "free_storage": {
                        "current": 68_719_476_736,
                        "peak": 70_000_000_000,
                        "unit": "bytes",
                        "status": "available",
                    },
                    "read_iops": {
                        "current": 18.0,
                        "peak": 27.0,
                        "unit": "count_per_second",
                        "status": "available",
                    },
                    "write_iops": {
                        "current": 7.0,
                        "peak": 13.0,
                        "unit": "count_per_second",
                        "status": "available",
                    },
                    "network_receive": {
                        "current": 48_000,
                        "peak": 62_000,
                        "unit": "bytes_per_second",
                        "status": "available",
                    },
                    "network_transmit": {
                        "current": 36_000,
                        "peak": 54_000,
                        "unit": "bytes_per_second",
                        "status": "available",
                    },
                },
            },
            {
                "resource_id": "dcc-sessions-cache",
                "resource_type": "elasticache",
                "resource_scope": "cache_cluster",
                "engine": "redis",
                "status": "available",
                "availability": "available",
                "source": self.name,
                "metrics": {
                    "cpu_utilization": {
                        "current": 16.2,
                        "peak": 22.8,
                        "unit": "percent",
                        "status": "available",
                    },
                    "memory_usage_bytes": {
                        "current": 1_610_612_736,
                        "peak": 1_825_361_920,
                        "unit": "bytes",
                        "status": "available",
                    },
                    "memory_usage_percent": {
                        "current": 42.0,
                        "peak": 47.5,
                        "unit": "percent",
                        "status": "available",
                    },
                    "connections": {
                        "current": 86,
                        "peak": 103,
                        "unit": "count",
                        "status": "available",
                    },
                    "network_receive": {
                        "current": 52_000,
                        "peak": 73_000,
                        "unit": "bytes_per_second",
                        "status": "available",
                    },
                    "network_transmit": {
                        "current": 44_000,
                        "peak": 61_000,
                        "unit": "bytes_per_second",
                        "status": "available",
                    },
                },
            },
        ]
        filtered = [
            resource for resource in resources
            if resource_type is None or resource["resource_type"] == resource_type
        ]
        return deepcopy(filtered)

    def list_impact_dependencies(self) -> list[dict[str, Any]]:
        resources = self.list_dependencies()
        for resource in resources:
            resource["metrics"] = {
                name: resource["metrics"][name]
                for name in (
                    ("cpu_utilization", "database_connections")
                    if resource["resource_type"] == "rds"
                    else ("cpu_utilization", "memory_usage_bytes", "memory_usage_percent")
                )
            }
        return resources
