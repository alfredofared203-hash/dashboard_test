import { ApiError, requestJson } from "./client";

export interface TaskSummary {
  id: string;
  service_id: string;
  name: string;
  status: string;
  health: string;
  desired_count: number | null;
  current_count: number | null;
  availability: string;
  task_arn: string;
  cluster_arn: string;
  service_name: string | null;
  task_definition_family: string;
  task_definition_revision: number | null;
  desired_status: string;
  last_status: string;
  health_status: string;
  started_at: string | null;
  launch_type: string | null;
  cpu: string | null;
  memory: string | null;
  availability_zone: string | null;
  network_mode: string | null;
  network: {
    eni_id: string | null;
    private_ip: string | null;
    subnet_id: string | null;
    security_group_ids: string[];
  };
  containers: Array<{
    name: string;
    image: string;
    image_digest: string | null;
    last_status: string;
    cpu: number | null;
    memory: number | null;
    memory_reservation: number | null;
    essential: boolean;
    runtime_id: string | null;
  }>;
}

export interface ECSServiceSummary {
  id: string;
  name: string;
  cluster_arn: string;
  desired_count: number | null;
  running_count: number | null;
  pending_count: number | null;
  status: "healthy" | "warning" | "critical" | "unknown";
}

export interface ECSInventory {
  services: ECSServiceSummary[];
  tasks: TaskSummary[];
}

interface MetricValues {
  baseline: number;
  current: number;
  peak: number;
  unit: string;
}

export type CpuMetrics = MetricValues;
export type MemoryMetrics = MetricValues;
export type NetworkMetrics = MetricValues;

export interface ResourceImpact {
  status: string;
  cpu_delta: number;
  memory_delta: number;
  network_delta: number;
}

export interface ResourceMetrics {
  task_id: string;
  cpu: CpuMetrics;
  memory: MemoryMetrics;
  network: NetworkMetrics;
  impact: ResourceImpact;
  source: "mock" | "cloudwatch" | "prometheus";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isCount(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function parseContainerSummary(value: unknown): TaskSummary["containers"][number] {
  if (
    !isRecord(value)
    || !isNonEmptyString(value.name)
    || typeof value.image !== "string"
    || !(value.image_digest === null || isNonEmptyString(value.image_digest))
    || !isNonEmptyString(value.last_status)
    || !(value.cpu === null || isCount(value.cpu))
    || !(value.memory === null || isCount(value.memory))
    || !(value.memory_reservation === null || isCount(value.memory_reservation))
    || typeof value.essential !== "boolean"
    || !(value.runtime_id === null || isNonEmptyString(value.runtime_id))
  ) {
    throw new ApiError("The DCC backend returned an invalid ECS container.", "invalid_response");
  }
  return {
    name: value.name,
    image: value.image,
    image_digest: value.image_digest,
    last_status: value.last_status,
    cpu: value.cpu,
    memory: value.memory,
    memory_reservation: value.memory_reservation,
    essential: value.essential,
    runtime_id: value.runtime_id,
  };
}

function parseTaskSummary(value: unknown): TaskSummary {
  if (
    !isRecord(value)
    || !isNonEmptyString(value.id)
    || !isNonEmptyString(value.service_id)
    || !isNonEmptyString(value.name)
    || !isNonEmptyString(value.status)
    || !isNonEmptyString(value.health)
    || !(value.desired_count === null || isCount(value.desired_count))
    || !(value.current_count === null || isCount(value.current_count))
    || !isNonEmptyString(value.availability)
    || !isNonEmptyString(value.task_arn)
    || !isNonEmptyString(value.cluster_arn)
    || !(value.service_name === null || isNonEmptyString(value.service_name))
    || !isNonEmptyString(value.task_definition_family)
    || !(value.task_definition_revision === null || isCount(value.task_definition_revision))
    || !isNonEmptyString(value.desired_status)
    || !isNonEmptyString(value.last_status)
    || !isNonEmptyString(value.health_status)
    || !(value.started_at === null || isNonEmptyString(value.started_at))
    || !(value.launch_type === null || isNonEmptyString(value.launch_type))
    || !(value.cpu === null || isNonEmptyString(value.cpu))
    || !(value.memory === null || isNonEmptyString(value.memory))
    || !(value.availability_zone === null || isNonEmptyString(value.availability_zone))
    || !(value.network_mode === null || isNonEmptyString(value.network_mode))
    || !isRecord(value.network)
    || !(value.network.eni_id === null || isNonEmptyString(value.network.eni_id))
    || !(value.network.private_ip === null || isNonEmptyString(value.network.private_ip))
    || !(value.network.subnet_id === null || isNonEmptyString(value.network.subnet_id))
    || !Array.isArray(value.network.security_group_ids)
    || !value.network.security_group_ids.every(isNonEmptyString)
    || !Array.isArray(value.containers)
  ) {
    throw new ApiError(
      "The DCC backend returned an invalid task record.",
      "invalid_response",
    );
  }

  return {
    id: value.id,
    service_id: value.service_id,
    name: value.name,
    status: value.status,
    health: value.health,
    desired_count: value.desired_count,
    current_count: value.current_count,
    availability: value.availability,
    task_arn: value.task_arn,
    cluster_arn: value.cluster_arn,
    service_name: value.service_name,
    task_definition_family: value.task_definition_family,
    task_definition_revision: value.task_definition_revision,
    desired_status: value.desired_status,
    last_status: value.last_status,
    health_status: value.health_status,
    started_at: value.started_at,
    launch_type: value.launch_type,
    cpu: value.cpu,
    memory: value.memory,
    availability_zone: value.availability_zone,
    network_mode: value.network_mode,
    network: {
      eni_id: value.network.eni_id,
      private_ip: value.network.private_ip,
      subnet_id: value.network.subnet_id,
      security_group_ids: value.network.security_group_ids,
    },
    containers: value.containers.map(parseContainerSummary),
  };
}

function parseMetricValues(value: unknown): MetricValues {
  if (
    !isRecord(value)
    || !isFiniteNumber(value.baseline)
    || !isFiniteNumber(value.current)
    || !isFiniteNumber(value.peak)
    || !isNonEmptyString(value.unit)
  ) {
    throw new ApiError(
      "The DCC backend returned invalid resource metrics.",
      "invalid_response",
    );
  }
  return {
    baseline: value.baseline,
    current: value.current,
    peak: value.peak,
    unit: value.unit,
  };
}

function parseResourceMetrics(value: unknown): ResourceMetrics {
  if (
    !isRecord(value)
    || !isNonEmptyString(value.task_id)
    || !isRecord(value.impact)
    || (
      value.source !== "mock"
      && value.source !== "cloudwatch"
      && value.source !== "prometheus"
    )
  ) {
    throw new ApiError(
      "The DCC backend returned invalid resource metrics.",
      "invalid_response",
    );
  }

  const impact = value.impact;
  if (
    !isNonEmptyString(impact.status)
    || !isFiniteNumber(impact.cpu_delta)
    || !isFiniteNumber(impact.memory_delta)
    || !isFiniteNumber(impact.network_delta)
  ) {
    throw new ApiError(
      "The DCC backend returned invalid resource impact values.",
      "invalid_response",
    );
  }

  return {
    task_id: value.task_id,
    cpu: parseMetricValues(value.cpu),
    memory: parseMetricValues(value.memory),
    network: parseMetricValues(value.network),
    impact: {
      status: impact.status,
      cpu_delta: impact.cpu_delta,
      memory_delta: impact.memory_delta,
      network_delta: impact.network_delta,
    },
    source: value.source,
  };
}

export async function listECSInventory(): Promise<ECSInventory> {
  const clusterResponse = await requestJson("/api/ecs/clusters/");
  if (!Array.isArray(clusterResponse)) {
    throw new ApiError(
      "The DCC backend returned an invalid ECS cluster list.",
      "invalid_response",
    );
  }
  const clusters = clusterResponse.map((cluster) => {
    if (!isRecord(cluster) || !isNonEmptyString(cluster.cluster_arn)) {
      throw new ApiError("The DCC backend returned an invalid ECS cluster.", "invalid_response");
    }
    return cluster.cluster_arn;
  });
  const clusterInventories = await Promise.all(clusters.map(async (clusterArn) => {
    const clusterPath = encodeURIComponent(clusterArn);
    const [servicesResponse, tasksResponse] = await Promise.all([
      requestJson(`/api/ecs/clusters/${clusterPath}/services/`),
      requestJson(`/api/ecs/clusters/${clusterPath}/tasks/`),
    ]);
    if (!Array.isArray(servicesResponse) || !Array.isArray(tasksResponse)) {
      throw new ApiError("The DCC backend returned invalid ECS inventory.", "invalid_response");
    }
    const serviceNames = new Map<string, string>();
    const services: ECSServiceSummary[] = [];
    for (const service of servicesResponse) {
      if (
        !isRecord(service)
        || !(service.service_arn === null || isNonEmptyString(service.service_arn))
        || !isNonEmptyString(service.service_name)
        || !isNonEmptyString(service.cluster_arn)
        || !(service.desired_count === null || isCount(service.desired_count))
        || !(service.running_count === null || isCount(service.running_count))
        || !(service.pending_count === null || isCount(service.pending_count))
        || !(service.status === null || typeof service.status === "string")
      ) {
        throw new ApiError("The DCC backend returned an invalid ECS service.", "invalid_response");
      }
      if (service.service_arn) serviceNames.set(service.service_arn, service.service_name);
      services.push({
        id: service.service_arn ?? service.service_name,
        name: service.service_name,
        cluster_arn: service.cluster_arn,
        desired_count: service.desired_count,
        running_count: service.running_count,
        pending_count: service.pending_count,
        status: service.running_count === null || service.desired_count === null
          ? "unknown"
          : service.running_count >= service.desired_count
            ? "healthy"
            : service.running_count > 0
              ? "warning"
              : "critical",
      });
    }
    const tasks = tasksResponse.map((task) => {
      if (!isRecord(task)) {
        throw new ApiError("The DCC backend returned an invalid ECS task.", "invalid_response");
      }
      return parseTaskSummary({
        ...task,
        id: task.task_id,
        service_id: (task.service_arn && serviceNames.get(String(task.service_arn))) || task.service_name || "Standalone task",
        name: task.task_definition_family || task.task_id,
        status: String(task.last_status ?? "").toLowerCase(),
        health: String(task.health_status ?? "UNKNOWN").toLowerCase(),
        desired_count: task.desired_count,
        current_count: task.current_count,
        availability: task.last_status === "RUNNING" ? "available" : "unavailable",
      });
    });
    return { services, tasks };
  }));
  return {
    services: clusterInventories.flatMap((inventory) => inventory.services),
    tasks: clusterInventories.flatMap((inventory) => inventory.tasks),
  };
}

export async function listTasks(): Promise<TaskSummary[]> {
  return (await listECSInventory()).tasks;
}

export async function getTaskResources(taskId: string): Promise<ResourceMetrics> {
  const metrics = parseResourceMetrics(
    await requestJson(`/api/tasks/${encodeURIComponent(taskId)}/resources/`),
  );
  if (metrics.task_id !== taskId) {
    throw new ApiError(
      "The DCC backend returned resource metrics for a different task.",
      "invalid_response",
    );
  }
  return metrics;
}
