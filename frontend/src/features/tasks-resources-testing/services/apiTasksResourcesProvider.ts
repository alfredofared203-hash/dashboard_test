import {
  getTaskResources,
  listTasks,
  type ResourceMetrics,
  type TaskSummary,
} from "@/lib/api/tasksResources";
import type { DiagnosticSessionStatus } from "@/types/diagnosticSession";
import type {
  WorkspaceResourceImpact,
  WorkspaceResourceMetrics,
  WorkspaceTask,
} from "../types/tasksResources";

export interface ApiTasksResourcesProvider {
  listTasks(): Promise<WorkspaceTask[]>;
  getTaskResources(
    task: WorkspaceTask,
    sessionStatus: DiagnosticSessionStatus,
  ): Promise<WorkspaceResourceMetrics>;
}

function isTaskStatus(value: string): value is "RUNNING" | "PENDING" | "STOPPED" {
  return value === "RUNNING" || value === "PENDING" || value === "STOPPED";
}

function isTaskHealth(
  value: string,
): value is "HEALTHY" | "WARNING" | "UNHEALTHY" | "UNKNOWN" | "CRITICAL" {
  return ["HEALTHY", "WARNING", "UNHEALTHY", "UNKNOWN", "CRITICAL"].includes(value);
}

function mapTask(task: TaskSummary): WorkspaceTask {
  const status = task.status.toUpperCase();
  const health = task.health.toUpperCase();
  const availability = task.availability.toUpperCase();

  if (!isTaskStatus(status)) {
    throw new Error("The backend returned an unsupported task status.");
  }
  if (!isTaskHealth(health)) {
    throw new Error("The backend returned an unsupported task health state.");
  }
  if (availability !== "AVAILABLE" && availability !== "UNAVAILABLE" && availability !== "NOT APPLICABLE") {
    throw new Error("The backend returned an unsupported task availability state.");
  }

  return {
    id: task.id,
    name: task.name,
    serviceName: task.service_id,
    taskId: task.id,
    status,
    health,
    desiredCount: task.desired_count,
    currentCount: task.current_count,
    availability: availability === "AVAILABLE"
      ? "REACHABLE"
      : availability === "UNAVAILABLE"
        ? "UNREACHABLE"
        : "NOT APPLICABLE",
    taskArn: task.task_arn,
    clusterArn: task.cluster_arn,
    taskDefinition: `${task.task_definition_family}:${task.task_definition_revision ?? "?"}`,
    launchType: task.launch_type ?? "Unknown",
    cpu: task.cpu,
    memory: task.memory,
    availabilityZone: task.availability_zone,
    networkMode: task.network_mode,
    privateIp: task.network.private_ip,
    subnetId: task.network.subnet_id,
    securityGroupIds: task.network.security_group_ids,
    containers: task.containers.map((container) => ({
      name: container.name,
      image: container.image,
      imageDigest: container.image_digest,
      lastStatus: container.last_status,
    })),
  };
}

function mapImpact(delta: number, baseline: number, unit: string): WorkspaceResourceImpact {
  return {
    absoluteChange: delta,
    percentageChange: baseline === 0 ? null : delta / baseline * 100,
    unit,
  };
}

function displayUnit(unit: string): string {
  const normalized = unit.toLowerCase();
  if (normalized === "percent") return "%";
  if (normalized === "mbps") return "Mbps";
  return unit;
}

function resourceValues(metrics: ResourceMetrics, field: "baseline" | "current" | "peak") {
  return {
    cpu: { value: metrics.cpu[field], unit: displayUnit(metrics.cpu.unit) },
    memory: { value: metrics.memory[field], unit: displayUnit(metrics.memory.unit) },
    network: { value: metrics.network[field], unit: displayUnit(metrics.network.unit) },
  };
}

function hasDiagnosticMeasurements(status: DiagnosticSessionStatus): boolean {
  return status === "running" || status === "completed" || status === "failed";
}

export const apiTasksResourcesProvider: ApiTasksResourcesProvider = {
  async listTasks() {
    return (await listTasks()).map(mapTask);
  },

  async getTaskResources(task, sessionStatus) {
    const response = await getTaskResources(task.id);
    const available = task.status === "RUNNING";
    const showCurrentValues = available
      && (response.source === "cloudwatch" || hasDiagnosticMeasurements(sessionStatus));
    return {
      available,
      provider: response.source,
      baseline: resourceValues(response, "baseline"),
      duringTest: showCurrentValues ? resourceValues(response, "current") : null,
      peakDuringTest: showCurrentValues ? resourceValues(response, "peak") : null,
      impact: showCurrentValues
        ? {
            cpu: mapImpact(
              response.impact.cpu_delta,
              response.cpu.baseline,
              "percentage points",
            ),
            memory: mapImpact(
              response.impact.memory_delta,
              response.memory.baseline,
              "percentage points",
            ),
            network: mapImpact(
              response.impact.network_delta,
              response.network.baseline,
              displayUnit(response.network.unit),
            ),
          }
        : null,
      source: response.source === "mock"
        ? "Backend mock metrics · illustrative, not live"
        : response.source === "cloudwatch"
          ? "CloudWatch metrics · configured ECS service"
          : "Prometheus metrics · configured task labels",
    };
  },
};
