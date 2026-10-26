import { AlertTriangle, ClipboardList, RotateCw } from "lucide-react";
import { ActionButton } from "@/components/atoms/ActionButton";
import { formatDuration } from "@/lib/time";
import { ResourceMetrics } from "../components/ResourceMetrics";
import { TaskSelector } from "../components/TaskSelector";
import { TestResultSummary } from "../components/TestResultSummary";
import { useTasksResourcesWorkspace } from "../hooks/useTasksResourcesWorkspace";

const diagnosticLabels = {
  idle: "IDLE",
  starting: "STARTING",
  running: "RUNNING",
  completed: "COMPLETED",
  stopped: "STOPPED",
  failed: "FAILED",
} as const;

export function TasksResourcesPage() {
  const {
    tasks,
    selectedRecord,
    selectedTaskId,
    diagnosticSession,
    status,
    resourceStatus,
    error,
    resourceError,
    selectTask,
    reload,
  } = useTasksResourcesWorkspace();

  const isEmpty = status === "success" && tasks.length === 0;
  const noSelection = status === "success" && tasks.length > 0 && selectedTaskId === null;
  const diagnosticStatus = diagnosticSession.status;
  const diagnosticStatusClass = diagnosticStatus === "starting" ? "diagnostic-running" : `diagnostic-${diagnosticStatus}`;
  const elapsedLabel = formatDuration(diagnosticSession.elapsedSeconds, "compact");

  return (
    <div className="tasks-resources-page">
      <header className="tasks-resources-heading">
        <div>
          <div className="eyebrow">TESTING / TASKS & RESOURCES</div>
          <h1>Tasks & Resources Testing</h1>
          <p>Inspect running ECS tasks and resource metrics discovered from the configured AWS clusters.</p>
        </div>
        <span className="task-demo-badge"><span /> AWS ECS INVENTORY</span>
      </header>

      <div className="task-resource-safety-note">
        <AlertTriangle size={14} />
        <span>
          {selectedRecord?.metrics.provider === "mock"
            ? "Mock metrics were explicitly enabled; these values are not live AWS telemetry."
            : selectedRecord?.metrics.provider === "cloudwatch"
              ? "Resource measurements are CloudWatch aggregates for the configured ECS service, not task-specific diagnostic execution results."
              : selectedRecord?.metrics.provider === "prometheus"
                ? "Resource measurements are Prometheus range aggregates for the configured task_id label, not diagnostic execution results."
                  : "The backend reports the metrics source with each response. Resource measurements are unavailable until a live provider is configured."}
        </span>
      </div>

      <section className="task-resource-panel task-diagnostic-context" aria-labelledby="diagnostic-context-title">
        <div className="task-diagnostic-context-title">
          <div className="task-resource-panel-title"><ClipboardList size={15} /><h2 id="diagnostic-context-title">Diagnostic observation</h2></div>
          <span className={`task-diagnostic-state ${diagnosticStatusClass}`} role="status" aria-live="polite">
            <span />{diagnosticLabels[diagnosticStatus]}
          </span>
        </div>
        <div className="task-diagnostic-context-controls">
          <div>
            <strong>{diagnosticSession.targetScope?.displayName ?? "No active diagnostic session"}</strong>
            <span>
              {diagnosticSession.sessionId
                ? `Session ${diagnosticSession.sessionId} · ${diagnosticSession.startedAt?.toLocaleTimeString() ?? "Start time unavailable"} · ${elapsedLabel}`
                : "Start a diagnostic session from System Overview to share its state here."}
            </span>
          </div>
          <div className="task-diagnostic-session-meta">
            {diagnosticSession.endedAt && <span>Ended <strong>{diagnosticSession.endedAt.toLocaleTimeString()}</strong></span>}
          </div>
        </div>
      </section>

      {status === "loading" && (
        <div className="task-resource-state-card" role="status">
          <span className="task-resource-spinner" />
          <strong>Loading backend task data</strong>
          <span>Reading task inventory from the DCC API…</span>
        </div>
      )}
      {status === "error" && (
        <div className="task-resource-state-card error" role="alert">
          <AlertTriangle size={22} />
          <strong>Could not load task/resource data</strong>
          <span>{error ?? "The DCC backend returned an unknown error."}</span>
          <ActionButton variant="outline" size="sm" onClick={reload}><RotateCw size={13} /> Retry</ActionButton>
        </div>
      )}
      {isEmpty && (
        <div className="task-resource-state-card" role="status">
          <ClipboardList size={22} />
          <strong>No tasks available</strong>
          <span>The backend task endpoint returned no tasks.</span>
        </div>
      )}

      {status === "success" && tasks.length > 0 && (
        <>
          <TaskSelector tasks={tasks} selectedTaskId={selectedTaskId} onSelect={selectTask} />

          {noSelection ? (
            <div className="task-resource-state-card" role="status">
              <ClipboardList size={22} />
              <strong>Select a task</strong>
              <span>Choose a task above to inspect its state and resource metrics.</span>
            </div>
          ) : resourceStatus === "loading" ? (
            <div className="task-resource-state-card" role="status">
              <span className="task-resource-spinner" />
              <strong>Loading task resources</strong>
              <span>Reading resource metrics for {selectedTaskId}…</span>
            </div>
          ) : resourceStatus === "error" || resourceStatus === "unavailable" ? (
            <div className={`task-resource-state-card${resourceStatus === "error" ? " error" : ""}`} role={resourceStatus === "error" ? "alert" : "status"}>
              <AlertTriangle size={22} />
              <strong>{resourceStatus === "error" ? "Could not load task resources" : "Task resources unavailable"}</strong>
              <span>{resourceError ?? "The selected task is no longer available from the backend."}</span>
              <ActionButton variant="outline" size="sm" onClick={reload}><RotateCw size={13} /> Retry</ActionButton>
            </div>
          ) : selectedRecord ? (
            <>
              <section className="task-selected-summary" aria-label="Selected task details">
                <div>
                  <span>SELECTED TASK</span>
                  <strong>{selectedRecord.task.name}</strong>
                  <code>{selectedRecord.task.taskId}</code>
                </div>
                <dl>
                  <div><dt>Service</dt><dd>{selectedRecord.task.serviceName}</dd></div>
                  <div><dt>Desired count</dt><dd>{selectedRecord.task.desiredCount ?? "Unavailable"}</dd></div>
                  <div><dt>Current count</dt><dd>{selectedRecord.task.currentCount ?? "Unavailable"}</dd></div>
                  <div><dt>Health</dt><dd>{selectedRecord.task.health}</dd></div>
                  <div><dt>Availability</dt><dd>{selectedRecord.task.availability}</dd></div>
                  <div><dt>Cluster</dt><dd>{selectedRecord.task.clusterArn}</dd></div>
                  <div><dt>Task definition</dt><dd>{selectedRecord.task.taskDefinition}</dd></div>
                  <div><dt>Launch type</dt><dd>{selectedRecord.task.launchType}</dd></div>
                  <div><dt>CPU / memory</dt><dd>{selectedRecord.task.cpu ?? "—"} / {selectedRecord.task.memory ?? "—"}</dd></div>
                  <div><dt>Availability zone</dt><dd>{selectedRecord.task.availabilityZone ?? "—"}</dd></div>
                  <div><dt>Network mode</dt><dd>{selectedRecord.task.networkMode ?? "—"}</dd></div>
                  <div><dt>Private IP</dt><dd>{selectedRecord.task.privateIp ?? "—"}</dd></div>
                  <div><dt>Subnet</dt><dd>{selectedRecord.task.subnetId ?? "—"}</dd></div>
                  <div><dt>Security groups</dt><dd>{selectedRecord.task.securityGroupIds.join(", ") || "—"}</dd></div>
                  <div><dt>Containers</dt><dd>{selectedRecord.task.containers.map((container) => `${container.name} (${container.lastStatus})`).join(", ") || "—"}</dd></div>
                </dl>
              </section>

              <div className="task-resource-section-heading">
                <div>
                  <h2>{selectedRecord.metrics.provider === "mock" ? "Baseline vs during session" : "Baseline vs current metrics"}</h2>
                  <p>{selectedRecord.metrics.provider === "mock"
                    ? "Backend mock values are not measured diagnostic results."
                    : `${selectedRecord.metrics.provider === "cloudwatch" ? "CloudWatch" : "Prometheus"} values are aggregates, not measurements attributed to this diagnostic session.`}</p>
                </div>
                <span>{selectedRecord.metrics.source}</span>
              </div>
              <ResourceMetrics metrics={selectedRecord.metrics} />

              <div className="task-resource-lower-grid">
                <section className="task-resource-panel task-trend-unavailable" role="status">
                  <ClipboardList size={20} />
                  <strong>Resource trend unavailable</strong>
                  <span>The backend currently returns aggregate baseline, current, and peak values only; it does not provide time-series samples.</span>
                </section>
                <TestResultSummary
                  session={diagnosticSession}
                  metricsProvider={selectedRecord.metrics.provider}
                />
              </div>
            </>
          ) : null}
        </>
      )}

      <footer className="tasks-resources-footer">
        <span>Task/resource observation · Backend metric provider</span>
        <span>DCC · TASKS & RESOURCES</span>
      </footer>
    </div>
  );
}
