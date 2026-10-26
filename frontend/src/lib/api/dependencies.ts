import { ApiError, requestJson } from "./client";

export type DependencyResourceType = "rds" | "elasticache";
export type DependencySource = "mock" | "cloudwatch";
export type DependencyResourceScope = "db_instance" | "cache_cluster" | "replication_group";

export interface DependencyMetric {
  current: number | null;
  peak: number | null;
  unit: string;
  status: "available" | "unavailable";
}

export interface DependencyResource {
  resource_id: string;
  resource_type: DependencyResourceType;
  resource_scope: DependencyResourceScope;
  engine: string;
  status: string;
  availability: "available" | "unavailable";
  source: DependencySource;
  metrics: Record<string, DependencyMetric>;
}

export interface DependencyList {
  measurement_context: "active_session_observation" | "current_health";
  diagnostic_session_id: string | null;
  resources: DependencyResource[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isResourceType(value: unknown): value is DependencyResourceType {
  return value === "rds" || value === "elasticache";
}

function isResourceScope(value: unknown): value is DependencyResourceScope {
  return value === "db_instance" || value === "cache_cluster" || value === "replication_group";
}

function isFiniteOrNull(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value));
}

function invalidResponse(): never {
  throw new ApiError(
    "The DCC backend returned invalid dependency observations.",
    "invalid_response",
  );
}

function parseMetric(value: unknown): DependencyMetric {
  if (
    !isRecord(value)
    || !isFiniteOrNull(value.current)
    || !isFiniteOrNull(value.peak)
    || typeof value.unit !== "string"
    || (value.status !== "available" && value.status !== "unavailable")
  ) {
    return invalidResponse();
  }
  return {
    current: value.current,
    peak: value.peak,
    unit: value.unit,
    status: value.status,
  };
}

function parseResource(value: unknown): DependencyResource {
  if (
    !isRecord(value)
    || typeof value.resource_id !== "string"
    || !isResourceType(value.resource_type)
    || !isResourceScope(value.resource_scope)
    || typeof value.engine !== "string"
    || typeof value.status !== "string"
    || (value.availability !== "available" && value.availability !== "unavailable")
    || (value.source !== "mock" && value.source !== "cloudwatch")
    || !isRecord(value.metrics)
  ) {
    return invalidResponse();
  }

  const metrics: Record<string, DependencyMetric> = {};
  for (const [name, metric] of Object.entries(value.metrics)) {
    metrics[name] = parseMetric(metric);
  }

  return {
    resource_id: value.resource_id,
    resource_type: value.resource_type,
    resource_scope: value.resource_scope,
    engine: value.engine,
    status: value.status,
    availability: value.availability,
    source: value.source,
    metrics,
  };
}

export async function listDependencies(
  resourceType: DependencyResourceType | "all" = "all",
): Promise<DependencyList> {
  const query = new URLSearchParams();
  if (resourceType !== "all") query.set("resource_type", resourceType);
  const suffix = query.size ? `?${query.toString()}` : "";
  const response = await requestJson(`/api/dependencies/${suffix}`);
  if (
    !isRecord(response)
    || (response.measurement_context !== "active_session_observation"
      && response.measurement_context !== "current_health")
    || !(response.diagnostic_session_id === null || typeof response.diagnostic_session_id === "string")
    || !Array.isArray(response.resources)
  ) {
    return invalidResponse();
  }
  return {
    measurement_context: response.measurement_context,
    diagnostic_session_id: response.diagnostic_session_id,
    resources: response.resources.map(parseResource),
  };
}
