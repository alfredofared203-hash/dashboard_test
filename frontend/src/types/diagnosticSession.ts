export type DiagnosticSessionStatus =
  | "idle"
  | "starting"
  | "running"
  | "completed"
  | "stopped"
  | "failed";

export interface DiagnosticTargetScope {
  type: "system" | "service" | "task";
  identifier: string;
  displayName: string;
}

export interface DiagnosticSessionError {
  code: string;
  message: string;
}

export interface DiagnosticSessionResultSummary {
  overallStatus: "completed" | "warning" | "failed";
  checkedItems: number;
  passedItems: number;
  warningItems: number;
  failedItems: number;
}

export interface DiagnosticSession {
  sessionId: string | null;
  status: DiagnosticSessionStatus;
  startedAt: Date | null;
  endedAt: Date | null;
  elapsedSeconds: number;
  targetScope: DiagnosticTargetScope | null;
  error: DiagnosticSessionError | null;
  resultSummary: DiagnosticSessionResultSummary | null;
}
