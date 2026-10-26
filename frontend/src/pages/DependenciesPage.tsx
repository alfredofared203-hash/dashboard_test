import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, Database, RotateCw, Server } from "lucide-react";
import { ActionButton } from "@/components/atoms/ActionButton";
import { PageTitle } from "@/components/molecules/PageTitle";
import {
  listDependencies,
  type DependencyList,
  type DependencyResource,
  type DependencyResourceType,
} from "@/lib/api/dependencies";
import "../styles/dependencies.css";

type LoadState = "loading" | "loaded" | "error";
type ResourceFilter = "all" | DependencyResourceType;

function isResourceFilter(value: string): value is ResourceFilter {
  return value === "all" || value === "rds" || value === "elasticache";
}

const metricLabels: Record<string, string> = {
  cpu_utilization: "CPU utilization",
  database_connections: "Database connections",
  free_storage: "Free storage",
  read_iops: "Read IOPS",
  write_iops: "Write IOPS",
  network_receive: "Network receive",
  network_transmit: "Network transmit",
  memory_usage_bytes: "Memory used",
  memory_usage_percent: "Memory usage",
  connections: "Connections",
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
  return `${Number.isInteger(value) ? value : value.toFixed(1)} ${unit === "percent" ? "%" : unit}`;
}

function DependencyCard({ resource }: { resource: DependencyResource }) {
  const Icon = resource.resource_type === "rds" ? Database : Server;
  const status = resource.status === "unknown" ? "Status unknown" : resource.status;
  return (
    <article className="dependency-card">
      <header className="dependency-card-heading">
        <span className="dependency-icon"><Icon size={17} /></span>
        <div className="dependency-identity">
          <h2>{resource.resource_id}</h2>
          <p>{resource.resource_type === "rds" ? "Amazon RDS" : "Amazon ElastiCache"} · {resource.engine}</p>
        </div>
        <span className={`dependency-health dependency-health-${resource.availability}`}>
          <span />{resource.availability === "available" ? status : "Metrics unavailable"}
        </span>
      </header>
      <div className="dependency-card-meta">
        <span>Resource scope</span>
        <strong>{resource.resource_scope.replaceAll("_", " ")}</strong>
        <span>Source</span>
        <strong className={resource.source === "mock" ? "dependency-mock-source" : ""}>
          {resource.source === "mock" ? "Mock · illustrative, not live" : "CloudWatch"}
        </strong>
      </div>
      <div className="dependency-metrics">
        {Object.entries(resource.metrics).map(([name, metric]) => (
          <div className="dependency-metric" key={name}>
            <span>{metricLabels[name] ?? name.replaceAll("_", " ")}</span>
            <strong>{metric.status === "available"
              ? formatValue(metric.current, metric.unit)
              : "Unavailable"}
            </strong>
            {metric.peak !== null && (
              <small>Peak {formatValue(metric.peak, metric.unit)}</small>
            )}
          </div>
        ))}
        {Object.keys(resource.metrics).length === 0 && (
          <p className="dependency-inline-empty">No supported metrics are available for this resource.</p>
        )}
      </div>
    </article>
  );
}

export function DependenciesPage() {
  const [filter, setFilter] = useState<ResourceFilter>("all");
  const [data, setData] = useState<DependencyList | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => setReloadKey((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    setError(null);
    listDependencies(filter).then(
      (result) => {
        if (cancelled) return;
        setData(result);
        setState("loaded");
      },
      (reason: unknown) => {
        if (cancelled) return;
        setData(null);
        setError(reason instanceof Error ? reason.message : "Dependency data could not be loaded.");
        setState("error");
      },
    );
    return () => {
      cancelled = true;
    };
  }, [filter, reloadKey]);

  return (
    <div className="dependencies-page">
      <PageTitle
        eyebrow="OBSERVABILITY / DEPENDENCIES"
        title="Dependency Observability"
        description="Read-only health and CloudWatch metrics for configured RDS and ElastiCache resources."
        actions={
          <ActionButton variant="outline" size="sm" onClick={reload} disabled={state === "loading"}>
            <RotateCw size={14} /> Refresh
          </ActionButton>
        }
      />

      <section className="dependency-context" aria-live="polite">
        <Activity size={15} />
        {data?.measurement_context === "active_session_observation"
          ? <span>Active diagnostic observation · session <code>{data.diagnostic_session_id}</code></span>
          : <span>Current dependency health · not diagnostic impact</span>}
      </section>

      <div className="dependency-toolbar">
        <label htmlFor="dependency-type">Resource type</label>
        <select
          id="dependency-type"
          value={filter}
          onChange={(event) => {
            if (isResourceFilter(event.target.value)) setFilter(event.target.value);
          }}
        >
          <option value="all">All resources</option>
          <option value="rds">RDS</option>
          <option value="elasticache">ElastiCache</option>
        </select>
        {data?.resources.length ? (
          <span>{data.resources.length} {data.resources.length === 1 ? "resource" : "resources"}</span>
        ) : null}
      </div>

      {state === "loading" && (
        <section className="dependency-state" role="status">
          <span className="dependency-spinner" />
          <strong>Loading dependency observations</strong>
          <span>Reading normalized resource metrics from the DCC backend.</span>
        </section>
      )}

      {state === "error" && (
        <section className="dependency-state dependency-state-error" role="alert">
          <AlertTriangle size={22} />
          <strong>Could not load dependencies</strong>
          <span>{error}</span>
          <ActionButton variant="outline" size="sm" onClick={reload}>
            <RotateCw size={13} /> Try again
          </ActionButton>
        </section>
      )}

      {state === "loaded" && data?.resources.length === 0 && (
        <section className="dependency-state" role="status">
          <Database size={22} />
          <strong>No dependency resources configured</strong>
          <span>Configure the backend dependency provider to list read-only RDS or ElastiCache observations.</span>
        </section>
      )}

      {state === "loaded" && data && data.resources.length > 0 && (
        <div className="dependency-list">
          {data.resources.map((resource) => (
            <DependencyCard
              key={`${resource.resource_type}:${resource.resource_id}`}
              resource={resource}
            />
          ))}
        </div>
      )}

      <p className="dependency-readonly-note">
        This workspace is read-only. It does not restart, modify, scale, flush, fail over, or delete infrastructure.
      </p>
    </div>
  );
}
