from django.urls import path
from django.urls import re_path

from apps.api.ecs_views import (
    ECSClusterListView,
    ECSServiceListView,
    ECSServiceTaskListView,
    ECSGlobalTaskDetailView,
    ECSGlobalTaskListView,
    ECSTaskDetailView,
    ECSTaskListView,
)
from apps.api.views import (
    DiagnosticImpactView,
    DependencyListView,
    LogListView,
    ServiceListView,
    TaskListView,
    TaskResourceView,
)

urlpatterns = [
    path("ecs/clusters/", ECSClusterListView.as_view(), name="ecs-cluster-list"),
    path("ecs/tasks/", ECSGlobalTaskListView.as_view(), name="ecs-task-global-list"),
    re_path(
        r"^ecs/tasks/(?P<task_id>.+)/$",
        ECSGlobalTaskDetailView.as_view(),
        name="ecs-task-global-detail",
    ),
    re_path(
        r"^ecs/clusters/(?P<cluster>.+)/services/(?P<service>.+)/tasks/$",
        ECSServiceTaskListView.as_view(),
        name="ecs-service-task-list",
    ),
    re_path(
        r"^ecs/clusters/(?P<cluster>.+)/services/$",
        ECSServiceListView.as_view(),
        name="ecs-service-list",
    ),
    re_path(
        r"^ecs/clusters/(?P<cluster>.+)/tasks/(?P<task_id>[^/]+)/$",
        ECSTaskDetailView.as_view(),
        name="ecs-task-detail",
    ),
    re_path(
        r"^ecs/clusters/(?P<cluster>.+)/tasks/$",
        ECSTaskListView.as_view(),
        name="ecs-task-list",
    ),
    path("services/", ServiceListView.as_view(), name="service-list"),
    path("tasks/", TaskListView.as_view(), name="task-list"),
    path(
        "tasks/<str:task_id>/resources/",
        TaskResourceView.as_view(),
        name="task-resources",
    ),
    path("dependencies/", DependencyListView.as_view(), name="dependency-list"),
    path("logs/", LogListView.as_view(), name="log-list"),
    path(
        "diagnostic-impact/",
        DiagnosticImpactView.as_view(),
        name="diagnostic-impact",
    ),
]
