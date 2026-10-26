from dataclasses import dataclass
import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.diagnostics.models import ExecutionReference
from apps.diagnostics.providers import DiagnosticProviderError
from apps.diagnostics.validation import is_valid_session_id, is_valid_task_id


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ECSExecutionConfig:
    region: str
    cluster: str
    task_definition: str
    subnets: tuple[str, ...]
    security_groups: tuple[str, ...]
    container_name: str
    assign_public_ip: bool
    max_task_cpu: int = 1024
    max_task_memory_mib: int = 2048

    @classmethod
    def from_settings(cls) -> "ECSExecutionConfig":
        required = {
            "AWS_REGION": settings.AWS_REGION,
            "DCC_ECS_CLUSTER": settings.DCC_ECS_CLUSTER,
            "DCC_ECS_TASK_DEFINITION": settings.DCC_ECS_TASK_DEFINITION,
            "DCC_ECS_SUBNETS": settings.DCC_ECS_SUBNETS,
            "DCC_ECS_CONTAINER_NAME": settings.DCC_ECS_CONTAINER_NAME,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ImproperlyConfigured(
                "ECS diagnostic provider configuration is incomplete. "
                f"Set: {', '.join(missing)}."
            )

        return cls(
            region=settings.AWS_REGION,
            cluster=settings.DCC_ECS_CLUSTER,
            task_definition=settings.DCC_ECS_TASK_DEFINITION,
            subnets=tuple(settings.DCC_ECS_SUBNETS),
            security_groups=tuple(settings.DCC_ECS_SECURITY_GROUPS),
            container_name=settings.DCC_ECS_CONTAINER_NAME,
            assign_public_ip=settings.DCC_ECS_ASSIGN_PUBLIC_IP,
            max_task_cpu=settings.DCC_ECS_MAX_TASK_CPU,
            max_task_memory_mib=settings.DCC_ECS_MAX_TASK_MEMORY_MIB,
        )


class ECSDiagnosticExecutionProvider:
    name = "ecs"

    def __init__(self, config: ECSExecutionConfig, client: Any | None = None) -> None:
        self._config = config
        self._client = client

    @classmethod
    def from_settings(cls) -> "ECSDiagnosticExecutionProvider":
        return cls(ECSExecutionConfig.from_settings())

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = boto3.client("ecs", region_name=self._config.region)
        return self._client

    def start(
        self,
        session_id: str,
        target_task_id: str,
        target_cluster_arn: str | None = None,
    ) -> ExecutionReference:
        if not is_valid_session_id(session_id):
            raise DiagnosticProviderError("The diagnostic session ID is invalid.")
        if not is_valid_task_id(target_task_id):
            raise DiagnosticProviderError("The diagnostic target task ID is invalid.")
        self._validate_task_definition()
        request: dict[str, Any] = {
            "cluster": self._config.cluster,
            "taskDefinition": self._config.task_definition,
            "launchType": "FARGATE",
            "count": 1,
            "networkConfiguration": {
                "awsvpcConfiguration": {
                    "subnets": list(self._config.subnets),
                    "assignPublicIp": (
                        "ENABLED" if self._config.assign_public_ip else "DISABLED"
                    ),
                }
            },
            "overrides": {
                "containerOverrides": [{
                    "name": self._config.container_name,
                    "environment": [
                        {"name": "DIAGNOSTIC_SESSION_ID", "value": session_id},
                        {"name": "TARGET_TASK_ID", "value": target_task_id},
                        *(
                            [{"name": "TARGET_CLUSTER_ARN", "value": target_cluster_arn}]
                            if target_cluster_arn
                            else []
                        ),
                    ],
                }]
            },
        }
        if self._config.security_groups:
            request["networkConfiguration"]["awsvpcConfiguration"][
                "securityGroups"
            ] = list(self._config.security_groups)

        try:
            response = self._get_client().run_task(**request)
        except (BotoCoreError, ClientError):
            logger.warning(
                "ECS diagnostic worker launch failed (session_id=%s, target_task_id=%s).",
                session_id,
                target_task_id,
            )
            raise DiagnosticProviderError(
                "The diagnostic worker could not be started."
            ) from None

        failures = response.get("failures", [])
        tasks = response.get("tasks", [])
        task_arn = tasks[0].get("taskArn") if tasks else None
        if failures or not task_arn:
            logger.warning(
                "ECS diagnostic worker launch returned no task (session_id=%s, target_task_id=%s).",
                session_id,
                target_task_id,
            )
            raise DiagnosticProviderError(
                "The diagnostic worker could not be started."
            )

        return ExecutionReference(
            provider=self.name,
            reference=task_arn,
            cluster=self._config.cluster,
        )

    def _validate_task_definition(self) -> None:
        try:
            response = self._get_client().describe_task_definition(
                taskDefinition=self._config.task_definition,
            )
        except (BotoCoreError, ClientError):
            logger.warning("ECS diagnostic task definition validation failed.")
            raise DiagnosticProviderError(
                "The diagnostic worker configuration could not be validated."
            ) from None

        definition = response.get("taskDefinition")
        if not isinstance(definition, dict):
            raise DiagnosticProviderError(
                "The diagnostic worker configuration could not be validated."
            )
        if definition.get("status", "ACTIVE") != "ACTIVE":
            raise DiagnosticProviderError(
                "The configured diagnostic worker is not active."
            )
        containers = definition.get("containerDefinitions")
        matching_containers = [
            container
            for container in containers
            if isinstance(container, dict)
            and container.get("name") == self._config.container_name
        ] if isinstance(containers, list) else []
        if not matching_containers:
            raise DiagnosticProviderError(
                "The configured diagnostic worker container was not found."
            )
        credential_variable_names = {
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_SECURITY_TOKEN",
        }
        environment = matching_containers[0].get("environment", [])
        secrets = matching_containers[0].get("secrets", [])
        if not isinstance(environment, list) or not isinstance(secrets, list):
            raise DiagnosticProviderError(
                "The diagnostic worker environment configuration is invalid."
            )
        worker_variables = {
            item.get("name")
            for item in environment + secrets
            if isinstance(item, dict)
        }
        if credential_variable_names.intersection(worker_variables):
            raise DiagnosticProviderError(
                "AWS credentials must not be configured as worker environment variables."
            )
        try:
            cpu = int(definition["cpu"])
            memory_mib = int(definition["memory"])
        except (KeyError, TypeError, ValueError):
            raise DiagnosticProviderError(
                "The diagnostic worker resource configuration is invalid."
            ) from None
        if cpu <= 0 or memory_mib <= 0:
            raise DiagnosticProviderError(
                "The diagnostic worker resource configuration is invalid."
            )
        if (
            cpu > self._config.max_task_cpu
            or memory_mib > self._config.max_task_memory_mib
        ):
            raise DiagnosticProviderError(
                "The diagnostic worker exceeds the configured resource limits."
            )

    def stop(self, execution: ExecutionReference) -> None:
        if execution.provider != self.name or not execution.cluster:
            raise DiagnosticProviderError(
                "The ECS diagnostic execution reference is invalid."
            )
        try:
            response = self._get_client().stop_task(
                cluster=execution.cluster,
                task=execution.reference,
                reason="DCC diagnostic session stopped",
            )
        except (BotoCoreError, ClientError):
            logger.warning(
                "ECS diagnostic worker stop failed (cluster=%s).",
                execution.cluster,
            )
            raise DiagnosticProviderError(
                "The diagnostic worker could not be stopped."
            ) from None

        if response.get("failures") or not response.get("tasks"):
            logger.warning(
                "ECS diagnostic worker stop returned a failure (cluster=%s).",
                execution.cluster,
            )
            raise DiagnosticProviderError(
                "The diagnostic worker could not be stopped."
            )
