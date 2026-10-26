import logging
from typing import Protocol
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.diagnostics.models import ExecutionReference


logger = logging.getLogger(__name__)


class DiagnosticProviderError(Exception):
    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


class DiagnosticExecutionProvider(Protocol):
    name: str

    def start(
        self,
        session_id: str,
        target_task_id: str,
        target_cluster_arn: str | None = None,
    ) -> ExecutionReference: ...

    def stop(self, execution: ExecutionReference) -> None: ...


class InMemoryDiagnosticExecutionProvider:
    name = "inmemory"

    def __init__(self) -> None:
        self._running: set[str] = set()

    def start(
        self,
        session_id: str,
        target_task_id: str,
        target_cluster_arn: str | None = None,
    ) -> ExecutionReference:
        reference = str(uuid4())
        self._running.add(reference)
        return ExecutionReference(provider=self.name, reference=reference)

    def stop(self, execution: ExecutionReference) -> None:
        if execution.provider != self.name or execution.reference not in self._running:
            raise DiagnosticProviderError(
                "The in-memory diagnostic execution is not running."
            )
        self._running.remove(execution.reference)


def get_diagnostic_execution_provider() -> DiagnosticExecutionProvider:
    provider_name = settings.DCC_DIAGNOSTIC_PROVIDER
    if provider_name == "inmemory":
        return InMemoryDiagnosticExecutionProvider()
    if provider_name == "ecs":
        from apps.diagnostics.ecs_provider import ECSDiagnosticExecutionProvider

        return ECSDiagnosticExecutionProvider.from_settings()
    raise ImproperlyConfigured(
        "DCC_DIAGNOSTIC_PROVIDER must be either 'inmemory' or 'ecs'."
    )
