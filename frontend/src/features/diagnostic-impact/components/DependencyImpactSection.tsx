import { Database, Server } from "lucide-react";
import type {
  DependencyImpactReport,
  DependencyImpactResource,
  ImpactPhaseName,
} from "../types/report";

const phaseNames: ImpactPhaseName[] = ["baseline", "during", "post"];
const phaseLabels: Record<ImpactPhaseName, string> = {
  baseline: "Baseline",
  during: "During diagnostic",
  post: "Post diagnostic",
};

const metricLabels: Record<string, string> = {
  cpu_utilization: "CPU utilization",
  database_connections: "Database connections",
  memory_usage_bytes: "Memory used",
  memory_usage_percent: "Memory usage",
};

function formatValue(value: number | null, unit: string): string {
  if (value === null) return "Unavailable";
  if (unit === "bytes") {
    const units = ["B", "KB", "MB", "GB", "TB"];
    let amount = value;
    let index = 0;
    while (amount >= 1024 && index < units.length - 1) {
      amount /= 1024;
      index += 1;
    }
    return `${amount.toFixed(1)} ${units[index]}`;
  }
  const displayUnit = unit === "percent" ? "%" : unit;
  return `${Number.isInteger(value) ? value : value.toFixed(1)} ${displayUnit}`;
}

function phaseReading(
  phase: DependencyImpactReport["phases"][ImpactPhaseName],
  key: string,
  metricName: string,
): number | null {
  return phase.resources[key]?.metrics[metricName]?.current ?? null;
}

function formatDelta(
  resource: DependencyImpactResource,
  metricName: string,
  phase: "during" | "post",
): string {
  const metric = resource.metrics[metricName];
  if (!metric) return "Unavailable";
  const delta = metric[`${phase}_delta`];
  if (delta.status !== "available" || delta.absolute_delta === null) {
    return "Unavailable";
  }
  const absolute = `${delta.absolute_delta > 0 ? "+" : ""}${delta.absolute_delta.toFixed(1)} ${metric.unit}`;
  return delta.percentage_delta === null
    ? `${absolute}; percentage unavailable`
    : `${absolute} (${delta.percentage_delta > 0 ? "+" : ""}${delta.percentage_delta.toFixed(1)}%)`;
}

function DependencyResourceCard({
  resourceKey,
  resource,
  report,
}: {
  resourceKey: string;
  resource: DependencyImpactResource;
  report: DependencyImpactReport;
}) {
  const Icon = resource.resource_type === "rds" ? Database : Server;
  return (
    <article className="dependency-impact-resource">
      <header>
        <Icon size={15} />
        <div>
          <strong>{resource.resource_id}</strong>
          <span>{resource.resource_type === "rds" ? "RDS" : "ElastiCache"} · {resource.engine} · {resource.status}</span>
        </div>
      </header>
      <div className="dependency-impact-metrics">
        {Object.entries(resource.metrics).map(([metricName, metric]) => (
          <div className="dependency-impact-metric" key={metricName}>
            <strong>{metricLabels[metricName] ?? metricName.replaceAll("_", " ")}</strong>
            <div className="dependency-impact-phase-grid">
              {phaseNames.map((phase) => (
                <div key={phase}>
                  <span>{phaseLabels[phase]}</span>
                  <b>{formatValue(
                    phaseReading(report.phases[phase], resourceKey, metricName),
                    metric.unit,
                  )}</b>
                </div>
              ))}
            </div>
            <p>
              Peak during: {formatValue(metric.peak_during, metric.unit)}
              <span>During delta: {formatDelta(resource, metricName, "during")}</span>
              <span>Post delta: {formatDelta(resource, metricName, "post")}</span>
            </p>
          </div>
        ))}
      </div>
    </article>
  );
}

export function DependencyImpactSection({ report }: { report: DependencyImpactReport }) {
  const resourceEntries = Object.entries(report.resources);
  return (
    <section className="impact-panel dependency-impact-panel" aria-labelledby="dependency-impact-heading">
      <div className="impact-panel-heading">
        <div className="impact-panel-title">
          <Database size={15} />
          <h2 id="dependency-impact-heading">Dependency observations · RDS &amp; ElastiCache</h2>
        </div>
        <p>Separate from ECS target impact · no dependency causal classification</p>
      </div>
      <div className="dependency-impact-context">
        Session <code>{report.session_id}</code> · Availability: <strong>{report.availability}</strong>
        {report.sources.length > 0 && <> · Source: <strong>{report.sources.join(", ")}</strong></>}
      </div>
      <div className="dependency-impact-phase-status">
        {phaseNames.map((phase) => (
          <div key={phase}>
            <span>{phaseLabels[phase]}</span>
            <strong>{report.phases[phase].status.replaceAll("_", " ")}</strong>
            {report.phases[phase].captured_at !== null && (
              <time dateTime={report.phases[phase].captured_at}>
                {new Date(report.phases[phase].captured_at).toLocaleTimeString()}
              </time>
            )}
            {report.phases[phase].detail && <small>{report.phases[phase].detail}</small>}
          </div>
        ))}
      </div>
      {resourceEntries.length === 0 ? (
        <p className="dependency-impact-empty">
          Dependency measurements are unavailable or no dependencies were configured for this session.
        </p>
      ) : (
        <div className="dependency-impact-list">
          {(["rds", "elasticache"] as const).map((type) => {
            const resources = resourceEntries.filter(([, resource]) => resource.resource_type === type);
            if (!resources.length) return null;
            return (
              <section key={type} aria-label={type === "rds" ? "RDS observations" : "ElastiCache observations"}>
                <h3><span>{type === "rds" ? "RDS" : "ElastiCache"}</span> observations</h3>
                <div className="dependency-impact-resource-list">
                  {resources.map(([key, resource]) => (
                    <DependencyResourceCard
                      key={key}
                      resourceKey={key}
                      resource={resource}
                      report={report}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </section>
  );
}
