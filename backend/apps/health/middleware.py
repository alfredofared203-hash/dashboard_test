from django.conf import settings
from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin


class LoadBalancerHealthHostMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest) -> None:
        if request.path_info == "/api/health/":
            trusted_host = "dcc-app.dcc-test.internal"
            if trusted_host not in settings.ALLOWED_HOSTS:
                trusted_host = settings.ALLOWED_HOSTS[0]
            request.META["HTTP_HOST"] = trusted_host
            request.META.pop("HTTP_X_FORWARDED_HOST", None)
