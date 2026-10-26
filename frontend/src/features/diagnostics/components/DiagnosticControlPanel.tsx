import { ActionButton } from "@/components/atoms/ActionButton";
import { SectionHeader } from "@/components/molecules/SectionHeader";
import type { DiagnosticSession } from "@/features/diagnostics/types";
import { formatDuration } from "@/lib/time";

export interface DiagnosticControlPanelProps {
  session: DiagnosticSession;
  isBusy: boolean;
  targetTasks: Array<{ id: string; label: string }>;
  selectedTaskId: string;
  onSelectTask: (taskId: string) => void;
  onStart: () => void;
  onStop: () => void;
}

const statusLabels: Record<DiagnosticSession["status"], string> = {
  idle: "Ready to run",
  starting: "Starting diagnostic…",
  running: "Diagnostic running",
  completed: "Diagnostic completed",
  stopped: "Session stopped",
  failed: "Diagnostic error",
};

export function DiagnosticControlPanel({
  session,
  isBusy,
  targetTasks,
  selectedTaskId,
  onSelectTask,
  onStart,
  onStop,
}: DiagnosticControlPanelProps) {
  const { status, startedAt, elapsedSeconds } = session;
  const active = status === "starting" || status === "running";
  const elapsedLabel = formatDuration(elapsedSeconds);
  const startedLabel = startedAt
    ? new Intl.DateTimeFormat(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(startedAt)
    : null;

  return (
    <section className="panel diagnostics-panel">
      <SectionHeader
        title="Diagnostics"
        description="Run a diagnostic session"
        action={<span className={`diagnostic-indicator ${status}`} />}
      />
      <div className={`diagnostic-status ${status}`} aria-live="polite">
        <span className="diagnostic-status-dot" />
        <span>{statusLabels[status]}</span>
        <span className="status-time">{startedAt ? elapsedLabel : "—"}</span>
      </div>
      {startedLabel && (
        <div className="diagnostic-session-meta">
          <span>Started at <strong>{startedLabel} local</strong></span>
          <span>Elapsed <strong>{elapsedLabel}</strong></span>
        </div>
      )}
      {session.error && (
        <p className="diagnostic-note" role="alert">
          {session.error.message}
        </p>
      )}
      <label className="diagnostic-target">
        <span>Running ECS task</span>
        <select
          value={selectedTaskId}
          onChange={(event) => onSelectTask(event.currentTarget.value)}
          disabled={active || isBusy || targetTasks.length === 0}
        >
          <option value="">Select a running task</option>
          {targetTasks.map((task) => (
            <option key={task.id} value={task.id}>{task.label}</option>
          ))}
        </select>
      </label>
      <div className="diagnostic-actions">
        <ActionButton className="check-button" onClick={onStart} disabled={active || isBusy || !selectedTaskId}>
          <span className="play-icon">▶</span> CHECK
        </ActionButton>
        <ActionButton className="stop-button" variant="destructive" onClick={onStop} disabled={!active || isBusy}>
          <span className="stop-icon" /> STOP
        </ActionButton>
      </div>
      <p className="diagnostic-note">Session lifecycle and safety limits are managed by the DCC backend.</p>
    </section>
  );
}
