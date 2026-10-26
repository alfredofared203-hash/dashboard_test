import type { ApiTestRequest, ApiTestResult, MockScenario } from "../types/apiTest";

export interface ApiTestProvider {
  /** Executes one request through the selected provider; rejects when execution cannot return a result. */
  execute(request: ApiTestRequest): Promise<ApiTestResult>;
}

interface MockResponse {
  status: number | null;
  statusText: string;
  body: ApiTestResult["body"];
  error: string | null;
}

const mockResponses: Record<Exclude<MockScenario, "automatic">, MockResponse> = {
  success: {
    status: 200,
    statusText: "OK",
    body: { status: "healthy", version: "1.4.2", message: "Mock request completed successfully." },
    error: null,
  },
  created: {
    status: 201,
    statusText: "Created",
    body: { id: "demo-resource-204", status: "created", message: "Mock resource created." },
    error: null,
  },
  "bad-request": {
    status: 400,
    statusText: "Bad Request",
    body: { code: "VALIDATION_ERROR", message: "The mock server rejected one or more request fields." },
    error: null,
  },
  unauthorized: {
    status: 401,
    statusText: "Unauthorized",
    body: { code: "AUTH_REQUIRED", message: "A valid authorization header is required." },
    error: null,
  },
  "not-found": {
    status: 404,
    statusText: "Not Found",
    body: { code: "NOT_FOUND", message: "The requested mock resource was not found." },
    error: null,
  },
  "server-error": {
    status: 500,
    statusText: "Internal Server Error",
    body: { code: "MOCK_SERVER_ERROR", message: "The mock server encountered an error." },
    error: null,
  },
  "network-error": {
    status: null,
    statusText: "Network Error",
    body: null,
    error: "The mock connection was interrupted. No network request was sent.",
  },
};

function chooseAutomaticResponse(request: ApiTestRequest): MockResponse {
  const hasAuthorization = request.headers.some(
    (header) => header.enabled && header.name.toLowerCase() === "authorization" && header.value.trim(),
  );

  if (request.endpoint.authentication.required && !hasAuthorization) {
    return mockResponses.unauthorized;
  }
  if (request.method === "POST") {
    return mockResponses.created;
  }
  if (/\/(?:missing|not-found)(?:\/|$)/i.test(request.url)) {
    return mockResponses["not-found"];
  }
  return mockResponses.success;
}

export const mockApiTestProvider: ApiTestProvider = {
  async execute(request) {
    await new Promise<void>((resolve) => window.setTimeout(resolve, 520));
    const response = request.scenario === "automatic"
      ? chooseAutomaticResponse(request)
      : mockResponses[request.scenario];
    const query = new URLSearchParams();
    request.queryParams.forEach((parameter) => query.append(parameter.name, parameter.value));
    const requestUrl = query.size > 0 ? `${request.url}?${query.toString()}` : request.url;
    const duration = 86 + ((requestUrl.length * 17 + request.method.length * 13) % 190);

    return {
      id: `mock-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      endpointId: request.endpoint.id,
      method: request.method,
      url: requestUrl,
      status: response.status,
      statusText: response.statusText,
      duration,
      headers: {
        "content-type": response.body === null ? "text/plain; charset=utf-8" : "application/json; charset=utf-8",
        "x-request-mode": "mock",
        "cache-control": "no-store",
      },
      body: response.body,
      success: response.status !== null && response.status >= 200 && response.status < 300,
      error: response.error,
      timestamp: new Date().toISOString(),
    };
  },
};
