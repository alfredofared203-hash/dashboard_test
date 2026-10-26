import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.api.logs import LogsProvider, LogsProviderError, LogsQuery
from apps.api.mock_logs_provider import MockLogsProvider


logger = logging.getLogger(__name__)


def get_logs_provider() -> LogsProvider:
    provider_name = settings.DCC_LOGS_PROVIDER
    if provider_name == "mock":
        return MockLogsProvider()
    if provider_name == "loki":
        from apps.api.loki_logs_provider import LokiLogsProvider

        try:
            return LokiLogsProvider.from_settings()
        except ImproperlyConfigured:
            logger.warning("Loki logs configuration is incomplete or invalid.")
            raise LogsProviderError(
                "Logs are unavailable because the Loki provider is not configured."
            ) from None
    logger.warning("An unsupported logs provider is configured.")
    raise LogsProviderError(
        "Logs are unavailable because the configured provider is unsupported."
    )


def list_logs(query: LogsQuery | None = None) -> list[dict]:
    return get_logs_provider().list_logs(query)
