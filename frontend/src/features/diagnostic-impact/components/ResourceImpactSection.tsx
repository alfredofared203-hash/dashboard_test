import { Activity } from "lucide-react";
import type {
  CalculatedImpactMetric,
  ImpactPhaseName,
} from "../types/report";

interface ResourceImpactSectionProps {
  resources: Record<"cpu" | "memory" | "network", CalculatedImpactMetric>;
}

const metricNames = ["cpu", "memory", "network"] as const;
const phaseNames: ImpactPhaseName[] = ["baseline", "during", "post"];
const metricLabels = { cpu: "CPU", memory: "Memory", network: "Network" };
const phaseLabels: Record<ImpactPhaseName, string> = {
  baseline: "Baseline",
  during: "During",
  post: "Post",
};

function formatValue(value: number | null, unit: string): string {
  return value === null ? "Not captured" : `${value.toFixed(1)} ${unit}`;
}

function formatDelta(metric: CalculatedImpactMetric, phase: "during" | "post"): string {
  const delta = metric[`${phase}_delta`];
  if (delta.status !== "available" || delta.absolute_delta === null) {
    return "Unavailable";
  }
  const absolute = `${delta.absolute_delta > 0 ? "+" : ""}${delta.absolute_delta.toFixed(1)} ${metric.unit}`;
  if (delta.percentage_delta === null) {
    return `${absolute}; percentage unavailable`;
  }
  const percentage = `${delta.percentage_delta > 0 ? "+" : ""}${delta.percentage_delta.toFixed(1)}%`;
  return `${absolute} (${percentage})`;
}

export function ResourceImpactSection({ resources }: ResourceImpactSectionProps) {
  return (
    <section className="impact-panel" aria-labelledby="resource-impact-heading">
      <div className="impact-panel-heading">
        <div className="impact-panel-title"><Activity size={15} /><h2 id="resource-impact-heading">ECS target impact</h2></div>
        <p>Backend-calculated comparisons; unavailable data is not treated as zero</p>
      </div>
      <div className="impact-metrics">
        {metricNames.map((name) => {
          const metric = resources[name];
          return (
            <article className="impact-metric" key={name}>
              <div className="impact-metric-heading">
                <strong>{metricLabels[name]}</strong>
                <span>Peak during: {formatValue(metric.peak_during, metric.unit)}</span>
              </div>
              <div className="impact-phase-values">
                {phaseNames.map((phase) => (
                  <div key={phase}>
                    <span>{phaseLabels[phase]}</span>
                    <strong>{formatValue(metric[phase], metric.unit)}</strong>
                  </div>
                ))}
              </div>
              <div className="impact-delta-values">
                <span>During delta <strong>{formatDelta(metric, "during")}</strong></span>
                <span>Post delta <strong>{formatDelta(metric, "post")}</strong></span>
              </div>
            </article>
          );
        })}
      </div>
      <div className="impact-legend">
        <span>Zero baselines have an absolute delta but no percentage delta.</span>
      </div>
    </section>
  );
}
