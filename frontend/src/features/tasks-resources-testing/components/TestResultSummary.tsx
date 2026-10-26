import { CircleDashed, Clock3, LoaderCircle, XCircle } from "lucide-react";
import type { DiagnosticSession } from "@/types/diagnosticSession";
import { formatDuration } from "@/lib/time";

interface TestResultSummaryProps {
  session: DiagnosticSession;
  metricsProvider: "mock" | "cloudwatch" | "prometheus";
}

function statusPresentation(
  metricsProvider: TestResultSummaryProps["metricsProvider"],
): Record<
  DiagnosticSession["status"],
  { label: string; className: string; icon: typeof CircleDashed; message: string }
> {
  const metricsDescription = metricsProvider === "mock"
    ? "Displayed resource values remain illustrative backend mock data."
    : metricsProvider === "cloudwatch"
      ? "Displayed resource values are CloudWatch aggregates, not diagnostic execution results."
      : "Displayed resource values are Prometheus range aggregates, not diagnostic execution results.";
  return {
    idle: {
      label: "NOT PROVIDED",
      className: "result-not-running",
      icon: CircleDashed,
      message: metricsProvider === "mock"
        ? "No diagnostic session is active. Displayed resource values are explicitly enabled mock metrics."
        : "No diagnostic session is active. Provider resource metrics are available independently of a diagnostic run.",
    },
    starting: {
      label: "STARTING",
      className: "result-running",
      icon: LoaderCircle,
      message: "The backend diagnostic session is starting; no execution results are available.",
    },
    running: {
      label: "RUNNING",
      className: "result-running",
      icon: LoaderCircle,
      message: `The diagnostic session is running. ${metricsDescription}`,
    },
    completed: {
      label: "NOT PROVIDED",
      className: "result-not-running",
      icon: CircleDashed,
      message: "The backend does not currently return diagnostic execution results.",
    },
    stopped: {
      label: "NOT PROVIDED",
      className: "result-not-running",
      icon: CircleDashed,
      message: "The diagnostic session was stopped; no final diagnostic result is available.",
    },
    failed: {
      label: "FAILED",
      className: "result-fail",
      icon: XCircle,
      message: "The diagnostic session failed. The backend does not provide a resource test result.",
    },
  };
}

const diagnosticLabel: Record<DiagnosticSession["status"], string> = {
  idle: "Idle",
  starting: "Starting",
  running: "Running",
  completed: "Completed",
  stopped: "Stopped",
  failed: "Failed",
};

export function TestResultSummary({ session, metricsProvider }: TestResultSummaryProps) {
  const presentation = statusPresentation(metricsProvider)[session.status];
  const Icon = presentation.icon;
  const durationLabel = session.sessionId
    ? formatDuration(session.elapsedSeconds, "compact")
    : "—";

  return (
    <section className="task-resource-panel task-test-result" aria-labelledby="task-test-result-title">
      <header className="task-resource-panel-heading">
        <div className="task-resource-panel-title"><Clock3 size={15} /><h2 id="task-test-result-title">Diagnostic result</h2></div>
        <span className={`task-result-badge ${presentation.className}`}><Icon size={13} />{presentation.label}</span>
      </header>
      <div className="task-test-result-content">
        <p className="task-result-summary-text">{presentation.message}</p>
        <dl className="task-result-details">
          <div><dt>Diagnostic state</dt><dd>{diagnosticLabel[session.status]}</dd></div>
          <div><dt>Target</dt><dd>{session.targetScope?.displayName ?? "No active session"}</dd></div>
          <div><dt>Started</dt><dd>{session.startedAt ? session.startedAt.toLocaleTimeString() : "Not started"}</dd></div>
          <div><dt>Duration</dt><dd>{durationLabel}</dd></div>
          <div><dt>Session ID</dt><dd>{session.sessionId ?? "—"}</dd></div>
          <div><dt>Execution result</dt><dd>Not provided by backend</dd></div>
        </dl>
        {session.error && (
          <div className="task-result-messages failure" role="alert">
            <strong>{session.error.code}</strong>
            <span>{session.error.message}</span>
          </div>
        )}
      </div>
    </section>
  );
}
