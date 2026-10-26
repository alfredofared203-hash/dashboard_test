import { mockLogsProvider } from "./services/logsProvider";
import type { DiagnosticLogEntry } from "./types/logs";

export type { DiagnosticLogEntry } from "./types/logs";

export async function getLogsForDiagnosticSession(sessionId: string): Promise<DiagnosticLogEntry[]> {
  const result = await mockLogsProvider.getLogs(sessionId);
  return result.entries.filter((entry) => entry.diagnosticSessionId === sessionId);
}
