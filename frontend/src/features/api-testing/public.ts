import { getDiscoveryCatalog } from "@/features/api-discovery/public";

export interface MockApiTestingReportSummary {
  source: "mock-report-sample";
  totalRequests: number;
  successfulRequests: number;
  clientErrors: number;
  serverErrors: number;
  networkErrors: number;
  averageDurationMs: number | null;
}

export type { ApiTestResult } from "./types/apiTest";

export async function getMockApiTestingReportSummary(): Promise<MockApiTestingReportSummary> {
  const catalog = await getDiscoveryCatalog();
  if (catalog.endpoints.length === 0) {
    return {
      source: "mock-report-sample",
      totalRequests: 0,
      successfulRequests: 0,
      clientErrors: 0,
      serverErrors: 0,
      networkErrors: 0,
      averageDurationMs: null,
    };
  }

  return {
    source: "mock-report-sample",
    totalRequests: 6,
    successfulRequests: 3,
    clientErrors: 1,
    serverErrors: 1,
    networkErrors: 1,
    averageDurationMs: 134.2,
  };
}
