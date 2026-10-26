export type LogSeverity = "DEBUG" | "INFO" | "WARN" | "ERROR";

export type LogMetadataValue =
  | string
  | number
  | boolean
  | null
  | LogMetadataValue[]
  | { [key: string]: LogMetadataValue };

export type LogMetadata = Record<string, LogMetadataValue>;

export interface LogEntry {
  id: string;
  timestamp: string;
  severity: LogSeverity;
  service: string;
  taskId: string;
  source: string;
  message: string;
  diagnosticSessionId: string | null;
  traceId?: string;
  metadata?: LogMetadata;
}

export type DiagnosticLogEntry = LogEntry;

export interface LogsResult {
  entries: DiagnosticLogEntry[];
  generatedAt: string;
}

export type LogsLoadStatus = "loading" | "success" | "empty" | "error";
