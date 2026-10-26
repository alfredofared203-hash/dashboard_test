import { ApiError, requestJson } from "./client";

export type DiagnosticSessionStatus = "running" | "stopped" | "completed" | "failed";

export interface DiagnosticSession {
  id: string;
  status: DiagnosticSessionStatus;
  target_task_id: string;
  started_at: string;
  stopped_at: string | null;
  duration_seconds: number;
  execution?: {
    provider: string;
    status: DiagnosticSessionStatus;
  } | null;
  error?: string | null;
}

export interface CreateDiagnosticSessionRequest {
  target_task_id: string;
}

const collectionPath = "/api/diagnostic-sessions/";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isDiagnosticSessionStatus(value: unknown): value is DiagnosticSessionStatus {
  return ["running", "stopped", "completed", "failed"].includes(String(value));
}

function isValidDate(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}

function parseDiagnosticSession(value: unknown): DiagnosticSession {
  if (
    !isRecord(value)
    || typeof value.id !== "string"
    || !isDiagnosticSessionStatus(value.status)
    || typeof value.target_task_id !== "string"
    || !isValidDate(value.started_at)
    || !(value.stopped_at === null || isValidDate(value.stopped_at))
    || typeof value.duration_seconds !== "number"
    || !Number.isInteger(value.duration_seconds)
    || value.duration_seconds < 0
  ) {
    throw new ApiError(
      "The DCC backend returned an invalid diagnostic session.",
      "invalid_response",
    );
  }

  const session: DiagnosticSession = {
    id: value.id,
    status: value.status,
    target_task_id: value.target_task_id,
    started_at: value.started_at,
    stopped_at: value.stopped_at,
    duration_seconds: value.duration_seconds,
  };

  if (value.execution !== undefined && value.execution !== null) {
    if (
      !isRecord(value.execution)
      || typeof value.execution.provider !== "string"
      || !isDiagnosticSessionStatus(value.execution.status)
    ) {
      throw new ApiError(
        "The DCC backend returned invalid diagnostic execution metadata.",
        "invalid_response",
      );
    }
    session.execution = {
      provider: value.execution.provider,
      status: value.execution.status,
    };
  }

  if (value.error !== undefined && value.error !== null && typeof value.error !== "string") {
    throw new ApiError(
      "The DCC backend returned an invalid diagnostic session error.",
      "invalid_response",
    );
  }
  if (typeof value.error === "string" || value.error === null) {
    session.error = value.error;
  }

  return session;
}

export async function getActiveDiagnosticSession(): Promise<DiagnosticSession | null> {
  const response = await requestJson(`${collectionPath}active/`);
  if (!isRecord(response) || !("session" in response)) {
    throw new ApiError(
      "The DCC backend returned an invalid active-session response.",
      "invalid_response",
    );
  }
  return response.session === null ? null : parseDiagnosticSession(response.session);
}

export async function getDiagnosticSession(sessionId: string): Promise<DiagnosticSession> {
  return parseDiagnosticSession(
    await requestJson(`${collectionPath}${encodeURIComponent(sessionId)}/`),
  );
}

export async function createDiagnosticSession(
  targetTaskId: string,
): Promise<DiagnosticSession> {
  const request: CreateDiagnosticSessionRequest = { target_task_id: targetTaskId };
  return parseDiagnosticSession(await requestJson(collectionPath, {
    method: "POST",
    body: JSON.stringify(request),
  }));
}

export async function stopDiagnosticSession(sessionId: string): Promise<DiagnosticSession> {
  return parseDiagnosticSession(await requestJson(
    `${collectionPath}${encodeURIComponent(sessionId)}/stop/`,
    { method: "POST" },
  ));
}

export async function listDiagnosticSessions(): Promise<DiagnosticSession[]> {
  const response = await requestJson(collectionPath);
  if (!Array.isArray(response)) {
    throw new ApiError(
      "The DCC backend returned an invalid diagnostic-session list.",
      "invalid_response",
    );
  }
  return response.map(parseDiagnosticSession);
}
