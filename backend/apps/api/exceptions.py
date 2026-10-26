import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler


logger = logging.getLogger(__name__)


def safe_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        return response

    request = context.get("request")
    logger.error(
        "Unhandled API exception (method=%s path=%s type=%s).",
        getattr(request, "method", "unknown"),
        getattr(request, "path", "unknown"),
        type(exc).__name__,
    )
    return Response(
        {"detail": "The request could not be completed safely."},
        status=500,
    )
