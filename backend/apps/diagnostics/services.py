from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import logging
from threading import RLock
from typing import Any, Callable
from uuid import uuid4

from django.conf import settings
from rest_framework.exceptions import APIException, NotFound, Throttled

from apps.api.ecs_discovery import ECSDiscoveryError, get_ecs_discovery_provider
from apps.diagnostics.models import (
    DiagnosticSession,
    ExecutionReference,
    TerminalSessionStatus,
)
from apps.diagnostics.impact import DiagnosticImpactService, diagnostic_impact_service
from apps.diagnostics.providers import (
    DiagnosticExecutionProvider,
    DiagnosticProviderError,
    get_diagnostic_execution_provider,
)
from apps.diagnostics.validation import is_valid_session_id, is_valid_task_id


logger = logging.getLogger(__name__)

DIAGNOSTIC_TIMEOUT_ERROR = (
    "Diagnostic session exceeded the configured maximum duration."
)
UNKNOWN_WORKER_ERROR = "The diagnostic execution provider failed."


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionConflict(APIException):
    status_code = 409
    default_detail = "The diagnostic session cannot perform this transition."
    default_code = "session_conflict"


class InvalidTargetTask(APIException):
    status_code = 400
    default_detail = "Unknown task ID."
    default_code = "invalid_target_task"


class IneligibleTargetTask(APIException):
    status_code = 409
    default_detail = "The target task is not eligible for diagnostics."
    default_code = "ineligible_target_task"


class DiagnosticExecutionFailure(APIException):
    status_code = 502
    default_detail = "The diagnostic execution provider failed."
    default_code = "diagnostic_execution_failed"


class ECSDiscoveryUnavailable(APIException):
    status_code = 503
    default_detail = (
        "AWS ECS discovery is unavailable; diagnostics require a configured live ECS task."
    )
    default_code = "ecs_discovery_unavailable"


@dataclass
class _SessionRecord:
    session: DiagnosticSession


class DiagnosticSessionService:
    def __init__(
        self,
        execution_provider: DiagnosticExecutionProvider,
        impact_service: DiagnosticImpactService | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._execution_provider = execution_provider
        self._impact_service = impact_service or DiagnosticImpactService()
        self._clock = clock or _utc_now
        self._sessions: dict[str, _SessionRecord] = {}
        self._start_attempts: deque[datetime] = deque()
        self._stop_attempts: deque[datetime] = deque()
        self._target_last_started: dict[str, datetime] = {}
        self._cleanup_pending_session_ids: set[str] = set()
        self._lock = RLock()

    def start_session(
        self,
        target_task_id: str,
    ) -> DiagnosticSession:
        if not is_valid_task_id(target_task_id):
            raise InvalidTargetTask()
        try:
            task = get_ecs_discovery_provider().get_running_task(target_task_id)
        except ECSDiscoveryError:
            raise ECSDiscoveryUnavailable() from None
        if task is None:
            raise InvalidTargetTask()
        if task.get("last_status") != "RUNNING":
            raise IneligibleTargetTask()

        with self._lock:
            now = self._clock()
            self._expire_sessions_locked(now)
            active_sessions = [
                record.session
                for record in self._sessions.values()
                if (
                    record.session.status == "running"
                    or record.session.id in self._cleanup_pending_session_ids
                )
            ]
            if len(active_sessions) >= settings.DCC_DIAGNOSTIC_MAX_ACTIVE_SESSIONS:
                message = (
                    "A diagnostic session is already running."
                    if settings.DCC_DIAGNOSTIC_MAX_ACTIVE_SESSIONS == 1
                    else "The maximum number of active diagnostic sessions has been reached."
                )
                raise SessionConflict(message)
            cooldown_seconds = settings.DCC_DIAGNOSTIC_TARGET_COOLDOWN_SECONDS
            last_started = self._target_last_started.get(target_task_id)
            if (
                cooldown_seconds
                and last_started is not None
                and (now - last_started).total_seconds() < cooldown_seconds
            ):
                raise Throttled(
                    wait=max(
                        1,
                        cooldown_seconds - int((now - last_started).total_seconds()),
                    ),
                    detail="This target is in its diagnostic cooldown period.",
                )

            self._enforce_rate_limit(
                self._start_attempts,
                now,
                settings.DCC_DIAGNOSTIC_START_RATE_LIMIT,
                settings.DCC_DIAGNOSTIC_START_RATE_WINDOW_SECONDS,
            )
            self._start_attempts.append(now)

            session = DiagnosticSession(
                id=str(uuid4()),
                status="running",
                target_task_id=target_task_id,
                started_at=now,
                stopped_at=None,
                duration_seconds=0,
                execution_provider=self._execution_provider.name,
            )
            record = _SessionRecord(session)
            self._sessions[session.id] = record
            try:
                self._impact_service.capture_baseline(session.id, target_task_id)
                session.execution_reference = self._execution_provider.start(
                    session.id,
                    target_task_id,
                    task["cluster_arn"],
                )
                self._impact_service.start_during_sampling(session.id)
            except Exception as exc:
                logger.warning(
                    "Diagnostic start failed (session_id=%s target_task_id=%s provider=%s error_type=%s).",
                    session.id,
                    target_task_id,
                    session.execution_provider,
                    type(exc).__name__,
                )
                self._stop_execution_safely(session)
                self._mark_terminal(
                    record,
                    "failed",
                    error=self._safe_provider_error(exc),
                    finished_at=now,
                )
                self._capture_terminal_safely(session.id)
                raise DiagnosticExecutionFailure() from None
            self._target_last_started[target_task_id] = now
            return replace(session)

    def stop_session(
        self,
        session_id: str,
    ) -> DiagnosticSession:
        return self._finish_session(session_id, "stopped")

    def complete_session(self, session_id: str) -> DiagnosticSession:
        return self._finish_session(session_id, "completed")

    def fail_session(self, session_id: str) -> DiagnosticSession:
        return self._finish_session(session_id, "failed")

    def get_session(self, session_id: str) -> DiagnosticSession:
        if not is_valid_session_id(session_id):
            raise NotFound("Diagnostic session not found.")
        with self._lock:
            now = self._clock()
            self._expire_sessions_locked(now)
            record = self._sessions.get(session_id)
            if record is None:
                raise NotFound("Diagnostic session not found.")
            return replace(record.session)

    def list_sessions(self) -> list[DiagnosticSession]:
        with self._lock:
            self._expire_sessions_locked(self._clock())
            return [
                replace(record.session) for record in self._sessions.values()
            ]

    def get_active_session(self) -> DiagnosticSession | None:
        with self._lock:
            self._expire_sessions_locked(self._clock())
            session = next(
                (
                    record.session
                    for record in self._sessions.values()
                    if record.session.status == "running"
                ),
                None,
            )
            return replace(session) if session is not None else None

    def get_impact_report(self, session_id: str | None = None) -> dict[str, Any]:
        if session_id is not None and not is_valid_session_id(session_id):
            raise NotFound("Diagnostic session not found.")
        with self._lock:
            self._expire_sessions_locked(self._clock())
            if session_id is not None:
                record = self._sessions.get(session_id)
            else:
                record = next(
                    (
                        item for item in reversed(tuple(self._sessions.values()))
                        if item.session.status == "running"
                    ),
                    None,
                )
                if record is None and self._sessions:
                    record = next(reversed(self._sessions.values()))
            if record is None:
                raise NotFound("Diagnostic session not found.")
            session = replace(record.session)
        return self._impact_service.get_report(session)

    def transition_session(
        self,
        session_id: str,
        target_status: TerminalSessionStatus,
    ) -> DiagnosticSession:
        return self._finish_session(session_id, target_status)

    def reset(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._start_attempts.clear()
            self._stop_attempts.clear()
            self._target_last_started.clear()
            self._cleanup_pending_session_ids.clear()
            self._impact_service.reset()

    def _finish_session(
        self,
        session_id: str,
        target_status: TerminalSessionStatus,
    ) -> DiagnosticSession:
        if target_status not in {"stopped", "completed", "failed"}:
            raise SessionConflict("A session must transition to a terminal state.")
        if not is_valid_session_id(session_id):
            raise NotFound("Diagnostic session not found.")
        with self._lock:
            now = self._clock()
            self._expire_sessions_locked(now)
            record = self._sessions.get(session_id)
            if record is None:
                raise NotFound("Diagnostic session not found.")
            if record.session.status != "running":
                raise SessionConflict(
                    f"Cannot transition a {record.session.status} session to "
                    f"{target_status}."
                )

            if target_status == "stopped":
                self._enforce_rate_limit(
                    self._stop_attempts,
                    now,
                    settings.DCC_DIAGNOSTIC_STOP_RATE_LIMIT,
                    settings.DCC_DIAGNOSTIC_STOP_RATE_WINDOW_SECONDS,
                )
                self._stop_attempts.append(now)

            if (
                target_status == "stopped"
                and record.session.execution_reference is not None
            ):
                try:
                    self._execution_provider.stop(
                        record.session.execution_reference
                    )
                except Exception as exc:
                    self._cleanup_pending_session_ids.add(record.session.id)
                    logger.warning(
                        "Diagnostic stop failed (session_id=%s target_task_id=%s provider=%s error_type=%s).",
                        record.session.id,
                        record.session.target_task_id,
                        record.session.execution_provider,
                        type(exc).__name__,
                    )
                    self._mark_terminal(
                        record,
                        "failed",
                        error=self._safe_provider_error(exc),
                        finished_at=now,
                    )
                    self._capture_terminal_safely(session_id)
                    raise DiagnosticExecutionFailure() from None

            self._mark_terminal(record, target_status, finished_at=now)
            self._capture_terminal_safely(session_id)
            return replace(record.session)

    def _expire_sessions_locked(self, now: datetime) -> None:
        # Without a worker, expiration is enforced whenever session state is accessed.
        max_duration = settings.DCC_DIAGNOSTIC_MAX_DURATION_SECONDS
        for record in self._sessions.values():
            session = record.session
            if (
                session.status == "running"
                and (now - session.started_at).total_seconds() >= max_duration
            ):
                self._stop_execution_safely(session)
                self._mark_terminal(
                    record,
                    "failed",
                    error=DIAGNOSTIC_TIMEOUT_ERROR,
                    finished_at=now,
                )
                self._capture_terminal_safely(session.id)

    def _stop_execution_safely(self, session: DiagnosticSession) -> bool:
        if session.execution_reference is None:
            return True
        try:
            self._execution_provider.stop(session.execution_reference)
        except Exception as exc:
            self._cleanup_pending_session_ids.add(session.id)
            logger.warning(
                "Diagnostic worker cleanup failed (session_id=%s provider=%s error_type=%s).",
                session.id,
                session.execution_provider,
                type(exc).__name__,
            )
            return False
        self._cleanup_pending_session_ids.discard(session.id)
        return True

    def _capture_terminal_safely(self, session_id: str) -> None:
        try:
            self._impact_service.capture_terminal(session_id)
        except Exception as exc:
            logger.warning(
                "Diagnostic terminal measurements could not be captured (session_id=%s error_type=%s).",
                session_id,
                type(exc).__name__,
            )

    @staticmethod
    def _safe_provider_error(error: Exception) -> str:
        if isinstance(error, DiagnosticProviderError):
            return error.safe_message
        return UNKNOWN_WORKER_ERROR

    def _enforce_rate_limit(
        self,
        attempts: deque[datetime],
        now: datetime,
        limit: int,
        window_seconds: int,
    ) -> None:
        cutoff = now.timestamp() - window_seconds
        while attempts and attempts[0].timestamp() <= cutoff:
            attempts.popleft()
        if len(attempts) >= limit:
            wait = max(
                1,
                int(window_seconds - (now - attempts[0]).total_seconds()),
            )
            raise Throttled(wait=wait)

    def _mark_terminal(
        self,
        record: _SessionRecord,
        status: TerminalSessionStatus,
        *,
        error: str | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        finished_at = finished_at or self._clock()
        record.session.status = status
        record.session.stopped_at = finished_at
        record.session.duration_seconds = max(
            0, int((finished_at - record.session.started_at).total_seconds())
        )
        record.session.error = error


diagnostic_session_service = DiagnosticSessionService(
    get_diagnostic_execution_provider(),
    diagnostic_impact_service,
)


def session_data(session: DiagnosticSession) -> dict[str, Any]:
    return {
        "id": session.id,
        "status": session.status,
        "target_task_id": session.target_task_id,
        "started_at": session.started_at,
        "stopped_at": session.stopped_at,
        "duration_seconds": session.duration_seconds,
        "execution": (
            {
                "provider": session.execution_provider,
                "status": session.status,
            }
            if session.execution_provider
            else None
        ),
        "error": session.error,
    }
