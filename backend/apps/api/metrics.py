from typing import Any, Protocol


class MetricsProviderError(Exception):
    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


class TaskMetricsProvider(Protocol):
    name: str

    def get_task_resources(self, task_id: str) -> dict[str, Any] | None: ...
