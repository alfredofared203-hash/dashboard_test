export type ImpactClassification = "none" | "low" | "moderate" | "high" | "unknown";
export type ImpactPhaseName = "baseline" | "during" | "post";
export type ImpactPhaseStatus =
  | "captured"
  | "partial"
  | "unavailable"
  | "not_configured"
  | "not_captured";

export interface ImpactPhaseMetric {
  value: number;
  peak: number;
  unit: string;
}

export interface ImpactPhase {
  status: ImpactPhaseStatus;
  captured_at: string | null;
  source: "mock" | "cloudwatch" | "prometheus" | null;
  metrics: Partial<Record<"cpu" | "memory" | "network", ImpactPhaseMetric>>;
  sample_count: number;
  detail?: string;
}

export interface ImpactDelta {
  status: "available" | "unavailable";
  absolute_delta: number | null;
  percentage_delta: number | null;
  reason: string | null;
}

export interface CalculatedImpactMetric {
  unit: string;
  baseline: number | null;
  during: number | null;
  post: number | null;
  peak_during: number | null;
  during_delta: ImpactDelta;
  post_delta: ImpactDelta;
}

export interface DependencyPhaseMetric {
  current: number | null;
  peak: number | null;
  unit: string;
  status: "available" | "unavailable";
}

export interface DependencyPhaseResource {
  resource_id: string;
  resource_type: "rds" | "elasticache";
  resource_scope: "db_instance" | "cache_cluster" | "replication_group";
  engine: string;
  status: string;
  availability: "available" | "unavailable";
  source: "mock" | "cloudwatch";
  metrics: Record<string, DependencyPhaseMetric>;
}

export interface DependencyMeasurementPhase {
  status: "captured" | "empty" | "unavailable" | "not_configured" | "not_captured";
  captured_at: string | null;
  source: "mock" | "cloudwatch" | null;
  resources: Record<string, DependencyPhaseResource>;
  sample_count: number;
  detail?: string;
}

export interface DependencyImpactResource {
  resource_id: string;
  resource_type: "rds" | "elasticache";
  resource_scope: "db_instance" | "cache_cluster" | "replication_group";
  engine: string;
  status: string;
  metrics: Record<string, CalculatedImpactMetric>;
}

export interface DependencyImpactReport {
  session_id: string;
  availability: "available" | "partial" | "unavailable";
  sources: Array<"mock" | "cloudwatch">;
  phases: Record<ImpactPhaseName, DependencyMeasurementPhase>;
  resources: Record<string, DependencyImpactResource>;
}

export interface ImpactLogEntry {
  id: string;
  timestamp: string;
  severity: "DEBUG" | "INFO" | "WARN" | "ERROR";
  service: string;
  task_id: string;
  source: string;
  message: string;
  diagnostic_session_id: string | null;
  trace_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface DiagnosticImpactReport {
  session: {
    id: string;
    status: "running" | "stopped" | "completed" | "failed";
    target_task_id: string;
    started_at: string;
    stopped_at: string | null;
    duration_seconds: number;
    error: string | null;
  };
  target: {
    task_id: string;
    name: string | null;
    service_id: string | null;
    service_name: string | null;
  };
  measurements: {
    availability: "available" | "partial" | "unavailable";
    scope: "target_task" | "configured_service_aggregate";
    sources: Array<"mock" | "cloudwatch" | "prometheus">;
    phases: Record<ImpactPhaseName, ImpactPhase>;
    metrics: Record<"cpu" | "memory" | "network", CalculatedImpactMetric>;
  };
  dependencies: DependencyImpactReport;
  impact: {
    classification: ImpactClassification;
    summary: string;
    thresholds: {
      none_max_percent: number;
      low_max_percent: number;
      moderate_max_percent: number;
    };
  };
  logs: {
    availability: "available" | "unavailable" | "not_configured";
    session_correlated: ImpactLogEntry[];
    contextual: ImpactLogEntry[];
    summary: {
      session_correlated_count: number | null;
      errors: number | null;
      warnings: number | null;
      contextual_count: number | null;
    };
  };
  api_testing: {
    status: "not_provided";
    message: string;
  };
  limitations: string[];
  generated_at: string;
}

export type DiagnosticImpactLoadStatus = "loading" | "report" | "empty" | "error";
