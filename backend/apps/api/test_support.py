from datetime import datetime, timezone
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings


TEST_CLUSTER_ARN = "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster"
TEST_SERVICE_ARN = (
    "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service"
)
TEST_TASK_DEFINITION_ARN = (
    "arn:aws:ecs:us-east-1:123456789012:task-definition/test-family:1"
)


class _ECSDiscoveryTestProvider:
    def list_clusters(self):
        return [{
            "cluster_arn": TEST_CLUSTER_ARN,
            "cluster_name": "test-cluster",
            "status": "ACTIVE",
        }]

    def list_services(self, cluster):
        return [{
            "service_arn": TEST_SERVICE_ARN,
            "service_name": "test-service",
            "cluster_arn": TEST_CLUSTER_ARN,
            "desired_count": 2,
            "running_count": 2,
            "pending_count": 0,
            "task_definition_arn": TEST_TASK_DEFINITION_ARN,
            "task_definition_family": "test-family",
            "task_definition_revision": 1,
            "launch_type": "FARGATE",
            "status": "ACTIVE",
        }]

    def list_running_tasks(self, cluster):
        return [
            self._task("task-001", "HEALTHY"),
            self._task("task-002", "UNKNOWN"),
        ]

    def list_service_tasks(self, cluster, service):
        return [
            task for task in self.list_running_tasks(cluster)
            if service in {TEST_SERVICE_ARN, task["service_name"]}
        ]

    def list_all_running_tasks(self):
        return self.list_running_tasks(TEST_CLUSTER_ARN)

    def get_running_task(self, task_id, *, cluster=None):
        if cluster is not None and cluster not in {TEST_CLUSTER_ARN, "test-cluster"}:
            return None
        return next(
            (task for task in self.list_running_tasks(TEST_CLUSTER_ARN)
             if task["task_id"] == task_id),
            None,
        )

    @staticmethod
    def _task(task_id, health_status):
        return {
            "task_arn": (
                f"arn:aws:ecs:us-east-1:123456789012:task/test-cluster/{task_id}"
            ),
            "task_id": task_id,
            "cluster_arn": TEST_CLUSTER_ARN,
            "service_arn": TEST_SERVICE_ARN,
            "service_name": "test-service",
            "task_definition_arn": TEST_TASK_DEFINITION_ARN,
            "task_definition_family": "test-family",
            "task_definition_revision": 1,
            "desired_status": "RUNNING",
            "last_status": "RUNNING",
            "health_status": health_status,
            "started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "launch_type": "FARGATE",
            "cpu": "256",
            "memory": "512",
            "availability_zone": "us-east-1a",
            "network_mode": "awsvpc",
            "network": {
                "eni_id": "eni-test",
                "private_ip": "10.0.0.10",
                "subnet_id": "subnet-test",
                "security_group_ids": ["sg-test"],
            },
            "containers": [{
                "container_arn": f"arn:aws:ecs:container/{task_id}",
                "name": "app",
                "image": "example.invalid/test:1",
                "image_digest": "sha256:test",
                "last_status": "RUNNING",
                "cpu": 128,
                "memory": 256,
                "memory_reservation": 128,
                "essential": True,
                "runtime_id": "runtime-test",
                "exit_code": None,
                "reason": None,
            }],
            "desired_count": 2,
            "current_count": 2,
        }


class ECSDiscoveryTestMixin:
    def setUp(self):
        super().setUp()
        settings_override = override_settings(
            AWS_REGION="us-east-1",
            DCC_ECS_CLUSTERS=["test-cluster"],
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        provider = _ECSDiscoveryTestProvider()
        for target in (
            "apps.api.providers.get_ecs_discovery_provider",
            "apps.api.ecs_views.get_ecs_discovery_provider",
            "apps.diagnostics.services.get_ecs_discovery_provider",
        ):
            patcher = patch(target, return_value=provider)
            patcher.start()
            self.addCleanup(patcher.stop)


class ECSDiscoveryTestCase(ECSDiscoveryTestMixin, SimpleTestCase):
    pass
