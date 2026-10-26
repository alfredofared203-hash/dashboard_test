import { AlertTriangle, CheckCircle2, Clock3, Code2, WifiOff, XCircle } from "lucide-react";
import type { ApiTestResult } from "../types/apiTest";

interface ResponsePanelProps {
  result: ApiTestResult | null;
  isSending: boolean;
  validationError: string | null;
}

function formatBody(body: ApiTestResult["body"]): string {
  if (body === null) return "No response body.";
  if (typeof body === "string") {
    try {
      const parsed: unknown = JSON.parse(body);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return body;
    }
  }
  return JSON.stringify(body, null, 2);
}

export function ResponsePanel({ result, isSending, validationError }: ResponsePanelProps) {
  const stateLabel = isSending
    ? "SENDING"
    : validationError
      ? "INVALID REQUEST"
    : !result
      ? "IDLE"
      : result.status === null
        ? "NETWORK ERROR"
        : result.success
          ? "SUCCESS"
          : "HTTP ERROR";

  const stateIcon = isSending
    ? <span className="api-test-spinner" />
    : validationError
    ? <AlertTriangle size={14} />
    : result?.status === null
      ? <WifiOff size={14} />
      : result?.success
        ? <CheckCircle2 size={14} />
        : result
          ? <XCircle size={14} />
          : <Code2 size={14} />;

  return (
    <section className="api-test-panel api-test-response" aria-labelledby="api-response-title">
      <header className="api-test-panel-heading">
        <div className="api-test-panel-title"><Code2 size={15} /><h2 id="api-response-title">Response</h2></div>
        <span className={`api-test-state state-${stateLabel.toLowerCase().replaceAll(" ", "-")}`} role="status" aria-live="polite">
          {stateIcon}{stateLabel}
        </span>
      </header>
      {isSending ? (
        <div className="api-test-response-empty" role="status" aria-live="polite">
          <span className="api-test-spinner large" />
          <strong>Running mock request…</strong>
          <span>No external request is being sent.</span>
        </div>
      ) : validationError ? (
        <div className="api-test-response-empty api-test-invalid-state" role="alert">
          <AlertTriangle size={22} />
          <strong>Request was not sent</strong>
          <span>{validationError}</span>
        </div>
      ) : !result ? (
        <div className="api-test-response-empty">
          <Code2 size={23} />
          <strong>Response will appear here</strong>
          <span>Configure a request and select Send Request to view its result.</span>
        </div>
      ) : (
        <div className="api-test-response-content">
          <div className={`api-test-result-summary ${result.success ? "result-success" : result.status === null ? "result-network-error" : "result-http-error"}`}>
            <div className="api-test-result-status">
              <span className="api-test-result-label">STATUS</span>
              <strong>{result.status === null ? result.statusText : `${result.status} ${result.statusText}`}</strong>
            </div>
            <div className="api-test-result-duration"><Clock3 size={14} /><strong>{result.duration} ms</strong></div>
          </div>
          {result.error && <div className="api-test-error-message" role="alert"><WifiOff size={15} /><span>{result.error}</span></div>}

          <div className="api-test-request-summary">
            <span><strong>{result.method}</strong> <code>{result.url}</code></span>
            <time dateTime={result.timestamp}>{new Date(result.timestamp).toLocaleString()}</time>
          </div>

          <section className="api-test-viewer-section">
            <div className="api-test-viewer-heading"><h3>Response headers</h3><span>{Object.keys(result.headers).length}</span></div>
            {Object.keys(result.headers).length > 0 ? (
              <dl className="api-test-response-headers">
                {Object.entries(result.headers).map(([name, value]) => (
                  <div key={name}><dt>{name}</dt><dd>{value}</dd></div>
                ))}
              </dl>
            ) : <p className="api-test-empty-inline">No response headers.</p>}
          </section>

          <section className="api-test-viewer-section">
            <div className="api-test-viewer-heading"><h3>Response body</h3><span>{result.body !== null && typeof result.body !== "string" ? "JSON" : "TEXT"}</span></div>
            <pre className="api-test-response-body"><code>{formatBody(result.body)}</code></pre>
          </section>
        </div>
      )}
    </section>
  );
}
