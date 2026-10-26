from datetime import datetime, timezone
from typing import Any

from apps.api import providers
from apps.api.logs import LogsQuery


class MockLogsProvider:
    name = "mock"

    def list_logs(self, query: LogsQuery | None = None) -> list[dict[str, Any]]:
        entries = providers.get_logs()
        if query is None:
            return entries

        cutoff = None
        if query.since_minutes is not None:
            cutoff = datetime.now(timezone.utc).timestamp() - query.since_minutes * 60
        def searchable(entry: dict[str, Any]) -> str:
            return (
                f"{entry['message']} {entry['service']} "
                f"{entry['task_id']} {entry['source']}"
            ).casefold()

        return [
            entry
            for entry in entries
            if (query.search is None or query.search.casefold() in searchable(entry))
            and (query.service is None or entry["service"] == query.service)
            and (query.task_id is None or entry["task_id"] == query.task_id)
            and (query.source is None or entry["source"] == query.source)
            and (query.severity is None or entry["severity"] == query.severity)
            and (
                query.diagnostic_session_id is None
                or entry["diagnostic_session_id"] == query.diagnostic_session_id
            )
            and (
                cutoff is None
                or datetime.fromisoformat(
                    entry["timestamp"].replace("Z", "+00:00")
                ).timestamp() >= cutoff
            )
        ]
