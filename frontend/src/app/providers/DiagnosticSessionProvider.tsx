import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type {
  DiagnosticSession,
  DiagnosticSessionError,
} from "@/types/diagnosticSession";
import { ApiError } from "@/lib/api/client";
import {
  createDiagnosticSession,
  getActiveDiagnosticSession,
  getDiagnosticSession,
  listDiagnosticSessions,
  stopDiagnosticSession,
  type DiagnosticSession as ApiDiagnosticSession,
} from "@/lib/api/diagnosticSessions";

export interface DiagnosticSessionActions {
  start: (targetTaskId: string) => Promise<boolean>;
  stop: () => Promise<boolean>;
}

interface DiagnosticSessionContextValue {
  session: DiagnosticSession;
  actions: DiagnosticSessionActions;
  isBusy: boolean;
  loadError: string | null;
}

const DiagnosticSessionContext = createContext<DiagnosticSessionContextValue | null>(null);

const initialSession: DiagnosticSession = {
  sessionId: null,
  status: "idle",
  startedAt: null,
  endedAt: null,
  elapsedSeconds: 0,
  targetScope: null,
  error: null,
  resultSummary: null,
};

function isActiveStatus(status: DiagnosticSession["status"]): boolean {
  return status === "starting" || status === "running";
}

function toUiSession(session: ApiDiagnosticSession): DiagnosticSession {
  return {
    sessionId: session.id,
    status: session.status,
    startedAt: new Date(session.started_at),
    endedAt: session.stopped_at ? new Date(session.stopped_at) : null,
    elapsedSeconds: session.duration_seconds,
    targetScope: {
      type: "task",
      identifier: session.target_task_id,
      displayName: session.target_task_id,
    },
    error: session.status === "failed"
      ? {
          code: "session_failed",
          message: session.error ?? "The diagnostic session failed.",
        }
      : null,
    resultSummary: null,
  };
}

function toSafeError(reason: unknown): DiagnosticSessionError {
  if (reason instanceof ApiError) {
    return { code: reason.code, message: reason.message };
  }
  return {
    code: "unexpected_error",
    message: "The diagnostic session request could not be completed.",
  };
}

export interface DiagnosticSessionProviderProps {
  children: ReactNode;
}

export function DiagnosticSessionProvider({ children }: DiagnosticSessionProviderProps) {
  const [session, setSession] = useState<DiagnosticSession>(initialSession);
  const [isBusy, setIsBusy] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const sessionRef = useRef(session);
  const busyRef = useRef(true);

  const updateSession = useCallback((next: DiagnosticSession) => {
    sessionRef.current = next;
    setSession(next);
  }, []);

  const updateBusy = useCallback((next: boolean) => {
    busyRef.current = next;
    setIsBusy(next);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadCurrentSession = async () => {
      const activeSession = await getActiveDiagnosticSession();
      if (activeSession) return activeSession;
      const sessions = await listDiagnosticSessions();
      return sessions.at(-1) ?? null;
    };

    loadCurrentSession().then(
      (currentSession) => {
        if (!cancelled && currentSession) updateSession(toUiSession(currentSession));
      },
      (reason: unknown) => {
        if (!cancelled) setLoadError(toSafeError(reason).message);
      },
    ).finally(() => {
      if (!cancelled) updateBusy(false);
    });

    return () => {
      cancelled = true;
    };
  }, [updateBusy, updateSession]);

  const start = useCallback(async (targetTaskId: string) => {
    if (
      busyRef.current
      || isActiveStatus(sessionRef.current.status)
    ) {
      return false;
    }
    if (!targetTaskId.trim()) {
      throw new ApiError("Select a running ECS task before starting diagnostics.", "invalid_target");
    }

    updateBusy(true);
    setLoadError(null);
    const startedAt = new Date();
    const targetScope = {
      type: "task" as const,
      identifier: targetTaskId,
      displayName: targetTaskId,
    };
    updateSession({
      ...initialSession,
      status: "starting",
      startedAt,
      targetScope,
    });

    try {
      const created = await createDiagnosticSession(targetTaskId);
      updateSession(toUiSession(created));
      return true;
    } catch (reason) {
      const error = toSafeError(reason);
      const endedAt = new Date();
      updateSession({
        ...initialSession,
        status: "failed",
        startedAt,
        endedAt,
        elapsedSeconds: Math.max(0, Math.floor((endedAt.getTime() - startedAt.getTime()) / 1000)),
        targetScope,
        error,
      });
      throw reason;
    } finally {
      updateBusy(false);
    }
  }, [updateBusy, updateSession]);

  const stop = useCallback(async () => {
    const current = sessionRef.current;
    if (busyRef.current || current.status !== "running" || !current.sessionId) {
      return false;
    }

    updateBusy(true);
    setLoadError(null);
    try {
      const stopped = await stopDiagnosticSession(current.sessionId);
      updateSession(toUiSession(stopped));
      return true;
    } catch (reason) {
      try {
        const authoritative = await getDiagnosticSession(current.sessionId);
        updateSession(toUiSession(authoritative));
      } catch {
        setLoadError("The session could not be refreshed after the stop request failed.");
      }
      throw reason;
    } finally {
      updateBusy(false);
    }
  }, [updateBusy, updateSession]);

  useEffect(() => {
    if (session.status !== "running" || !session.startedAt) return;
    const interval = window.setInterval(() => {
      const current = sessionRef.current;
      if (current.status !== "running" || !current.startedAt) return;
      const elapsedSeconds = Math.max(
        0,
        Math.floor((Date.now() - current.startedAt.getTime()) / 1000),
      );
      updateSession({ ...current, elapsedSeconds });
    }, 1000);
    return () => window.clearInterval(interval);
  }, [session.sessionId, session.startedAt, session.status, updateSession]);

  useEffect(() => {
    if (session.status !== "running" || !session.sessionId) return;
    let cancelled = false;
    let requestPending = false;
    const sessionId = session.sessionId;

    const refreshSession = async () => {
      if (requestPending) return;
      requestPending = true;
      try {
        const current = await getDiagnosticSession(sessionId);
        const latest = sessionRef.current;
        if (
          !cancelled
          && latest.sessionId === sessionId
          && latest.status === "running"
        ) {
          setLoadError(null);
          if (current.status !== "running") updateSession(toUiSession(current));
        }
      } catch (reason) {
        if (cancelled) return;
        if (reason instanceof ApiError && reason.status === 404) {
          const latest = sessionRef.current;
          if (latest.sessionId === sessionId && latest.status === "running") {
            const endedAt = new Date();
            const startedAt = latest.startedAt?.getTime() ?? endedAt.getTime();
            setLoadError(null);
            updateSession({
              ...latest,
              status: "failed",
              endedAt,
              elapsedSeconds: Math.max(0, Math.floor((endedAt.getTime() - startedAt) / 1000)),
              error: {
                code: "session_not_found",
                message: "The diagnostic session is no longer available on the backend.",
              },
            });
          }
        } else {
          setLoadError(toSafeError(reason).message);
        }
      } finally {
        requestPending = false;
      }
    };

    const interval = window.setInterval(() => {
      void refreshSession();
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [session.sessionId, session.status, updateSession]);

  const actions = useMemo(() => ({ start, stop }), [start, stop]);
  const value = useMemo(
    () => ({ session, actions, isBusy, loadError }),
    [actions, isBusy, loadError, session],
  );

  return <DiagnosticSessionContext.Provider value={value}>{children}</DiagnosticSessionContext.Provider>;
}

function useDiagnosticSessionContext(): DiagnosticSessionContextValue {
  const context = useContext(DiagnosticSessionContext);
  if (!context) {
    throw new Error("DiagnosticSessionProvider must be used within the application root.");
  }
  return context;
}

export function useDiagnosticSessionState(): DiagnosticSession {
  return useDiagnosticSessionContext().session;
}

export function useDiagnosticSessionActions(): DiagnosticSessionActions {
  return useDiagnosticSessionContext().actions;
}

export function useDiagnosticSessionLoadError(): string | null {
  return useDiagnosticSessionContext().loadError;
}

export function useDiagnosticSessionBusy(): boolean {
  return useDiagnosticSessionContext().isBusy;
}
