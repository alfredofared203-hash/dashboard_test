from django.urls import path

from apps.diagnostics.views import (
    ActiveDiagnosticSessionView,
    DiagnosticSessionCollectionView,
    DiagnosticSessionDetailView,
    StopDiagnosticSessionView,
)

urlpatterns = [
    path(
        "",
        DiagnosticSessionCollectionView.as_view(),
        name="diagnostic-session-list",
    ),
    path(
        "active/",
        ActiveDiagnosticSessionView.as_view(),
        name="active-diagnostic-session",
    ),
    path(
        "<str:session_id>/stop/",
        StopDiagnosticSessionView.as_view(),
        name="diagnostic-session-stop",
    ),
    path(
        "<str:session_id>/",
        DiagnosticSessionDetailView.as_view(),
        name="diagnostic-session-detail",
    ),
]
