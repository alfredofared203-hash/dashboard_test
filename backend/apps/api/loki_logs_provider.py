from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
import hashlib
import json
import logging
import math
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.api.logs import LogsProviderError, LogsQuery


logger = logging.getLogger(__name__)

QUERY_WINDOW = timedelta(hours=1)
QUERY_LIMIT = 500
REQUEST_TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 4_000_000
UNKNOWN_FIELD_VALUE = "unknown"


@dataclass(frozen=True)
class LokiConfig:
    base_url: str
    bearer_token: str
    tenant_id: str

    @classmethod
    def from_settings(cls) -> "LokiConfig":
        base_url = settings.DCC_LOKI_URL.rstrip("/")
        try:
            parsed = urlparse(base_url)
            parsed.port
        except ValueError:
            raise ImproperlyConfigured("DCC_LOKI_URL is invalid.") from None
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ImproperlyConfigured("DCC_LOKI_URL is invalid.")
        return cls(
            base_url=base_url,
            bearer_token=settings.DCC_LOKI_BEARER_TOKEN,
            tenant_id=settings.DCC_LOKI_TENANT_ID,
        )


class LokiLogsProvider:
    name = "loki"

    def __init__(self, config: LokiConfig) -> None:
        self._config = config

    @classmethod
    def from_settings(cls) -> "LokiLogsProvider":
        return cls(LokiConfig.from_settings())

    def _query(self, filters: LogsQuery | None = None) -> list[Any]:
        end = datetime.now(timezone.utc)
        start = end - QUERY_WINDOW
        matchers = ['service=~".+"']
        if filters is not None:
            for label, value in (
                ("service", filters.service),
                ("task_id", filters.task_id),
                ("source", filters.source),
                ("diagnostic_session_id", filters.diagnostic_session_id),
            ):
                if value is not None:
                    matchers.append(f"{label}={json.dumps(value)}")
            if filters.since_minutes is not None:
                start = end - timedelta(minutes=filters.since_minutes)
        query = "{" + ",".join(matchers) + "}"
        if filters is not None and filters.search:
            escaped_search = re.escape(filters.search).replace(r"\ ", " ")
            query += f" |~ {json.dumps(f'(?i){escaped_search}')}"
        if filters is not None and filters.severity is not None:
            severity_values = {
                "DEBUG": "DEBUG|TRACE",
                "INFO": "INFO",
                "WARN": "WARN|WARNING",
                "ERROR": "ERROR|CRITICAL|FATAL",
            }[filters.severity]
            query += (
                ' | json | line_format "{{.severity}} {{.level}}" |~ '
                + json.dumps(f"(?i)(^| )({severity_values})( |$)")
            )
        params = urlencode(
            {
                "query": query,
                "start": int(start.timestamp() * 1_000_000_000),
                "end": int(end.timestamp() * 1_000_000_000),
                "limit": QUERY_LIMIT,
                "direction": "backward",
            }
        )
        endpoint = urljoin(f"{self._config.base_url}/", "loki/api/v1/query_range")
        headers = {"Accept": "application/json"}
        if self._config.bearer_token:
            headers["Authorization"] = f"Bearer {self._config.bearer_token}"
        if self._config.tenant_id:
            headers["X-Scope-OrgID"] = self._config.tenant_id
        try:
            request = Request(f"{endpoint}?{params}", headers=headers)
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError:
            logger.warning("Loki logs request returned an HTTP error.")
            raise LogsProviderError("The Loki logs provider could not return logs.") from None
        except (URLError, TimeoutError, OSError, HTTPException, ValueError):
            logger.warning("The Loki logs endpoint could not return a response.")
            raise LogsProviderError("The Loki logs provider could not return logs.") from None

        if len(body) > MAX_RESPONSE_BYTES:
            raise LogsProviderError("The Loki logs provider returned an oversized response.")
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise LogsProviderError("The Loki logs provider returned invalid JSON.") from None
        if (
            not isinstance(payload, dict)
            or payload.get("status") != "success"
            or not isinstance(payload.get("data"), dict)
            or payload["data"].get("resultType") != "streams"
            or not isinstance(payload["data"].get("result"), list)
        ):
            raise LogsProviderError("The Loki logs provider returned an invalid response.")
        return payload["data"]["result"]

    @staticmethod
    def _string_value(value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None

    @classmethod
    def _first_string(cls, *values: Any) -> str | None:
        for value in values:
            result = cls._string_value(value)
            if result is not None:
                return result
        return None

    @staticmethod
    def _severity(value: Any) -> str:
        if not isinstance(value, str):
            return "INFO"
        normalized = value.strip().upper()
        if normalized == "WARNING":
            return "WARN"
        if normalized in {"CRITICAL", "FATAL"}:
            return "ERROR"
        if normalized == "TRACE":
            return "DEBUG"
        if normalized in {"DEBUG", "INFO", "WARN", "ERROR"}:
            return normalized
        return "INFO"

    @staticmethod
    def _timestamp(value: Any) -> str:
        try:
            if isinstance(value, bool):
                raise ValueError
            timestamp_ns = int(value)
            seconds, nanoseconds = divmod(timestamp_ns, 1_000_000_000)
            timestamp = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(
                microsecond=nanoseconds // 1_000
            )
        except (OverflowError, OSError, TypeError, ValueError):
            raise LogsProviderError("The Loki logs provider returned an invalid timestamp.") from None
        return timestamp.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _metadata(value: Any, labels: dict[str, Any]) -> dict[str, Any] | None:
        metadata = value.get("metadata") if isinstance(value, dict) else None
        if isinstance(metadata, dict):
            return metadata
        known_fields = {
            "timestamp", "severity", "level", "service", "service_id", "task_id",
            "task_identifier", "source", "component", "message", "log",
            "diagnostic_session_id", "session_id", "trace_id", "request_id",
            "metadata",
        }
        if isinstance(value, dict):
            extra_fields = {
                key: item for key, item in value.items() if key not in known_fields
            }
            if extra_fields:
                return extra_fields
        label_fields = {
            key: item
            for key, item in labels.items()
            if key not in known_fields
        }
        extra_fields = label_fields
        return extra_fields or None

    def _normalize_entry(self, stream: Any, sample: Any) -> dict[str, Any]:
        if not isinstance(stream, dict) or not isinstance(stream.get("stream"), dict):
            raise LogsProviderError("The Loki logs provider returned invalid stream data.")
        labels = stream["stream"]
        if not isinstance(sample, list) or len(sample) != 2:
            raise LogsProviderError("The Loki logs provider returned invalid log data.")

        timestamp_ns, raw_line = sample
        if not isinstance(raw_line, str):
            raise LogsProviderError("The Loki logs provider returned invalid log content.")
        timestamp = self._timestamp(timestamp_ns)
        try:
            parsed_line = json.loads(raw_line)
        except json.JSONDecodeError:
            parsed_line = None
        log_data = parsed_line if isinstance(parsed_line, dict) else {}
        message = self._first_string(
            log_data.get("message"),
            log_data.get("log"),
            raw_line,
        )
        service = self._first_string(
            log_data.get("service"),
            log_data.get("service_id"),
            labels.get("service"),
        )
        task_id = self._first_string(
            log_data.get("task_id"),
            log_data.get("task_identifier"),
            labels.get("task_id"),
            labels.get("task_identifier"),
        )
        source = self._first_string(
            log_data.get("source"),
            log_data.get("component"),
            labels.get("source"),
            labels.get("component"),
            labels.get("container"),
        )
        severity = self._severity(
            self._first_string(
                log_data.get("severity"),
                log_data.get("level"),
                labels.get("severity"),
                labels.get("level"),
            )
        )
        session_id = self._first_string(
            log_data.get("diagnostic_session_id"),
            log_data.get("session_id"),
            labels.get("diagnostic_session_id"),
            labels.get("session_id"),
        )
        trace_id = self._first_string(
            log_data.get("trace_id"),
            log_data.get("request_id"),
            labels.get("trace_id"),
            labels.get("request_id"),
        )
        metadata = self._metadata(log_data, labels)
        identity = json.dumps(
            [timestamp_ns, labels, raw_line],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        entry = {
            "id": f"loki-{hashlib.sha256(identity).hexdigest()[:24]}",
            "timestamp": timestamp,
            "severity": severity,
            "service": service or UNKNOWN_FIELD_VALUE,
            "task_id": task_id or UNKNOWN_FIELD_VALUE,
            "source": source or UNKNOWN_FIELD_VALUE,
            "message": message,
            "diagnostic_session_id": session_id,
        }
        if trace_id is not None:
            entry["trace_id"] = trace_id
        if metadata is not None:
            entry["metadata"] = metadata
        return entry

    def list_logs(self, query: LogsQuery | None = None) -> list[dict[str, Any]]:
        streams = self._query(query)
        entries = []
        for stream in streams:
            if not isinstance(stream, dict) or not isinstance(stream.get("values"), list):
                raise LogsProviderError("The Loki logs provider returned invalid stream data.")
            entries.extend(
                self._normalize_entry(stream, sample)
                for sample in stream["values"]
            )
        entries.sort(key=lambda entry: entry["timestamp"], reverse=True)
        if query is not None:
            if query.search is not None:
                normalized_search = query.search.casefold()
                entries = [
                    entry
                    for entry in entries
                    if normalized_search in (
                        f"{entry['message']} {entry['service']} "
                        f"{entry['task_id']} {entry['source']}"
                    ).casefold()
                ]
            if query.severity is not None:
                entries = [
                    entry for entry in entries
                    if entry["severity"] == query.severity
                ]
        return entries[:QUERY_LIMIT]
