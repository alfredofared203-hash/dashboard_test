from dataclasses import dataclass
from datetime import datetime
from typing import Literal


SessionStatus = Literal["running", "stopped", "completed", "failed"]
TerminalSessionStatus = Literal["stopped", "completed", "failed"]


@dataclass(frozen=True)
class ExecutionReference:
    provider: str
    reference: str
    cluster: str | None = None


@dataclass
class DiagnosticSession:
    id: str
    status: SessionStatus
    target_task_id: str
    started_at: datetime
    stopped_at: datetime | None
    duration_seconds: int
    execution_provider: str
    execution_reference: ExecutionReference | None = None
    error: str | None = None
