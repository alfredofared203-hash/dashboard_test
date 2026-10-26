import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import type { DiagnosticLogEntry } from "../types/logs";

interface LogDetailsDialogProps {
  entry: DiagnosticLogEntry | null;
  onClose: () => void;
}

const fullTimestampFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "full",
  timeStyle: "medium",
});

export function LogDetailsDialog({ entry, onClose }: LogDetailsDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (entry && !dialog.open) dialog.showModal();
    if (!entry && dialog.open) dialog.close();
  }, [entry]);

  if (!entry) return null;

  return (
    <dialog
      ref={dialogRef}
      className="logs-detail-dialog"
      aria-labelledby="log-detail-title"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          onClose();
        }
      }}
      onCancel={onClose}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialogRef.current) onClose();
      }}
    >
      <div className="logs-detail-heading">
        <div>
          <div className="logs-detail-eyebrow">LOG ENTRY · {entry.id}</div>
          <h2 id="log-detail-title">Log details</h2>
        </div>
        <button type="button" className="logs-icon-button" aria-label="Close log details" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <dl className="logs-detail-grid">
        <div><dt>Timestamp</dt><dd>{fullTimestampFormatter.format(new Date(entry.timestamp))}</dd></div>
        <div><dt>Severity</dt><dd><span className={`logs-severity logs-severity-${entry.severity.toLowerCase()}`}>{entry.severity}</span></dd></div>
        <div><dt>Service</dt><dd>{entry.service}</dd></div>
        <div><dt>Task</dt><dd><code>{entry.taskId}</code></dd></div>
        <div><dt>Source / component</dt><dd>{entry.source}</dd></div>
        <div><dt>Diagnostic session</dt><dd><code>{entry.diagnosticSessionId ?? "—"}</code></dd></div>
        {entry.traceId && <div><dt>Trace / request ID</dt><dd><code>{entry.traceId}</code></dd></div>}
        <div className="logs-detail-message"><dt>Message</dt><dd>{entry.message}</dd></div>
        {entry.metadata && (
          <div className="logs-detail-metadata">
            <dt>Metadata</dt>
            <dd>
              <pre>{JSON.stringify(entry.metadata, null, 2)}</pre>
            </dd>
          </div>
        )}
      </dl>
    </dialog>
  );
}
