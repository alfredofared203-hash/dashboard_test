import { useCallback, useEffect, useState } from "react";
import { useDiagnosticSessionState } from "@/app/providers/DiagnosticSessionProvider";
import { ApiError } from "@/lib/api/client";
import { apiLogsProvider, type LogsProvider } from "../services/logsProvider";
import type { DiagnosticLogEntry, LogsLoadStatus } from "../types/logs";

export function useDiagnosticLogs(provider: LogsProvider = apiLogsProvider) {
  const diagnosticSession = useDiagnosticSessionState();
  const [entries, setEntries] = useState<DiagnosticLogEntry[]>([]);
  const [status, setStatus] = useState<LogsLoadStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [reloadCount, setReloadCount] = useState(0);

  const reload = useCallback(() => setReloadCount((current) => current + 1), []);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setError(null);

    Promise.resolve().then(() => provider.getLogs(null)).then(
      (result) => {
        if (cancelled) return;
        setEntries(result.entries);
        setGeneratedAt(result.generatedAt);
        setStatus(result.entries.length > 0 ? "success" : "empty");
      },
      (reason: unknown) => {
        if (cancelled) return;
        setError(
          reason instanceof ApiError
            ? reason.message
            : "The DCC backend could not return diagnostic logs.",
        );
        setStatus("error");
      },
    );

    return () => {
      cancelled = true;
    };
  }, [provider, reloadCount]);

  return { entries, status, error, generatedAt, diagnosticSession, reload };
}
