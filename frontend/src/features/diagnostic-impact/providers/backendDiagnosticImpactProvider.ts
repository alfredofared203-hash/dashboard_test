import { ApiError, requestJson } from "@/lib/api/client";
import type { DiagnosticSession } from "@/types/diagnosticSession";
import type {
  CalculatedImpactMetric,
  DependencyImpactReport,
  DependencyImpactResource,
  DependencyMeasurementPhase,
  DependencyPhaseMetric,
  DependencyPhaseResource,
  DiagnosticImpactReport,
  ImpactDelta,
  ImpactLogEntry,
  ImpactPhase,
  ImpactPhaseMetric,
} from "../types/report";
import type { DiagnosticImpactProvider } from "./diagnosticImpactProvider";

const phaseStatuses = [
  "captured",
  "partial",
  "unavailable",
  "not_configured",
  "not_captured",
] as const;
const classifications = ["none", "low", "moderate", "high", "unknown"] as const;
const sources = ["mock", "cloudwatch", "prometheus"] as const;
const metrics = ["cpu", "memory", "network"] as const;
const severities = ["DEBUG", "INFO", "WARN", "ERROR"] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isOneOf<const T extends readonly string[]>(
  value: unknown,
  allowed: T,
): value is T[number] {
  return typeof value === "string" && allowed.some((item) => item === value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function invalidReport(): never {
  throw new ApiError(
    "The DCC backend returned an invalid diagnostic impact report.",
    "invalid_response",
  );
}

function parsePhaseMetric(value: unknown): ImpactPhaseMetric {
  if (
    !isRecord(value)
    || !isFiniteNumber(value.value)
    || !isFiniteNumber(value.peak)
    || typeof value.unit !== "string"
  ) {
    return invalidReport();
  }
  return { value: value.value, peak: value.peak, unit: value.unit };
}

function parsePhase(value: unknown): ImpactPhase {
  if (
    !isRecord(value)
    || !isOneOf(value.status, phaseStatuses)
    || !(value.captured_at === null || (
      typeof value.captured_at === "string"
      && !Number.isNaN(Date.parse(value.captured_at))
    ))
    || !(value.source === null || isOneOf(value.source, sources))
    || !isRecord(value.metrics)
    || !Number.isInteger(value.sample_count)
    || Number(value.sample_count) < 0
  ) {
    return invalidReport();
  }
  const phaseMetrics: ImpactPhase["metrics"] = {};
  for (const name of metrics) {
    if (value.metrics[name] !== undefined) {
      phaseMetrics[name] = parsePhaseMetric(value.metrics[name]);
    }
  }
  if (value.detail !== undefined && typeof value.detail !== "string") {
    return invalidReport();
  }
  return {
    status: value.status,
    captured_at: value.captured_at,
    source: value.source,
    metrics: phaseMetrics,
    sample_count: Number(value.sample_count),
    ...(typeof value.detail === "string" ? { detail: value.detail } : {}),
  };
}

function parseDelta(value: unknown): ImpactDelta {
  if (
    !isRecord(value)
    || !isOneOf(value.status, ["available", "unavailable"] as const)
    || !(value.absolute_delta === null || isFiniteNumber(value.absolute_delta))
    || !(value.percentage_delta === null || isFiniteNumber(value.percentage_delta))
    || !isNullableString(value.reason)
  ) {
    return invalidReport();
  }
  return {
    status: value.status,
    absolute_delta: value.absolute_delta,
    percentage_delta: value.percentage_delta,
    reason: value.reason,
  };
}

function parseNullableCount(value: unknown): number | null {
  if (value === null) return null;
  if (!isFiniteNumber(value) || value < 0) return invalidReport();
  return value;
}

function parseCalculatedMetric(value: unknown): CalculatedImpactMetric {
  if (
    !isRecord(value)
    || typeof value.unit !== "string"
    || !(value.baseline === null || isFiniteNumber(value.baseline))
    || !(value.during === null || isFiniteNumber(value.during))
    || !(value.post === null || isFiniteNumber(value.post))
    || !(value.peak_during === null || isFiniteNumber(value.peak_during))
  ) {
    return invalidReport();
  }
  return {
    unit: value.unit,
    baseline: value.baseline,
    during: value.during,
    post: value.post,
    peak_during: value.peak_during,
    during_delta: parseDelta(value.during_delta),
    post_delta: parseDelta(value.post_delta),
  };
}

function parseDependencyPhaseMetric(value: unknown): DependencyPhaseMetric {
  if (
    !isRecord(value)
    || !(value.current === null || isFiniteNumber(value.current))
    || !(value.peak === null || isFiniteNumber(value.peak))
    || typeof value.unit !== "string"
    || !isOneOf(value.status, ["available", "unavailable"] as const)
  ) {
    return invalidReport();
  }
  return {
    current: value.current,
    peak: value.peak,
    unit: value.unit,
    status: value.status,
  };
}

function parseDependencyPhaseResource(value: unknown): DependencyPhaseResource {
  if (
    !isRecord(value)
    || typeof value.resource_id !== "string"
    || !isOneOf(value.resource_type, ["rds", "elasticache"] as const)
    || !isOneOf(
      value.resource_scope,
      ["db_instance", "cache_cluster", "replication_group"] as const,
    )
    || typeof value.engine !== "string"
    || typeof value.status !== "string"
    || !isOneOf(value.availability, ["available", "unavailable"] as const)
    || !isOneOf(value.source, ["mock", "cloudwatch"] as const)
    || !isRecord(value.metrics)
  ) {
    return invalidReport();
  }
  const parsedMetrics: DependencyPhaseResource["metrics"] = {};
  for (const [name, metric] of Object.entries(value.metrics)) {
    parsedMetrics[name] = parseDependencyPhaseMetric(metric);
  }
  return {
    resource_id: value.resource_id,
    resource_type: value.resource_type,
    resource_scope: value.resource_scope,
    engine: value.engine,
    status: value.status,
    availability: value.availability,
    source: value.source,
    metrics: parsedMetrics,
  };
}

function parseDependencyPhase(value: unknown): DependencyMeasurementPhase {
  if (
    !isRecord(value)
    || !isOneOf(
      value.status,
      ["captured", "empty", "unavailable", "not_configured", "not_captured"] as const,
    )
    || !(value.captured_at === null || (
      typeof value.captured_at === "string"
      && !Number.isNaN(Date.parse(value.captured_at))
    ))
    || !(value.source === null || isOneOf(value.source, ["mock", "cloudwatch"] as const))
    || !isRecord(value.resources)
    || !Number.isInteger(value.sample_count)
    || Number(value.sample_count) < 0
    || (value.detail !== undefined && typeof value.detail !== "string")
  ) {
    return invalidReport();
  }
  const resources: DependencyMeasurementPhase["resources"] = {};
  for (const [key, resource] of Object.entries(value.resources)) {
    resources[key] = parseDependencyPhaseResource(resource);
  }
  return {
    status: value.status,
    captured_at: value.captured_at,
    source: value.source,
    resources,
    sample_count: Number(value.sample_count),
    ...(typeof value.detail === "string" ? { detail: value.detail } : {}),
  };
}

function parseDependencyImpactResource(value: unknown): DependencyImpactResource {
  if (
    !isRecord(value)
    || typeof value.resource_id !== "string"
    || !isOneOf(value.resource_type, ["rds", "elasticache"] as const)
    || !isOneOf(
      value.resource_scope,
      ["db_instance", "cache_cluster", "replication_group"] as const,
    )
    || typeof value.engine !== "string"
    || typeof value.status !== "string"
    || !isRecord(value.metrics)
  ) {
    return invalidReport();
  }
  const parsedMetrics: DependencyImpactResource["metrics"] = {};
  for (const [name, metric] of Object.entries(value.metrics)) {
    parsedMetrics[name] = parseCalculatedMetric(metric);
  }
  return {
    resource_id: value.resource_id,
    resource_type: value.resource_type,
    resource_scope: value.resource_scope,
    engine: value.engine,
    status: value.status,
    metrics: parsedMetrics,
  };
}

function parseDependencyImpact(value: unknown, sessionId: string): DependencyImpactReport {
  if (
    !isRecord(value)
    || value.session_id !== sessionId
    || !isOneOf(value.availability, ["available", "partial", "unavailable"] as const)
    || !Array.isArray(value.sources)
    || !value.sources.every((source) => isOneOf(source, ["mock", "cloudwatch"] as const))
    || !isRecord(value.phases)
    || !isRecord(value.resources)
  ) {
    return invalidReport();
  }
  const phases = {
    baseline: parseDependencyPhase(value.phases.baseline),
    during: parseDependencyPhase(value.phases.during),
    post: parseDependencyPhase(value.phases.post),
  };
  const resources: DependencyImpactReport["resources"] = {};
  for (const [key, resource] of Object.entries(value.resources)) {
    resources[key] = parseDependencyImpactResource(resource);
  }
  return {
    session_id: value.session_id,
    availability: value.availability,
    sources: value.sources,
    phases,
    resources,
  };
}

function parseLog(value: unknown): ImpactLogEntry {
  if (
    !isRecord(value)
    || typeof value.id !== "string"
    || typeof value.timestamp !== "string"
    || Number.isNaN(Date.parse(value.timestamp))
    || !isOneOf(value.severity, severities)
    || typeof value.service !== "string"
    || typeof value.task_id !== "string"
    || typeof value.source !== "string"
    || typeof value.message !== "string"
    || !isNullableString(value.diagnostic_session_id)
    || (value.trace_id !== undefined && !isNullableString(value.trace_id))
    || (value.metadata !== undefined && !isRecord(value.metadata))
  ) {
    return invalidReport();
  }
  return {
    id: value.id,
    timestamp: value.timestamp,
    severity: value.severity,
    service: value.service,
    task_id: value.task_id,
    source: value.source,
    message: value.message,
    diagnostic_session_id: value.diagnostic_session_id,
    ...(value.trace_id !== undefined ? { trace_id: value.trace_id } : {}),
    ...(isRecord(value.metadata) ? { metadata: value.metadata } : {}),
  };
}

function parseLogs(value: unknown): DiagnosticImpactReport["logs"] {
  if (
    !isRecord(value)
    || !isOneOf(value.availability, ["available", "unavailable", "not_configured"] as const)
    || !Array.isArray(value.session_correlated)
    || !Array.isArray(value.contextual)
    || !isRecord(value.summary)
  ) {
    return invalidReport();
  }
  return {
    availability: value.availability,
    session_correlated: value.session_correlated.map(parseLog),
    contextual: value.contextual.map(parseLog),
    summary: {
      session_correlated_count: parseNullableCount(value.summary.session_correlated_count),
      errors: parseNullableCount(value.summary.errors),
      warnings: parseNullableCount(value.summary.warnings),
      contextual_count: parseNullableCount(value.summary.contextual_count),
    },
  };
}

function parseReport(value: unknown): DiagnosticImpactReport {
  if (
    !isRecord(value)
    || !isRecord(value.session)
    || typeof value.session.id !== "string"
    || !isOneOf(value.session.status, ["running", "stopped", "completed", "failed"] as const)
    || typeof value.session.target_task_id !== "string"
    || typeof value.session.started_at !== "string"
    || Number.isNaN(Date.parse(value.session.started_at))
    || !(value.session.stopped_at === null || typeof value.session.stopped_at === "string")
    || !isFiniteNumber(value.session.duration_seconds)
    || !isNullableString(value.session.error)
    || !isRecord(value.target)
    || typeof value.target.task_id !== "string"
    || !isNullableString(value.target.name)
    || !isNullableString(value.target.service_id)
    || !isNullableString(value.target.service_name)
    || !isRecord(value.measurements)
    || !isRecord(value.dependencies)
    || !isOneOf(value.measurements.availability, ["available", "partial", "unavailable"] as const)
    || !Array.isArray(value.measurements.sources)
    || !value.measurements.sources.every((source) => isOneOf(source, sources))
    || !isOneOf(
      value.measurements.scope,
      ["target_task", "configured_service_aggregate"] as const,
    )
    || !isRecord(value.measurements.phases)
    || !isRecord(value.measurements.metrics)
    || !isRecord(value.impact)
    || !isOneOf(value.impact.classification, classifications)
    || typeof value.impact.summary !== "string"
    || !isRecord(value.impact.thresholds)
    || !isFiniteNumber(value.impact.thresholds.none_max_percent)
    || !isFiniteNumber(value.impact.thresholds.low_max_percent)
    || !isFiniteNumber(value.impact.thresholds.moderate_max_percent)
    || !isRecord(value.api_testing)
    || value.api_testing.status !== "not_provided"
    || typeof value.api_testing.message !== "string"
    || !Array.isArray(value.limitations)
    || !value.limitations.every((item) => typeof item === "string")
    || typeof value.generated_at !== "string"
    || Number.isNaN(Date.parse(value.generated_at))
  ) {
    return invalidReport();
  }

  if (
    !isRecord(value.measurements.phases.baseline)
    || !isRecord(value.measurements.phases.during)
    || !isRecord(value.measurements.phases.post)
  ) {
    return invalidReport();
  }
  const phases = {
    baseline: parsePhase(value.measurements.phases.baseline),
    during: parsePhase(value.measurements.phases.during),
    post: parsePhase(value.measurements.phases.post),
  };
  const calculatedMetrics = {
    cpu: parseCalculatedMetric(value.measurements.metrics.cpu),
    memory: parseCalculatedMetric(value.measurements.metrics.memory),
    network: parseCalculatedMetric(value.measurements.metrics.network),
  };
  if (
    value.session.stopped_at !== null
    && Number.isNaN(Date.parse(value.session.stopped_at))
  ) {
    return invalidReport();
  }

  return {
    session: {
      id: value.session.id,
      status: value.session.status,
      target_task_id: value.session.target_task_id,
      started_at: value.session.started_at,
      stopped_at: value.session.stopped_at,
      duration_seconds: value.session.duration_seconds,
      error: value.session.error,
    },
    target: {
      task_id: value.target.task_id,
      name: value.target.name,
      service_id: value.target.service_id,
      service_name: value.target.service_name,
    },
    measurements: {
      availability: value.measurements.availability,
      scope: value.measurements.scope,
      sources: value.measurements.sources,
      phases,
      metrics: calculatedMetrics,
    },
    dependencies: parseDependencyImpact(value.dependencies, value.session.id),
    impact: {
      classification: value.impact.classification,
      summary: value.impact.summary,
      thresholds: {
        none_max_percent: value.impact.thresholds.none_max_percent,
        low_max_percent: value.impact.thresholds.low_max_percent,
        moderate_max_percent: value.impact.thresholds.moderate_max_percent,
      },
    },
    logs: parseLogs(value.logs),
    api_testing: {
      status: "not_provided",
      message: value.api_testing.message,
    },
    limitations: value.limitations,
    generated_at: value.generated_at,
  };
}

export const backendDiagnosticImpactProvider: DiagnosticImpactProvider = {
  async getReport(session: DiagnosticSession): Promise<DiagnosticImpactReport | null> {
    if (!session.sessionId) return null;
    const query = new URLSearchParams({ session_id: session.sessionId });
    return parseReport(await requestJson(`/api/diagnostic-impact/?${query.toString()}`));
  },
};
