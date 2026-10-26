from django.http import JsonResponse


class ApiContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            if response.status_code == 500:
                response = JsonResponse(
                    {"detail": "The request could not be completed safely."},
                    status=500,
                )
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )
        return response
