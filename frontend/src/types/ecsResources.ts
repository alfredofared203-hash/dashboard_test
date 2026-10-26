export interface EcsCluster {
  clusterArn: string;
  clusterName: string;
  status: string;
}

export interface EcsService {
  serviceArn: string | null;
  serviceName: string;
  clusterArn: string;
  desiredCount: number | null;
  runningCount: number | null;
  pendingCount: number | null;
  taskDefinitionArn: string;
  taskDefinitionFamily: string;
  taskDefinitionRevision: number | null;
  launchType: string | null;
  status: string | null;
}

export interface EcsContainer {
  containerArn: string | null;
  name: string;
  image: string;
  imageDigest: string | null;
  lastStatus: string;
  cpu: number | null;
  memory: number | null;
  memoryReservation: number | null;
  essential: boolean;
  runtimeId: string | null;
  exitCode: number | null;
  reason: string | null;
}

export interface EcsTask {
  taskArn: string;
  taskId: string;
  clusterArn: string;
  serviceArn: string | null;
  serviceName: string | null;
  taskDefinitionArn: string;
  taskDefinitionFamily: string;
  taskDefinitionRevision: number | null;
  desiredStatus: string;
  lastStatus: string;
  healthStatus: string;
  startedAt: string | null;
  launchType: string | null;
  cpu: string | null;
  memory: string | null;
  availabilityZone: string | null;
  networkMode: string | null;
  network: {
    eniId: string | null;
    privateIp: string | null;
    subnetId: string | null;
    securityGroupIds: string[];
  };
  containers: EcsContainer[];
  desiredCount: number | null;
  currentCount: number | null;
}
