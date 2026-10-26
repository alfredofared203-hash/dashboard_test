import { createMockLogs } from "../mocks/mockLogs";
import type { LogsResult } from "../types/logs";
import { listLogs } from "@/lib/api/logs";

export interface LogsProvider {
  /**
   * Returns entries scoped to a session, or all available entries when the ID is null.
   * Rejects if retrieval fails; implementations must not control diagnostic sessions.
   */
  getLogs(diagnosticSessionId: string | null): Promise<LogsResult>;
}

export const mockLogsProvider: LogsProvider = {
  async getLogs(diagnosticSessionId) {
    await new Promise<void>((resolve) => window.setTimeout(resolve, 220));
    return {
      entries: createMockLogs(diagnosticSessionId),
      generatedAt: new Date().toISOString(),
    };
  },
};

export const apiLogsProvider: LogsProvider = {
  async getLogs() {
    const entries = await listLogs();
    return {
      entries,
      generatedAt: new Date().toISOString(),
    };
  },
};
