export type TaskStatus = "RUNNING" | "PENDING" | "STOPPED";
export type TaskHealth = "HEALTHY" | "UNHEALTHY" | "UNKNOWN";
export type TaskAvailability = "REACHABLE" | "UNREACHABLE" | "NOT APPLICABLE";
export type TestResultStatus = "PASS" | "WARNING" | "FAIL" | "RUNNING" | "NOT RUNNING";
export type MetricPhase = "Baseline" | "During test";

export interface TargetTask {
  id: string;
  name: string;
  serviceName: string;
  taskId: string;
  status: TaskStatus;
  health: TaskHealth;
  desiredState: "RUNNING" | "STOPPED";
  currentState: TaskStatus;
  availability: TaskAvailability;
  startedAt: string | null;
  stoppedAt: string | null;
}

export interface ResourceValues {
  cpuPercent: number;
  memoryMb: number;
  memoryLimitMb: number;
  networkMbPerSecond: number;
}

export interface ResourceMetrics {
  available: boolean;
  baseline: ResourceValues;
  duringTest: ResourceValues | null;
  peakDuringTest: ResourceValues | null;
  source: string;
  capturedAt: string | null;
}

export interface MetricSample {
  time: string;
  phase: MetricPhase;
  cpuPercent: number;
  memoryPercent: number;
  networkMbPerSecond: number;
}

export interface ResourceImpact {
  absoluteChange: number;
  percentageChange: number | null;
  unit: string;
}

export interface ResourceTestResult {
  status: TestResultStatus;
  summary: string;
  baselineCaptured: boolean;
  duringTestCaptured: boolean;
  impactCalculated: boolean;
  warnings: string[];
  errors: string[];
  finishedAt: string | null;
}

export interface TaskResourceRecord {
  task: TargetTask;
  metrics: ResourceMetrics;
  samples: MetricSample[];
  result: ResourceTestResult;
}

export interface TasksResourcesWorkspace {
  tasks: TargetTask[];
  selectedRecord: TaskResourceRecord | null;
}

export interface WorkspaceTask {
  id: string;
  name: string;
  serviceName: string;
  taskId: string;
  status: TaskStatus;
  health: TaskHealth | "WARNING" | "CRITICAL";
  desiredCount: number | null;
  currentCount: number | null;
  availability: TaskAvailability;
  taskArn: string;
  clusterArn: string;
  taskDefinition: string;
  launchType: string;
  cpu: string | null;
  memory: string | null;
  availabilityZone: string | null;
  networkMode: string | null;
  privateIp: string | null;
  subnetId: string | null;
  securityGroupIds: string[];
  containers: Array<{
    name: string;
    image: string;
    imageDigest: string | null;
    lastStatus: string;
  }>;
}

export interface WorkspaceResourceImpact {
  absoluteChange: number;
  percentageChange: number | null;
  unit: string;
}

export interface WorkspaceMetricValues {
  value: number;
  unit: string;
}

export interface WorkspaceResourceMetrics {
  available: boolean;
  provider: "mock" | "cloudwatch" | "prometheus";
  baseline: {
    cpu: WorkspaceMetricValues;
    memory: WorkspaceMetricValues;
    network: WorkspaceMetricValues;
  };
  duringTest: {
    cpu: WorkspaceMetricValues;
    memory: WorkspaceMetricValues;
    network: WorkspaceMetricValues;
  } | null;
  peakDuringTest: {
    cpu: WorkspaceMetricValues;
    memory: WorkspaceMetricValues;
    network: WorkspaceMetricValues;
  } | null;
  impact: {
    cpu: WorkspaceResourceImpact;
    memory: WorkspaceResourceImpact;
    network: WorkspaceResourceImpact;
  } | null;
  source: string;
}

export interface WorkspaceTaskResourceRecord {
  task: WorkspaceTask;
  metrics: WorkspaceResourceMetrics;
}
