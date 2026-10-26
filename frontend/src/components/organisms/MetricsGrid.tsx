import { Activity, Cpu, Layers, MemoryStick } from "lucide-react";
import { MetricCard } from "@/components/molecules/MetricCard";
import type { SystemOverviewMetrics } from "@/types/dashboard";

export interface MetricsGridProps {
  metrics: SystemOverviewMetrics;
}

export function MetricsGrid({ metrics }: MetricsGridProps) {
  return (
    <section className="summary-grid" aria-label="System summary">
      <MetricCard
        label="Total Services"
        value={String(metrics.totalServices)}
        unit=" services"
        icon={Layers}
        tone="blue"
        footer={<><span className="mini-dot green" />{metrics.healthyServices} healthy <span className="foot-divider">·</span> {metrics.servicesNeedingAttention} need attention</>}
      />
      <MetricCard
        label="Running Tasks"
        value={String(metrics.runningTasks)}
        unit={` / ${metrics.desiredTasks}`}
        icon={Cpu}
        tone="violet"
        footer={`Across ${metrics.totalServices} discovered ECS services`}
      />
      <MetricCard
        label="Average CPU Utilization"
        value={metrics.averageCpu === null ? "—" : String(metrics.averageCpu)}
        unit={metrics.averageCpu === null ? undefined : "%"}
        icon={Activity}
        tone="cyan"
        range={metrics.averageCpu === null ? "NOT AVAILABLE" : "LAST 15 MIN"}
        {...(metrics.averageCpu === null ? {} : { progress: metrics.averageCpu, progressTone: "cpu" as const })}
      />
      <MetricCard
        label="Average Memory Utilization"
        value={metrics.averageMemory === null ? "—" : String(metrics.averageMemory)}
        unit={metrics.averageMemory === null ? undefined : "%"}
        icon={MemoryStick}
        tone="orange"
        range={metrics.averageMemory === null ? "NOT AVAILABLE" : "LAST 15 MIN"}
        {...(metrics.averageMemory === null ? {} : { progress: metrics.averageMemory, progressTone: "memory" as const })}
      />
    </section>
  );
}
