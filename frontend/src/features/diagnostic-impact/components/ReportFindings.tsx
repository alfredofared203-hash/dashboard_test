import { AlertTriangle, FileText } from "lucide-react";
import type { DiagnosticImpactReport, ImpactLogEntry } from "../types/report";

interface ReportFindingsProps {
  report: DiagnosticImpactReport;
}

function LogList({ entries, label }: { entries: ImpactLogEntry[]; label: string }) {
  if (entries.length === 0) {
    return <div className="impact-inline-empty">No {label.toLowerCase()} log entries were returned.</div>;
  }
  return (
    <ul className="impact-observations">
      {entries.map((entry) => (
        <li key={entry.id}>
          <FileText size={14} />
          <span>
            <strong>{entry.severity} · {entry.service} · {new Date(entry.timestamp).toLocaleString()}</strong>
            {entry.message}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function ReportFindings({ report }: ReportFindingsProps) {
  return (
    <div className="impact-lower-grid">
      <section className="impact-panel" aria-labelledby="impact-limitations-heading">
        <div className="impact-panel-heading">
          <div className="impact-panel-title"><AlertTriangle size={15} /><h2 id="impact-limitations-heading">Limitations &amp; data gaps</h2></div>
          <p>{report.limitations.length} notes</p>
        </div>
        {report.limitations.length > 0 ? (
          <ul className="impact-observations">
            {report.limitations.map((limitation, index) => (
              <li key={`${index}-${limitation}`}>
                <AlertTriangle size={14} />
                <span>{limitation}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="impact-inline-empty">No limitations were returned.</div>
        )}
      </section>

      <section className="impact-panel" aria-labelledby="impact-logs-heading">
        <div className="impact-panel-heading">
          <div className="impact-panel-title"><FileText size={15} /><h2 id="impact-logs-heading">Log observations</h2></div>
          <p>{report.logs.availability === "available" ? "Normalized backend logs" : "Unavailable"}</p>
        </div>
        <div className="impact-log-group">
          <h3>Explicitly correlated with this session</h3>
          <LogList entries={report.logs.session_correlated} label="Session-correlated" />
        </div>
        <div className="impact-log-group">
          <h3>Contextual only — not attributed to this session</h3>
          <LogList entries={report.logs.contextual} label="Contextual" />
        </div>
      </section>
    </div>
  );
}
