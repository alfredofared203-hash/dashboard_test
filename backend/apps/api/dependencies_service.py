import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.api.dependencies import (
    DependencyObservabilityProvider,
    DependencyProviderError,
    DependencyType,
)
from apps.api.mock_dependencies_provider import MockDependencyObservabilityProvider


logger = logging.getLogger(__name__)


def get_dependency_provider() -> DependencyObservabilityProvider:
    provider_name = settings.DCC_DEPENDENCIES_PROVIDER
    if provider_name == "mock":
        return MockDependencyObservabilityProvider()
    if provider_name == "cloudwatch":
        from apps.api.cloudwatch_dependencies_provider import (
            CloudWatchDependencyObservabilityProvider,
        )

        try:
            return CloudWatchDependencyObservabilityProvider.from_settings()
        except ImproperlyConfigured:
            logger.warning("CloudWatch dependency configuration is invalid.")
            raise DependencyProviderError(
                "Dependency observations are unavailable because the CloudWatch provider is not configured."
            ) from None
    logger.warning("An unsupported dependency provider is configured.")
    raise DependencyProviderError(
        "Dependency observations are unavailable because the configured provider is unsupported."
    )


def list_dependencies(
    resource_type: DependencyType | None = None,
) -> list[dict]:
    return get_dependency_provider().list_dependencies(resource_type)


def list_dependency_impact_measurements() -> list[dict]:
    return get_dependency_provider().list_impact_dependencies()
