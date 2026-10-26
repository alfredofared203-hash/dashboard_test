import {
  AlertTriangle,
  CheckCircle2,
  CircleAlert,
  CircleX,
  Clock3,
  RotateCw,
} from "lucide-react";
import { ActionButton } from "@/components/atoms/ActionButton";
import { formatDuration } from "@/lib/time";
import { useDiagnosticImpactReport } from "../hooks/useDiagnosticImpactReport";
import { ReportFindings } from "../components/ReportFindings";
import { ResourceImpactSection } from "../components/ResourceImpactSection";
import { DependencyImpactSection } from "../components/DependencyImpactSection";
import { ReportSummaryCards } from "../components/ReportSummaryCards";
import type { ImpactClassification } from "../types/report";
import "../diagnostic-impact.css";

const sessionStatusLabels = {
  idle: "IDLE",
  starting: "STARTING",
  running: "RUNNING",
  completed: "COMPLETED",
  stopped: "STOPPED",
  failed: "FAILED",
} as const;

const classificationIcons: Record<ImpactClassification, typeof CheckCircle2> = {
  none: CheckCircle2,
  low: CircleAlert,
  moderate: CircleAlert,
  high: CircleX,
  unknown: Clock3,
};

export function DiagnosticImpactWorkspace() {
  const { report, status, error, session, reload } = useDiagnosticImpactReport();
  const sessionIsActive = report?.session.status === "running"
    || session.status === "starting"
    || session.status === "running";
  const OutcomeIcon = report ? classificationIcons[report.impact.classification] : Clock3;
  const classificationStyle = report?.impact.classification === "high"
    ? "fail"
    : report?.impact.classification === "low" || report?.impact.classification === "moderate"
      ? "warning"
      : report?.impact.classification === "unknown"
        ? "not-completed"
        : "";
  const sourceLabel = report?.measurements.sources.length
    ? report.measurements.sources.join(" · ")
    : "NO RESOURCE SOURCE";

  return (
    <div className="diagnostic-impact-page">
      <header className="impact-page-heading">
        <div>
          <div className="eyebrow">REPORTING / DIAGNOSTIC IMPACT</div>
          <h1>Diagnostic Impact Report</h1>
          <p>Review backend-captured resource measurements, session logs, and data limitations.</p>
        </div>
        <span className="impact-mock-badge"><span /> BACKEND REPORT · {sourceLabel}</span>
      </header>

      {!session.sessionId && status === "empty" && (
        <section className="impact-empty-state" role="status">
          <span className="impact-empty-icon"><Clock3 size={23} /></span>
          <div className="eyebrow">CURRENT SESSION</div>
          <h2>No diagnostic session selected</h2>
          <p>Start a diagnostic session from the System Overview to generate or inspect a diagnostic impact report.</p>
        </section>
      )}

      {status === "loading" && (
        <section className="impact-state-card" role="status">
          <span className="impact-spinner" />
          <strong>Loading diagnostic impact report</strong>
          <span>Retrieving the session-associated measurements and report from DCC.</span>
        </section>
      )}

      {status === "error" && (
        <section className="impact-state-card impact-state-error" role="alert">
          <AlertTriangle size={22} />
          <strong>Could not load the diagnostic impact report</strong>
          <span>{error ?? "The diagnostic impact provider failed unexpectedly."}</span>
          <ActionButton variant="outline" size="sm" onClick={reload}><RotateCw size={13} /> Try again</ActionButton>
        </section>
      )}

      {status === "empty" && session.sessionId && (
        <section className="impact-state-card" role="status">
          <CircleAlert size={22} />
          <strong>No report data available</strong>
          <span>A diagnostic session exists, but the provider did not return report data.</span>
          <ActionButton variant="outline" size="sm" onClick={reload}><RotateCw size={13} /> Retry report</ActionButton>
        </section>
      )}

      {status === "report" && report && (
        <>
          <section className="impact-report-header" aria-labelledby="impact-report-session-heading">
            <div className="impact-report-header-top">
              <div>
                <div className="impact-report-eyebrow">BACKEND SESSION REPORT</div>
                <h2 id="impact-report-session-heading">{report.target.name ?? report.target.task_id}</h2>
                <code>{report.session.id}</code>
              </div>
              <div className="impact-report-header-actions">
                <span className={`impact-session-status impact-session-${report.session.status}`}>
                  <span />{sessionStatusLabels[report.session.status]}
                </span>
                <ActionButton variant="outline" size="sm" onClick={reload}>
                  <RotateCw size={13} /> Refresh
                </ActionButton>
              </div>
            </div>
            <div className="impact-session-meta">
              <div><span>Started</span><strong>{new Date(report.session.started_at).toLocaleString()}</strong></div>
              <div><span>Duration</span><strong>{formatDuration(report.session.duration_seconds)}</strong></div>
              <div><span>Target</span><strong>{report.target.service_name ?? report.target.task_id}</strong></div>
              <div><span>Report updated</span><strong>{new Date(report.generated_at).toLocaleTimeString()}</strong></div>
            </div>
          </section>

          {sessionIsActive && (
            <div className="impact-incomplete-banner" role="status">
              <Clock3 size={15} />
              <span><strong>Report is still being collected.</strong> The session is active; some results may be incomplete.</span>
            </div>
          )}
          {report.session.status === "stopped" && (
            <div className="impact-incomplete-banner" role="status">
              <AlertTriangle size={15} />
              <span><strong>Session stopped before completion.</strong> The available measurements are not a final diagnostic result.</span>
            </div>
          )}

          {report.session.status === "failed" && report.session.error && (
            <div className="impact-incomplete-banner" role="status">
              <AlertTriangle size={15} />
              <span><strong>Diagnostic session failed.</strong> {report.session.error}</span>
            </div>
          )}

          <section className={`impact-outcome ${classificationStyle ? `impact-outcome-${classificationStyle}` : ""}`} aria-label="Diagnostic impact classification">
            <div className="impact-outcome-icon"><OutcomeIcon size={19} /></div>
            <div className="impact-outcome-copy">
              <span>DCC IMPACT CLASSIFICATION</span>
              <strong>{report.impact.classification.toUpperCase()}</strong>
              <p>{report.impact.summary}</p>
            </div>
            <div className="impact-outcome-duration">
              <span><Clock3 size={13} /> DURATION</span>
              <strong>{formatDuration(report.session.duration_seconds)}</strong>
            </div>
          </section>

          <ReportSummaryCards report={report} />
          <ResourceImpactSection resources={report.measurements.metrics} />
          <DependencyImpactSection report={report.dependencies} />
          <ReportFindings report={report} />

          <footer className="impact-page-footer">
            <span>
              {report.measurements.sources.includes("mock")
                ? "Mock provider values are not live AWS telemetry."
                : "Measurements are normalized by the DCC backend."}
              {" "}This report is read-only and does not execute checks or control infrastructure.
            </span>
            <span>DCC · DIAGNOSTIC IMPACT</span>
          </footer>
        </>
      )}
    </div>
  );
}
