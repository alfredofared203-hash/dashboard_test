import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ActionButton } from "@/components/atoms/ActionButton";
import { PageTitle } from "@/components/molecules/PageTitle";
import { Toast } from "@/components/molecules/Toast";
import { DiagnosticControlPanel } from "@/features/diagnostics/components/DiagnosticControlPanel";
import { MetricsGrid } from "@/components/organisms/MetricsGrid";
import { RecentEventsPanel } from "@/components/organisms/RecentEventsPanel";
import { ServiceHealthTable } from "@/components/organisms/ServiceHealthTable";
import { useDiagnosticSession } from "@/features/diagnostics/hooks/useDiagnosticSession";
import { listECSInventory } from "@/lib/api/tasksResources";
import { listLogs } from "@/lib/api/logs";
import type { RecentEvent, Service, SystemOverviewMetrics } from "@/types/dashboard";
import type { LogEntry } from "@/features/logs-diagnostics/types/logs";
import { ApiError } from "@/lib/api/client";

function getOverviewMetrics(services: Service[], runningTasks: number): SystemOverviewMetrics {
  const totals = services.reduce(
    (summary, service) => ({
      desiredTasks: summary.desiredTasks + (service.desiredTasks ?? 0),
      healthyServices: summary.healthyServices + (service.status === "Healthy" ? 1 : 0),
    }),
    { desiredTasks: 0, healthyServices: 0 },
  );
  return {
    totalServices: services.length,
    healthyServices: totals.healthyServices,
    servicesNeedingAttention: services.length - totals.healthyServices,
    runningTasks,
    desiredTasks: totals.desiredTasks,
    averageCpu: null,
    averageMemory: null,
  };
}

function toRecentEvent(log: LogEntry): RecentEvent {
  return {
    time: new Date(log.timestamp).toLocaleTimeString(),
    title: log.message || log.source,
    detail: log.taskId,
    service: log.service,
    severity: log.severity === "ERROR"
      ? "critical"
      : log.severity === "WARN"
        ? "warning"
        : "info",
  };
}

export function SystemOverviewPage() {
  const navigate = useNavigate();
  const diagnosticSession = useDiagnosticSession();
  const { start, stop } = diagnosticSession;
  const [notice, setNotice] = useState("");
  const [services, setServices] = useState<Service[]>([]);
  const [runningTasks, setRunningTasks] = useState<Array<{ id: string; label: string }>>([]);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [events, setEvents] = useState<RecentEvent[]>([]);
  const [logsUnavailable, setLogsUnavailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const inventory = await listECSInventory();
      setServices(inventory.services.map((service) => ({
        name: service.name,
        detail: service.cluster_arn,
        status: service.status === "healthy" ? "Healthy" : "Degraded",
        runningTasks: service.running_count,
        desiredTasks: service.desired_count,
        cpu: null,
        memory: null,
        updated: "Just now",
      })));
      const tasks = inventory.tasks.map((task) => ({
        id: task.id,
        label: `${task.service_name ?? task.task_definition_family} · ${task.id}`,
      }));
      setRunningTasks(tasks);
      setSelectedTaskId((current) => tasks.some((task) => task.id === current) ? current : "");
    } catch (reason) {
      setServices([]);
      setRunningTasks([]);
      setLoadError(reason instanceof ApiError
        ? reason.message
        : "AWS ECS inventory could not be loaded.");
    } finally {
      setLoading(false);
    }

    try {
      setEvents((await listLogs()).map(toRecentEvent));
      setLogsUnavailable(false);
    } catch {
      setEvents([]);
      setLogsUnavailable(true);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (diagnosticSession.loadError) setNotice(diagnosticSession.loadError);
  }, [diagnosticSession.loadError]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 3200);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const metrics = useMemo(
    () => getOverviewMetrics(services, runningTasks.length),
    [services, runningTasks.length],
  );

  const startDiagnostic = async () => {
    try {
      setNotice(
        await start(selectedTaskId)
          ? "Diagnostic session started."
          : "A diagnostic session is already active.",
      );
    } catch (reason) {
      setNotice(
        reason instanceof ApiError
          ? reason.message
          : "The diagnostic session could not be started.",
      );
    }
  };

  const stopDiagnostic = async () => {
    try {
      setNotice(
        await stop()
          ? "Diagnostic session stopped."
          : "There is no active diagnostic session to stop.",
      );
    } catch (reason) {
      setNotice(
        reason instanceof ApiError
          ? reason.message
          : "The diagnostic session could not be stopped.",
      );
    }
  };

  return (
    <>
      <PageTitle
        eyebrow="MONITORING / OVERVIEW"
        title="System Overview"
        description="Live services and running task inventory from configured AWS ECS clusters."
        actions={
          <>
            <span className="data-label">
              <span className="data-indicator" />
              {loading ? "LOADING ECS" : loadError ? "ECS UNAVAILABLE" : "LIVE ECS INVENTORY"}
            </span>
            <ActionButton
              variant="outline"
              size="sm"
              className="refresh-button"
              onClick={() => void reload()}
              disabled={loading}
            >
              <RotateCw size={14} /> Refresh
            </ActionButton>
          </>
        }
      />
      {loadError ? (
        <section className="task-resource-state-card error" role="alert">
          <AlertTriangle size={22} />
          <strong>Could not load AWS ECS inventory</strong>
          <span>{loadError}</span>
          <ActionButton variant="outline" size="sm" onClick={() => void reload()}>
            <RotateCw size={13} /> Retry
          </ActionButton>
        </section>
      ) : (
        <>
          <MetricsGrid metrics={metrics} />
          <div className="task-resource-state-card" role="status">
            <strong>Resource utilization unavailable</strong>
            <span>System-wide CPU and memory aggregates are not inferred from task inventory. Configure a real metrics provider to display measurements.</span>
          </div>
          <div className="lower-grid">
            <ServiceHealthTable
              services={services}
              onViewAll={() => navigate("/tasks-resources")}
              onViewDirectory={() => navigate("/tasks-resources")}
              emptyMessage={loading ? "Loading configured ECS services…" : undefined}
            />
            <div className="right-column">
              <RecentEventsPanel
                events={events}
                onViewAll={() => navigate("/logs")}
                emptyMessage={logsUnavailable
                  ? "Logs are unavailable. Configure the backend logs provider to inspect live events."
                  : "No recent log events were returned."}
              />
              <DiagnosticControlPanel
                session={diagnosticSession}
                isBusy={diagnosticSession.isBusy}
                targetTasks={runningTasks}
                selectedTaskId={selectedTaskId}
                onSelectTask={setSelectedTaskId}
                onStart={() => void startDiagnostic()}
                onStop={() => void stopDiagnostic()}
              />
            </div>
          </div>
        </>
      )}
      {notice && <Toast message={notice} onDismiss={() => setNotice("")} />}
    </>
  );
}
