from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path, re_path

from apps.health.views import FrontendIndexView

urlpatterns = [
    path("api/", include("apps.health.urls")),
    path(
        "api/diagnostic-sessions/",
        include("apps.diagnostics.urls"),
    ),
    path("api/", include("apps.api.urls")),
]

urlpatterns += staticfiles_urlpatterns()

if not settings.DEBUG:
    urlpatterns += [
        re_path(
            r"^(?!api/|admin/|assets/|static/).*",
            FrontendIndexView.as_view(),
        )
    ]
