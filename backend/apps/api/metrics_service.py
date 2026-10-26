import logging
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.api.metrics import MetricsProviderError, TaskMetricsProvider
from apps.api.mock_metrics_provider import MockTaskMetricsProvider


logger = logging.getLogger(__name__)


def get_task_metrics_provider() -> TaskMetricsProvider:
    provider_name = settings.DCC_METRICS_PROVIDER
    if provider_name == "mock":
        return MockTaskMetricsProvider()
    if provider_name == "cloudwatch":
        from apps.api.cloudwatch_metrics_provider import (
            CloudWatchTaskMetricsProvider,
        )

        try:
            return CloudWatchTaskMetricsProvider.from_settings()
        except ImproperlyConfigured:
            logger.warning("CloudWatch task metrics configuration is incomplete.")
            raise MetricsProviderError(
                "Task resource metrics are unavailable because the CloudWatch provider is not configured."
            ) from None
    if provider_name == "prometheus":
        from apps.api.prometheus_metrics_provider import (
            PrometheusTaskMetricsProvider,
        )

        try:
            return PrometheusTaskMetricsProvider.from_settings()
        except ImproperlyConfigured:
            logger.warning("Prometheus task metrics configuration is incomplete.")
            raise MetricsProviderError(
                "Task resource metrics are unavailable because the Prometheus provider is not configured."
            ) from None
    logger.warning("An unsupported task metrics provider is configured.")
    raise MetricsProviderError(
        "Task resource metrics are unavailable because the configured provider is unsupported."
    )


def get_task_resources(task_id: str) -> dict[str, Any] | None:
    return get_task_metrics_provider().get_task_resources(task_id)
