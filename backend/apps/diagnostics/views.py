from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.diagnostics.serializers import (
    CreateDiagnosticSessionSerializer,
    DiagnosticSessionSerializer,
)
from apps.diagnostics.services import diagnostic_session_service, session_data


class DiagnosticSessionCollectionView(APIView):
    def get(self, request: Request) -> Response:
        data = [
            session_data(session)
            for session in diagnostic_session_service.list_sessions()
        ]
        serializer = DiagnosticSessionSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def post(self, request: Request) -> Response:
        request_serializer = CreateDiagnosticSessionSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        session = diagnostic_session_service.start_session(
            request_serializer.validated_data["target_task_id"],
        )
        response_serializer = DiagnosticSessionSerializer(session_data(session))
        return Response(response_serializer.data, status=201)


class ActiveDiagnosticSessionView(APIView):
    def get(self, request: Request) -> Response:
        session = diagnostic_session_service.get_active_session()
        if session is None:
            return Response({"session": None})
        serializer = DiagnosticSessionSerializer(session_data(session))
        return Response({"session": serializer.data})


class DiagnosticSessionDetailView(APIView):
    def get(self, request: Request, session_id: str) -> Response:
        session = diagnostic_session_service.get_session(session_id)
        serializer = DiagnosticSessionSerializer(session_data(session))
        return Response(serializer.data)


class StopDiagnosticSessionView(APIView):
    def post(self, request: Request, session_id: str) -> Response:
        session = diagnostic_session_service.stop_session(session_id)
        serializer = DiagnosticSessionSerializer(session_data(session))
        return Response(serializer.data)
