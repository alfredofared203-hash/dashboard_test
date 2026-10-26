export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const localApiBaseUrl = typeof window !== "undefined"
  ? `http://${window.location.hostname}:8000`
  : "http://localhost:8000";
const apiBaseUrl = ((import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? localApiBaseUrl : "/")))
  .replace(/\/+$/, "");

const httpErrorMessages: Record<number, { code: string; message: string }> = {
  400: {
    code: "invalid_request",
    message: "The diagnostic session request is invalid.",
  },
  404: {
    code: "not_found",
    message: "The requested DCC resource was not found.",
  },
  409: {
    code: "session_conflict",
    message: "A diagnostic session cannot perform that action right now.",
  },
  401: {
    code: "request_unauthorized",
    message: "The DCC backend rejected this request.",
  },
  403: {
    code: "permission_denied",
    message: "The DCC backend does not permit this action.",
  },
  429: {
    code: "rate_limited",
    message: "Too many diagnostic requests. Wait before trying again.",
  },
  502: {
    code: "provider_failure",
    message: "The diagnostic execution provider failed.",
  },
  503: {
    code: "service_unavailable",
    message: "A required DCC provider is temporarily unavailable.",
  },
  504: {
    code: "request_timeout",
    message: "The DCC request timed out. Check the current session state before trying again.",
  },
};

export async function requestJson(path: string, init?: RequestInit): Promise<unknown> {
  let response: Response;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15_000);
  const abortFromCaller = () => controller.abort();
  init?.signal?.addEventListener("abort", abortFromCaller, { once: true });
  try {
    const headers = new Headers(init?.headers);
    headers.set("Accept", "application/json");
    if (init?.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers,
      credentials: "omit",
      signal: controller.signal,
    });
  } catch {
    if (controller.signal.aborted) {
      throw new ApiError(
        "The DCC request timed out. Check the current session state before trying again.",
        "request_timeout",
        504,
      );
    }
    throw new ApiError(
      "Cannot reach the DCC backend. Check that it is running and VITE_API_BASE_URL is correct.",
      "network_error",
    );
  } finally {
    window.clearTimeout(timeout);
    init?.signal?.removeEventListener("abort", abortFromCaller);
  }

  if (!response.ok) {
    const knownError = httpErrorMessages[response.status];
    throw new ApiError(
      knownError?.message ?? "The DCC backend could not complete the request.",
      knownError?.code ?? "http_error",
      response.status,
    );
  }

  try {
    return await response.json();
  } catch {
    throw new ApiError(
      "The DCC backend returned an invalid response.",
      "invalid_response",
      response.status,
    );
  }
}
