import { Activity, FileText, FlaskConical } from "lucide-react";
import type { DiagnosticImpactReport, ImpactPhaseName } from "../types/report";

interface ReportSummaryCardsProps {
  report: DiagnosticImpactReport;
}

const phaseNames: ImpactPhaseName[] = ["baseline", "during", "post"];

export function ReportSummaryCards({ report }: ReportSummaryCardsProps) {
  const { measurements, logs, api_testing: apiTesting } = report;
  const sourceLabel = measurements.sources.length > 0
    ? measurements.sources.join(", ")
    : "No source captured";
  const sessionLogCount = logs.summary.session_correlated_count;
  const contextualLogCount = logs.summary.contextual_count;

  return (
    <div className="impact-summary-grid">
      <section className="impact-summary-card" aria-labelledby="impact-measurements-heading">
        <div className="impact-summary-heading"><Activity size={15} /><h2 id="impact-measurements-heading">Resource measurements</h2></div>
        <div className="impact-summary-primary">
          <strong>{measurements.availability.toUpperCase()}</strong>
          <span>measurement availability</span>
        </div>
        <div className="impact-summary-stats">
          {phaseNames.map((phaseName) => (
            <span key={phaseName}>
              <strong>{phaseName}</strong>
              {measurements.phases[phaseName].status.replaceAll("_", " ")}
            </span>
          ))}
        </div>
        <p>
          Source: {sourceLabel}. Scope: {measurements.scope === "configured_service_aggregate"
            ? "configured ECS service aggregate, not per-task"
            : "target task"}.
          {" "}Mock metrics are not live telemetry.
        </p>
      </section>

      <section className="impact-summary-card" aria-labelledby="impact-api-heading">
        <div className="impact-summary-heading"><FlaskConical size={15} /><h2 id="impact-api-heading">API Testing</h2></div>
        <div className="impact-summary-primary"><strong>NOT COLLECTED</strong></div>
        <p>{apiTesting.message}</p>
      </section>

      <section className="impact-summary-card" aria-labelledby="impact-logs-heading">
        <div className="impact-summary-heading"><FileText size={15} /><h2 id="impact-logs-heading">Logs</h2></div>
        <div className="impact-summary-primary">
          <strong>{sessionLogCount === null ? "—" : sessionLogCount}</strong>
          <span>session-correlated entries</span>
        </div>
        <div className="impact-summary-stats">
          <span><strong>{logs.summary.errors ?? "—"}</strong> errors</span>
          <span><strong>{logs.summary.warnings ?? "—"}</strong> warnings</span>
          <span><strong>{contextualLogCount ?? "—"}</strong> contextual only</span>
        </div>
        <p>
          {logs.availability === "available"
            ? "Only exact session-ID matches are correlated."
            : logs.availability === "not_configured"
              ? "The logs provider is not configured."
              : "Log measurements are unavailable."}
        </p>
      </section>
    </div>
  );
}
