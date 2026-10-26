from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LogsQuery:
    search: str | None = None
    service: str | None = None
    task_id: str | None = None
    source: str | None = None
    severity: str | None = None
    since_minutes: int | None = None
    diagnostic_session_id: str | None = None


class LogsProviderError(Exception):
    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


class LogsProvider(Protocol):
    name: str

    def list_logs(self, query: LogsQuery | None = None) -> list[dict[str, Any]]: ...
