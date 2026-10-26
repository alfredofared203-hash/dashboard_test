from dataclasses import dataclass
import logging
from typing import Any, Iterable

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


logger = logging.getLogger(__name__)

DISCOVERY_UNAVAILABLE = "AWS ECS discovery is temporarily unavailable."


class ECSDiscoveryError(Exception):
    def __init__(self, safe_message: str = DISCOVERY_UNAVAILABLE) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


class ECSClusterNotConfigured(ECSDiscoveryError):
    pass


class ECSServiceNotFound(ECSDiscoveryError):
    pass


class ECSTaskAmbiguous(ECSDiscoveryError):
    pass


@dataclass(frozen=True)
class ECSDiscoveryConfig:
    region: str
    clusters: tuple[str, ...]

    @classmethod
    def from_settings(cls) -> "ECSDiscoveryConfig":
        if not settings.AWS_REGION:
            raise ImproperlyConfigured("AWS_REGION is required for ECS discovery.")
        clusters = tuple(dict.fromkeys(settings.DCC_ECS_CLUSTERS))
        if not clusters:
            raise ImproperlyConfigured(
                "DCC_ECS_CLUSTERS must contain at least one configured ECS cluster."
            )
        return cls(region=settings.AWS_REGION, clusters=clusters)


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _task_id(task_arn: str) -> str:
    return task_arn.rsplit("/", 1)[-1]


def _definition_parts(task_definition_arn: str) -> tuple[str, int | None]:
    family_revision = task_definition_arn.rsplit("/", 1)[-1]
    family, separator, revision = family_revision.rpartition(":")
    if not separator:
        return family_revision, None
    try:
        return family, int(revision)
    except ValueError:
        return family, None


class AWSECSDiscoveryProvider:
    """Read-only discovery limited to the ECS clusters explicitly configured for DCC."""

    def __init__(self, config: ECSDiscoveryConfig, client: Any | None = None) -> None:
        self._config = config
        self._client = client
        self._task_definitions: dict[str, dict[str, Any]] = {}

    @classmethod
    def from_settings(cls) -> "AWSECSDiscoveryProvider":
        return cls(ECSDiscoveryConfig.from_settings())

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                self._client = boto3.client(
                    "ecs",
                    region_name=self._config.region,
                )
            except (BotoCoreError, ValueError):
                logger.warning("AWS ECS client initialization failed.")
                raise ECSDiscoveryError() from None
        return self._client

    def _configured_cluster(self, cluster: str) -> str:
        requested_name = cluster.rsplit("/", 1)[-1]
        for configured in self._config.clusters:
            configured_name = configured.rsplit("/", 1)[-1]
            if (
                cluster == configured
                or requested_name == configured
                or requested_name == configured_name
            ):
                return configured
        raise ECSClusterNotConfigured("The requested ECS cluster is not configured.")

    def list_clusters(self) -> list[dict[str, Any]]:
        client = self._get_client()
        result: list[dict[str, Any]] = []
        try:
            for configured in _chunks(list(self._config.clusters), 100):
                response = client.describe_clusters(clusters=configured)
                if not isinstance(response, dict):
                    raise ECSDiscoveryError()
                if response.get("failures"):
                    raise ECSDiscoveryError()
                clusters = response.get("clusters")
                if not isinstance(clusters, list):
                    raise ECSDiscoveryError()
                for cluster in clusters:
                    if not isinstance(cluster, dict):
                        raise ECSDiscoveryError()
                    if not all(
                        isinstance(cluster.get(field), str) and cluster[field]
                        for field in ("clusterArn", "clusterName")
                    ):
                        raise ECSDiscoveryError()
                    result.append({
                        "cluster_arn": cluster.get("clusterArn", ""),
                        "cluster_name": cluster.get("clusterName", ""),
                        "status": cluster.get("status", "UNKNOWN"),
                    })
        except ECSDiscoveryError:
            raise
        except (BotoCoreError, ClientError, AttributeError, KeyError, TypeError):
            logger.warning("AWS ECS cluster discovery failed.")
            raise ECSDiscoveryError() from None
        return result

    def list_services(self, cluster: str) -> list[dict[str, Any]]:
        cluster_ref = self._configured_cluster(cluster)
        client = self._get_client()
        service_arns: list[str] = []
        token: str | None = None
        try:
            while True:
                request: dict[str, Any] = {
                    "cluster": cluster_ref,
                    "maxResults": 100,
                }
                if token:
                    request["nextToken"] = token
                response = client.list_services(**request)
                if not isinstance(response, dict):
                    raise ECSDiscoveryError()
                arns = response.get("serviceArns")
                if not isinstance(arns, list):
                    raise ECSDiscoveryError()
                service_arns.extend(arns)
                token = response.get("nextToken")
                if not token:
                    break
            result: list[dict[str, Any]] = []
            for arns in _chunks(service_arns, 10):
                if not arns:
                    continue
                response = client.describe_services(
                    cluster=cluster_ref,
                    services=arns,
                )
                if not isinstance(response, dict):
                    raise ECSDiscoveryError()
                if response.get("failures"):
                    raise ECSDiscoveryError()
                services = response.get("services")
                if not isinstance(services, list):
                    raise ECSDiscoveryError()
                for service in services:
                    if not isinstance(service, dict):
                        raise ECSDiscoveryError()
                    definition_arn = service.get("taskDefinition", "")
                    if not isinstance(definition_arn, str):
                        raise ECSDiscoveryError()
                    if (
                        not (
                            service.get("serviceArn") is None
                            or (
                                isinstance(service.get("serviceArn"), str)
                                and service["serviceArn"]
                            )
                        )
                        or not isinstance(service.get("serviceName"), str)
                        or not service["serviceName"]
                    ):
                        raise ECSDiscoveryError()
                    if not all(
                        service.get(field) is None
                        or (
                            isinstance(service.get(field), int)
                            and service[field] >= 0
                        )
                        for field in ("desiredCount", "runningCount", "pendingCount")
                    ):
                        raise ECSDiscoveryError()
                    family, revision = _definition_parts(definition_arn)
                    result.append({
                        "service_arn": service.get("serviceArn"),
                        "service_name": service["serviceName"],
                        "cluster_arn": service.get("clusterArn", cluster_ref),
                        "desired_count": service.get("desiredCount"),
                        "running_count": service.get("runningCount"),
                        "pending_count": service.get("pendingCount"),
                        "task_definition_arn": definition_arn,
                        "task_definition_family": family,
                        "task_definition_revision": revision,
                        "launch_type": service.get("launchType"),
                        "status": service.get("status"),
                    })
            return result
        except ECSDiscoveryError:
            raise
        except (BotoCoreError, ClientError, AttributeError, KeyError, TypeError):
            logger.warning("AWS ECS service discovery failed.")
            raise ECSDiscoveryError() from None

    def list_running_tasks(
        self,
        cluster: str,
        *,
        service_name: str | None = None,
        services: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        cluster_ref = self._configured_cluster(cluster)
        client = self._get_client()
        task_arns: list[str] = []
        token: str | None = None
        try:
            while True:
                request: dict[str, Any] = {
                    "cluster": cluster_ref,
                    "desiredStatus": "RUNNING",
                    "maxResults": 100,
                }
                if service_name:
                    request["serviceName"] = service_name
                if token:
                    request["nextToken"] = token
                response = client.list_tasks(**request)
                if not isinstance(response, dict):
                    raise ECSDiscoveryError()
                arns = response.get("taskArns")
                if not isinstance(arns, list):
                    raise ECSDiscoveryError()
                task_arns.extend(arns)
                token = response.get("nextToken")
                if not token:
                    break

            discovered_services = services if services is not None else self.list_services(cluster_ref)
            service_by_name = {
                service["service_name"]: service
                for service in discovered_services
            }
            result: list[dict[str, Any]] = []
            for arns in _chunks(task_arns, 100):
                if not arns:
                    continue
                response = client.describe_tasks(cluster=cluster_ref, tasks=arns)
                if not isinstance(response, dict):
                    raise ECSDiscoveryError()
                if response.get("failures"):
                    raise ECSDiscoveryError()
                tasks = response.get("tasks")
                if not isinstance(tasks, list):
                    raise ECSDiscoveryError()
                for task in tasks:
                    if not isinstance(task, dict):
                        raise ECSDiscoveryError()
                    if task.get("lastStatus") != "RUNNING":
                        continue
                    task_arn = task.get("taskArn")
                    if not isinstance(task_arn, str) or not task_arn:
                        raise ECSDiscoveryError()
                    task_cluster_arn = task.get("clusterArn", cluster_ref)
                    if not isinstance(task_cluster_arn, str) or not task_cluster_arn:
                        raise ECSDiscoveryError()
                    task_definition_arn = task.get("taskDefinitionArn", "")
                    if not isinstance(task_definition_arn, str) or not task_definition_arn:
                        raise ECSDiscoveryError()
                    definition = self._describe_task_definition(task_definition_arn)
                    family, revision = _definition_parts(task_definition_arn)
                    group = task.get("group", "")
                    if not isinstance(group, str):
                        raise ECSDiscoveryError()
                    service_name = (
                        group.removeprefix("service:")
                        if group.startswith("service:")
                        else ""
                    )
                    service = service_by_name.get(service_name)
                    result.append(self._task_data(
                        task,
                        task_cluster_arn,
                        family,
                        revision,
                        definition,
                        service,
                    ))
            return result
        except ECSDiscoveryError:
            raise
        except (BotoCoreError, ClientError, AttributeError, KeyError, TypeError):
            logger.warning("AWS ECS running-task discovery failed.")
            raise ECSDiscoveryError() from None

    def list_service_tasks(
        self,
        cluster: str,
        service: str,
    ) -> list[dict[str, Any]]:
        cluster_ref = self._configured_cluster(cluster)
        services = self.list_services(cluster_ref)
        selected = next(
            (
                item for item in services
                if service in {item["service_arn"], item["service_name"]}
            ),
            None,
        )
        if selected is None:
            raise ECSServiceNotFound("The requested ECS service was not found.")
        return self.list_running_tasks(
            cluster_ref,
            service_name=selected["service_name"],
            services=services,
        )

    def list_all_running_tasks(self) -> list[dict[str, Any]]:
        return [
            task
            for cluster in self._config.clusters
            for task in self.list_running_tasks(cluster)
        ]

    def get_running_task(
        self,
        task_id: str,
        *,
        cluster: str | None = None,
    ) -> dict[str, Any] | None:
        clusters = (
            [self._configured_cluster(cluster)]
            if cluster is not None
            else list(self._config.clusters)
        )
        matches = [
            task
            for cluster_ref in clusters
            for task in self.list_running_tasks(cluster_ref)
            if task["task_id"] == task_id
        ]
        if len(matches) > 1:
            raise ECSTaskAmbiguous(
                "The task ID exists in more than one configured cluster. Specify a cluster."
            )
        return matches[0] if matches else None

    def _describe_task_definition(self, task_definition_arn: str) -> dict[str, Any]:
        if not task_definition_arn:
            return {}
        if task_definition_arn not in self._task_definitions:
            response = self._get_client().describe_task_definition(
                taskDefinition=task_definition_arn,
            )
            if not isinstance(response, dict):
                raise ECSDiscoveryError()
            definition = response.get("taskDefinition")
            if not isinstance(definition, dict):
                raise ECSDiscoveryError()
            self._task_definitions[task_definition_arn] = definition
        return self._task_definitions[task_definition_arn]

    @staticmethod
    def _task_data(
        task: dict[str, Any],
        cluster_arn: str,
        family: str,
        revision: int | None,
        definition: dict[str, Any],
        service: dict[str, Any] | None,
    ) -> dict[str, Any]:
        task_definition_arn = task.get("taskDefinitionArn", "")
        container_definitions = {
            container.get("name"): container
            for container in definition.get("containerDefinitions", [])
            if isinstance(container, dict)
        }
        containers = []
        for container in task.get("containers", []):
            if not isinstance(container, dict):
                continue
            configured = container_definitions.get(container.get("name"), {})
            containers.append({
                "container_arn": container.get("containerArn"),
                "name": container.get("name", ""),
                "image": container.get("image", ""),
                "image_digest": container.get("imageDigest"),
                "last_status": container.get("lastStatus", "UNKNOWN"),
                "cpu": container.get("cpu", configured.get("cpu")),
                "memory": container.get("memory"),
                "memory_reservation": configured.get("memoryReservation"),
                "essential": configured.get("essential", True),
                "runtime_id": container.get("runtimeId"),
                "exit_code": container.get("exitCode"),
                "reason": container.get("reason"),
            })

        eni_id = None
        private_ip = None
        subnet_id = None
        security_group_ids: list[str] = []
        for attachment in task.get("attachments", []):
            if not isinstance(attachment, dict):
                continue
            for detail in attachment.get("details", []):
                if not isinstance(detail, dict):
                    continue
                key, value = detail.get("name"), detail.get("value")
                if key == "networkInterfaceId":
                    eni_id = value
                elif key == "privateIPv4Address":
                    private_ip = value
                elif key == "subnetId":
                    subnet_id = value
                elif key == "securityGroups" and isinstance(value, str):
                    security_group_ids = [
                        group.strip() for group in value.split(",") if group.strip()
                    ]

        launch_type = task.get("launchType")
        return {
            "task_arn": task["taskArn"],
            "task_id": _task_id(task["taskArn"]),
            "cluster_arn": cluster_arn,
            "service_arn": service.get("service_arn") if service else None,
            "service_name": service.get("service_name") if service else None,
            "task_definition_arn": task_definition_arn,
            "task_definition_family": family,
            "task_definition_revision": revision,
            "desired_status": task.get("desiredStatus", "UNKNOWN"),
            "last_status": task.get("lastStatus", "UNKNOWN"),
            "health_status": task.get("healthStatus", "UNKNOWN"),
            "started_at": task.get("startedAt"),
            "launch_type": launch_type,
            "cpu": task.get("cpu", definition.get("cpu")),
            "memory": task.get("memory", definition.get("memory")),
            "availability_zone": task.get("availabilityZone"),
            "network_mode": definition.get("networkMode"),
            "network": {
                "eni_id": eni_id,
                "private_ip": private_ip,
                "subnet_id": subnet_id,
                "security_group_ids": security_group_ids,
            },
            "containers": containers,
            "desired_count": service.get("desired_count") if service else None,
            "current_count": service.get("running_count") if service else None,
        }


def get_ecs_discovery_provider() -> AWSECSDiscoveryProvider:
    try:
        return AWSECSDiscoveryProvider.from_settings()
    except ImproperlyConfigured as error:
        raise ECSDiscoveryError(
            "AWS ECS discovery is not configured. Set AWS_REGION and DCC_ECS_CLUSTERS."
        ) from error
