from typing import Any

from apps.api import providers


class MockTaskMetricsProvider:
    name = "mock"

    def get_task_resources(self, task_id: str) -> dict[str, Any] | None:
        metrics = providers.get_task_resources(task_id)
        if metrics is None:
            return None
        return {**metrics, "source": self.name}
