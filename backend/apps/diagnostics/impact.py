from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import math
from threading import Event, Lock, Thread
from typing import Any, Callable

from django.conf import settings
from rest_framework.exceptions import NotFound

from apps.api.logs import LogsProviderError, LogsQuery
from apps.api.logs_service import list_logs
from apps.api.metrics import MetricsProviderError
from apps.api.metrics_service import get_task_resources
from apps.api.dependencies import DependencyProviderError
from apps.api.dependencies_service import list_dependency_impact_measurements
from apps.api.providers import get_services, get_tasks
from apps.diagnostics.models import DiagnosticSession


logger = logging.getLogger(__name__)

METRIC_NAMES = ("cpu", "memory", "network")
SAMPLE_INTERVAL_SECONDS = 5
MAX_DURING_SAMPLES = 60
SAMPLER_JOIN_TIMEOUT_SECONDS = 1
CAPTURE_LOCK_TIMEOUT_SECONDS = 1

# DCC application thresholds, not universal or scientifically validated limits.
IMPACT_NONE_MAX_PERCENT = 5
IMPACT_LOW_MAX_PERCENT = 15
IMPACT_MODERATE_MAX_PERCENT = 30

METRIC_SOURCE_NAMES = {"mock", "cloudwatch", "prometheus"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


@dataclass
class _SessionMeasurements:
    target_task_id: str
    baseline: dict[str, Any] | None = None
    during_samples: list[dict[str, Any]] = field(default_factory=list)
    during_attempted: bool = False
    during_last_failure: dict[str, Any] | None = None
    post: dict[str, Any] | None = None
    dependency_baseline: dict[str, Any] | None = None
    dependency_during_samples: list[dict[str, Any]] = field(default_factory=list)
    dependency_during_attempted: bool = False
    dependency_post: dict[str, Any] | None = None
    capture_lock: Lock = field(default_factory=Lock)
    sample_limit_reached: bool = False


@dataclass
class _SamplingControl:
    stop_event: Event
    thread: Thread


class DiagnosticImpactService:
    def __init__(
        self,
        metrics_reader: Callable[[str], dict[str, Any] | None] | None = None,
        logs_reader: Callable[[LogsQuery | None], list[dict[str, Any]]] | None = None,
        dependencies_reader: Callable[[], list[dict[str, Any]]] | None = None,
        *,
        sample_interval_seconds: float = SAMPLE_INTERVAL_SECONDS,
        max_during_samples: int = MAX_DURING_SAMPLES,
    ) -> None:
        self._metrics_reader = metrics_reader or get_task_resources
        self._logs_reader = logs_reader or list_logs
        self._dependencies_reader = (
            dependencies_reader or list_dependency_impact_measurements
        )
        self._sample_interval_seconds = sample_interval_seconds
        self._max_during_samples = max_during_samples
        self._records: dict[str, _SessionMeasurements] = {}
        self._sampling: dict[str, _SamplingControl] = {}
        self._lock = Lock()

    def capture_baseline(self, session_id: str, target_task_id: str) -> None:
        record = _SessionMeasurements(target_task_id=target_task_id)
        with self._lock:
            self._records[session_id] = record
        baseline = self._capture_snapshot(session_id, target_task_id)
        dependency_baseline = self._capture_dependency_snapshot(session_id)
        with self._lock:
            if self._records.get(session_id) is record:
                record.baseline = baseline
                record.dependency_baseline = dependency_baseline

    def start_during_sampling(self, session_id: str) -> None:
        with self._lock:
            record = self._records.get(session_id)
            if record is None or session_id in self._sampling:
                return
            if any(control.thread.is_alive() for control in self._sampling.values()):
                record.during_attempted = True
                record.during_last_failure = self._phase_unavailable(
                    source=self._configured_source(),
                    status="unavailable",
                    detail="A prior bounded measurement sampler is still stopping.",
                )
                return

        self._capture_during(session_id)
        self._capture_dependency_during(session_id)
        stop_event = Event()
        try:
            thread = Thread(
                target=self._sampling_loop,
                args=(session_id, stop_event),
                name=f"dcc-impact-{session_id[:8]}",
                daemon=True,
            )
            with self._lock:
                if session_id not in self._records or session_id in self._sampling:
                    return
                self._sampling[session_id] = _SamplingControl(stop_event, thread)
            thread.start()
        except Exception:
            with self._lock:
                self._sampling.pop(session_id, None)
                record = self._records.get(session_id)
                if record is not None:
                    record.during_last_failure = self._phase_unavailable(
                        source=self._configured_source(),
                        status="unavailable",
                        detail="The bounded measurement sampler could not be started.",
                    )
            logger.warning(
                "Diagnostic impact sampler could not be started (session_id=%s).",
                session_id,
            )

    def capture_terminal(self, session_id: str) -> None:
        with self._lock:
            control = self._sampling.get(session_id)
            record = self._records.get(session_id)
        if record is None:
            return
        if control is not None:
            control.stop_event.set()
            control.thread.join(timeout=SAMPLER_JOIN_TIMEOUT_SECONDS)
        if record.capture_lock.acquire(timeout=CAPTURE_LOCK_TIMEOUT_SECONDS):
            try:
                post = self._capture_snapshot(session_id, record.target_task_id)
                dependency_post = self._capture_dependency_snapshot(session_id)
            finally:
                record.capture_lock.release()
        else:
            post = self._phase_unavailable(
                source=self._configured_source(),
                status="unavailable",
                detail="A resource measurement was still in progress at session end.",
            )
            dependency_post = self._dependency_unavailable(
                "A dependency measurement was still in progress at session end."
            )
        with self._lock:
            if self._records.get(session_id) is record:
                record.post = post
                record.dependency_post = dependency_post

    def get_report(self, session: DiagnosticSession) -> dict[str, Any]:
        with self._lock:
            stored_record = self._records.get(session.id)
            if stored_record is None:
                raise NotFound("Diagnostic impact report not found.")
            record = _SessionMeasurements(
                target_task_id=stored_record.target_task_id,
                baseline=deepcopy(stored_record.baseline),
                during_samples=deepcopy(stored_record.during_samples),
                during_attempted=stored_record.during_attempted,
                during_last_failure=deepcopy(stored_record.during_last_failure),
                post=deepcopy(stored_record.post),
                dependency_baseline=deepcopy(stored_record.dependency_baseline),
                dependency_during_samples=deepcopy(stored_record.dependency_during_samples),
                dependency_during_attempted=stored_record.dependency_during_attempted,
                dependency_post=deepcopy(stored_record.dependency_post),
                sample_limit_reached=stored_record.sample_limit_reached,
            )

        baseline = deepcopy(record.baseline) if record.baseline else self._phase_unavailable(
            source=self._configured_source(),
            status="not_captured",
            detail="No baseline measurement was captured.",
        )
        during = self._during_phase(record)
        post = deepcopy(record.post) if record.post else self._phase_unavailable(
            source=self._configured_source(),
            status="not_captured",
            detail="No post-diagnostic measurement was captured.",
        )
        dependency_baseline = (
            deepcopy(record.dependency_baseline)
            if record.dependency_baseline
            else self._dependency_phase("not_captured", "No dependency baseline was captured.")
        )
        dependency_during = self._dependency_during_phase(record)
        dependency_post = (
            deepcopy(record.dependency_post)
            if record.dependency_post
            else self._dependency_phase("not_captured", "No dependency post measurement was captured.")
        )
        dependency_impact = self._calculate_dependency_impact(
            dependency_baseline,
            dependency_during,
            dependency_post,
        )
        metrics = self._calculate_metrics(baseline, during, post)
        classification, summary = self._classify(metrics)
        sources = sorted({
            phase["source"]
            for phase in (baseline, during, post)
            if phase.get("source") in METRIC_SOURCE_NAMES
        })
        task = next(
            (item for item in get_tasks() if item["id"] == session.target_task_id),
            None,
        )
        service = next(
            (
                item for item in get_services()
                if task is not None and item["id"] == task["service_id"]
            ),
            None,
        )

        logs, _ = self._session_logs(session)
        limitations = self._limitations(
            baseline,
            during,
            post,
            metrics,
            logs["availability"],
            task is None,
            record.sample_limit_reached,
            "cloudwatch" in sources,
        )
        limitations.extend(
            self._dependency_limitations(
                dependency_baseline,
                dependency_during,
                dependency_post,
                dependency_impact,
            )
        )
        phase_statuses = [phase["status"] for phase in (baseline, during, post)]
        availability = (
            "available" if all(status == "captured" for status in phase_statuses)
            else "partial" if any(status in {"captured", "partial"} for status in phase_statuses)
            else "unavailable"
        )
        current_time = _now()
        duration_seconds = session.duration_seconds
        if session.status == "running":
            duration_seconds = max(
                0,
                int((current_time - session.started_at).total_seconds()),
            )
        return {
            "session": {
                "id": session.id,
                "status": session.status,
                "target_task_id": session.target_task_id,
                "started_at": _isoformat(session.started_at),
                "stopped_at": _isoformat(session.stopped_at),
                "duration_seconds": duration_seconds,
                "error": session.error,
            },
            "target": {
                "task_id": session.target_task_id,
                "name": task["name"] if task else None,
                "service_id": task["service_id"] if task else None,
                "service_name": service["name"] if service else None,
            },
            "measurements": {
                "availability": availability,
                "scope": (
                    "configured_service_aggregate"
                    if "cloudwatch" in sources
                    else "target_task"
                ),
                "sources": sources,
                "phases": {
                    "baseline": baseline,
                    "during": during,
                    "post": post,
                },
                "metrics": metrics,
            },
            "dependencies": {
                "session_id": session.id,
                "availability": self._dependency_availability(
                    dependency_baseline,
                    dependency_during,
                    dependency_post,
                ),
                "sources": sorted({
                    phase["source"]
                    for phase in (
                        dependency_baseline,
                        dependency_during,
                        dependency_post,
                    )
                    if phase.get("source") in {"mock", "cloudwatch"}
                }),
                "phases": {
                    "baseline": dependency_baseline,
                    "during": dependency_during,
                    "post": dependency_post,
                },
                "resources": dependency_impact,
            },
            "impact": {
                "classification": classification,
                "summary": summary,
                "thresholds": {
                    "none_max_percent": IMPACT_NONE_MAX_PERCENT,
                    "low_max_percent": IMPACT_LOW_MAX_PERCENT,
                    "moderate_max_percent": IMPACT_MODERATE_MAX_PERCENT,
                },
            },
            "logs": logs,
            "api_testing": {
                "status": "not_provided",
                "message": "The backend has no API test results associated with this diagnostic session.",
            },
            "limitations": limitations,
            "generated_at": _isoformat(current_time),
        }

    def reset(self) -> None:
        with self._lock:
            controls = list(self._sampling.values())
            self._sampling.clear()
            self._records.clear()
        for control in controls:
            control.stop_event.set()
        for control in controls:
            control.thread.join(timeout=SAMPLER_JOIN_TIMEOUT_SECONDS)

    def _sampling_loop(self, session_id: str, stop_event: Event) -> None:
        try:
            for sample_index in range(max(0, self._max_during_samples - 1)):
                if stop_event.wait(self._sample_interval_seconds):
                    return
                self._capture_during(session_id)
                if (sample_index + 1) % 12 == 0:
                    self._capture_dependency_during(session_id)
            with self._lock:
                record = self._records.get(session_id)
                if record is not None:
                    record.sample_limit_reached = True
        finally:
            with self._lock:
                control = self._sampling.get(session_id)
                if control is not None and control.stop_event is stop_event:
                    self._sampling.pop(session_id, None)

    def _capture_during(self, session_id: str) -> None:
        with self._lock:
            record = self._records.get(session_id)
        if record is None:
            return
        if not record.capture_lock.acquire(timeout=CAPTURE_LOCK_TIMEOUT_SECONDS):
            with self._lock:
                record.during_attempted = True
                record.during_last_failure = self._phase_unavailable(
                    source=self._configured_source(),
                    status="unavailable",
                    detail="A resource measurement was already in progress.",
                )
            return
        try:
            snapshot = self._capture_snapshot(session_id, record.target_task_id)
        finally:
            record.capture_lock.release()
        with self._lock:
            if session_id not in self._records:
                return
            record.during_attempted = True
            if snapshot["status"] in {"captured", "partial"}:
                if len(record.during_samples) < self._max_during_samples:
                    record.during_samples.append(snapshot)
            else:
                record.during_last_failure = snapshot

    def _capture_snapshot(self, session_id: str, task_id: str) -> dict[str, Any]:
        source = self._configured_source()
        try:
            response = self._metrics_reader(task_id)
        except MetricsProviderError as error:
            status = (
                "not_configured"
                if "not configured" in error.safe_message.casefold()
                or "unsupported" in error.safe_message.casefold()
                else "unavailable"
            )
            return self._phase_unavailable(
                source=source,
                status=status,
                detail=error.safe_message,
            )
        except Exception:
            logger.warning(
                "Diagnostic impact metric capture failed (session_id=%s).",
                session_id,
            )
            return self._phase_unavailable(
                source=source,
                status="unavailable",
                detail="The configured metrics provider could not return a measurement.",
            )
        if response is None:
            return self._phase_unavailable(
                source=source,
                status="unavailable",
                detail="No resource measurement was returned for the target task.",
            )

        try:
            if not isinstance(response, dict):
                raise ValueError("Invalid metrics response.")
            metrics: dict[str, dict[str, Any]] = {}
            provider_source = response.get("source")
            if provider_source not in METRIC_SOURCE_NAMES:
                provider_source = source
            for name in METRIC_NAMES:
                resource = response.get(name)
                if not isinstance(resource, dict):
                    continue
                value = resource.get("current")
                unit = resource.get("unit")
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or not isinstance(unit, str)
                ):
                    continue
                metrics[name] = {
                    "value": float(value),
                    "peak": float(value),
                    "unit": unit,
                }
        except Exception:
            logger.warning(
                "Diagnostic impact metric response was invalid (session_id=%s).",
                session_id,
            )
            return self._phase_unavailable(
                source=source,
                status="unavailable",
                detail="The configured metrics provider returned an invalid measurement.",
            )
        status = "captured" if len(metrics) == len(METRIC_NAMES) else (
            "partial" if metrics else "unavailable"
        )
        return {
            "status": status,
            "captured_at": _isoformat(_now()),
            "source": provider_source,
            "metrics": metrics,
            "sample_count": 1,
            **(
                {"detail": "Some resource measurements were unavailable."}
                if status == "partial"
                else {}
            ),
        }

    def _capture_dependency_snapshot(self, session_id: str) -> dict[str, Any]:
        source = self._configured_dependency_source()
        try:
            resources = self._dependencies_reader()
            if not isinstance(resources, list):
                raise ValueError("Invalid dependency response.")
            normalized: dict[str, Any] = {}
            for resource in resources:
                if (
                    not isinstance(resource, dict)
                    or resource.get("resource_type") not in {"rds", "elasticache"}
                    or not isinstance(resource.get("resource_id"), str)
                    or not resource.get("resource_id")
                    or not isinstance(resource.get("metrics"), dict)
                ):
                    raise ValueError("Invalid dependency resource.")
                metrics: dict[str, dict[str, Any]] = {}
                for metric_name, metric in resource["metrics"].items():
                    if (
                        not isinstance(metric_name, str)
                        or not isinstance(metric, dict)
                        or not isinstance(metric.get("unit"), str)
                    ):
                        continue
                    current = metric.get("current")
                    peak = metric.get("peak")
                    if (
                        current is not None
                        and (
                            isinstance(current, bool)
                            or not isinstance(current, (int, float))
                            or not math.isfinite(current)
                        )
                    ):
                        current = None
                    if (
                        peak is not None
                        and (
                            isinstance(peak, bool)
                            or not isinstance(peak, (int, float))
                            or not math.isfinite(peak)
                        )
                    ):
                        peak = None
                    metrics[metric_name] = {
                        "current": float(current) if current is not None else None,
                        "peak": float(peak) if peak is not None else None,
                        "unit": metric["unit"],
                        "status": (
                            "available"
                            if current is not None and metric.get("status") == "available"
                            else "unavailable"
                        ),
                    }
                key = f"{resource['resource_type']}:{resource['resource_id']}"
                normalized[key] = {
                    "resource_id": resource["resource_id"],
                    "resource_type": resource["resource_type"],
                    "resource_scope": resource.get(
                        "resource_scope",
                        "db_instance" if resource["resource_type"] == "rds"
                        else "cache_cluster",
                    ),
                    "engine": (
                        resource["engine"]
                        if isinstance(resource.get("engine"), str)
                        else "unknown"
                    ),
                    "status": (
                        resource["status"]
                        if isinstance(resource.get("status"), str)
                        else "unknown"
                    ),
                    "availability": (
                        resource["availability"]
                        if resource.get("availability") in {"available", "unavailable"}
                        else "unavailable"
                    ),
                    "source": (
                        resource["source"]
                        if resource.get("source") in {"mock", "cloudwatch"}
                        else source
                    ),
                    "metrics": metrics,
                }
        except DependencyProviderError as error:
            status = (
                "not_configured"
                if "not configured" in error.safe_message.casefold()
                or "invalid" in error.safe_message.casefold()
                else "unavailable"
            )
            return self._dependency_phase(status, error.safe_message, source=source)
        except Exception:
            logger.warning(
                "Diagnostic impact dependency capture failed (session_id=%s).",
                session_id,
            )
            return self._dependency_phase(
                "unavailable",
                "The configured dependency provider could not return resource measurements.",
                source=source,
            )
        return {
            "status": "captured" if normalized else "empty",
            "captured_at": _isoformat(_now()),
            "source": source,
            "resources": normalized,
            "sample_count": 1,
            **(
                {"detail": "No dependency resources are configured or available."}
                if not normalized
                else {}
            ),
        }

    def _capture_dependency_during(self, session_id: str) -> None:
        with self._lock:
            record = self._records.get(session_id)
        if record is None:
            return
        if not record.capture_lock.acquire(timeout=CAPTURE_LOCK_TIMEOUT_SECONDS):
            with self._lock:
                record.dependency_during_attempted = True
            return
        try:
            snapshot = self._capture_dependency_snapshot(session_id)
        finally:
            record.capture_lock.release()
        with self._lock:
            if self._records.get(session_id) is record:
                record.dependency_during_attempted = True
                if snapshot["status"] in {"captured", "empty"}:
                    if len(record.dependency_during_samples) < self._max_during_samples:
                        record.dependency_during_samples.append(snapshot)

    def _dependency_during_phase(
        self,
        record: _SessionMeasurements,
    ) -> dict[str, Any]:
        if not record.dependency_during_samples:
            if record.dependency_during_attempted:
                return self._dependency_phase(
                    "unavailable",
                    "No during-diagnostic dependency measurements were available.",
                )
            return self._dependency_phase(
                "not_captured",
                "No during-diagnostic dependency measurement was captured.",
            )
        samples = record.dependency_during_samples
        keys = set().union(*(sample["resources"].keys() for sample in samples))
        resources: dict[str, Any] = {}
        for key in keys:
            examples = [
                sample["resources"][key]
                for sample in samples
                if key in sample["resources"]
            ]
            metrics: dict[str, Any] = {}
            metric_names = set().union(*(item["metrics"].keys() for item in examples))
            for metric_name in metric_names:
                readings = [
                    item["metrics"][metric_name]
                    for item in examples
                    if metric_name in item["metrics"]
                    and item["metrics"][metric_name]["current"] is not None
                ]
                template = next(
                    (
                        item["metrics"][metric_name]
                        for item in examples
                        if metric_name in item["metrics"]
                    ),
                    None,
                )
                if template is None:
                    continue
                metrics[metric_name] = {
                    "current": (
                        sum(item["current"] for item in readings) / len(readings)
                        if readings
                        else None
                    ),
                    "peak": (
                        max(item["peak"] for item in readings if item["peak"] is not None)
                        if any(item["peak"] is not None for item in readings)
                        else None
                    ),
                    "unit": template["unit"],
                    "status": "available" if readings else "unavailable",
                }
            template_resource = examples[-1]
            resources[key] = {
                **{
                    name: template_resource[name]
                    for name in (
                        "resource_id", "resource_type", "resource_scope",
                        "engine", "status", "source",
                    )
                },
                "availability": "available" if any(
                    metric["status"] == "available" for metric in metrics.values()
                ) else "unavailable",
                "metrics": metrics,
            }
        timestamps = [
            sample["captured_at"] for sample in samples if sample.get("captured_at")
        ]
        return {
            "status": "captured" if resources else "empty",
            "captured_at": timestamps[-1] if timestamps else None,
            "source": samples[-1].get("source"),
            "resources": resources,
            "sample_count": len(samples),
        }

    @staticmethod
    def _dependency_phase(
        status: str,
        detail: str,
        *,
        source: str | None = None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "captured_at": None,
            "source": source or DiagnosticImpactService._configured_dependency_source(),
            "resources": {},
            "sample_count": 0,
            "detail": detail,
        }

    @staticmethod
    def _dependency_unavailable(detail: str) -> dict[str, Any]:
        return DiagnosticImpactService._dependency_phase("unavailable", detail)

    @staticmethod
    def _configured_dependency_source() -> str | None:
        source = getattr(settings, "DCC_DEPENDENCIES_PROVIDER", None)
        return source if source in {"mock", "cloudwatch"} else None

    @staticmethod
    def _dependency_availability(*phases: dict[str, Any]) -> str:
        statuses = [phase["status"] for phase in phases]
        if all(status == "captured" for status in statuses):
            return "available"
        if any(status in {"captured", "empty"} for status in statuses):
            return "partial"
        return "unavailable"

    @staticmethod
    def _calculate_dependency_impact(
        baseline: dict[str, Any],
        during: dict[str, Any],
        post: dict[str, Any],
    ) -> dict[str, Any]:
        resource_keys = set(baseline["resources"]) | set(during["resources"]) | set(
            post["resources"]
        )
        results: dict[str, Any] = {}
        for key in resource_keys:
            phase_resources = {
                "baseline": baseline["resources"].get(key),
                "during": during["resources"].get(key),
                "post": post["resources"].get(key),
            }
            template = next(item for item in phase_resources.values() if item is not None)
            metric_names = set().union(*(
                item["metrics"].keys()
                for item in phase_resources.values()
                if item is not None
            ))
            metrics: dict[str, Any] = {}
            for metric_name in metric_names:
                values = {
                    phase: (
                        item["metrics"].get(metric_name, {}).get("current")
                        if item else None
                    )
                    for phase, item in phase_resources.items()
                }
                baseline_metric = phase_resources["baseline"]
                during_metric = phase_resources["during"]
                post_metric = phase_resources["post"]
                unit = next(
                    (
                        item["metrics"][metric_name]["unit"]
                        for item in phase_resources.values()
                        if item and metric_name in item["metrics"]
                    ),
                    "",
                )
                metrics[metric_name] = {
                    "unit": unit,
                    **values,
                    "peak_during": (
                        during_metric["metrics"].get(metric_name, {}).get("peak")
                        if during_metric else None
                    ),
                    "during_delta": DiagnosticImpactService._delta(
                        values["baseline"], values["during"]
                    ),
                    "post_delta": DiagnosticImpactService._delta(
                        values["baseline"], values["post"]
                    ),
                }
            results[key] = {
                "resource_id": template["resource_id"],
                "resource_type": template["resource_type"],
                "resource_scope": template["resource_scope"],
                "engine": template["engine"],
                "status": template["status"],
                "metrics": metrics,
            }
        return results

    @staticmethod
    def _dependency_limitations(*phases_and_results: Any) -> list[str]:
        baseline, during, post, results = phases_and_results
        limitations: list[str] = []
        for phase_name, phase in (
            ("baseline", baseline),
            ("during", during),
            ("post", post),
        ):
            if phase["status"] not in {"captured", "empty"}:
                limitations.append(
                    f"Dependency {phase_name} measurements are {phase['status']}."
                )
        resources = list(results.values())
        if resources and any(
            resource["resource_type"] == "elasticache"
            and "memory_usage_bytes" not in resource["metrics"]
            and "memory_usage_percent" not in resource["metrics"]
            for resource in resources
        ):
            limitations.append(
                "ElastiCache memory usage metrics are unavailable for one or more configured resources."
            )
        sources = {
            phase.get("source")
            for phase in (baseline, during, post)
            if phase.get("source")
        }
        if "mock" in sources:
            limitations.append(
                "Mock dependency observations are deterministic examples, not live AWS telemetry."
            )
        if "cloudwatch" in sources:
            limitations.append(
                "CloudWatch dependency metrics do not include RDS or ElastiCache resource health status."
            )
        return limitations

    @staticmethod
    def _phase_unavailable(
        *,
        source: str | None,
        status: str,
        detail: str,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "captured_at": None,
            "source": source,
            "metrics": {},
            "sample_count": 0,
            "detail": detail,
        }

    @staticmethod
    def _configured_source() -> str | None:
        source = getattr(settings, "DCC_METRICS_PROVIDER", None)
        return source if source in METRIC_SOURCE_NAMES else None

    def _during_phase(self, record: _SessionMeasurements) -> dict[str, Any]:
        if not record.during_samples:
            if record.during_last_failure:
                return deepcopy(record.during_last_failure)
            status = "unavailable" if record.during_attempted else "not_captured"
            detail = (
                "No during-diagnostic measurements were available."
                if record.during_attempted
                else "No during-diagnostic measurement was captured."
            )
            return self._phase_unavailable(
                source=self._configured_source(),
                status=status,
                detail=detail,
            )

        timestamps = [
            sample["captured_at"]
            for sample in record.during_samples
            if sample.get("captured_at")
        ]
        metrics: dict[str, dict[str, Any]] = {}
        for name in METRIC_NAMES:
            values = [
                sample["metrics"][name]
                for sample in record.during_samples
                if name in sample.get("metrics", {})
            ]
            if values:
                metrics[name] = {
                    "value": sum(item["value"] for item in values) / len(values),
                    "peak": max(item["peak"] for item in values),
                    "unit": values[-1]["unit"],
                }
        sources = {
            sample.get("source")
            for sample in record.during_samples
            if sample.get("source") in METRIC_SOURCE_NAMES
        }
        return {
            "status": "captured" if len(metrics) == len(METRIC_NAMES) else "partial",
            "captured_at": timestamps[-1] if timestamps else None,
            "source": next(iter(sources)) if len(sources) == 1 else None,
            "metrics": metrics,
            "sample_count": len(record.during_samples),
            **(
                {"detail": "The sampling limit was reached."}
                if record.sample_limit_reached
                else {}
            ),
        }

    @staticmethod
    def _calculate_metrics(
        baseline: dict[str, Any],
        during: dict[str, Any],
        post: dict[str, Any],
    ) -> dict[str, Any]:
        calculated: dict[str, Any] = {}
        for name in METRIC_NAMES:
            baseline_measurement = baseline.get("metrics", {}).get(name)
            during_measurement = during.get("metrics", {}).get(name)
            post_measurement = post.get("metrics", {}).get(name)
            baseline_value = (
                baseline_measurement["value"] if baseline_measurement else None
            )
            during_value = during_measurement["value"] if during_measurement else None
            post_value = post_measurement["value"] if post_measurement else None
            comparisons = {
                phase: DiagnosticImpactService._delta(baseline_value, value)
                for phase, value in (("during", during_value), ("post", post_value))
            }
            calculated[name] = {
                "unit": (
                    baseline_measurement
                    or during_measurement
                    or post_measurement
                    or {}
                ).get("unit", ""),
                "baseline": baseline_value,
                "during": during_value,
                "post": post_value,
                "peak_during": during_measurement["peak"] if during_measurement else None,
                "during_delta": comparisons["during"],
                "post_delta": comparisons["post"],
            }
        return calculated

    @staticmethod
    def _delta(baseline: float | None, measurement: float | None) -> dict[str, Any]:
        if baseline is None or measurement is None:
            return {
                "status": "unavailable",
                "absolute_delta": None,
                "percentage_delta": None,
                "reason": "A baseline or phase measurement is unavailable.",
            }
        absolute_delta = measurement - baseline
        if baseline == 0:
            return {
                "status": "available",
                "absolute_delta": absolute_delta,
                "percentage_delta": None,
                "reason": "Percentage delta is unavailable because the baseline is zero.",
            }
        return {
            "status": "available",
            "absolute_delta": absolute_delta,
            "percentage_delta": absolute_delta / abs(baseline) * 100,
            "reason": None,
        }

    @staticmethod
    def _classify(metrics: dict[str, Any]) -> tuple[str, str]:
        during_deltas = [
            metric["during_delta"]
            for metric in metrics.values()
            if metric["during_delta"]["status"] == "available"
        ]
        deltas = during_deltas or [
            metric["post_delta"]
            for metric in metrics.values()
            if metric["post_delta"]["status"] == "available"
        ]
        if not deltas:
            return (
                "unknown",
                "Impact is unknown because there are not enough measurements to compare.",
            )
        if any(
            delta["absolute_delta"] != 0
            and delta["percentage_delta"] is None
            for delta in deltas
        ):
            return (
                "unknown",
                "Impact is unknown because a non-zero change has a zero baseline and cannot be classified by percentage.",
            )
        valid_percentages = [
            abs(delta["percentage_delta"])
            for delta in deltas
            if delta["percentage_delta"] is not None
        ]
        if not valid_percentages:
            if all(delta["absolute_delta"] == 0 for delta in deltas):
                return "none", "No measured change was observed in comparable metrics."
            return (
                "unknown",
                "Impact is unknown because percentage changes cannot be calculated safely.",
            )
        maximum_change = max(valid_percentages)
        if maximum_change <= IMPACT_NONE_MAX_PERCENT:
            classification = "none"
        elif maximum_change <= IMPACT_LOW_MAX_PERCENT:
            classification = "low"
        elif maximum_change <= IMPACT_MODERATE_MAX_PERCENT:
            classification = "moderate"
        else:
            classification = "high"
        phase_name = "during" if during_deltas else "post"
        return (
            classification,
            f"DCC application classification based on the largest available absolute {phase_name} percentage delta ({maximum_change:.1f}%).",
        )

    def _session_logs(
        self,
        session: DiagnosticSession,
    ) -> tuple[dict[str, Any], str]:
        try:
            entries = self._logs_reader(LogsQuery(task_id=session.target_task_id))
        except LogsProviderError as error:
            logger.warning(
                "Diagnostic impact log retrieval failed (session_id=%s).",
                session.id,
            )
            status = (
                "not_configured"
                if "not configured" in error.safe_message.casefold()
                or "unsupported" in error.safe_message.casefold()
                else "unavailable"
            )
            return {
                "availability": status,
                "session_correlated": [],
                "contextual": [],
                "summary": {
                    "session_correlated_count": None,
                    "errors": None,
                    "warnings": None,
                    "contextual_count": None,
                },
            }, status
        except Exception:
            logger.warning(
                "Diagnostic impact log retrieval failed (session_id=%s).",
                session.id,
            )
            return {
                "availability": "unavailable",
                "session_correlated": [],
                "contextual": [],
                "summary": {
                    "session_correlated_count": None,
                    "errors": None,
                    "warnings": None,
                    "contextual_count": None,
                },
            }, "unavailable"

        correlated = [
            entry for entry in entries
            if entry.get("diagnostic_session_id") == session.id
        ]
        contextual = [
            entry for entry in entries
            if entry.get("diagnostic_session_id") != session.id
        ]
        return {
            "availability": "available",
            "session_correlated": correlated,
            "contextual": contextual,
            "summary": {
                "session_correlated_count": len(correlated),
                "errors": sum(entry.get("severity") == "ERROR" for entry in correlated),
                "warnings": sum(entry.get("severity") == "WARN" for entry in correlated),
                "contextual_count": len(contextual),
            },
        }, "available"

    @staticmethod
    def _limitations(
        baseline: dict[str, Any],
        during: dict[str, Any],
        post: dict[str, Any],
        metrics: dict[str, Any],
        logs_status: str,
        task_missing: bool,
        sample_limit_reached: bool,
        cloudwatch_aggregate: bool,
    ) -> list[str]:
        limitations: list[str] = [
            "This is an application-level measurement and comparison, not scientific causal analysis.",
            "Diagnostic impact does not prove that a measured change was caused by the diagnostic session.",
            "Session and measurement data are process-local and are lost when the backend process restarts.",
            "API test results are not collected or attributed to this diagnostic session.",
            "Phase timestamps are capture times; the normalized metrics contract does not include source sample timestamps.",
        ]
        for phase_name, phase in (
            ("baseline", baseline),
            ("during", during),
            ("post", post),
        ):
            if phase["status"] != "captured":
                limitations.append(
                    f"The {phase_name} phase is {phase['status']}: {phase.get('detail', 'measurements are incomplete')}."
                )
        if any(
            comparison["reason"] and comparison["absolute_delta"] is not None
            for metric in metrics.values()
            for comparison in (metric["during_delta"], metric["post_delta"])
        ):
            limitations.append(
                "Percentage change is unavailable for one or more metrics with a zero baseline."
            )
        if logs_status == "not_configured":
            limitations.append("The logs provider is not configured.")
        elif logs_status == "unavailable":
            limitations.append("Logs were unavailable when this report was generated.")
        else:
            limitations.append(
                "Logs without this session's exact ID are contextual only and are not attributed as diagnostic effects."
            )
        if cloudwatch_aggregate:
            limitations.append(
                "CloudWatch measurements are configured ECS service aggregates and are not specific to this target task."
            )
        if task_missing:
            limitations.append("The target task was not present in the current task inventory.")
        if sample_limit_reached:
            limitations.append(
                "During-diagnostic sampling stopped after reaching the bounded sample limit."
            )
        return limitations


diagnostic_impact_service = DiagnosticImpactService()
