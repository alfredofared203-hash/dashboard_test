export type ServiceStatus = "Healthy" | "Degraded";
export type EventSeverity = "info" | "warning" | "critical";

export interface Service {
  name: string;
  detail: string;
  status: ServiceStatus;
  runningTasks: number | null;
  desiredTasks: number | null;
  cpu: number | null;
  memory: number | null;
  updated: string;
}

export interface ResourcePoint {
  time: string;
  cpu: number;
  memory: number;
}

export interface RecentEvent {
  time: string;
  title: string;
  detail: string;
  service?: string;
  severity: EventSeverity;
}

export interface SystemOverviewMetrics {
  totalServices: number;
  healthyServices: number;
  servicesNeedingAttention: number;
  runningTasks: number;
  desiredTasks: number;
  averageCpu: number | null;
  averageMemory: number | null;
}
