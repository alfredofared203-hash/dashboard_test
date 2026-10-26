import { ApiError, requestJson } from "./client";
import type { EcsCluster, EcsContainer, EcsService, EcsTask } from "@/types/ecsResources";

type ApiRecord = Record<string, unknown>;

function isRecord(value: unknown): value is ApiRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNonEmptyString(value: unknown): value is string {
  return isString(value) && value.trim().length > 0;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || isNonEmptyString(value);
}

function isCount(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isNullableCount(value: unknown): value is number | null {
  return value === null || isCount(value);
}

function parseCluster(value: unknown): EcsCluster {
  if (
    !isRecord(value)
    || !isNonEmptyString(value.cluster_arn)
    || !isNonEmptyString(value.cluster_name)
    || !isNonEmptyString(value.status)
  ) {
    throw new ApiError("The DCC backend returned an invalid ECS cluster.", "invalid_response");
  }
  return {
    clusterArn: value.cluster_arn,
    clusterName: value.cluster_name,
    status: value.status,
  };
}

function parseService(value: unknown): EcsService {
  if (
    !isRecord(value)
    || !isNullableString(value.service_arn)
    || !isNonEmptyString(value.service_name)
    || !isNonEmptyString(value.cluster_arn)
    || !isNullableCount(value.desired_count)
    || !isNullableCount(value.running_count)
    || !isNullableCount(value.pending_count)
    || !isString(value.task_definition_arn)
    || !isString(value.task_definition_family)
    || !isNullableCount(value.task_definition_revision)
    || !isNullableString(value.launch_type)
    || !isNullableString(value.status)
  ) {
    throw new ApiError("The DCC backend returned an invalid ECS service.", "invalid_response");
  }
  return {
    serviceArn: value.service_arn,
    serviceName: value.service_name,
    clusterArn: value.cluster_arn,
    desiredCount: value.desired_count,
    runningCount: value.running_count,
    pendingCount: value.pending_count,
    taskDefinitionArn: value.task_definition_arn,
    taskDefinitionFamily: value.task_definition_family,
    taskDefinitionRevision: value.task_definition_revision,
    launchType: value.launch_type,
    status: value.status,
  };
}

function parseContainer(value: unknown): EcsContainer {
  if (
    !isRecord(value)
    || !isNullableString(value.container_arn)
    || !isNonEmptyString(value.name)
    || !isString(value.image)
    || !isNullableString(value.image_digest)
    || !isNonEmptyString(value.last_status)
    || !isNullableCount(value.cpu)
    || !isNullableCount(value.memory)
    || !isNullableCount(value.memory_reservation)
    || typeof value.essential !== "boolean"
    || !isNullableString(value.runtime_id)
    || !isNullableCount(value.exit_code)
    || !isNullableString(value.reason)
  ) {
    throw new ApiError("The DCC backend returned an invalid ECS container.", "invalid_response");
  }
  return {
    containerArn: value.container_arn,
    name: value.name,
    image: value.image,
    imageDigest: value.image_digest,
    lastStatus: value.last_status,
    cpu: value.cpu,
    memory: value.memory,
    memoryReservation: value.memory_reservation,
    essential: value.essential,
    runtimeId: value.runtime_id,
    exitCode: value.exit_code,
    reason: value.reason,
  };
}

function parseTask(value: unknown): EcsTask {
  if (
    !isRecord(value)
    || !isNonEmptyString(value.task_arn)
    || !isNonEmptyString(value.task_id)
    || !isNonEmptyString(value.cluster_arn)
    || !isNullableString(value.service_arn)
    || !isNullableString(value.service_name)
    || !isNonEmptyString(value.task_definition_arn)
    || !isString(value.task_definition_family)
    || !isNullableCount(value.task_definition_revision)
    || !isNonEmptyString(value.desired_status)
    || !isNonEmptyString(value.last_status)
    || !isNonEmptyString(value.health_status)
    || !isNullableString(value.started_at)
    || !isNullableString(value.launch_type)
    || !isNullableString(value.cpu)
    || !isNullableString(value.memory)
    || !isNullableString(value.availability_zone)
    || !isNullableString(value.network_mode)
    || !isRecord(value.network)
    || !isNullableString(value.network.eni_id)
    || !isNullableString(value.network.private_ip)
    || !isNullableString(value.network.subnet_id)
    || !Array.isArray(value.network.security_group_ids)
    || !value.network.security_group_ids.every(isNonEmptyString)
    || !Array.isArray(value.containers)
    || !isNullableCount(value.desired_count)
    || !isNullableCount(value.current_count)
  ) {
    throw new ApiError("The DCC backend returned an invalid ECS task.", "invalid_response");
  }
  return {
    taskArn: value.task_arn,
    taskId: value.task_id,
    clusterArn: value.cluster_arn,
    serviceArn: value.service_arn,
    serviceName: value.service_name,
    taskDefinitionArn: value.task_definition_arn,
    taskDefinitionFamily: value.task_definition_family,
    taskDefinitionRevision: value.task_definition_revision,
    desiredStatus: value.desired_status,
    lastStatus: value.last_status,
    healthStatus: value.health_status,
    startedAt: value.started_at,
    launchType: value.launch_type,
    cpu: value.cpu,
    memory: value.memory,
    availabilityZone: value.availability_zone,
    networkMode: value.network_mode,
    network: {
      eniId: value.network.eni_id,
      privateIp: value.network.private_ip,
      subnetId: value.network.subnet_id,
      securityGroupIds: value.network.security_group_ids,
    },
    containers: value.containers.map(parseContainer),
    desiredCount: value.desired_count,
    currentCount: value.current_count,
  };
}

async function requestList<T>(
  path: string,
  parser: (value: unknown) => T,
  resourceName: string,
): Promise<T[]> {
  const response = await requestJson(path);
  if (!Array.isArray(response)) {
    throw new ApiError(`The DCC backend returned an invalid ECS ${resourceName} list.`, "invalid_response");
  }
  return response.map(parser);
}

export function listEcsClusters(): Promise<EcsCluster[]> {
  return requestList("/api/ecs/clusters/", parseCluster, "cluster");
}

export function listEcsServices(clusterArn: string): Promise<EcsService[]> {
  return requestList(
    `/api/ecs/clusters/${encodeURIComponent(clusterArn)}/services/`,
    parseService,
    "service",
  );
}

export function listAllEcsTasks(): Promise<EcsTask[]> {
  return requestList("/api/ecs/tasks/", parseTask, "task");
}

export function listEcsServiceTasks(
  clusterArn: string,
  service: string,
): Promise<EcsTask[]> {
  return requestList(
    `/api/ecs/clusters/${encodeURIComponent(clusterArn)}/services/${encodeURIComponent(service)}/tasks/`,
    parseTask,
    "service task",
  );
}

export async function getEcsTask(taskId: string, clusterArn?: string): Promise<EcsTask> {
  const query = clusterArn ? `?cluster=${encodeURIComponent(clusterArn)}` : "";
  return parseTask(await requestJson(
    `/api/ecs/tasks/${encodeURIComponent(taskId)}/${query}`,
  ));
}
