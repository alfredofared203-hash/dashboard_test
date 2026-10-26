import { ApiError, requestJson } from "./client";
import type {
  LogEntry,
  LogMetadata,
  LogMetadataValue,
  LogSeverity,
} from "@/features/logs-diagnostics/types/logs";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isLogMetadataValue(value: unknown): value is LogMetadataValue {
  if (
    value === null
    || typeof value === "string"
    || typeof value === "boolean"
    || (typeof value === "number" && Number.isFinite(value))
  ) {
    return true;
  }
  if (Array.isArray(value)) return value.every(isLogMetadataValue);
  return isRecord(value)
    && Object.values(value).every(isLogMetadataValue);
}

function isLogMetadata(value: unknown): value is LogMetadata {
  return isRecord(value) && Object.values(value).every(isLogMetadataValue);
}

function isLogSeverity(value: unknown): value is LogSeverity {
  return value === "DEBUG" || value === "INFO" || value === "WARN" || value === "ERROR";
}

function requiredString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function parseLogEntry(value: unknown): LogEntry {
  const taskIdentifier = isRecord(value)
    ? value.task_identifier ?? value.task_id
    : undefined;
  if (
    !isRecord(value)
    || !requiredString(value.id)
    || !requiredString(value.timestamp)
    || Number.isNaN(Date.parse(value.timestamp))
    || !isLogSeverity(value.severity)
    || !requiredString(value.service)
    || !requiredString(taskIdentifier)
    || !requiredString(value.source)
    || typeof value.message !== "string"
    || !(value.diagnostic_session_id === null || requiredString(value.diagnostic_session_id))
  ) {
    throw new ApiError("The DCC backend returned an invalid log entry.", "invalid_response");
  }

  const traceId = value.trace_id ?? value.request_id;
  if (traceId !== undefined && traceId !== null && typeof traceId !== "string") {
    throw new ApiError("The DCC backend returned an invalid log identifier.", "invalid_response");
  }

  let metadata: LogMetadata | undefined;
  if (value.metadata !== undefined) {
    if (!isLogMetadata(value.metadata)) {
      throw new ApiError("The DCC backend returned invalid log metadata.", "invalid_response");
    }
    metadata = value.metadata;
  }

  return {
    id: value.id,
    timestamp: new Date(value.timestamp).toISOString(),
    severity: value.severity,
    service: value.service,
    taskId: taskIdentifier,
    source: value.source,
    message: value.message,
    diagnosticSessionId: value.diagnostic_session_id,
    ...(typeof traceId === "string" ? { traceId } : {}),
    ...(metadata ? { metadata } : {}),
  };
}

export async function listLogs(): Promise<LogEntry[]> {
  const response = await requestJson("/api/logs/");
  if (!Array.isArray(response)) {
    throw new ApiError("The DCC backend returned an invalid log list.", "invalid_response");
  }
  return response.map(parseLogEntry);
}
