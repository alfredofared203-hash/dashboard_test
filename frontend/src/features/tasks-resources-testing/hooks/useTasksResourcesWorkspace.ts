import { useCallback, useEffect, useState } from "react";
import { useDiagnosticSessionState } from "@/app/providers/DiagnosticSessionProvider";
import { ApiError } from "@/lib/api/client";
import {
  apiTasksResourcesProvider,
  type ApiTasksResourcesProvider,
} from "../services/apiTasksResourcesProvider";
import type {
  WorkspaceTask,
  WorkspaceTaskResourceRecord,
} from "../types/tasksResources";

export type WorkspaceLoadStatus = "loading" | "success" | "error";
export type ResourceLoadStatus = "idle" | "loading" | "success" | "unavailable" | "error";

function errorMessage(reason: unknown): string {
  return reason instanceof Error
    ? reason.message
    : "The backend could not return task/resource data.";
}

export function useTasksResourcesWorkspace(
  provider: ApiTasksResourcesProvider = apiTasksResourcesProvider,
) {
  const [tasks, setTasks] = useState<WorkspaceTask[]>([]);
  const [selectedRecord, setSelectedRecord] = useState<WorkspaceTaskResourceRecord | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<WorkspaceLoadStatus>("loading");
  const [resourceStatus, setResourceStatus] = useState<ResourceLoadStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [resourceError, setResourceError] = useState<string | null>(null);
  const [reloadCount, setReloadCount] = useState(0);
  const diagnosticSession = useDiagnosticSessionState();

  const reload = useCallback(() => setReloadCount((current) => current + 1), []);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setError(null);

    provider.listTasks().then(
      (nextTasks) => {
        if (cancelled) return;
        setTasks(nextTasks);
        setSelectedTaskId((currentId) => {
          if (currentId && nextTasks.some((task) => task.id === currentId)) return currentId;
          const diagnosticTarget = diagnosticSession.targetScope?.identifier;
          if (diagnosticTarget && nextTasks.some((task) => task.id === diagnosticTarget)) {
            return diagnosticTarget;
          }
          return nextTasks[0]?.id ?? null;
        });
        setStatus("success");
      },
      (reason: unknown) => {
        if (cancelled) return;
        setError(errorMessage(reason));
        setStatus("error");
      },
    );

    return () => {
      cancelled = true;
    };
  }, [diagnosticSession.sessionId, diagnosticSession.targetScope?.identifier, provider, reloadCount]);

  const selectedTask = tasks.find((task) => task.id === selectedTaskId) ?? null;

  useEffect(() => {
    if (status !== "success" || !selectedTask) {
      setSelectedRecord(null);
      setResourceStatus("idle");
      setResourceError(null);
      return;
    }

    let cancelled = false;
    setSelectedRecord(null);
    setResourceStatus("loading");
    setResourceError(null);

    provider.getTaskResources(selectedTask, diagnosticSession.status).then(
      (metrics) => {
        if (cancelled) return;
        setSelectedRecord({ task: selectedTask, metrics });
        setResourceStatus("success");
      },
      (reason: unknown) => {
        if (cancelled) return;
        setResourceError(errorMessage(reason));
        setResourceStatus(reason instanceof ApiError && reason.status === 404 ? "unavailable" : "error");
        if (reason instanceof ApiError && reason.status === 404) {
          const remainingTasks = tasks.filter((task) => task.id !== selectedTask.id);
          setTasks(remainingTasks);
          setSelectedTaskId(remainingTasks[0]?.id ?? null);
        }
      },
    );

    return () => {
      cancelled = true;
    };
  }, [diagnosticSession.status, provider, selectedTask, status, tasks]);

  const selectTask = useCallback((taskId: string) => {
    setSelectedTaskId(taskId);
  }, []);

  return {
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
  };
}
