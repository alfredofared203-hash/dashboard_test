from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from apps.api.ecs_discovery import (
    ECSClusterNotConfigured,
    ECSDiscoveryError,
    ECSServiceNotFound,
    ECSTaskAmbiguous,
    get_ecs_discovery_provider,
)
from apps.api.serializers import (
    ECSClusterSerializer,
    ECSServiceSerializer,
    ECSTaskSerializer,
)
from apps.api.views import ReadOnlyApiView


def discovery_error_response(error: ECSDiscoveryError) -> Response:
    if isinstance(error, (ECSClusterNotConfigured, ECSServiceNotFound)):
        return Response(
            {"detail": "The requested ECS resource was not found."},
            status=HTTP_404_NOT_FOUND,
        )
    if isinstance(error, ECSTaskAmbiguous):
        return Response(
            {"detail": "The task ID is ambiguous. Specify a cluster."},
            status=HTTP_409_CONFLICT,
        )
    return Response(
        {"detail": error.safe_message},
        status=HTTP_503_SERVICE_UNAVAILABLE,
    )


class ECSClusterListView(ReadOnlyApiView):
    def get(self, request: Request) -> Response:
        try:
            clusters = get_ecs_discovery_provider().list_clusters()
        except ECSDiscoveryError as error:
            return Response(
                {"detail": error.safe_message},
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        return self.serialized_response(ECSClusterSerializer, clusters, many=True)


class ECSServiceListView(ReadOnlyApiView):
    def get(self, request: Request, cluster: str) -> Response:
        try:
            services = get_ecs_discovery_provider().list_services(cluster)
        except ECSDiscoveryError as error:
            return discovery_error_response(error)
        return self.serialized_response(ECSServiceSerializer, services, many=True)


class ECSServiceTaskListView(ReadOnlyApiView):
    def get(self, request: Request, cluster: str, service: str) -> Response:
        try:
            tasks = get_ecs_discovery_provider().list_service_tasks(cluster, service)
        except ECSDiscoveryError as error:
            return discovery_error_response(error)
        return self.serialized_response(ECSTaskSerializer, tasks, many=True)


class ECSTaskListView(ReadOnlyApiView):
    def get(self, request: Request, cluster: str) -> Response:
        try:
            tasks = get_ecs_discovery_provider().list_running_tasks(cluster)
        except ECSDiscoveryError as error:
            return discovery_error_response(error)
        return self.serialized_response(ECSTaskSerializer, tasks, many=True)


class ECSTaskDetailView(ReadOnlyApiView):
    def get(self, request: Request, cluster: str, task_id: str) -> Response:
        try:
            task = get_ecs_discovery_provider().get_running_task(
                task_id,
                cluster=cluster,
            )
        except ECSDiscoveryError as error:
            return discovery_error_response(error)
        if task is None:
            return Response({"detail": "The requested ECS task was not found."}, status=HTTP_404_NOT_FOUND)
        return self.serialized_response(ECSTaskSerializer, task)


class ECSGlobalTaskListView(ReadOnlyApiView):
    def get(self, request: Request) -> Response:
        try:
            tasks = get_ecs_discovery_provider().list_all_running_tasks()
        except ECSDiscoveryError as error:
            return discovery_error_response(error)
        return self.serialized_response(ECSTaskSerializer, tasks, many=True)


class ECSGlobalTaskDetailView(ReadOnlyApiView):
    def get(self, request: Request, task_id: str) -> Response:
        cluster = request.query_params.get("cluster")
        try:
            task = get_ecs_discovery_provider().get_running_task(
                task_id,
                cluster=cluster,
            )
        except ECSDiscoveryError as error:
            return discovery_error_response(error)
        if task is None:
            return Response(
                {"detail": "The requested ECS task was not found."},
                status=HTTP_404_NOT_FOUND,
            )
        return self.serialized_response(ECSTaskSerializer, task)
