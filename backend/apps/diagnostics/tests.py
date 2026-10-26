from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient as DRFAPIClient
from rest_framework.exceptions import Throttled

from apps.api.logs import LogsProviderError, LogsQuery
from apps.api.metrics import MetricsProviderError
from apps.api.test_support import ECSDiscoveryTestMixin
from apps.diagnostics.ecs_provider import (
    ECSExecutionConfig,
    ECSDiagnosticExecutionProvider,
)
from apps.diagnostics.impact import DiagnosticImpactService
from apps.diagnostics.models import DiagnosticSession, ExecutionReference
from apps.diagnostics.providers import (
    DiagnosticProviderError,
    InMemoryDiagnosticExecutionProvider,
    get_diagnostic_execution_provider,
)
from apps.diagnostics.services import (
    DiagnosticSessionService,
    DiagnosticExecutionFailure,
    IneligibleTargetTask,
    InvalidTargetTask,
    SessionConflict,
    diagnostic_session_service,
)


APIClient = DRFAPIClient


class _RecordingImpactServiceForGuardrails:
    def capture_baseline(self, session_id: str, target_task_id: str) -> None:
        return None

    def start_during_sampling(self, session_id: str) -> None:
        return None

    def capture_terminal(self, session_id: str) -> None:
        return None

    def reset(self) -> None:
        return None


class InMemoryDiagnosticExecutionProviderTests(TestCase):
    def setUp(self) -> None:
        self.provider = InMemoryDiagnosticExecutionProvider()

    def test_start_and_stop_succeed(self) -> None:
        execution = self.provider.start("session-1", "task-001")

        self.assertEqual(execution.provider, "inmemory")
        self.provider.stop(execution)

    def test_stopping_unknown_execution_fails_safely(self) -> None:
        execution = ExecutionReference("inmemory", "missing")

        with self.assertRaises(DiagnosticProviderError):
            self.provider.stop(execution)


class ECSDiagnosticExecutionProviderTests(TestCase):
    def setUp(self) -> None:
        self.config = ECSExecutionConfig(
            region="us-east-1",
            cluster="dcc-cluster",
            task_definition="dcc-diagnostic:1",
            subnets=("subnet-123",),
            security_groups=("sg-123",),
            container_name="diagnostic-worker",
            assign_public_ip=False,
        )
        self.client = Mock()
        self.client.describe_task_definition.return_value = {
            "taskDefinition": {
                "status": "ACTIVE",
                "cpu": "512",
                "memory": "1024",
                "containerDefinitions": [{"name": "diagnostic-worker"}],
            }
        }
        self.provider = ECSDiagnosticExecutionProvider(self.config, self.client)

    def test_start_runs_fargate_task_with_worker_contract(self) -> None:
        self.client.run_task.return_value = {
            "tasks": [{"taskArn": "arn:aws:ecs:us-east-1:123:task/abc"}],
            "failures": [],
        }

        session_id = "123e4567-e89b-42d3-a456-426614174000"
        execution = self.provider.start(
            session_id,
            "task-001",
            "arn:aws:ecs:region:123:cluster/workloads",
        )

        self.assertEqual(execution.provider, "ecs")
        self.assertEqual(execution.reference, "arn:aws:ecs:us-east-1:123:task/abc")
        request = self.client.run_task.call_args.kwargs
        self.assertEqual(request["launchType"], "FARGATE")
        self.assertEqual(
            request["networkConfiguration"]["awsvpcConfiguration"]["subnets"],
            ["subnet-123"],
        )
        environment = request["overrides"]["containerOverrides"][0]["environment"]
        self.assertEqual(
            environment,
            [
                {"name": "DIAGNOSTIC_SESSION_ID", "value": session_id},
                {"name": "TARGET_TASK_ID", "value": "task-001"},
                {"name": "TARGET_CLUSTER_ARN", "value": "arn:aws:ecs:region:123:cluster/workloads"},
            ],
        )

    def test_start_rejects_missing_task_arn(self) -> None:
        self.client.run_task.return_value = {"tasks": [], "failures": []}

        with self.assertRaises(DiagnosticProviderError):
            self.provider.start("123e4567-e89b-42d3-a456-426614174000", "task-001")

    def test_start_rejects_ecs_failure_response(self) -> None:
        self.client.run_task.return_value = {
            "tasks": [],
            "failures": [{"reason": "ACCESS_DENIED"}],
        }

        with self.assertRaises(DiagnosticProviderError):
            self.provider.start("123e4567-e89b-42d3-a456-426614174000", "task-001")

    def test_start_rejects_invalid_identifiers_before_aws_calls(self) -> None:
        with self.assertRaises(DiagnosticProviderError):
            self.provider.start("not-a-session", "task-001")
        with self.assertRaises(DiagnosticProviderError):
            self.provider.start("123e4567-e89b-42d3-a456-426614174000", "task/001")

        self.client.describe_task_definition.assert_not_called()
        self.client.run_task.assert_not_called()

    def test_start_rejects_task_definition_above_resource_caps(self) -> None:
        self.client.describe_task_definition.return_value["taskDefinition"]["cpu"] = "2048"

        with self.assertRaisesRegex(DiagnosticProviderError, "resource limits"):
            self.provider.start("123e4567-e89b-42d3-a456-426614174000", "task-001")

        self.client.run_task.assert_not_called()

    def test_start_rejects_unknown_container_and_safe_describe_failures(self) -> None:
        self.client.describe_task_definition.return_value["taskDefinition"][
            "containerDefinitions"
        ] = [{"name": "unexpected"}]
        with self.assertRaisesRegex(DiagnosticProviderError, "container was not found"):
            self.provider.start("123e4567-e89b-42d3-a456-426614174000", "task-001")
        self.client.run_task.assert_not_called()

        self.client.describe_task_definition.side_effect = ClientError(
            {
                "Error": {"Code": "AccessDeniedException", "Message": "sensitive"},
                "ResponseMetadata": {"RequestId": "private-request-id"},
            },
            "DescribeTaskDefinition",
        )
        with self.assertRaises(DiagnosticProviderError) as raised:
            self.provider.start("123e4567-e89b-42d3-a456-426614174000", "task-001")
        self.assertNotIn("private-request-id", str(raised.exception))

    def test_start_rejects_aws_credentials_in_worker_environment(self) -> None:
        self.client.describe_task_definition.return_value["taskDefinition"][
            "containerDefinitions"
        ][0]["environment"] = [
            {"name": "AWS_ACCESS_KEY_ID", "value": "never-logged"}
        ]

        with self.assertRaisesRegex(DiagnosticProviderError, "AWS credentials"):
            self.provider.start("123e4567-e89b-42d3-a456-426614174000", "task-001")

        self.client.run_task.assert_not_called()

    def test_start_converts_aws_exception_without_leaking_details(self) -> None:
        self.client.run_task.side_effect = ClientError(
            {
                "Error": {"Code": "AccessDeniedException", "Message": "sensitive"},
                "ResponseMetadata": {"RequestId": "private-request-id"},
            },
            "RunTask",
        )

        with self.assertRaises(DiagnosticProviderError) as raised:
            self.provider.start("123e4567-e89b-42d3-a456-426614174000", "task-001")

        self.assertEqual(
            str(raised.exception),
            "The diagnostic worker could not be started.",
        )
        self.assertNotIn("private-request-id", str(raised.exception))

    def test_stop_calls_ecs_and_converts_errors_safely(self) -> None:
        self.client.stop_task.return_value = {
            "tasks": [{"taskArn": "arn:task/example"}],
            "failures": [],
        }
        execution = ExecutionReference(
            provider="ecs",
            reference="arn:task/example",
            cluster="dcc-cluster",
        )

        self.provider.stop(execution)
        self.client.stop_task.assert_called_once_with(
            cluster="dcc-cluster",
            task="arn:task/example",
            reason="DCC diagnostic session stopped",
        )

        self.client.stop_task.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "sensitive"}},
            "StopTask",
        )
        with self.assertRaises(DiagnosticProviderError) as raised:
            self.provider.stop(execution)
        self.assertEqual(
            str(raised.exception),
            "The diagnostic worker could not be stopped.",
        )

    def test_stop_rejects_ecs_failure_response(self) -> None:
        self.client.stop_task.return_value = {
            "failures": [{"reason": "MISSING"}]
        }
        execution = ExecutionReference(
            provider="ecs",
            reference="arn:task/example",
            cluster="dcc-cluster",
        )

        with self.assertRaises(DiagnosticProviderError):
            self.provider.stop(execution)

    @override_settings(
        AWS_REGION="us-east-1",
        DCC_ECS_CLUSTER="dcc-cluster",
        DCC_ECS_TASK_DEFINITION="dcc-diagnostic:1",
        DCC_ECS_SUBNETS=["subnet-123"],
        DCC_ECS_SECURITY_GROUPS=[],
        DCC_ECS_CONTAINER_NAME="diagnostic-worker",
        DCC_ECS_ASSIGN_PUBLIC_IP=False,
    )
    def test_ecs_configuration_is_read_from_settings(self) -> None:
        config = ECSExecutionConfig.from_settings()

        self.assertEqual(config.region, "us-east-1")
        self.assertEqual(config.subnets, ("subnet-123",))
        self.assertFalse(config.assign_public_ip)
        self.assertEqual(config.max_task_cpu, 1024)
        self.assertEqual(config.max_task_memory_mib, 2048)

    @override_settings(
        AWS_REGION="",
        DCC_ECS_CLUSTER="",
        DCC_ECS_TASK_DEFINITION="",
        DCC_ECS_SUBNETS=[],
        DCC_ECS_CONTAINER_NAME="",
    )
    def test_ecs_configuration_fails_clearly_when_required_values_are_missing(self) -> None:
        with self.assertRaisesRegex(ImproperlyConfigured, "AWS_REGION"):
            ECSExecutionConfig.from_settings()

    @override_settings(
        AWS_REGION="us-east-1",
        DCC_ECS_CLUSTER="dcc-cluster",
        DCC_ECS_TASK_DEFINITION="dcc-diagnostic:1",
        DCC_ECS_SUBNETS=["subnet-123"],
        DCC_ECS_SECURITY_GROUPS=[],
        DCC_ECS_CONTAINER_NAME="diagnostic-worker",
        DCC_ECS_ASSIGN_PUBLIC_IP=False,
        DCC_DIAGNOSTIC_PROVIDER="ecs",
    )
    @patch("apps.diagnostics.ecs_provider.boto3.client")
    def test_factory_resolves_ecs_provider(self, client_factory: Mock) -> None:
        provider = get_diagnostic_execution_provider()

        self.assertIsInstance(provider, ECSDiagnosticExecutionProvider)
        self.assertIsNone(provider._client)
        client_factory.assert_not_called()
        client_factory.return_value.run_task.return_value = {
            "tasks": [{"taskArn": "arn:task/example"}],
            "failures": [],
        }
        client_factory.return_value.describe_task_definition.return_value = {
            "taskDefinition": {
                "status": "ACTIVE",
                "cpu": "512",
                "memory": "1024",
                "containerDefinitions": [{"name": "diagnostic-worker"}],
            }
        }
        provider.start("123e4567-e89b-42d3-a456-426614174000", "task-001")
        client_factory.assert_called_once_with("ecs", region_name="us-east-1")

    @override_settings(DCC_DIAGNOSTIC_PROVIDER="inmemory")
    def test_factory_defaults_to_inmemory_provider_without_aws(self) -> None:
        self.assertIsInstance(
            get_diagnostic_execution_provider(),
            InMemoryDiagnosticExecutionProvider,
        )

    @override_settings(
        DCC_DIAGNOSTIC_PROVIDER="ecs",
        AWS_REGION="",
        DCC_ECS_CLUSTER="",
        DCC_ECS_TASK_DEFINITION="",
        DCC_ECS_SUBNETS=[],
        DCC_ECS_CONTAINER_NAME="",
    )
    def test_explicit_ecs_selection_does_not_fall_back_without_config(self) -> None:
        with self.assertRaisesRegex(ImproperlyConfigured, "ECS"):
            get_diagnostic_execution_provider()


class DiagnosticSessionApiTests(ECSDiscoveryTestMixin, SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        logs_settings = override_settings(DCC_LOGS_PROVIDER="mock")
        logs_settings.enable()
        self.addCleanup(logs_settings.disable)
        diagnostic_session_service.reset()
        self.addCleanup(diagnostic_session_service.reset)
        self.client = APIClient()

    def start_session(self, target_task_id: str = "task-001") -> dict:
        response = self.client.post(
            "/api/diagnostic-sessions/",
            {"target_task_id": target_task_id},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_start_creates_running_session_for_known_task(self) -> None:
        session = self.start_session()

        self.assertEqual(session["status"], "running")
        self.assertEqual(session["target_task_id"], "task-001")
        self.assertIsNotNone(session["started_at"])
        self.assertIsNone(session["stopped_at"])
        self.assertEqual(session["duration_seconds"], 0)
        self.assertTrue(session["id"])
        self.assertEqual(
            session["execution"],
            {"provider": "inmemory", "status": "running"},
        )
        self.assertNotIn("reference", session["execution"])
        self.assertIsNone(session["error"])

    def test_start_requires_target_and_rejects_unknown_task(self) -> None:
        missing = self.client.post(
            "/api/diagnostic-sessions/", {}, format="json"
        )
        unknown = self.client.post(
            "/api/diagnostic-sessions/",
            {"target_task_id": "not-a-task"},
            format="json",
        )

        self.assertEqual(missing.status_code, 400)
        self.assertIn("target_task_id", missing.json())
        self.assertEqual(unknown.status_code, 400)
        self.assertIn("Unknown task ID", unknown.json()["detail"])
        self.assertEqual(self.client.get("/api/diagnostic-sessions/").json(), [])

    def test_start_rejects_extra_infrastructure_parameters(self) -> None:
        response = self.client.post(
            "/api/diagnostic-sessions/",
            {
                "target_task_id": "task-001",
                "cluster": "attacker-controlled",
                "task_definition": "arbitrary-task",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("attacker-controlled", str(response.json()))
        self.assertEqual(diagnostic_session_service.list_sessions(), [])

    @override_settings(
        DCC_DIAGNOSTIC_START_RATE_LIMIT=1,
        DCC_DIAGNOSTIC_START_RATE_WINDOW_SECONDS=3600,
    )
    def test_start_rate_limit_returns_429(self) -> None:
        first = self.start_session()
        stopped = self.client.post(
            f"/api/diagnostic-sessions/{first['id']}/stop/",
            {},
            format="json",
        )
        self.assertEqual(stopped.status_code, 200)

        limited = self.client.post(
            "/api/diagnostic-sessions/",
            {"target_task_id": "task-002"},
            format="json",
        )
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(len(diagnostic_session_service.list_sessions()), 1)

    @override_settings(
        DCC_DIAGNOSTIC_START_RATE_LIMIT=5,
        DCC_DIAGNOSTIC_STOP_RATE_LIMIT=1,
        DCC_DIAGNOSTIC_STOP_RATE_WINDOW_SECONDS=3600,
    )
    def test_stop_rate_limit_returns_429_without_retrying_stop(self) -> None:
        first = self.start_session()
        self.assertEqual(
            self.client.post(
                f"/api/diagnostic-sessions/{first['id']}/stop/",
                {},
                format="json",
            ).status_code,
            200,
        )

        second = self.start_session("task-002")
        limited = self.client.post(
            f"/api/diagnostic-sessions/{second['id']}/stop/",
            {},
            format="json",
        )

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(
            self.client.get(
                f"/api/diagnostic-sessions/{second['id']}/"
            ).json()["status"],
            "running",
        )

    def test_malformed_session_and_impact_ids_are_rejected(self) -> None:
        detail = self.client.get("/api/diagnostic-sessions/not-a-uuid/")
        impact = self.client.get(
            "/api/diagnostic-impact/",
            {"session_id": "not-a-uuid"},
        )

        self.assertEqual(detail.status_code, 404)
        self.assertEqual(impact.status_code, 400)

    def test_logs_filter_inputs_reject_invalid_identifiers_and_ranges(self) -> None:
        invalid_task = self.client.get(
            "/api/logs/",
            {"task_id": "task/001"},
        )
        invalid_range = self.client.get(
            "/api/logs/",
            {"since_minutes": 999},
        )
        control_character = self.client.get(
            "/api/logs/",
            {"search": "worker\nunexpected"},
        )

        self.assertEqual(invalid_task.status_code, 400)
        self.assertEqual(invalid_range.status_code, 400)
        self.assertEqual(control_character.status_code, 400)

    def test_unhandled_api_exception_returns_generic_json_without_exception_details(self) -> None:
        with patch(
            "apps.api.views.providers.get_services",
            side_effect=RuntimeError("private path /srv/app and token=secret"),
        ):
            response = self.client.get("/api/services/")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"detail": "The request could not be completed safely."},
        )
        self.assertNotIn("private path", response.content.decode())
        self.assertNotIn("secret", response.content.decode())

    def test_security_headers_are_set_on_api_responses(self) -> None:
        response = self.client.get("/api/services/")

        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(
            response["Referrer-Policy"],
            "strict-origin-when-cross-origin",
        )
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_ecs_start_failure_returns_502_and_records_failed_session(self) -> None:
        original_provider = diagnostic_session_service._execution_provider
        diagnostic_session_service._execution_provider = _FailingExecutionProvider(
            fail_start=True
        )
        self.addCleanup(
            setattr,
            diagnostic_session_service,
            "_execution_provider",
            original_provider,
        )

        response = self.client.post(
            "/api/diagnostic-sessions/",
            {"target_task_id": "task-001"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "The diagnostic execution provider failed.",
        )
        session = self.client.get("/api/diagnostic-sessions/").json()[0]
        self.assertEqual(session["status"], "failed")
        self.assertEqual(
            session["error"],
            "The diagnostic worker could not be started.",
        )
        report = self.client.get(
            "/api/diagnostic-impact/",
            {"session_id": session["id"]},
        )
        self.assertEqual(report.status_code, 200)
        self.assertEqual(
            report.json()["measurements"]["phases"]["post"]["status"],
            "captured",
        )

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_ecs_stop_failure_returns_502_and_marks_session_failed(self) -> None:
        original_provider = diagnostic_session_service._execution_provider
        diagnostic_session_service._execution_provider = _FailingExecutionProvider(
            fail_stop=True
        )
        self.addCleanup(
            setattr,
            diagnostic_session_service,
            "_execution_provider",
            original_provider,
        )
        session = self.start_session()

        response = self.client.post(
            f"/api/diagnostic-sessions/{session['id']}/stop/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        failed = self.client.get(
            f"/api/diagnostic-sessions/{session['id']}/"
        ).json()
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(
            failed["error"],
            "The diagnostic worker could not be stopped.",
        )
        self.assertNotIn("private-task-arn", str(failed))
        report = self.client.get(
            "/api/diagnostic-impact/",
            {"session_id": session["id"]},
        )
        self.assertEqual(report.status_code, 200)
        self.assertEqual(
            report.json()["measurements"]["phases"]["post"]["status"],
            "captured",
        )

    def test_duplicate_start_conflicts_without_creating_second_session(self) -> None:
        self.start_session()

        duplicate = self.client.post(
            "/api/diagnostic-sessions/",
            {"target_task_id": "task-002"},
            format="json",
        )

        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("already running", duplicate.json()["detail"])
        self.assertEqual(len(self.client.get("/api/diagnostic-sessions/").json()), 1)

    def test_get_list_and_active_session(self) -> None:
        session = self.start_session()

        self.assertEqual(
            self.client.get(f"/api/diagnostic-sessions/{session['id']}/").status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/api/diagnostic-sessions/").json()[0]["id"],
            session["id"],
        )
        self.assertEqual(
            self.client.get("/api/diagnostic-sessions/active/").json()["session"][
                "id"
            ],
            session["id"],
        )

    def test_active_session_is_null_when_none_is_running(self) -> None:
        self.assertEqual(
            self.client.get("/api/diagnostic-sessions/active/").json(),
            {"session": None},
        )

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_diagnostic_impact_endpoint_returns_session_measurements(self) -> None:
        session = self.start_session()

        default_response = self.client.get("/api/diagnostic-impact/")
        response = self.client.get(
            "/api/diagnostic-impact/",
            {"session_id": session["id"]},
        )

        self.assertEqual(default_response.status_code, 200, default_response.content)
        self.assertEqual(default_response.json()["session"]["id"], session["id"])
        self.assertEqual(response.status_code, 200, response.content)
        report = response.json()
        self.assertEqual(report["session"]["id"], session["id"])
        self.assertEqual(report["dependencies"]["session_id"], session["id"])
        self.assertEqual(report["measurements"]["sources"], ["mock"])
        self.assertEqual(
            report["measurements"]["phases"]["baseline"]["status"],
            "captured",
        )
        self.assertEqual(report["api_testing"]["status"], "not_provided")
        self.assertIn("not scientific causal analysis", " ".join(report["limitations"]))
        self.client.post(f"/api/diagnostic-sessions/{session['id']}/stop/", {})
        repeated = self.client.get(
            "/api/diagnostic-impact/",
            {"session_id": session["id"]},
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(
            repeated.json()["measurements"]["phases"]["post"]["status"],
            "captured",
        )

    def test_diagnostic_impact_report_requires_an_existing_session(self) -> None:
        response = self.client.get("/api/diagnostic-impact/")

        self.assertEqual(response.status_code, 404)

    def test_diagnostic_impact_report_is_associated_with_requested_session(self) -> None:
        first = self.start_session()
        self.client.post(f"/api/diagnostic-sessions/{first['id']}/stop/", {})
        second = self.start_session("task-002")

        response = self.client.get(
            "/api/diagnostic-impact/",
            {"session_id": first["id"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session"]["id"], first["id"])
        self.assertEqual(response.json()["dependencies"]["session_id"], first["id"])
        self.assertEqual(response.json()["target"]["task_id"], "task-001")
        self.assertNotEqual(response.json()["session"]["id"], second["id"])

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_existing_backend_contract_routes_remain_available(self) -> None:
        for path in (
            "/api/health/",
            "/api/services/",
            "/api/tasks/",
            "/api/tasks/task-001/resources/",
            "/api/logs/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_logs_endpoint_returns_valid_contract(self) -> None:
        response = self.client.get("/api/logs/")

        self.assertEqual(response.status_code, 200)
        logs = response.json()
        self.assertIsInstance(logs, list)
        self.assertTrue(logs)
        required_fields = {
            "id",
            "timestamp",
            "severity",
            "service",
            "task_id",
            "source",
            "message",
            "diagnostic_session_id",
            "metadata",
        }
        for entry in logs:
            with self.subTest(log_id=entry["id"]):
                self.assertTrue(required_fields.issubset(entry))
                self.assertIn(entry["severity"], {"DEBUG", "INFO", "WARN", "ERROR"})
                self.assertIsInstance(entry["metadata"], dict)
                if "trace_id" in entry:
                    self.assertTrue(
                        entry["trace_id"] is None
                        or isinstance(entry["trace_id"], str)
                    )

    def test_stop_records_terminal_state_and_duration_once(self) -> None:
        session = self.start_session()

        response = self.client.post(
            f"/api/diagnostic-sessions/{session['id']}/stop/",
            {},
            format="json",
        )
        stopped = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(stopped["status"], "stopped")
        self.assertIsNotNone(stopped["stopped_at"])
        self.assertGreaterEqual(stopped["duration_seconds"], 0)

        repeated_stop = self.client.post(
            f"/api/diagnostic-sessions/{session['id']}/stop/",
            {},
            format="json",
        )
        self.assertEqual(repeated_stop.status_code, 409)
        self.assertEqual(
            self.client.get("/api/diagnostic-sessions/active/").json(),
            {"session": None},
        )

    def test_unknown_session_get_and_stop_return_json_404(self) -> None:
        detail = self.client.get("/api/diagnostic-sessions/missing/")
        stop = self.client.post("/api/diagnostic-sessions/missing/stop/", {})

        self.assertEqual(detail.status_code, 404)
        self.assertIn("detail", detail.json())
        self.assertEqual(stop.status_code, 404)
        self.assertIn("detail", stop.json())

    def test_methods_remain_read_only_except_session_operations(self) -> None:
        response = self.client.put(
            "/api/diagnostic-sessions/",
            {"target_task_id": "task-001"},
            format="json",
        )

        self.assertEqual(response.status_code, 405)

    def test_cors_allows_configured_frontend_for_integrated_api_routes_only(self) -> None:
        options = self.client.options(
            "/api/diagnostic-sessions/active/",
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
        )
        self.assertEqual(
            options["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )
        self.assertIn("POST", options["Access-Control-Allow-Methods"])
        self.assertIn("content-type", options["Access-Control-Allow-Headers"])
        self.assertFalse(settings.CORS_ALLOW_CREDENTIALS)
        self.assertEqual(
            self.client.get("/api/auth/login/").status_code,
            404,
        )

        task_list = self.client.get(
            "/api/tasks/",
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(
            task_list["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )
        task_resources = self.client.get(
            "/api/tasks/task-001/resources/",
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(
            task_resources["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )
        impact_report = self.client.get(
            "/api/diagnostic-impact/",
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(
            impact_report["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )
        logs_options = self.client.options(
            "/api/logs/",
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        self.assertEqual(
            logs_options["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )
        self.assertIn("GET", logs_options["Access-Control-Allow-Methods"])
        dependencies = self.client.get(
            "/api/dependencies/",
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(
            dependencies["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )
        services = self.client.get(
            "/api/services/",
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(
            services["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )

        unapproved = self.client.get(
            "/api/diagnostic-sessions/active/",
            HTTP_ORIGIN="http://unapproved.example",
        )
        self.assertNotIn("Access-Control-Allow-Origin", unapproved)


class DiagnosticSessionServiceTests(ECSDiscoveryTestMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        diagnostic_session_service.reset()
        self.addCleanup(diagnostic_session_service.reset)

    def test_running_session_can_complete_or_fail_but_not_transition_again(self) -> None:
        completed = diagnostic_session_service.start_session("task-001")
        completed_result = diagnostic_session_service.complete_session(completed.id)
        self.assertEqual(completed_result.status, "completed")
        self.assertIsNotNone(completed_result.stopped_at)

        with self.assertRaises(SessionConflict):
            diagnostic_session_service.stop_session(completed.id)
        with self.assertRaises(SessionConflict):
            diagnostic_session_service.transition_session(completed.id, "running")

        failed = diagnostic_session_service.start_session("task-002")
        failed_result = diagnostic_session_service.fail_session(failed.id)
        self.assertEqual(failed_result.status, "failed")
        self.assertIsNotNone(failed_result.stopped_at)

        with self.assertRaises(SessionConflict):
            diagnostic_session_service.complete_session(failed.id)

    def test_only_one_concurrent_start_can_become_active(self) -> None:
        def start() -> str:
            try:
                diagnostic_session_service.start_session("task-001")
                return "started"
            except SessionConflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: start(), range(2)))

        self.assertCountEqual(results, ["started", "conflict"])
        self.assertEqual(len(diagnostic_session_service.list_sessions()), 1)

    def test_a_new_session_can_start_after_previous_session_stops(self) -> None:
        first = diagnostic_session_service.start_session("task-001")
        diagnostic_session_service.stop_session(first.id)

        second = diagnostic_session_service.start_session("task-002")

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(second.status, "running")
        self.assertEqual(len(diagnostic_session_service.list_sessions()), 2)

    def test_invalid_and_ineligible_targets_are_rejected_before_execution(self) -> None:
        class _RecordingExecutionProvider:
            name = "inmemory"

            def start(
                self,
                session_id: str,
                target_task_id: str,
                target_cluster_arn: str | None = None,
            ) -> ExecutionReference:
                raise AssertionError("Provider must not start for an invalid target.")

            def stop(self, execution: ExecutionReference) -> None:
                raise AssertionError("No execution should need stopping.")

        service = DiagnosticSessionService(
            _RecordingExecutionProvider(),
            _RecordingImpactServiceForGuardrails(),
        )
        self.addCleanup(service.reset)

        with self.assertRaises(InvalidTargetTask):
            service.start_session("task/001")
        with patch(
            "apps.diagnostics.services.get_ecs_discovery_provider",
        ) as discovery_provider:
            discovery_provider.return_value.get_running_task.return_value = {
                "last_status": "STOPPED",
                "cluster_arn": "arn:aws:ecs:region:123:cluster/workloads",
            }
            with self.assertRaises(IneligibleTargetTask):
                service.start_session("task-001")

    @override_settings(
        DCC_DIAGNOSTIC_MAX_DURATION_SECONDS=10,
        DCC_DIAGNOSTIC_MAX_ACTIVE_SESSIONS=2,
    )
    def test_max_duration_stops_worker_and_marks_session_failed(self) -> None:
        now = [datetime(2026, 1, 1, tzinfo=timezone.utc)]

        class _RecordingExecutionProvider:
            name = "inmemory"

            def __init__(self) -> None:
                self.stopped = []

            def start(
                self,
                session_id: str,
                target_task_id: str,
                target_cluster_arn: str | None = None,
            ) -> ExecutionReference:
                return ExecutionReference("inmemory", "worker-1")

            def stop(self, execution: ExecutionReference) -> None:
                self.stopped.append(execution.reference)

        provider = _RecordingExecutionProvider()
        service = DiagnosticSessionService(
            provider,
            _RecordingImpactServiceForGuardrails(),
            clock=lambda: now[0],
        )
        self.addCleanup(service.reset)
        session = service.start_session("task-001")

        now[0] += timedelta(seconds=10)
        active = service.get_active_session()
        expired = service.get_session(session.id)

        self.assertIsNone(active)
        self.assertEqual(expired.status, "failed")
        self.assertEqual(
            expired.error,
            "Diagnostic session exceeded the configured maximum duration.",
        )
        self.assertEqual(provider.stopped, ["worker-1"])

    @override_settings(
        DCC_DIAGNOSTIC_START_RATE_LIMIT=1,
        DCC_DIAGNOSTIC_START_RATE_WINDOW_SECONDS=3600,
    )
    def test_start_rate_limit_is_global(self) -> None:
        first = diagnostic_session_service.start_session("task-001")
        diagnostic_session_service.stop_session(first.id)

        with self.assertRaises(Throttled):
            diagnostic_session_service.start_session("task-002")

    @override_settings(DCC_DIAGNOSTIC_TARGET_COOLDOWN_SECONDS=60)
    def test_target_cooldown_returns_throttled_after_stop(self) -> None:
        first = diagnostic_session_service.start_session("task-001")
        diagnostic_session_service.stop_session(first.id)

        with self.assertRaises(Throttled):
            diagnostic_session_service.start_session("task-001")

    def test_failed_worker_cleanup_blocks_additional_starts(self) -> None:
        class _CleanupFailsProvider:
            name = "ecs"

            def start(
                self,
                session_id: str,
                target_task_id: str,
                target_cluster_arn: str | None = None,
            ) -> ExecutionReference:
                return ExecutionReference("ecs", "private-worker-ref")

            def stop(self, execution: ExecutionReference) -> None:
                raise DiagnosticProviderError("The diagnostic worker could not be stopped.")

        service = DiagnosticSessionService(
            _CleanupFailsProvider(),
            _RecordingImpactServiceForGuardrails(),
        )
        self.addCleanup(service.reset)
        started = service.start_session("task-001")

        with self.assertRaises(DiagnosticExecutionFailure):
            service.stop_session(started.id)
        self.assertEqual(service.get_session(started.id).status, "failed")
        with self.assertRaises(SessionConflict):
            service.start_session("task-002")

    def test_duration_uses_start_and_stop_timestamps(self) -> None:
        started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        stopped_at = started_at + timedelta(seconds=5)
        with patch("apps.diagnostics.services.datetime") as mocked_datetime:
            mocked_datetime.now.side_effect = [started_at, stopped_at]
            session = diagnostic_session_service.start_session("task-001")
            stopped = diagnostic_session_service.stop_session(session.id)

        self.assertEqual(stopped.duration_seconds, 5)

    def test_measurement_capture_follows_session_execution_lifecycle(self) -> None:
        events = []

        class _RecordingImpactService:
            def capture_baseline(self, session_id: str, task_id: str) -> None:
                events.append("baseline")

            def start_during_sampling(self, session_id: str) -> None:
                events.append("during")

            def capture_terminal(self, session_id: str) -> None:
                events.append("terminal")

            def reset(self) -> None:
                events.clear()

        class _RecordingExecutionProvider:
            name = "inmemory"

            def start(
                self,
                session_id: str,
                task_id: str,
                target_cluster_arn: str | None = None,
            ) -> ExecutionReference:
                events.append("execution_start")
                return ExecutionReference("inmemory", "reference")

            def stop(self, execution: ExecutionReference) -> None:
                events.append("execution_stop")

        service = DiagnosticSessionService(
            _RecordingExecutionProvider(),
            _RecordingImpactService(),
        )

        session = service.start_session("task-001")
        service.stop_session(session.id)

        self.assertEqual(
            events,
            ["baseline", "execution_start", "during", "execution_stop", "terminal"],
        )

    def test_dependency_provider_failure_does_not_block_session_start_or_stop(self) -> None:
        impact_service = DiagnosticImpactService(
            dependencies_reader=lambda: (_ for _ in ()).throw(
                RuntimeError("private dependency provider detail")
            ),
            sample_interval_seconds=60,
            max_during_samples=1,
        )
        service = DiagnosticSessionService(
            InMemoryDiagnosticExecutionProvider(),
            impact_service,
        )
        self.addCleanup(service.reset)

        session = service.start_session("task-001")
        self.assertEqual(session.status, "running")
        stopped = service.stop_session(session.id)

        self.assertEqual(stopped.status, "stopped")
        report = service.get_impact_report(session.id)
        self.assertEqual(report["session"]["id"], session.id)
        self.assertEqual(report["dependencies"]["session_id"], session.id)
        self.assertEqual(report["dependencies"]["availability"], "unavailable")
        self.assertNotIn("private dependency provider detail", str(report))


class DiagnosticImpactMeasurementTests(ECSDiscoveryTestMixin, TestCase):
    def make_session(self, session_id: str = "impact-session") -> DiagnosticSession:
        return DiagnosticSession(
            id=session_id,
            status="running",
            target_task_id="task-001",
            started_at=datetime.now(timezone.utc),
            stopped_at=None,
            duration_seconds=0,
            execution_provider="inmemory",
        )

    @staticmethod
    def metrics(cpu: float, memory: float, network: float) -> dict:
        return {
            "source": "mock",
            "cpu": {"current": cpu, "unit": "percent"},
            "memory": {"current": memory, "unit": "percent"},
            "network": {"current": network, "unit": "mbps"},
        }

    @staticmethod
    def dependency_snapshot(cpu: float, connections: float) -> list[dict]:
        return [
            {
                "resource_id": "orders-db",
                "resource_type": "rds",
                "resource_scope": "db_instance",
                "engine": "postgres",
                "status": "available",
                "availability": "available",
                "source": "mock",
                "metrics": {
                    "cpu_utilization": {
                        "current": cpu,
                        "peak": cpu + 2,
                        "unit": "percent",
                        "status": "available",
                    },
                    "database_connections": {
                        "current": connections,
                        "peak": connections + 2,
                        "unit": "count",
                        "status": "available",
                    },
                },
            }
        ]

    def test_dcc_classification_thresholds_are_deterministic(self) -> None:
        cases = (
            (0, "none"),
            (5, "none"),
            (5.1, "low"),
            (15, "low"),
            (15.1, "moderate"),
            (30, "moderate"),
            (30.1, "high"),
        )
        for percentage, expected in cases:
            with self.subTest(percentage=percentage):
                delta = {
                    "status": "available",
                    "absolute_delta": percentage,
                    "percentage_delta": percentage,
                }
                classification, _ = DiagnosticImpactService._classify({
                    "cpu": {"during_delta": delta, "post_delta": delta},
                })
                self.assertEqual(classification, expected)

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_captures_and_calculates_all_phases_and_correlates_logs(self) -> None:
        metric_responses = iter([
            self.metrics(20, 40, 100),
            self.metrics(30, 44, 120),
            self.metrics(50, 46, 130),
            self.metrics(10, 42, 110),
        ])
        session = self.make_session()
        logs = [
            {"id": "correlated", "diagnostic_session_id": session.id},
            {"id": "contextual", "diagnostic_session_id": "another-session"},
            {"id": "unassociated", "diagnostic_session_id": None},
        ]
        service = DiagnosticImpactService(
            metrics_reader=lambda _: next(metric_responses),
            logs_reader=lambda _: logs,
            sample_interval_seconds=60,
            max_during_samples=2,
        )
        self.addCleanup(service.reset)

        service.capture_baseline(session.id, session.target_task_id)
        service.start_during_sampling(session.id)
        service._capture_during(session.id)
        service.capture_terminal(session.id)
        report = service.get_report(session)

        self.assertEqual(report["measurements"]["availability"], "available")
        self.assertEqual(
            [report["measurements"]["phases"][phase]["status"] for phase in (
                "baseline", "during", "post"
            )],
            ["captured", "captured", "captured"],
        )
        cpu = report["measurements"]["metrics"]["cpu"]
        self.assertEqual(cpu["baseline"], 20)
        self.assertEqual(cpu["during"], 40)
        self.assertEqual(cpu["post"], 10)
        self.assertEqual(cpu["peak_during"], 50)
        self.assertEqual(cpu["during_delta"]["absolute_delta"], 20)
        self.assertEqual(cpu["during_delta"]["percentage_delta"], 100)
        self.assertEqual(cpu["post_delta"]["percentage_delta"], -50)
        self.assertEqual(report["measurements"]["phases"]["during"]["sample_count"], 2)
        memory = report["measurements"]["metrics"]["memory"]
        self.assertEqual(memory["during_delta"]["absolute_delta"], 5)
        self.assertEqual(memory["during_delta"]["percentage_delta"], 12.5)
        self.assertEqual(report["impact"]["classification"], "high")
        self.assertEqual(
            [entry["id"] for entry in report["logs"]["session_correlated"]],
            ["correlated"],
        )
        self.assertEqual(
            [entry["id"] for entry in report["logs"]["contextual"]],
            ["contextual", "unassociated"],
        )

    @override_settings(
        DCC_METRICS_PROVIDER="mock",
        DCC_DEPENDENCIES_PROVIDER="mock",
    )
    def test_dependency_measurements_are_session_scoped_and_separate_from_ecs_classification(
        self,
    ) -> None:
        dependency_responses = iter([
            self.dependency_snapshot(10, 20),
            self.dependency_snapshot(90, 80),
            self.dependency_snapshot(15, 25),
        ])
        service = DiagnosticImpactService(
            metrics_reader=lambda _: self.metrics(20, 30, 40),
            logs_reader=lambda _: [],
            dependencies_reader=lambda: next(dependency_responses),
            sample_interval_seconds=60,
            max_during_samples=1,
        )
        self.addCleanup(service.reset)
        session = self.make_session("dependency-session")

        service.capture_baseline(session.id, session.target_task_id)
        service.start_during_sampling(session.id)
        service.capture_terminal(session.id)
        report = service.get_report(session)

        self.assertEqual(report["dependencies"]["session_id"], session.id)
        self.assertEqual(report["dependencies"]["availability"], "available")
        self.assertEqual(
            [
                report["dependencies"]["phases"][phase]["status"]
                for phase in ("baseline", "during", "post")
            ],
            ["captured", "captured", "captured"],
        )
        database = report["dependencies"]["resources"]["rds:orders-db"]
        self.assertEqual(database["metrics"]["cpu_utilization"]["during"], 90)
        self.assertEqual(
            database["metrics"]["cpu_utilization"]["during_delta"]["absolute_delta"],
            80,
        )
        self.assertEqual(
            database["metrics"]["database_connections"]["peak_during"],
            82,
        )
        self.assertEqual(report["impact"]["classification"], "none")

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_dependency_failure_does_not_fail_measurement_or_diagnostic_lifecycle(self) -> None:
        service = DiagnosticImpactService(
            metrics_reader=lambda _: self.metrics(20, 30, 40),
            logs_reader=lambda _: [],
            dependencies_reader=lambda: (_ for _ in ()).throw(RuntimeError("private")),
            sample_interval_seconds=60,
            max_during_samples=1,
        )
        self.addCleanup(service.reset)
        session = self.make_session("dependency-unavailable-session")

        service.capture_baseline(session.id, session.target_task_id)
        service.start_during_sampling(session.id)
        service.capture_terminal(session.id)
        report = service.get_report(session)

        self.assertEqual(report["measurements"]["availability"], "available")
        self.assertEqual(report["impact"]["classification"], "none")
        self.assertEqual(report["dependencies"]["availability"], "unavailable")
        self.assertTrue(all(
            report["dependencies"]["phases"][phase]["status"] == "unavailable"
            for phase in ("baseline", "during", "post")
        ))
        self.assertNotIn("private", str(report))

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_missing_metrics_remain_unavailable_not_zero(self) -> None:
        service = DiagnosticImpactService(
            metrics_reader=lambda _: None,
            logs_reader=lambda _: [],
            sample_interval_seconds=60,
            max_during_samples=1,
        )
        self.addCleanup(service.reset)
        session = self.make_session()

        service.capture_baseline(session.id, session.target_task_id)
        service.start_during_sampling(session.id)
        service.capture_terminal(session.id)
        report = service.get_report(session)

        cpu = report["measurements"]["metrics"]["cpu"]
        self.assertIsNone(cpu["baseline"])
        self.assertIsNone(cpu["during"])
        self.assertIsNone(cpu["during_delta"]["absolute_delta"])
        self.assertEqual(cpu["during_delta"]["status"], "unavailable")
        self.assertEqual(report["impact"]["classification"], "unknown")
        self.assertEqual(report["measurements"]["availability"], "unavailable")

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_zero_baseline_does_not_create_percentage_or_false_classification(self) -> None:
        service = DiagnosticImpactService(
            metrics_reader=lambda _: self.metrics(0, 0, 0),
            logs_reader=lambda _: [],
            sample_interval_seconds=60,
            max_during_samples=1,
        )
        self.addCleanup(service.reset)
        session = self.make_session()

        service.capture_baseline(session.id, session.target_task_id)
        service.start_during_sampling(session.id)
        service.capture_terminal(session.id)
        report = service.get_report(session)

        cpu = report["measurements"]["metrics"]["cpu"]
        self.assertEqual(cpu["during_delta"]["absolute_delta"], 0)
        self.assertIsNone(cpu["during_delta"]["percentage_delta"])
        self.assertEqual(report["impact"]["classification"], "none")

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_nonzero_change_from_zero_baseline_is_not_misclassified(self) -> None:
        metric_responses = iter([
            self.metrics(0, 0, 0),
            self.metrics(1, 1, 1),
            self.metrics(1, 1, 1),
        ])
        service = DiagnosticImpactService(
            metrics_reader=lambda _: next(metric_responses),
            logs_reader=lambda _: [],
            sample_interval_seconds=60,
            max_during_samples=1,
        )
        self.addCleanup(service.reset)
        session = self.make_session()

        service.capture_baseline(session.id, session.target_task_id)
        service.start_during_sampling(session.id)
        service.capture_terminal(session.id)
        report = service.get_report(session)

        self.assertEqual(report["impact"]["classification"], "unknown")
        self.assertIn("zero baseline", report["impact"]["summary"])

    @override_settings(DCC_METRICS_PROVIDER="cloudwatch")
    def test_unconfigured_providers_are_distinguished_from_empty_logs(self) -> None:
        service = DiagnosticImpactService(
            metrics_reader=lambda _: (_ for _ in ()).throw(
                MetricsProviderError(
                    "Task resource metrics are unavailable because the CloudWatch provider is not configured."
                )
            ),
            logs_reader=lambda _: (_ for _ in ()).throw(
                LogsProviderError(
                    "Logs are unavailable because the Loki provider is not configured."
                )
            ),
            sample_interval_seconds=60,
            max_during_samples=1,
        )
        self.addCleanup(service.reset)
        session = self.make_session()

        service.capture_baseline(session.id, session.target_task_id)
        service.start_during_sampling(session.id)
        service.capture_terminal(session.id)
        report = service.get_report(session)

        self.assertEqual(
            report["measurements"]["phases"]["baseline"]["status"],
            "not_configured",
        )
        self.assertEqual(report["logs"]["availability"], "not_configured")
        self.assertIsNone(report["logs"]["summary"]["errors"])

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_empty_log_result_is_available_with_zero_counts(self) -> None:
        service = DiagnosticImpactService(
            metrics_reader=lambda _: self.metrics(10, 20, 30),
            logs_reader=lambda _: [],
            sample_interval_seconds=60,
            max_during_samples=1,
        )
        self.addCleanup(service.reset)
        session = self.make_session()

        service.capture_baseline(session.id, session.target_task_id)
        service.start_during_sampling(session.id)
        service.capture_terminal(session.id)
        report = service.get_report(session)

        self.assertEqual(report["logs"]["availability"], "available")
        self.assertEqual(report["logs"]["summary"]["session_correlated_count"], 0)
        self.assertEqual(report["logs"]["summary"]["contextual_count"], 0)

    @override_settings(DCC_METRICS_PROVIDER="mock")
    def test_metric_and_log_failures_return_safe_partial_report(self) -> None:
        service = DiagnosticImpactService(
            metrics_reader=lambda _: (_ for _ in ()).throw(
                RuntimeError("private provider exception")
            ),
            logs_reader=lambda _: (_ for _ in ()).throw(
                RuntimeError("private log exception")
            ),
            sample_interval_seconds=60,
            max_during_samples=1,
        )
        self.addCleanup(service.reset)
        session = self.make_session()

        service.capture_baseline(session.id, session.target_task_id)
        service.start_during_sampling(session.id)
        service.capture_terminal(session.id)
        report = service.get_report(session)

        self.assertEqual(report["impact"]["classification"], "unknown")
        self.assertEqual(report["logs"]["availability"], "unavailable")
        self.assertNotIn("private", str(report))
        self.assertTrue(report["limitations"])


class _FailingExecutionProvider:
    name = "ecs"

    def __init__(self, *, fail_start: bool = False, fail_stop: bool = False) -> None:
        self.fail_start = fail_start
        self.fail_stop = fail_stop

    def start(
        self,
        session_id: str,
        target_task_id: str,
        target_cluster_arn: str | None = None,
    ) -> ExecutionReference:
        if self.fail_start:
            raise DiagnosticProviderError(
                "The diagnostic worker could not be started."
            )
        return ExecutionReference("ecs", "private-task-arn", "private-cluster")

    def stop(self, execution: ExecutionReference) -> None:
        if self.fail_stop:
            raise DiagnosticProviderError(
                "The diagnostic worker could not be stopped."
            )


class DiagnosticExecutionFailureTests(ECSDiscoveryTestMixin, TestCase):
    def test_start_failure_records_failed_session_with_safe_error(self) -> None:
        service = DiagnosticSessionService(
            _FailingExecutionProvider(fail_start=True)
        )

        with self.assertRaises(DiagnosticExecutionFailure):
            service.start_session("task-001")

        session = service.list_sessions()[0]
        self.assertEqual(session.status, "failed")
        self.assertEqual(
            session.error,
            "The diagnostic worker could not be started.",
        )
        self.assertIsNotNone(session.stopped_at)
        self.assertIsNone(session.execution_reference)

    def test_raw_provider_exceptions_are_converted_to_safe_failed_sessions(self) -> None:
        class _ExplodingProvider:
            name = "ecs"

            def start(
                self,
                session_id: str,
                target_task_id: str,
                target_cluster_arn: str | None = None,
            ) -> ExecutionReference:
                raise RuntimeError("private-aws-details")

            def stop(self, execution: ExecutionReference) -> None:
                raise RuntimeError("private-aws-details")

        service = DiagnosticSessionService(_ExplodingProvider())

        with self.assertRaises(DiagnosticExecutionFailure):
            service.start_session("task-001")

        failed = service.list_sessions()[0]
        self.assertEqual(failed.status, "failed")
        self.assertEqual(
            failed.error,
            "The diagnostic execution provider failed.",
        )
        self.assertNotIn("private-aws-details", str(failed))

    def test_stop_failure_marks_session_failed_and_does_not_expose_arn(self) -> None:
        service = DiagnosticSessionService(
            _FailingExecutionProvider(fail_stop=True)
        )
        started = service.start_session("task-001")

        with self.assertRaises(DiagnosticExecutionFailure):
            service.stop_session(started.id)

        failed = service.get_session(started.id)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(
            failed.error,
            "The diagnostic worker could not be stopped.",
        )
        self.assertEqual(failed.execution_reference.reference, "private-task-arn")

        from apps.diagnostics.services import session_data

        response_data = session_data(failed)
        self.assertNotIn("private-task-arn", str(response_data))
        self.assertEqual(response_data["execution"]["provider"], "ecs")
