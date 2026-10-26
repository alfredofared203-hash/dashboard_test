import { useCallback, useState } from "react";
import { mockApiTestProvider, type ApiTestProvider } from "../services/apiTestProvider";
import type { ApiTestHistoryItem, ApiTestRequest, ApiTestResult } from "../types/apiTest";

const HISTORY_LIMIT = 20;

export function useApiTestRunner(provider: ApiTestProvider = mockApiTestProvider) {
  const [isSending, setIsSending] = useState(false);
  const [history, setHistory] = useState<ApiTestHistoryItem[]>([]);
  const [selectedResult, setSelectedResult] = useState<ApiTestResult | null>(null);

  const execute = useCallback(async (request: ApiTestRequest) => {
    setIsSending(true);
    try {
      const result = await provider.execute(request);
      setSelectedResult(result);
      setHistory((current) => [
        {
          id: result.id,
          endpointName: request.endpoint.name,
          method: request.method,
          url: result.url,
          status: result.status,
          duration: result.duration,
          timestamp: result.timestamp,
          success: result.success,
          result,
        },
        ...current,
      ].slice(0, HISTORY_LIMIT));
      return result;
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "The API test provider failed unexpectedly.";
      const result: ApiTestResult = {
        id: `provider-error-${Date.now()}`,
        endpointId: request.endpoint.id,
        method: request.method,
        url: request.url,
        status: null,
        statusText: "Network Error",
        duration: 0,
        headers: {},
        body: null,
        success: false,
        error: message,
        timestamp: new Date().toISOString(),
      };
      setSelectedResult(result);
      setHistory((current) => [
        {
          id: result.id,
          endpointName: request.endpoint.name,
          method: request.method,
          url: result.url,
          status: null,
          duration: 0,
          timestamp: result.timestamp,
          success: false,
          result,
        },
        ...current,
      ].slice(0, HISTORY_LIMIT));
      return result;
    } finally {
      setIsSending(false);
    }
  }, [provider]);

  const inspectHistoryItem = useCallback((item: ApiTestHistoryItem) => {
    setSelectedResult(item.result);
  }, []);

  return { isSending, history, selectedResult, execute, inspectHistoryItem };
}
