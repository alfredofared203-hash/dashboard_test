from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request: Request) -> Response:
        return Response({"status": "ok", "service": "dcc-backend"})


class FrontendIndexView(APIView):
    def get(self, request: Request, *args, **kwargs) -> FileResponse:
        if settings.DEBUG:
            raise Http404("Frontend index is served by Vite during development.")

        index_path = Path(settings.STATIC_ROOT) / "index.html"
        if not index_path.exists():
            raise Http404("Frontend build artifacts are not available.")

        return FileResponse(index_path.open("rb"), content_type="text/html")
