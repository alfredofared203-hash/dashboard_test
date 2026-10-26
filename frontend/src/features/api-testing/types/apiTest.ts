import type { ApiSchemaValue, DiscoveredEndpoint, HttpMethod } from "@/features/api-discovery/public";

export type MockScenario =
  | "automatic"
  | "success"
  | "created"
  | "bad-request"
  | "unauthorized"
  | "not-found"
  | "server-error"
  | "network-error";

export interface RequestParameter {
  id: string;
  enabled: boolean;
  name: string;
  value: string;
}

export interface ApiTestRequest {
  endpoint: DiscoveredEndpoint;
  method: HttpMethod;
  url: string;
  queryParams: RequestParameter[];
  headers: RequestParameter[];
  body: ApiSchemaValue | null;
  scenario: MockScenario;
}

export interface ApiTestResult {
  id: string;
  endpointId: string;
  method: HttpMethod;
  url: string;
  status: number | null;
  statusText: string;
  duration: number;
  headers: Record<string, string>;
  body: ApiSchemaValue | string | null;
  success: boolean;
  error: string | null;
  timestamp: string;
}

export interface ApiTestHistoryItem {
  id: string;
  endpointName: string;
  method: HttpMethod;
  url: string;
  status: number | null;
  duration: number;
  timestamp: string;
  success: boolean;
  result: ApiTestResult;
}

export type ApiTestState = "idle" | "sending" | "success" | "http-error" | "network-error";
