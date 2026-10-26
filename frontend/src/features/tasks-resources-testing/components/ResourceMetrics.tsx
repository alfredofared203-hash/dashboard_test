import { Activity, ArrowDownRight, ArrowRight, ArrowUpRight, Cpu, MemoryStick, Network } from "lucide-react";
import type {
  WorkspaceResourceImpact,
  WorkspaceResourceMetrics,
} from "../types/tasksResources";

interface ResourceMetricsProps {
  metrics: WorkspaceResourceMetrics;
}

function formatNumber(value: number, digits = 0): string {
  return Number.isFinite(value) ? value.toFixed(digits) : "—";
}

function formatImpact(impact: WorkspaceResourceImpact | null | undefined, digits = 1): string {
  if (!impact) return "Not captured";
  const sign = impact.absoluteChange > 0 ? "+" : "";
  const absolute = `${sign}${formatNumber(impact.absoluteChange, digits)} ${impact.unit}`;
  if (impact.percentageChange === null) return `${absolute} · % N/A (zero baseline)`;
  const percentSign = impact.percentageChange > 0 ? "+" : "";
  return `${absolute} · ${percentSign}${formatNumber(impact.percentageChange, 1)}%`;
}

function impactTone(absoluteChange: number | null | undefined) {
  if (absoluteChange === null || absoluteChange === undefined || !Number.isFinite(absoluteChange)) return "impact-neutral";
  return absoluteChange > 0 ? "impact-up" : absoluteChange < 0 ? "impact-down" : "impact-neutral";
}

function ImpactIcon({ change }: { change: number | null | undefined }) {
  if (change !== null && change !== undefined && change > 0) return <ArrowUpRight size={13} />;
  if (change !== null && change !== undefined && change < 0) return <ArrowDownRight size={13} />;
  return <ArrowRight size={13} />;
}

export function ResourceMetrics({ metrics }: ResourceMetricsProps) {
  if (!metrics.available) {
    return (
      <section className="task-resource-panel task-metrics-unavailable" role="status">
        <Activity size={19} />
        <strong>Resource metrics unavailable</strong>
        <span>Resource metrics are unavailable for this task.</span>
      </section>
    );
  }
  const cards = [
    {
      label: "CPU",
      icon: Cpu,
      baseline: `${formatNumber(metrics.baseline.cpu.value)} ${metrics.baseline.cpu.unit}`,
      during: metrics.duringTest ? `${formatNumber(metrics.duringTest.cpu.value)} ${metrics.duringTest.cpu.unit}` : "—",
      peak: metrics.peakDuringTest ? `${formatNumber(metrics.peakDuringTest.cpu.value)} ${metrics.peakDuringTest.cpu.unit}` : "—",
      change: metrics.impact?.cpu,
      digits: 1,
    },
    {
      label: "Memory",
      icon: MemoryStick,
      baseline: `${formatNumber(metrics.baseline.memory.value)} ${metrics.baseline.memory.unit}`,
      during: metrics.duringTest ? `${formatNumber(metrics.duringTest.memory.value)} ${metrics.duringTest.memory.unit}` : "—",
      peak: metrics.peakDuringTest ? `${formatNumber(metrics.peakDuringTest.memory.value)} ${metrics.peakDuringTest.memory.unit}` : "—",
      change: metrics.impact?.memory,
      digits: 1,
    },
    {
      label: "Network",
      icon: Network,
      baseline: `${formatNumber(metrics.baseline.network.value, 2)} ${metrics.baseline.network.unit}`,
      during: metrics.duringTest ? `${formatNumber(metrics.duringTest.network.value, 2)} ${metrics.duringTest.network.unit}` : "—",
      peak: metrics.peakDuringTest ? `${formatNumber(metrics.peakDuringTest.network.value, 2)} ${metrics.peakDuringTest.network.unit}` : "—",
      change: metrics.impact?.network,
      digits: 2,
    },
  ];

  return (
    <section className="task-resource-metrics" aria-label="Selected task resource metrics">
      {cards.map(({ label, icon: Icon, baseline, during, peak, change, digits }) => (
        <article className="task-resource-panel task-metric-card" key={label}>
          <header className="task-metric-heading"><span><Icon size={14} />{label}</span><Activity size={13} /></header>
          <div className="task-metric-values">
            <div><span>BASELINE</span><strong>{baseline}</strong></div>
            <div><span>{metrics.provider === "mock" ? "DURING TEST" : "CURRENT"}</span><strong>{during}</strong></div>
            <div><span>PEAK</span><strong>{peak}</strong></div>
          </div>
          <div className={`task-metric-impact ${impactTone(change?.absoluteChange)}`}>
            <ImpactIcon change={change?.absoluteChange} />
            <span>{formatImpact(change, digits)}</span>
          </div>
        </article>
      ))}
    </section>
  );
}
