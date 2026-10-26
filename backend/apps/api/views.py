from typing import Any

from django.http import Http404
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_503_SERVICE_UNAVAILABLE
from rest_framework.views import APIView

from apps.api import providers
from apps.api.ecs_discovery import ECSDiscoveryError
from apps.api.dependencies import DependencyProviderError
from apps.api.dependencies_service import list_dependencies
from apps.api.logs import LogsProviderError, LogsQuery
from apps.api.logs_service import list_logs
from apps.api.metrics import MetricsProviderError
from apps.api.metrics_service import get_task_resources
from apps.api.serializers import (
    DependenciesQuerySerializer,
    DependencyListSerializer,
    DiagnosticImpactQuerySerializer,
    DiagnosticImpactReportSerializer,
    LogEntrySerializer,
    LogsQuerySerializer,
    ServiceSummarySerializer,
    TaskResourceMetricsSerializer,
    TaskSummarySerializer,
)
from apps.diagnostics.services import diagnostic_session_service
from apps.diagnostics.validation import is_valid_task_id


class ReadOnlyApiView(APIView):
    @staticmethod
    def serialized_response(
        serializer_class: type[serializers.Serializer],
        data: Any,
        *,
        many: bool = False,
    ) -> Response:
        serializer = serializer_class(data=data, many=many)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class ServiceListView(ReadOnlyApiView):
    def get(self, request: Request) -> Response:
        try:
            services = providers.get_services()
        except ECSDiscoveryError as error:
            return Response(
                {"detail": error.safe_message},
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        return self.serialized_response(
            ServiceSummarySerializer, services, many=True
        )


class TaskListView(ReadOnlyApiView):
    def get(self, request: Request) -> Response:
        try:
            tasks = providers.get_tasks()
        except ECSDiscoveryError as error:
            return Response(
                {"detail": error.safe_message},
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        return self.serialized_response(
            TaskSummarySerializer, tasks, many=True
        )


class TaskResourceView(ReadOnlyApiView):
    def get(self, request: Request, task_id: str) -> Response:
        if not is_valid_task_id(task_id):
            raise Http404("Task not found.")
        try:
            resources = get_task_resources(task_id)
        except ECSDiscoveryError as error:
            return Response(
                {"detail": error.safe_message},
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        except MetricsProviderError as error:
            return Response(
                {"detail": error.safe_message},
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        if resources is None:
            raise Http404("Task not found.")
        return self.serialized_response(TaskResourceMetricsSerializer, resources)


class DependencyListView(ReadOnlyApiView):
    def get(self, request: Request) -> Response:
        query_serializer = DependenciesQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        try:
            dependencies = list_dependencies(
                query_serializer.validated_data.get("resource_type")
            )
        except DependencyProviderError as error:
            return Response(
                {"detail": error.safe_message},
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        active_session = diagnostic_session_service.get_active_session()
        return self.serialized_response(
            DependencyListSerializer,
            {
                "measurement_context": (
                    "active_session_observation"
                    if active_session is not None
                    else "current_health"
                ),
                "diagnostic_session_id": (
                    active_session.id if active_session is not None else None
                ),
                "resources": dependencies,
            },
        )


class LogListView(ReadOnlyApiView):
    def get(self, request: Request) -> Response:
        query_serializer = LogsQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        query = LogsQuery(
            search=filters.get("search"),
            service=filters.get("service"),
            task_id=filters.get("task_id"),
            source=filters.get("source"),
            severity=(
                None if filters.get("severity") in {None, "ALL"}
                else filters["severity"]
            ),
            since_minutes=filters.get("since_minutes"),
            diagnostic_session_id=filters.get("diagnostic_session_id"),
        )
        try:
            logs = list_logs(query)
        except LogsProviderError as error:
            return Response(
                {"detail": error.safe_message},
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        return self.serialized_response(LogEntrySerializer, logs, many=True)


class DiagnosticImpactView(ReadOnlyApiView):
    def get(self, request: Request) -> Response:
        query_serializer = DiagnosticImpactQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        report = diagnostic_session_service.get_impact_report(
            query_serializer.validated_data.get("session_id")
        )
        return self.serialized_response(DiagnosticImpactReportSerializer, report)
