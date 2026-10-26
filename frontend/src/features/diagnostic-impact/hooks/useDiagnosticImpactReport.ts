import { useCallback, useEffect, useState } from "react";
import { useDiagnosticSessionState } from "@/app/providers/DiagnosticSessionProvider";
import { backendDiagnosticImpactProvider } from "../providers/backendDiagnosticImpactProvider";
import type { DiagnosticImpactProvider } from "../providers/diagnosticImpactProvider";
import type {
  DiagnosticImpactLoadStatus,
  DiagnosticImpactReport,
} from "../types/report";

export function useDiagnosticImpactReport(
  provider: DiagnosticImpactProvider = backendDiagnosticImpactProvider,
) {
  const session = useDiagnosticSessionState();
  const [report, setReport] = useState<DiagnosticImpactReport | null>(null);
  const [status, setStatus] = useState<DiagnosticImpactLoadStatus>("empty");
  const [error, setError] = useState<string | null>(null);
  const [reloadCount, setReloadCount] = useState(0);

  const reload = useCallback(() => setReloadCount((current) => current + 1), []);

  useEffect(() => {
    let cancelled = false;
    if (!session.sessionId) {
      setReport(null);
      setError(null);
      setStatus("empty");
      return () => {
        cancelled = true;
      };
    }

    setStatus("loading");
    setError(null);

    Promise.resolve().then(() => provider.getReport(session)).then(
      (result) => {
        if (cancelled) return;
        setReport(result);
        setStatus(result ? "report" : "empty");
      },
      (reason: unknown) => {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : "The diagnostic impact provider failed unexpectedly.");
        setStatus("error");
      },
    );

    return () => {
      cancelled = true;
    };
  }, [
    provider,
    reloadCount,
    session.endedAt,
    session.sessionId,
    session.startedAt,
    session.status,
  ]);

  return { report, status, error, session, reload };
}
