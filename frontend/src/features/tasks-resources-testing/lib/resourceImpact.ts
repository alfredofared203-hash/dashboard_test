import type { ResourceImpact, ResourceValues } from "../types/tasksResources";

export function calculateImpact(
  baseline: number | null | undefined,
  duringTest: number | null | undefined,
  unit: string,
): ResourceImpact | null {
  if (
    baseline === null
    || baseline === undefined
    || duringTest === null
    || duringTest === undefined
    || !Number.isFinite(baseline)
    || !Number.isFinite(duringTest)
  ) {
    return null;
  }

  const absoluteChange = duringTest - baseline;
  const percentageChange = baseline === 0 ? null : (absoluteChange / baseline) * 100;
  return { absoluteChange, percentageChange, unit };
}

export function getResourceImpacts(baseline: ResourceValues, duringTest: ResourceValues | null) {
  if (!duringTest) return null;
  return {
    cpu: calculateImpact(baseline.cpuPercent, duringTest.cpuPercent, "percentage points"),
    memory: calculateImpact(baseline.memoryMb, duringTest.memoryMb, "MB"),
    network: calculateImpact(baseline.networkMbPerSecond, duringTest.networkMbPerSecond, "MB/s"),
  };
}
