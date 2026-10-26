from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse

from botocore.exceptions import ClientError, NoCredentialsError, ReadTimeoutError
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APIClient as DRFAPIClient

from apps.api.cloudwatch_metrics_provider import (
    CloudWatchMetricsConfig,
    CloudWatchTaskMetricsProvider,
)
from apps.api.cloudwatch_dependencies_provider import (
    CloudWatchDependenciesConfig,
    CloudWatchDependencyObservabilityProvider,
    DependencyResourceConfig,
)
from apps.api.dependencies_service import get_dependency_provider, list_dependencies
from apps.api.ecs_discovery import (
    AWSECSDiscoveryProvider,
    ECSDiscoveryConfig,
    ECSDiscoveryError,
    ECSServiceNotFound,
    ECSTaskAmbiguous,
    get_ecs_discovery_provider,
)
from apps.api.mock_dependencies_provider import MockDependencyObservabilityProvider
from apps.api.metrics import MetricsProviderError
from apps.api.metrics_service import get_task_metrics_provider
from apps.api.logs import LogsProviderError, LogsQuery
from apps.api.logs_service import get_logs_provider
from apps.api.mock_logs_provider import MockLogsProvider
from apps.api.loki_logs_provider import LokiConfig, LokiLogsProvider
from apps.api.prometheus_metrics_provider import (
    PrometheusMetricsConfig,
    PrometheusTaskMetricsProvider,
)
from apps.api.test_support import (
    ECSDiscoveryTestCase,
    TEST_CLUSTER_ARN,
    TEST_SERVICE_ARN,
)


APIClient = DRFAPIClient


class AWSECSDiscoveryProviderTests(ECSDiscoveryTestCase):
    def make_provider(self, client=None):
        task_arn = (
            "arn:aws:ecs:us-east-1:123456789012:task/test-cluster/"
            "12345678-1234-4234-8234-123456789012"
        )
        service_arn = (
            "arn:aws:ecs:us-east-1:123456789012:service/"
            "test-cluster/test-service"
        )
        definition_arn = (
            "arn:aws:ecs:us-east-1:123456789012:task-definition/app:7"
        )
        client = client or Mock()
        client.describe_clusters.return_value = {
            "clusters": [{
                "clusterArn": TEST_CLUSTER_ARN,
                "clusterName": "test-cluster",
                "status": "ACTIVE",
            }],
            "failures": [],
        }
        client.list_services.return_value = {"serviceArns": [service_arn]}
        client.describe_services.return_value = {
            "services": [{
                "serviceArn": service_arn,
                "serviceName": "test-service",
                "clusterArn": TEST_CLUSTER_ARN,
                "desiredCount": 1,
                "runningCount": 1,
                "pendingCount": 0,
                "taskDefinition": definition_arn,
                "launchType": "FARGATE",
                "status": "ACTIVE",
            }],
            "failures": [],
        }
        client.list_tasks.return_value = {"taskArns": [task_arn]}
        client.describe_tasks.return_value = {
            "tasks": [{
                "taskArn": task_arn,
                "clusterArn": TEST_CLUSTER_ARN,
                "taskDefinitionArn": definition_arn,
                "group": "service:test-service",
                "desiredStatus": "RUNNING",
                "lastStatus": "RUNNING",
                "healthStatus": "HEALTHY",
                "startedAt": datetime(2026, 10, 25, tzinfo=timezone.utc),
                "launchType": "FARGATE",
                "availabilityZone": "us-east-1a",
                "attachments": [{
                    "details": [
                        {"name": "networkInterfaceId", "value": "eni-123"},
                        {"name": "privateIPv4Address", "value": "10.0.0.12"},
                        {"name": "subnetId", "value": "subnet-123"},
                        {"name": "securityGroups", "value": "sg-123,sg-456"},
                    ],
                }],
                "containers": [{
                    "containerArn": "arn:aws:ecs:container/test",
                    "name": "app",
                    "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/app:7",
                    "imageDigest": "sha256:abc",
                    "lastStatus": "RUNNING",
                    "cpu": 256,
                    "memory": 384,
                    "runtimeId": "container-runtime",
                    "overrides": {"environment": [{"name": "SECRET", "value": "must-not-return"}]},
                }],
            }],
            "failures": [],
        }
        client.describe_task_definition.return_value = {
            "taskDefinition": {
                "cpu": "512",
                "memory": "1024",
                "networkMode": "awsvpc",
                "containerDefinitions": [{
                    "name": "app",
                    "cpu": 256,
                    "memoryReservation": 256,
                    "essential": True,
                    "environment": [{"name": "API_KEY", "value": "must-not-return"}],
                    "secrets": [{"name": "TOKEN", "valueFrom": "arn:secret"}],
                }],
            },
        }
        provider = AWSECSDiscoveryProvider(
            ECSDiscoveryConfig("us-east-1", ("test-cluster",)),
            client=client,
        )
        return provider, client

    def test_discovers_real_aws_shapes_without_returning_environment_or_secrets(self) -> None:
        provider, client = self.make_provider()
        client.describe_tasks.return_value["tasks"].append({
            "taskArn": "arn:aws:ecs:us-east-1:123456789012:task/test-cluster/pending-task",
            "desiredStatus": "RUNNING",
            "lastStatus": "PENDING",
        })

        clusters = provider.list_clusters()
        services = provider.list_services(TEST_CLUSTER_ARN)
        tasks = provider.list_running_tasks("test-cluster")

        self.assertEqual(clusters[0]["cluster_name"], "test-cluster")
        self.assertEqual(services[0]["desired_count"], 1)
        self.assertEqual(len(tasks), 1)
        self.assertGreater(client.list_services.call_count, 0)
        for service_call in client.list_services.call_args_list:
            self.assertEqual(
                service_call.kwargs,
                {"cluster": "test-cluster", "maxResults": 100},
            )
        task = tasks[0]
        self.assertEqual(task["task_definition_family"], "app")
        self.assertEqual(task["task_definition_revision"], 7)
        self.assertEqual(task["network"]["private_ip"], "10.0.0.12")
        self.assertEqual(task["network"]["security_group_ids"], ["sg-123", "sg-456"])
        self.assertEqual(task["containers"][0]["image_digest"], "sha256:abc")
        self.assertNotIn("must-not-return", str(task))
        client.list_tasks.assert_called_with(
            cluster="test-cluster",
            desiredStatus="RUNNING",
            maxResults=100,
        )

    def test_service_task_discovery_uses_aws_service_filter(self) -> None:
        provider, client = self.make_provider()

        tasks = provider.list_service_tasks("test-cluster", TEST_SERVICE_ARN)

        self.assertEqual(len(tasks), 1)
        client.list_tasks.assert_called_once_with(
            cluster="test-cluster",
            desiredStatus="RUNNING",
            maxResults=100,
            serviceName="test-service",
        )

    def test_service_task_discovery_rejects_unconfigured_service(self) -> None:
        provider, client = self.make_provider()

        with self.assertRaises(ECSServiceNotFound):
            provider.list_service_tasks("test-cluster", "not-configured")

        client.list_tasks.assert_not_called()

    def test_global_task_discovery_queries_every_configured_cluster(self) -> None:
        provider, client = self.make_provider()
        original_response = client.describe_tasks.return_value

        def describe_tasks_for_cluster(*, cluster, tasks):
            response = original_response
            if cluster == "second-cluster":
                task = response["tasks"][0]
                response = {
                    **response,
                    "tasks": [{
                        **task,
                        "taskArn": task["taskArn"].replace(
                            "task/test-cluster/",
                            "task/second-cluster/",
                        ),
                        "clusterArn": (
                            "arn:aws:ecs:us-east-1:123456789012:cluster/second-cluster"
                        ),
                    }],
                }
            return response

        client.describe_tasks.side_effect = describe_tasks_for_cluster
        provider = AWSECSDiscoveryProvider(
            ECSDiscoveryConfig("us-east-1", ("test-cluster", "second-cluster")),
            client=client,
        )

        tasks = provider.list_all_running_tasks()

        self.assertEqual(
            [task["cluster_arn"] for task in tasks],
            [
                TEST_CLUSTER_ARN,
                "arn:aws:ecs:us-east-1:123456789012:cluster/second-cluster",
            ],
        )
        self.assertEqual(
            [call.kwargs["cluster"] for call in client.list_tasks.call_args_list],
            ["test-cluster", "second-cluster"],
        )

    def test_global_task_lookup_requires_cluster_when_ids_are_ambiguous(self) -> None:
        provider, client = self.make_provider()
        original_response = client.describe_tasks.return_value

        def describe_tasks_for_cluster(*, cluster, tasks):
            response = original_response
            if cluster == "second-cluster":
                task = response["tasks"][0]
                response = {
                    **response,
                    "tasks": [{
                        **task,
                        "taskArn": task["taskArn"].replace(
                            "task/test-cluster/",
                            "task/second-cluster/",
                        ),
                        "clusterArn": (
                            "arn:aws:ecs:us-east-1:123456789012:cluster/second-cluster"
                        ),
                    }],
                }
            return response

        client.describe_tasks.side_effect = describe_tasks_for_cluster
        provider = AWSECSDiscoveryProvider(
            ECSDiscoveryConfig("us-east-1", ("test-cluster", "second-cluster")),
            client=client,
        )

        with self.assertRaises(ECSTaskAmbiguous):
            provider.get_running_task("12345678-1234-4234-8234-123456789012")

        task = provider.get_running_task(
            "12345678-1234-4234-8234-123456789012",
            cluster="second-cluster",
        )
        self.assertEqual(
            task["cluster_arn"],
            "arn:aws:ecs:us-east-1:123456789012:cluster/second-cluster",
        )

    def test_optional_service_counts_are_not_fabricated(self) -> None:
        provider, client = self.make_provider()
        client.describe_services.return_value["services"][0].pop("desiredCount")
        client.describe_services.return_value["services"][0].pop("runningCount")
        client.describe_services.return_value["services"][0].pop("pendingCount")

        service = provider.list_services("test-cluster")[0]

        self.assertIsNone(service["desired_count"])
        self.assertIsNone(service["running_count"])
        self.assertIsNone(service["pending_count"])

    def test_aws_error_is_safe_and_does_not_include_provider_details(self) -> None:
        client = Mock()
        client.describe_clusters.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "secret provider detail"}},
            "DescribeClusters",
        )
        provider, _ = self.make_provider(client)

        with self.assertRaises(ECSDiscoveryError) as raised:
            provider.list_clusters()
        self.assertNotIn("secret provider detail", raised.exception.safe_message)

    @patch(
        "apps.api.ecs_discovery.boto3.client",
        side_effect=NoCredentialsError(),
    )
    def test_client_initialization_error_is_safe(
        self,
        _create_client: Mock,
    ) -> None:
        provider = AWSECSDiscoveryProvider(
            ECSDiscoveryConfig("us-east-1", ("test-cluster",)),
        )

        with self.assertRaises(ECSDiscoveryError) as raised:
            provider.list_clusters()

        self.assertEqual(
            raised.exception.safe_message,
            "AWS ECS discovery is temporarily unavailable.",
        )
        _create_client.assert_called_once_with(
            "ecs",
            region_name="us-east-1",
        )

    def test_cluster_and_task_api_routes_use_the_read_only_provider(self) -> None:
        provider, _ = self.make_provider()
        with patch(
            "apps.api.ecs_views.get_ecs_discovery_provider",
            return_value=provider,
        ):
            clusters = APIClient().get("/api/ecs/clusters/")
            cluster_path = quote(TEST_CLUSTER_ARN, safe="")
            services = APIClient().get(
                f"/api/ecs/clusters/{cluster_path}/services/"
            )
            service_tasks = APIClient().get(
                f"/api/ecs/clusters/{cluster_path}/services/"
                f"{quote(TEST_SERVICE_ARN, safe='')}/tasks/"
            )
            tasks = APIClient().get(
                f"/api/ecs/clusters/{cluster_path}/tasks/"
            )
            task_id = (
                "12345678-1234-4234-8234-123456789012"
            )
            detail = APIClient().get(
                f"/api/ecs/clusters/{cluster_path}/tasks/{task_id}/"
            )
            global_tasks = APIClient().get("/api/ecs/tasks/")
            global_detail = APIClient().get(
                f"/api/ecs/tasks/{task_id}/?cluster={cluster_path}"
            )

        self.assertEqual(clusters.status_code, 200, clusters.content)
        self.assertEqual(services.status_code, 200, services.content)
        self.assertEqual(service_tasks.status_code, 200, service_tasks.content)
        self.assertEqual(tasks.status_code, 200, tasks.content)
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(global_tasks.status_code, 200, global_tasks.content)
        self.assertEqual(global_detail.status_code, 200, global_detail.content)
        self.assertEqual(service_tasks.json()[0], tasks.json()[0])
        self.assertEqual(global_tasks.json()[0], tasks.json()[0])
        self.assertEqual(global_detail.json(), tasks.json()[0])
        self.assertEqual(detail.json()["network"]["private_ip"], "10.0.0.12")
        self.assertNotIn("must-not-return", detail.content.decode())

    def test_global_task_endpoint_reports_ambiguous_task_id_safely(self) -> None:
        provider, _ = self.make_provider()
        provider.get_running_task = Mock(
            side_effect=ECSTaskAmbiguous("internal cluster details"),
        )
        with patch(
            "apps.api.ecs_views.get_ecs_discovery_provider",
            return_value=provider,
        ):
            response = APIClient().get(
                "/api/ecs/tasks/12345678-1234-4234-8234-123456789012/"
            )

        self.assertEqual(response.status_code, 409)
        self.assertNotIn("internal cluster details", response.content.decode())

    @override_settings(AWS_REGION="us-east-1", DCC_ECS_CLUSTERS=[])
    def test_discovery_requires_explicit_cluster_configuration(self) -> None:
        with self.assertRaises(ECSDiscoveryError) as raised:
            get_ecs_discovery_provider()
        self.assertIn("DCC_ECS_CLUSTERS", raised.exception.safe_message)


class AnonymousOperationalAPIAccessTests(ECSDiscoveryTestCase):
    def setUp(self) -> None:
        super().setUp()
        from apps.diagnostics.services import diagnostic_session_service

        diagnostic_session_service.reset()
        self.addCleanup(diagnostic_session_service.reset)

    def test_django_has_no_account_session_or_database_configuration(self) -> None:
        self.assertNotIn("django.contrib.auth", settings.INSTALLED_APPS)
        self.assertNotIn("django.contrib.sessions", settings.INSTALLED_APPS)
        self.assertNotIn(
            "django.contrib.sessions.middleware.SessionMiddleware",
            settings.MIDDLEWARE,
        )
        self.assertEqual(
            settings.DATABASES["default"]["ENGINE"],
            "django.db.backends.dummy",
        )
        self.assertEqual(settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"], [])
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"],
            ["rest_framework.permissions.AllowAny"],
        )

    @override_settings(DCC_METRICS_PROVIDER="mock", DCC_LOGS_PROVIDER="mock")
    def test_operational_read_endpoints_are_available_without_credentials(self) -> None:
        client = APIClient()
        paths = (
            "/api/health/",
            "/api/services/",
            "/api/tasks/",
            "/api/tasks/task-001/resources/",
            "/api/logs/",
            "/api/dependencies/",
            "/api/diagnostic-sessions/",
            "/api/diagnostic-sessions/active/",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200)

    def test_diagnostic_lifecycle_is_available_without_identity_or_session_cookies(self) -> None:
        client = APIClient()
        client.cookies["sessionid"] = "ignored"
        started = client.post(
            "/api/diagnostic-sessions/",
            {"target_task_id": "task-001"},
            format="json",
            HTTP_AUTHORIZATION="Bearer ignored-test-value",
        )
        self.assertEqual(started.status_code, 201)
        session = started.json()
        self.assertNotIn("owner", session)

        stopped = client.post(
            f"/api/diagnostic-sessions/{session['id']}/stop/",
            {},
            format="json",
        )
        self.assertEqual(stopped.status_code, 200)
        self.assertEqual(stopped.json()["status"], "stopped")

        report = client.get("/api/diagnostic-impact/", {"session_id": session["id"]})
        self.assertEqual(report.status_code, 200)

    def test_application_authentication_endpoints_are_removed(self) -> None:
        client = APIClient()
        for path in (
            "/api/auth/csrf/",
            "/api/auth/login/",
            "/api/auth/me/",
            "/api/auth/logout/",
        ):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 404)


def cloudwatch_config() -> CloudWatchMetricsConfig:
    return CloudWatchMetricsConfig(
        region="test-region-1",
        cluster_name="test-cluster",
        service_name="test-service",
        ecs_namespace="test/ecs",
        container_insights_namespace="test/container-insights",
    )


def cloudwatch_dependency_config(resources=None) -> CloudWatchDependenciesConfig:
    return CloudWatchDependenciesConfig(
        region="test-region-1",
        resources=tuple(resources or (
            DependencyResourceConfig(
                resource_id="test-db",
                resource_type="rds",
                resource_scope="db_instance",
                engine="postgres",
                dimension_name="DBInstanceIdentifier",
            ),
            DependencyResourceConfig(
                resource_id="test-cache",
                resource_type="elasticache",
                resource_scope="replication_group",
                engine="redis",
                dimension_name="ReplicationGroupId",
            ),
        )),
    )


class MockTaskMetricsProviderTests(ECSDiscoveryTestCase):
    def test_cloudwatch_is_the_default_metrics_provider(self) -> None:
        self.assertEqual(settings.DCC_METRICS_PROVIDER, "cloudwatch")
        with self.assertRaises(MetricsProviderError):
            get_task_metrics_provider()

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_mock_api_contract_keeps_metrics_and_adds_source(self) -> None:
        response = APIClient().get("/api/tasks/task-001/resources/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "mock")
        self.assertEqual(payload["task_id"], "task-001")
        self.assertEqual(payload["cpu"], {
            "baseline": 20,
            "current": 24,
            "peak": 31,
            "unit": "percent",
        })
        self.assertEqual(set(payload), {"task_id", "cpu", "memory", "network", "impact", "source"})


class CloudWatchTaskMetricsProviderTests(ECSDiscoveryTestCase):
    @override_settings(
        DCC_METRICS_PROVIDER="cloudwatch",
        DCC_CLOUDWATCH_REGION="test-region-1",
        DCC_CLOUDWATCH_CLUSTER_NAME="test-cluster",
        DCC_CLOUDWATCH_SERVICE_NAME="test-service",
        DCC_CLOUDWATCH_ECS_NAMESPACE="test/ecs",
        DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE="test/container-insights",
    )
    def test_cloudwatch_provider_selection(self) -> None:
        provider = get_task_metrics_provider()

        self.assertIsInstance(provider, CloudWatchTaskMetricsProvider)
        self.assertEqual(provider.name, "cloudwatch")

    def test_metrics_are_transformed_to_existing_contract(self) -> None:
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(minutes=2)
        client = Mock()

        def get_metric_statistics(**request):
            metric_name = request["MetricName"]
            if metric_name == "CPUUtilization":
                return {"Datapoints": [
                    {"Timestamp": now, "Average": 20, "Maximum": 25},
                    {"Timestamp": earlier, "Average": 10, "Maximum": 15},
                ]}
            if metric_name == "MemoryUtilization":
                return {"Datapoints": [
                    {"Timestamp": earlier, "Average": 30, "Maximum": 35},
                    {"Timestamp": now, "Average": 40, "Maximum": 45},
                ]}
            if metric_name == "NetworkRxBytes":
                return {"Datapoints": [
                    {"Timestamp": earlier, "Sum": 600_000},
                    {"Timestamp": now, "Sum": 1_200_000},
                ]}
            if metric_name == "NetworkTxBytes":
                return {"Datapoints": [
                    {"Timestamp": now, "Sum": 300_000},
                    {"Timestamp": earlier, "Sum": 300_000},
                ]}
            self.fail(f"Unexpected CloudWatch metric: {metric_name}")

        client.get_metric_statistics.side_effect = get_metric_statistics
        provider = CloudWatchTaskMetricsProvider(cloudwatch_config(), client)

        result = provider.get_task_resources("task-001")

        self.assertEqual(result["source"], "cloudwatch")
        self.assertEqual(result["task_id"], "task-001")
        self.assertEqual(result["cpu"], {
            "baseline": 10,
            "current": 20,
            "peak": 25,
            "unit": "percent",
        })
        self.assertEqual(result["memory"], {
            "baseline": 30,
            "current": 40,
            "peak": 45,
            "unit": "percent",
        })
        self.assertEqual(result["network"], {
            "baseline": 0.12,
            "current": 0.2,
            "peak": 0.2,
            "unit": "mbps",
        })
        self.assertEqual(result["impact"]["cpu_delta"], 10)
        self.assertEqual(result["impact"]["status"], "unknown")

    def test_empty_cloudwatch_results_are_reported_as_unavailable(self) -> None:
        client = Mock()
        client.get_metric_statistics.return_value = {"Datapoints": []}
        provider = CloudWatchTaskMetricsProvider(cloudwatch_config(), client)

        with self.assertRaises(MetricsProviderError) as raised:
            provider.get_task_resources("task-001")

        self.assertIn("no resource metrics", raised.exception.safe_message)

    def test_aws_client_errors_are_converted_to_safe_errors(self) -> None:
        client = Mock()
        client.get_metric_statistics.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "private account and credential details",
                }
            },
            "GetMetricStatistics",
        )
        provider = CloudWatchTaskMetricsProvider(cloudwatch_config(), client)

        with self.assertRaises(MetricsProviderError) as raised:
            provider.get_task_resources("task-001")

        self.assertEqual(
            raised.exception.safe_message,
            "CloudWatch could not return task resource metrics.",
        )
        self.assertNotIn("private", str(raised.exception))

    def test_missing_aws_credentials_are_converted_to_safe_errors(self) -> None:
        client = Mock()
        client.get_metric_statistics.side_effect = NoCredentialsError()
        provider = CloudWatchTaskMetricsProvider(cloudwatch_config(), client)

        with self.assertRaises(MetricsProviderError) as raised:
            provider.get_task_resources("task-001")

        self.assertEqual(
            raised.exception.safe_message,
            "CloudWatch could not return task resource metrics.",
        )

    @override_settings(
        DCC_METRICS_PROVIDER="cloudwatch",
        DCC_CLOUDWATCH_REGION="",
        DCC_CLOUDWATCH_CLUSTER_NAME="",
        DCC_CLOUDWATCH_SERVICE_NAME="",
        DCC_CLOUDWATCH_ECS_NAMESPACE="",
        DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE="",
    )
    def test_missing_configuration_returns_safe_api_error_without_startup_failure(self) -> None:
        response = APIClient().get("/api/tasks/task-001/resources/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Task resource metrics are unavailable because the CloudWatch provider is not configured.",
        )

    @override_settings(DCC_METRICS_PROVIDER="unsupported")
    def test_invalid_provider_selection_returns_safe_api_error(self) -> None:
        response = APIClient().get("/api/tasks/task-001/resources/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Task resource metrics are unavailable because the configured provider is unsupported.",
        )

    def test_unknown_task_does_not_call_cloudwatch(self) -> None:
        client = Mock()
        provider = CloudWatchTaskMetricsProvider(cloudwatch_config(), client)

        self.assertIsNone(provider.get_task_resources("unknown"))
        client.get_metric_statistics.assert_not_called()


class DependencyObservabilityProviderTests(ECSDiscoveryTestCase):
    def test_cloudwatch_is_the_default_dependency_provider(self) -> None:
        self.assertEqual(settings.DCC_DEPENDENCIES_PROVIDER, "cloudwatch")

    def test_operational_providers_default_to_live_sources(self) -> None:
        self.assertEqual(settings.DCC_METRICS_PROVIDER, "cloudwatch")
        self.assertEqual(settings.DCC_DEPENDENCIES_PROVIDER, "cloudwatch")
        self.assertEqual(settings.DCC_LOGS_PROVIDER, "loki")

    @override_settings(DCC_DEPENDENCIES_PROVIDER="mock")
    def test_explicit_mock_returns_deterministic_rds_and_cache_data(self) -> None:
        provider = get_dependency_provider()

        self.assertIsInstance(provider, MockDependencyObservabilityProvider)
        first = provider.list_dependencies()
        second = provider.list_dependencies()
        self.assertEqual(first, second)
        self.assertEqual(
            [(item["resource_type"], item["resource_id"]) for item in first],
            [
                ("rds", "dcc-orders-db"),
                ("elasticache", "dcc-sessions-cache"),
            ],
        )
        self.assertEqual(first[0]["metrics"]["cpu_utilization"]["current"], 28.4)
        self.assertEqual(first[0]["metrics"]["database_connections"]["current"], 24)
        self.assertEqual(first[1]["metrics"]["memory_usage_percent"]["current"], 42.0)
        self.assertTrue(all(item["source"] == "mock" for item in first))

    @override_settings(DCC_DEPENDENCIES_PROVIDER="mock")
    def test_resource_type_filter_is_applied(self) -> None:
        self.assertEqual(
            [item["resource_id"] for item in list_dependencies("rds")],
            ["dcc-orders-db"],
        )
        self.assertEqual(
            [item["resource_id"] for item in list_dependencies("elasticache")],
            ["dcc-sessions-cache"],
        )

    @override_settings(
        DCC_DEPENDENCIES_PROVIDER="cloudwatch",
        DCC_CLOUDWATCH_REGION="eu-west-1",
        DCC_DEPENDENCY_RESOURCES=(
            '[{"resource_type":"rds","resource_id":"db-prod","engine":"postgres"},'
            '{"resource_type":"elasticache","resource_id":"cache-group",'
            '"resource_scope":"replication_group","engine":"redis"}]'
        ),
    )
    def test_cloudwatch_selection_and_resource_configuration(self) -> None:
        provider = get_dependency_provider()

        self.assertIsInstance(provider, CloudWatchDependencyObservabilityProvider)
        self.assertEqual(provider._config.region, "eu-west-1")
        self.assertEqual(len(provider._config.resources), 2)
        self.assertEqual(
            provider._config.resources[1].dimension_name,
            "ReplicationGroupId",
        )

    def test_cloudwatch_transforms_rds_and_elasticache_metrics(self) -> None:
        timestamp = datetime.now(timezone.utc)
        client = Mock()

        def metric_response(**request):
            metric_name = request["MetricName"]
            value = {
                "CPUUtilization": 25,
                "DatabaseConnections": 17,
                "FreeStorageSpace": 2_000,
                "ReadIOPS": 4,
                "WriteIOPS": 3,
                "NetworkReceiveThroughput": 1_000,
                "NetworkTransmitThroughput": 2_000,
                "BytesUsedForCache": 900,
                "DatabaseMemoryUsagePercentage": 40,
                "CurrConnections": 8,
                "NetworkBytesIn": 50,
                "NetworkBytesOut": 70,
            }[metric_name]
            stats = request["Statistics"]
            return {"Datapoints": [{
                "Timestamp": timestamp,
                **{stat: value for stat in stats},
            }]}

        client.get_metric_statistics.side_effect = metric_response
        result = CloudWatchDependencyObservabilityProvider(
            cloudwatch_dependency_config(),
            client,
        ).list_dependencies()

        rds, cache = result
        self.assertEqual(rds["resource_type"], "rds")
        self.assertEqual(rds["status"], "unknown")
        self.assertEqual(rds["source"], "cloudwatch")
        self.assertEqual(rds["metrics"]["cpu_utilization"]["current"], 25)
        self.assertEqual(rds["metrics"]["database_connections"]["current"], 17)
        self.assertEqual(rds["metrics"]["free_storage"]["unit"], "bytes")
        self.assertEqual(cache["resource_scope"], "replication_group")
        self.assertEqual(cache["metrics"]["cpu_utilization"]["current"], 25)
        self.assertEqual(cache["metrics"]["memory_usage_bytes"]["current"], 900)
        self.assertEqual(cache["metrics"]["memory_usage_percent"]["current"], 40)
        self.assertEqual(
            cache["metrics"]["network_receive"]["current"],
            50 / 60,
        )
        self.assertEqual(
            cache["metrics"]["network_receive"]["unit"],
            "bytes_per_second",
        )
        self.assertTrue(all(item["availability"] == "available" for item in result))
        cache_requests = [
            call.kwargs for call in client.get_metric_statistics.call_args_list
            if call.kwargs["Namespace"] == "AWS/ElastiCache"
        ]
        self.assertTrue(all(
            request["Dimensions"][0]["Name"] == "ReplicationGroupId"
            for request in cache_requests
        ))

    def test_missing_or_empty_cloudwatch_metrics_remain_unavailable(self) -> None:
        client = Mock()
        client.get_metric_statistics.return_value = {"Datapoints": []}
        result = CloudWatchDependencyObservabilityProvider(
            cloudwatch_dependency_config(),
            client,
        ).list_dependencies("rds")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["availability"], "unavailable")
        self.assertIsNone(result[0]["metrics"]["cpu_utilization"]["current"])
        self.assertEqual(result[0]["metrics"]["cpu_utilization"]["status"], "unavailable")

    @override_settings(
        DCC_DEPENDENCIES_PROVIDER="cloudwatch",
        DCC_CLOUDWATCH_REGION="test-region-1",
        DCC_DEPENDENCY_RESOURCES='[{"resource_type":"rds","resource_id":"missing-db"}]',
    )
    @patch("apps.api.cloudwatch_dependencies_provider.create_cloudwatch_client")
    def test_missing_resource_and_raw_aws_errors_are_normalized_in_api(
        self,
        create_client: Mock,
    ) -> None:
        client = Mock()
        client.get_metric_statistics.return_value = {"Datapoints": []}
        create_client.return_value = client

        response = APIClient().get("/api/dependencies/")

        self.assertEqual(response.status_code, 200)
        resource = response.json()["resources"][0]
        self.assertEqual(resource["resource_id"], "missing-db")
        self.assertEqual(resource["availability"], "unavailable")
        self.assertIsNone(resource["metrics"]["cpu_utilization"]["current"])

        client.get_metric_statistics.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDenied",
                    "Message": "private authorization and account details",
                }
            },
            "GetMetricStatistics",
        )
        response = APIClient().get("/api/dependencies/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("private", response.content.decode())
        self.assertNotIn("AccessDenied", response.content.decode())
        self.assertEqual(
            response.json()["resources"][0]["availability"],
            "unavailable",
        )

    def test_permission_throttling_and_timeout_are_safe(self) -> None:
        failures = (
            NoCredentialsError(),
            ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "private auth details"}},
                "GetMetricStatistics",
            ),
            ClientError(
                {"Error": {"Code": "Throttling", "Message": "private throttle details"}},
                "GetMetricStatistics",
            ),
            ReadTimeoutError(endpoint_url="https://private.aws.example"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                client = Mock()
                client.get_metric_statistics.side_effect = failure
                result = CloudWatchDependencyObservabilityProvider(
                    cloudwatch_dependency_config(),
                    client,
                ).list_dependencies("rds")
                self.assertEqual(result[0]["availability"], "unavailable")
                self.assertNotIn("private", str(result))
                self.assertNotIn("AccessDenied", str(result))

    @override_settings(
        DCC_DEPENDENCIES_PROVIDER="cloudwatch",
        DCC_CLOUDWATCH_REGION="",
        AWS_REGION="",
        DCC_DEPENDENCY_RESOURCES="invalid-json",
    )
    def test_invalid_cloudwatch_configuration_returns_safe_api_error(self) -> None:
        response = APIClient().get("/api/dependencies/")

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("invalid-json", response.content.decode())
        self.assertNotIn("Traceback", response.content.decode())

    @override_settings(DCC_DEPENDENCIES_PROVIDER="unsupported")
    def test_unsupported_provider_returns_safe_api_error(self) -> None:
        response = APIClient().get("/api/dependencies/")

        self.assertEqual(response.status_code, 503)
        self.assertIn(
            "configured provider is unsupported",
            response.json()["detail"],
        )

    @override_settings(DCC_DEPENDENCIES_PROVIDER="mock")
    def test_dependencies_api_returns_normalized_read_only_resources(self) -> None:
        client = APIClient()
        response = client.get("/api/dependencies/")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["measurement_context"], "current_health")
        self.assertIsNone(payload["diagnostic_session_id"])
        self.assertEqual(len(payload["resources"]), 2)
        self.assertEqual(payload["resources"][0]["resource_type"], "rds")
        self.assertEqual(payload["resources"][0]["source"], "mock")
        self.assertEqual(payload["resources"][1]["resource_type"], "elasticache")
        self.assertEqual(
            client.get("/api/dependencies/?resource_type=rds").json()["resources"][0]["resource_type"],
            "rds",
        )
        self.assertNotIn("Datapoints", str(payload))
        self.assertEqual(client.get("/api/dependencies/?resource_type=unknown").status_code, 400)
        self.assertEqual(client.post("/api/dependencies/", {}, format="json").status_code, 405)

    @patch(
        "apps.api.views.diagnostic_session_service.get_active_session",
        return_value=SimpleNamespace(id="backend-session-123"),
    )
    def test_dependencies_api_marks_observations_with_the_active_backend_session(
        self,
        _active_session: Mock,
    ) -> None:
        response = APIClient().get("/api/dependencies/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["measurement_context"],
            "active_session_observation",
        )
        self.assertEqual(response.json()["diagnostic_session_id"], "backend-session-123")

    @override_settings(DCC_DEPENDENCIES_PROVIDER="mock")
    def test_unknown_resource_type_filter_returns_empty_list(self) -> None:
        response = APIClient().get("/api/dependencies/?resource_type=rds")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["resource_type"] for item in response.json()["resources"]],
            ["rds"],
        )


def prometheus_payload(values: list[list[float | str]], *, status: str = "success") -> bytes:
    return json.dumps({
        "status": status,
        "data": {
            "resultType": "matrix",
            "result": [{"metric": {}, "values": values}] if status == "success" else [],
        },
    }).encode()


def prometheus_response(body: bytes) -> Mock:
    response = Mock()
    response.read.return_value = body
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    return response


class PrometheusTaskMetricsProviderTests(ECSDiscoveryTestCase):
    @override_settings(
        DCC_METRICS_PROVIDER="prometheus",
        DCC_PROMETHEUS_URL="http://prometheus.internal:9090/prom",
    )
    def test_prometheus_provider_selection_and_url_configuration(self) -> None:
        provider = get_task_metrics_provider()

        self.assertIsInstance(provider, PrometheusTaskMetricsProvider)
        self.assertEqual(provider.name, "prometheus")
        self.assertEqual(
            provider._config.base_url,
            "http://prometheus.internal:9090/prom",
        )

    @override_settings(DCC_PROMETHEUS_URL="http://prometheus.internal:9090/prefix")
    def test_configured_base_path_is_used_for_http_api(self) -> None:
        with patch(
            "apps.api.prometheus_metrics_provider.urlopen",
            return_value=prometheus_response(prometheus_payload([[100, "1"]])),
        ) as request:
            provider = PrometheusTaskMetricsProvider.from_settings()
            provider._query("up")

        self.assertEqual(
            urlparse(request.call_args.args[0].full_url).path,
            "/prefix/api/v1/query_range",
        )

    @override_settings(
        DCC_METRICS_PROVIDER="prometheus",
        DCC_PROMETHEUS_URL="",
    )
    def test_missing_url_returns_safe_api_error(self) -> None:
        response = APIClient().get("/api/tasks/task-001/resources/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Task resource metrics are unavailable because the Prometheus provider is not configured.",
        )

    @override_settings(
        DCC_METRICS_PROVIDER="prometheus",
        DCC_PROMETHEUS_URL="http://user:secret@prometheus.test",
    )
    def test_invalid_url_configuration_returns_safe_api_error(self) -> None:
        response = APIClient().get("/api/tasks/task-001/resources/")

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.content.decode())

    def test_successful_response_is_transformed_to_metrics_contract(self) -> None:
        data = [
            [[100.0, "12.5"], [160.0, "20"]],
            [[100.0, "32"], [160.0, "40"]],
            [[100.0, "0.15"], [160.0, "0.30"]],
        ]
        with patch(
            "apps.api.prometheus_metrics_provider.urlopen",
            side_effect=[prometheus_response(prometheus_payload(values)) for values in data],
        ) as request:
            provider = PrometheusTaskMetricsProvider(
                PrometheusMetricsConfig("http://prometheus.test:9090")
            )
            result = provider.get_task_resources("task-001")

        self.assertEqual(result, {
            "task_id": "task-001",
            "cpu": {
                "baseline": 12.5,
                "current": 20.0,
                "peak": 20.0,
                "unit": "percent",
            },
            "memory": {
                "baseline": 32.0,
                "current": 40.0,
                "peak": 40.0,
                "unit": "percent",
            },
            "network": {
                "baseline": 0.15,
                "current": 0.3,
                "peak": 0.3,
                "unit": "mbps",
            },
            "impact": {
                "status": "unknown",
                "cpu_delta": 7.5,
                "memory_delta": 8.0,
                "network_delta": 0.15,
            },
            "source": "prometheus",
        })
        first_request = request.call_args_list[0].args[0]
        parsed_url = urlparse(first_request.full_url)
        self.assertEqual(parsed_url.netloc, "prometheus.test:9090")
        query = parse_qs(parsed_url.query)["query"][0]
        self.assertIn('task_id="task-001"', query)
        self.assertEqual(request.call_args.kwargs["timeout"], 5)

    def test_prometheus_metrics_are_returned_through_existing_api(self) -> None:
        data = [
            [[100.0, "10"], [160.0, "20"]],
            [[100.0, "30"], [160.0, "40"]],
            [[100.0, "0.1"], [160.0, "0.2"]],
        ]
        with (
            override_settings(
                DCC_METRICS_PROVIDER="prometheus",
                DCC_PROMETHEUS_URL="http://prometheus.test",
            ),
            patch(
                "apps.api.prometheus_metrics_provider.urlopen",
                side_effect=[
                    prometheus_response(prometheus_payload(values))
                    for values in data
                ],
            ),
        ):
            response = APIClient().get("/api/tasks/task-001/resources/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "prometheus")
        self.assertEqual(response.json()["task_id"], "task-001")

    @override_settings(
        DCC_METRICS_PROVIDER="prometheus",
        DCC_PROMETHEUS_URL="http://prometheus.test",
    )
    def test_prometheus_http_failure_returns_safe_api_error(self) -> None:
        failure = HTTPError(
            "http://prometheus.test/api/v1/query_range",
            503,
            "private server response",
            hdrs=None,
            fp=None,
        )
        with patch(
            "apps.api.prometheus_metrics_provider.urlopen",
            side_effect=failure,
        ):
            response = APIClient().get("/api/tasks/task-001/resources/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Prometheus could not return task resource metrics.",
        )
        self.assertNotIn("private", response.content.decode())

    def test_empty_result_returns_safe_unavailable_error(self) -> None:
        body = json.dumps({
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
        }).encode()
        with patch(
            "apps.api.prometheus_metrics_provider.urlopen",
            return_value=prometheus_response(body),
        ):
            provider = PrometheusTaskMetricsProvider(
                PrometheusMetricsConfig("http://prometheus.test")
            )
            with self.assertRaises(MetricsProviderError) as raised:
                provider.get_task_resources("task-001")

        self.assertIn("no resource metrics", raised.exception.safe_message)

    def test_prometheus_api_error_response_is_safe(self) -> None:
        body = json.dumps({
            "status": "error",
            "errorType": "bad_data",
            "error": "sensitive query detail",
        }).encode()
        with patch(
            "apps.api.prometheus_metrics_provider.urlopen",
            return_value=prometheus_response(body),
        ):
            provider = PrometheusTaskMetricsProvider(
                PrometheusMetricsConfig("http://prometheus.test")
            )
            with self.assertRaises(MetricsProviderError) as raised:
                provider.get_task_resources("task-001")

        self.assertNotIn("sensitive", str(raised.exception))

    def test_http_4xx_and_5xx_are_handled_safely(self) -> None:
        for status_code in (401, 500):
            with self.subTest(status_code=status_code):
                http_error = HTTPError(
                    "http://prometheus.test/api/v1/query_range",
                    status_code,
                    "server details",
                    hdrs=None,
                    fp=None,
                )
                with patch(
                    "apps.api.prometheus_metrics_provider.urlopen",
                    side_effect=http_error,
                ):
                    provider = PrometheusTaskMetricsProvider(
                        PrometheusMetricsConfig("http://prometheus.test")
                    )
                    with self.assertRaises(MetricsProviderError) as raised:
                        provider.get_task_resources("task-001")
                self.assertEqual(
                    raised.exception.safe_message,
                    "Prometheus could not return task resource metrics.",
                )

    def test_connection_and_timeout_failures_are_handled_safely(self) -> None:
        for failure in (URLError("private connection details"), TimeoutError()):
            with self.subTest(failure=type(failure).__name__):
                with patch(
                    "apps.api.prometheus_metrics_provider.urlopen",
                    side_effect=failure,
                ):
                    provider = PrometheusTaskMetricsProvider(
                        PrometheusMetricsConfig("http://prometheus.test")
                    )
                    with self.assertRaises(MetricsProviderError) as raised:
                        provider.get_task_resources("task-001")
                self.assertEqual(
                    raised.exception.safe_message,
                    "Prometheus could not return task resource metrics.",
                )
                self.assertNotIn("private", str(raised.exception))

    def test_malformed_json_is_handled_safely(self) -> None:
        with patch(
            "apps.api.prometheus_metrics_provider.urlopen",
            return_value=prometheus_response(b"{"),
        ):
            provider = PrometheusTaskMetricsProvider(
                PrometheusMetricsConfig("http://prometheus.test")
            )
            with self.assertRaises(MetricsProviderError) as raised:
                provider.get_task_resources("task-001")

        self.assertEqual(
            raised.exception.safe_message,
            "Prometheus returned an invalid task metrics response.",
        )

    def test_unknown_task_does_not_query_prometheus(self) -> None:
        with patch("apps.api.prometheus_metrics_provider.urlopen") as request:
            provider = PrometheusTaskMetricsProvider(
                PrometheusMetricsConfig("http://prometheus.test")
            )

            self.assertIsNone(provider.get_task_resources("unknown-task"))

        request.assert_not_called()


def loki_payload(streams: list[dict]) -> bytes:
    return json.dumps({
        "status": "success",
        "data": {"resultType": "streams", "result": streams},
    }).encode()


class LokiLogsProviderTests(ECSDiscoveryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.config = LokiConfig("http://loki.test:3100", "", "")

    def test_loki_is_the_default_logs_provider(self) -> None:
        self.assertEqual(settings.DCC_LOGS_PROVIDER, "loki")
        with self.assertRaises(LogsProviderError):
            get_logs_provider()

    @override_settings(DCC_LOGS_PROVIDER="mock")
    def test_mock_provider_requires_explicit_opt_in(self) -> None:
        self.assertIsInstance(get_logs_provider(), MockLogsProvider)

    @override_settings(
        DCC_LOGS_PROVIDER="loki",
        DCC_LOKI_URL="http://loki.internal:3100/loki",
    )
    def test_loki_provider_selection_and_url_configuration(self) -> None:
        provider = get_logs_provider()

        self.assertIsInstance(provider, LokiLogsProvider)
        self.assertEqual(provider._config.base_url, "http://loki.internal:3100/loki")

    @override_settings(DCC_LOKI_URL="http://loki.internal:3100/prefix")
    def test_configured_url_and_request_headers_are_used(self) -> None:
        with patch(
            "apps.api.loki_logs_provider.urlopen",
            return_value=prometheus_response(loki_payload([])),
        ) as request:
            provider = LokiLogsProvider.from_settings()
            self.assertEqual(provider.list_logs(), [])

        actual_request = request.call_args.args[0]
        parsed_url = urlparse(actual_request.full_url)
        params = parse_qs(parsed_url.query)
        self.assertEqual(parsed_url.path, "/prefix/loki/api/v1/query_range")
        self.assertEqual(params["query"], ['{service=~".+"}'])
        self.assertEqual(params["limit"], ["500"])
        self.assertEqual(params["direction"], ["backward"])
        self.assertEqual(request.call_args.kwargs["timeout"], 5)

    def test_supported_filters_are_translated_inside_loki_provider(self) -> None:
        filters = LogsQuery(
            search='payment "failed"',
            service="payments",
            task_id="task-002",
            source="worker",
            severity="ERROR",
            since_minutes=15,
            diagnostic_session_id="session-2",
        )
        with patch(
            "apps.api.loki_logs_provider.urlopen",
            return_value=prometheus_response(loki_payload([])),
        ) as request:
            LokiLogsProvider(self.config).list_logs(filters)

        params = parse_qs(urlparse(request.call_args.args[0].full_url).query)
        query = params["query"][0]
        for matcher in (
            'service="payments"',
            'task_id="task-002"',
            'source="worker"',
            'diagnostic_session_id="session-2"',
        ):
            self.assertIn(matcher, query)
        self.assertIn("|~ ", query)
        self.assertIn('line_format "{{.severity}} {{.level}}"', query)
        self.assertIn("ERROR|CRITICAL|FATAL", query)
        start_ns = int(params["start"][0])
        end_ns = int(params["end"][0])
        self.assertAlmostEqual(
            (end_ns - start_ns) / 1_000_000_000,
            15 * 60,
            delta=0.001,
        )

    def test_severity_filter_uses_normalized_dcc_severity(self) -> None:
        timestamp = str(int(datetime.now(timezone.utc).timestamp()) * 1_000_000_000)
        body = loki_payload([{
            "stream": {"service": "payments", "task_id": "task-002", "source": "worker"},
            "values": [
                [timestamp, json.dumps({"message": "warning", "level": "WARNING"})],
                [timestamp, json.dumps({"message": "failed", "level": "ERROR"})],
            ],
        }])
        with patch(
            "apps.api.loki_logs_provider.urlopen",
            return_value=prometheus_response(body),
        ):
            logs = LokiLogsProvider(self.config).list_logs(LogsQuery(severity="WARN"))

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["severity"], "WARN")
        self.assertEqual(logs[0]["message"], "warning")

    @override_settings(DCC_LOGS_PROVIDER="mock")
    def test_mock_api_accepts_optional_filters_when_explicitly_enabled(self) -> None:
        response = APIClient().get(
            "/api/logs/?service=Payments+Service&severity=WARN",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["severity"], "WARN")

    def test_invalid_log_filter_returns_client_error(self) -> None:
        response = APIClient().get("/api/logs/?since_minutes=7")

        self.assertEqual(response.status_code, 400)
        self.assertIn("since_minutes", response.json())

    def test_authentication_and_tenant_headers_are_optional_config(self) -> None:
        config = LokiConfig(
            "http://loki.test",
            "sensitive-token",
            "tenant-abc",
        )
        with patch(
            "apps.api.loki_logs_provider.urlopen",
            return_value=prometheus_response(loki_payload([])),
        ) as request:
            LokiLogsProvider(config).list_logs()

        headers = request.call_args.args[0].headers
        self.assertEqual(headers["Authorization"], "Bearer sensitive-token")
        self.assertEqual(headers["X-scope-orgid"], "tenant-abc")

    @override_settings(DCC_LOGS_PROVIDER="loki", DCC_LOKI_URL="")
    def test_missing_loki_url_returns_safe_api_error(self) -> None:
        response = APIClient().get("/api/logs/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Logs are unavailable because the Loki provider is not configured.",
        )

    @override_settings(
        DCC_LOGS_PROVIDER="loki",
        DCC_LOKI_URL="http://user:secret@loki.test",
    )
    def test_invalid_loki_url_returns_safe_api_error(self) -> None:
        response = APIClient().get("/api/logs/")

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.content.decode())

    def test_loki_response_is_normalized_to_existing_log_contract(self) -> None:
        timestamp_a = str(int(datetime(2026, 10, 25, tzinfo=timezone.utc).timestamp()) * 1_000_000_000)
        timestamp_b = str(int(datetime(2026, 10, 25, 0, 1, tzinfo=timezone.utc).timestamp()) * 1_000_000_000)
        body = loki_payload([{
            "stream": {
                "service": "orders-service",
                "task_id": "task-001",
                "source": "orders-worker",
                "severity": "warning",
                "diagnostic_session_id": "session-22",
                "trace_id": "trace-22",
                "environment": "staging",
            },
            "values": [
                [timestamp_a, "worker started"],
                [
                    timestamp_b,
                    json.dumps({
                        "message": "slow request",
                        "level": "ERROR",
                        "request_id": "request-22",
                        "metadata": {"duration_ms": 400},
                    }),
                ],
            ],
        }])
        with patch(
            "apps.api.loki_logs_provider.urlopen",
            return_value=prometheus_response(body),
        ):
            logs = LokiLogsProvider(self.config).list_logs()

        self.assertEqual(len(logs), 2)
        newest, older = logs
        self.assertEqual(newest["severity"], "ERROR")
        self.assertEqual(newest["service"], "orders-service")
        self.assertEqual(newest["task_id"], "task-001")
        self.assertEqual(newest["source"], "orders-worker")
        self.assertEqual(newest["message"], "slow request")
        self.assertEqual(newest["trace_id"], "request-22")
        self.assertEqual(newest["diagnostic_session_id"], "session-22")
        self.assertEqual(newest["metadata"], {"duration_ms": 400})
        self.assertEqual(older["severity"], "WARN")
        self.assertEqual(older["message"], "worker started")
        self.assertEqual(older["metadata"], {"environment": "staging"})
        self.assertEqual(older["trace_id"], "trace-22")
        self.assertEqual(older["timestamp"], "2026-10-25T00:00:00Z")
        self.assertTrue(newest["id"].startswith("loki-"))

    def test_unrecognized_severity_uses_info_fallback_and_missing_fields_are_safe(self) -> None:
        timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1e9))
        body = loki_payload([{
            "stream": {"severity": "notice"},
            "values": [[timestamp, "unclassified entry"]],
        }])
        with patch(
            "apps.api.loki_logs_provider.urlopen",
            return_value=prometheus_response(body),
        ):
            log = LokiLogsProvider(self.config).list_logs()[0]

        self.assertEqual(log["severity"], "INFO")
        self.assertEqual(log["service"], "unknown")
        self.assertEqual(log["task_id"], "unknown")
        self.assertEqual(log["source"], "unknown")
        self.assertIsNone(log["diagnostic_session_id"])
        self.assertNotIn("metadata", log)

    def test_logs_are_available_through_existing_api(self) -> None:
        timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1e9))
        body = loki_payload([{
            "stream": {"service": "orders", "task_id": "task-001", "source": "worker"},
            "values": [[timestamp, "started"]],
        }])
        with (
            override_settings(
                DCC_LOGS_PROVIDER="loki",
                DCC_LOKI_URL="http://loki.test",
            ),
            patch(
                "apps.api.loki_logs_provider.urlopen",
                return_value=prometheus_response(body),
            ),
        ):
            response = APIClient().get("/api/logs/")

        self.assertEqual(response.status_code, 200)
        log = response.json()[0]
        self.assertEqual(log["task_id"], "task-001")
        self.assertEqual(log["message"], "started")
        self.assertNotIn("metadata", log)

    def test_empty_loki_result_returns_an_empty_list(self) -> None:
        with patch(
            "apps.api.loki_logs_provider.urlopen",
            return_value=prometheus_response(loki_payload([])),
        ):
            self.assertEqual(LokiLogsProvider(self.config).list_logs(), [])

    def test_http_and_connection_failures_are_safe(self) -> None:
        failures = (
            HTTPError("http://loki.test", 401, "private auth response", None, None),
            HTTPError("http://loki.test", 502, "private server response", None, None),
            URLError("private connection detail"),
            TimeoutError(),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with patch(
                    "apps.api.loki_logs_provider.urlopen",
                    side_effect=failure,
                ):
                    with self.assertRaises(LogsProviderError) as raised:
                        LokiLogsProvider(self.config).list_logs()
                self.assertEqual(
                    raised.exception.safe_message,
                    "The Loki logs provider could not return logs.",
                )
                self.assertNotIn("private", str(raised.exception))

    def test_invalid_json_and_loki_api_errors_are_safe(self) -> None:
        payloads = (
            b"{",
            json.dumps({
                "status": "error",
                "errorType": "query_error",
                "error": "private query details",
            }).encode(),
        )
        for body in payloads:
            with self.subTest(body=body):
                with patch(
                    "apps.api.loki_logs_provider.urlopen",
                    return_value=prometheus_response(body),
                ):
                    with self.assertRaises(LogsProviderError) as raised:
                        LokiLogsProvider(self.config).list_logs()
                self.assertNotIn("private", str(raised.exception))

    @override_settings(DCC_LOGS_PROVIDER="unsupported")
    def test_unsupported_logs_provider_returns_safe_api_error(self) -> None:
        response = APIClient().get("/api/logs/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Logs are unavailable because the configured provider is unsupported.",
        )
