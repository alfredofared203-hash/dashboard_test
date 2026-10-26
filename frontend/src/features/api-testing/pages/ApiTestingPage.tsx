import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AlertTriangle, ArrowRight, FlaskConical, LockKeyhole, Send } from "lucide-react";
import { ActionButton } from "@/components/atoms/ActionButton";
import { getDiscoveryCatalog, type DiscoveryCatalog, type DiscoveredEndpoint } from "@/features/api-discovery/public";
import { KeyValueEditor } from "../components/KeyValueEditor";
import { RequestHistory } from "../components/RequestHistory";
import { ResponsePanel } from "../components/ResponsePanel";
import { useApiTestRunner } from "../hooks/useApiTestRunner";
import type { ApiTestRequest, MockScenario, RequestParameter } from "../types/apiTest";

const scenarios: Array<{ value: MockScenario; label: string }> = [
  { value: "automatic", label: "Automatic (based on request)" },
  { value: "success", label: "200 · Success" },
  { value: "created", label: "201 · Created" },
  { value: "bad-request", label: "400 · Validation error" },
  { value: "unauthorized", label: "401 · Unauthorized" },
  { value: "not-found", label: "404 · Not found" },
  { value: "server-error", label: "500 · Server error" },
  { value: "network-error", label: "Network failure" },
];

function newParameter(name = "", value = ""): RequestParameter {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    enabled: true,
    name,
    value,
  };
}

function defaultPath(endpoint: DiscoveredEndpoint): string {
  return endpoint.path.replace(/\{([^}]+)\}/g, (_match, name: string) => `demo-${name}`);
}

function initialParameters(endpoint: DiscoveredEndpoint, location: "query" | "header"): RequestParameter[] {
  return endpoint.parameters
    .filter((parameter) => parameter.location === location)
    .map((parameter) => ({
      ...newParameter(
        parameter.name,
        location === "header" && parameter.name.toLowerCase() === "content-type"
          ? "application/json"
          : "",
      ),
      enabled: parameter.required,
    }));
}

function isApiSchemaValue(value: unknown): value is ApiTestRequest["body"] {
  if (value === null || typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return true;
  }
  if (Array.isArray(value)) {
    return value.every(isApiSchemaValue);
  }
  if (typeof value === "object") {
    return Object.values(value).every(isApiSchemaValue);
  }
  return false;
}

function parseJsonBody(rawBody: string): { body: ApiTestRequest["body"]; error: null }
  | { body: null; error: string } {
  if (!rawBody.trim()) return { body: null, error: null };
  try {
    const parsed: unknown = JSON.parse(rawBody);
    if (!isApiSchemaValue(parsed)) {
      return { body: null, error: "The JSON body contains an unsupported value." };
    }
    return { body: parsed, error: null };
  } catch (reason: unknown) {
    return {
      body: null,
      error: reason instanceof Error ? `Invalid JSON: ${reason.message}` : "Invalid JSON. Check the request body syntax.",
    };
  }
}

export function ApiTestingPage() {
  const [catalog, setCatalog] = useState<DiscoveryCatalog>({ services: [], endpoints: [] });
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [isCatalogLoading, setIsCatalogLoading] = useState(true);
  const [selectedEndpointId, setSelectedEndpointId] = useState("");
  const [url, setUrl] = useState("");
  const [queryParams, setQueryParams] = useState<RequestParameter[]>([]);
  const [headers, setHeaders] = useState<RequestParameter[]>([]);
  const [bodyText, setBodyText] = useState("{\n  \n}");
  const [scenario, setScenario] = useState<MockScenario>("automatic");
  const [validationError, setValidationError] = useState<string | null>(null);
  const { isSending, history, selectedResult, execute, inspectHistoryItem } = useApiTestRunner();

  useEffect(() => {
    let cancelled = false;
    setIsCatalogLoading(true);
    setCatalogError(null);
    Promise.resolve().then(getDiscoveryCatalog).then(
      (result) => {
        if (cancelled) return;
        setCatalog(result);
        setSelectedEndpointId(result.endpoints[0]?.id ?? "");
        setIsCatalogLoading(false);
      },
      (reason: unknown) => {
        if (cancelled) return;
        setCatalogError(reason instanceof Error ? reason.message : "The discovery catalog could not be loaded.");
        setIsCatalogLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedEndpoint = useMemo(
    () => catalog.endpoints.find((endpoint) => endpoint.id === selectedEndpointId) ?? null,
    [catalog.endpoints, selectedEndpointId],
  );

  useEffect(() => {
    if (!selectedEndpoint) return;
    setUrl(defaultPath(selectedEndpoint));
    setQueryParams(initialParameters(selectedEndpoint, "query"));
    setHeaders(initialParameters(selectedEndpoint, "header"));
    setBodyText("{\n  \n}");
    setScenario("automatic");
    setValidationError(null);
  }, [selectedEndpoint]);

  function handleEndpointChange(endpointId: string) {
    setSelectedEndpointId(endpointId);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationError(null);
    if (!selectedEndpoint) {
      setValidationError("Select a discovered endpoint before sending a request.");
      return;
    }
    if (!url.trim() || !url.startsWith("/") || url.startsWith("//") || url.includes("://") || url.includes("?") || /\s/.test(url)) {
      setValidationError("Enter a valid relative path beginning with /. External URLs are disabled in mock mode.");
      return;
    }
    if (/\{[^}]+\}/.test(url)) {
      setValidationError("Replace all path parameters in braces with example values before sending.");
      return;
    }
    if (queryParams.some((parameter) => parameter.enabled && !parameter.name.trim())) {
      setValidationError("Every enabled query parameter must have a name.");
      return;
    }
    if (headers.some((header) => header.enabled && !header.name.trim())) {
      setValidationError("Every enabled header must have a name.");
      return;
    }

    let parsedBody: ApiTestRequest["body"] = null;
    if (["POST", "PUT", "PATCH"].includes(selectedEndpoint.method)) {
      const parsed = parseJsonBody(bodyText);
      if (parsed.error) {
        setValidationError(parsed.error);
        return;
      }
      parsedBody = parsed.body;
    }

    const request: ApiTestRequest = {
      endpoint: selectedEndpoint,
      method: selectedEndpoint.method,
      url: url.trim(),
      queryParams: queryParams.filter((parameter) => parameter.enabled && parameter.name.trim()),
      headers: headers.filter((header) => header.enabled && header.name.trim()),
      body: parsedBody,
      scenario,
    };
    await execute(request);
  }

  const selectedService = selectedEndpoint
    ? catalog.services.find((service) => service.id === selectedEndpoint.serviceId)
    : null;
  const bodySupported = selectedEndpoint !== null && ["POST", "PUT", "PATCH"].includes(selectedEndpoint.method);

  return (
    <div className="api-testing-page">
      <header className="api-testing-heading">
        <div>
          <div className="eyebrow">WORKSPACE / API TESTING</div>
          <h1>API Testing</h1>
          <p>Prepare and run safe, simulated requests against discovered endpoint examples.</p>
        </div>
        <span className="api-test-mode-badge"><FlaskConical size={13} /> MOCK EXECUTION · NO NETWORK</span>
      </header>

      <div className="api-test-safety-note">
        <AlertTriangle size={14} />
        <span>Mock mode only. Requests are simulated in this browser and are never sent to a real service.</span>
      </div>

      <section className="api-test-panel api-test-endpoint-picker" aria-labelledby="api-endpoint-picker-title">
        <header className="api-test-panel-heading">
          <div className="api-test-panel-title"><ArrowRight size={15} /><h2 id="api-endpoint-picker-title">Select discovered endpoint</h2></div>
          <span className="api-test-source-badge">FROM API DISCOVERY</span>
        </header>
        {isCatalogLoading ? (
          <div className="api-test-catalog-state" role="status"><span className="api-test-spinner" /> Loading discovered endpoints…</div>
        ) : catalogError ? (
          <div className="api-test-catalog-state error" role="alert">Could not load the Discovery catalog: {catalogError}</div>
        ) : catalog.endpoints.length === 0 ? (
          <div className="api-test-catalog-state">No discovered endpoints are available.</div>
        ) : (
          <div className="api-test-endpoint-selection">
            <label htmlFor="api-test-endpoint">Endpoint</label>
            <select
              id="api-test-endpoint"
              className="api-test-input"
              value={selectedEndpointId}
              onChange={(event) => handleEndpointChange(event.currentTarget.value)}
            >
              {catalog.endpoints.map((endpoint) => {
                const service = catalog.services.find((entry) => entry.id === endpoint.serviceId);
                return (
                  <option key={endpoint.id} value={endpoint.id}>
                    {endpoint.method} · {endpoint.path} · {endpoint.name} ({service?.name ?? "Unknown service"})
                  </option>
                );
              })}
            </select>
            {selectedEndpoint && (
              <div className="api-test-selected-endpoint">
                <span className={`http-method method-${selectedEndpoint.method.toLowerCase()}`}>{selectedEndpoint.method}</span>
                <code>{selectedEndpoint.path}</code>
                <strong>{selectedEndpoint.name}</strong>
                <span>{selectedService?.name ?? "Unknown service"}</span>
              </div>
            )}
          </div>
        )}
      </section>

      <div className="api-test-workspace">
        <form className="api-test-panel api-test-request" onSubmit={handleSubmit} noValidate aria-labelledby="api-request-title">
          <header className="api-test-panel-heading">
            <div className="api-test-panel-title"><Send size={15} /><h2 id="api-request-title">Request builder</h2></div>
            {selectedEndpoint && <span className={`http-method method-${selectedEndpoint.method.toLowerCase()}`}>{selectedEndpoint.method}</span>}
          </header>

          {!selectedEndpoint ? (
            <div className="api-test-catalog-state">Select an endpoint to configure a request.</div>
          ) : (
            <div className="api-test-request-content">
              <div className="api-test-target-summary">
                <div className="api-test-target-method">
                  <span className={`http-method method-${selectedEndpoint.method.toLowerCase()}`}>{selectedEndpoint.method}</span>
                  <span>{selectedService?.name}</span>
                </div>
                <label htmlFor="api-test-url">Target path</label>
                <div className="api-test-url-row">
                  <input
                    id="api-test-url"
                    className="api-test-input api-test-url-input"
                    value={url}
                    onChange={(event) => setUrl(event.currentTarget.value)}
                    placeholder="/resource/{id}"
                    spellCheck={false}
                    autoComplete="off"
                    aria-describedby="api-test-mock-origin"
                  />
                  <span id="api-test-mock-origin">mock-api.dcc.local</span>
                </div>
                <small>Relative paths only. Replace any {`{path parameters}`} with example values.</small>
              </div>

              <KeyValueEditor
                title="Query parameters"
                rows={queryParams}
                onChange={setQueryParams}
                onAdd={() => setQueryParams((current) => [...current, newParameter()])}
                emptyMessage="No query parameters. Add one if needed."
                nameLabel="Parameter"
                valueLabel="Value"
              />

              <KeyValueEditor
                title="Headers"
                rows={headers}
                onChange={setHeaders}
                onAdd={() => setHeaders((current) => [...current, newParameter()])}
                emptyMessage="No headers configured."
                nameLabel="Header"
                valueLabel="Value"
              />

              {selectedEndpoint.authentication.required ? (
                <div className="api-test-auth-note">
                  <LockKeyhole size={14} />
                  <span><strong>Authentication required</strong> · {selectedEndpoint.authentication.type} — {selectedEndpoint.authentication.description} Add credentials only for this temporary demo session.</span>
                </div>
              ) : (
                <div className="api-test-auth-note public"><LockKeyhole size={14} /><span>No authentication is declared for this endpoint.</span></div>
              )}

              {bodySupported && (
                <section className="api-test-subsection">
                  <div className="api-test-subheading">
                    <h3>Request body <span>JSON</span></h3>
                    <span className="api-test-content-type">application/json</span>
                  </div>
                  {selectedEndpoint.requestSchema && (
                    <p className="api-test-schema-hint">A request schema is available in API Discovery. This mock validates JSON syntax only.</p>
                  )}
                  <label className="sr-only" htmlFor="api-test-body">JSON request body</label>
                  <textarea
                    id="api-test-body"
                    className="api-test-body-editor"
                    value={bodyText}
                    onChange={(event) => setBodyText(event.currentTarget.value)}
                    rows={8}
                    spellCheck={false}
                    aria-label="JSON request body"
                  />
                </section>
              )}

              <section className="api-test-subsection api-test-scenario">
                <div className="api-test-subheading"><h3>Mock response scenario</h3></div>
                <label className="sr-only" htmlFor="api-test-scenario">Select mock response scenario</label>
                <select
                  id="api-test-scenario"
                  className="api-test-input"
                  value={scenario}
                  onChange={(event) => {
                    const option = scenarios.find((entry) => entry.value === event.currentTarget.value);
                    if (option) setScenario(option.value);
                  }}
                >
                  {scenarios.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
                <p>Scenarios exercise the response viewer; they do not contact the selected service.</p>
              </section>

              {validationError && <div className="api-test-validation-error" role="alert">{validationError}</div>}
              <div className="api-test-submit-row">
                <span>Endpoint schema and authentication metadata are read from Discovery.</span>
                <ActionButton type="submit" disabled={isSending}>
                  {isSending ? <><span className="api-test-spinner" /> Sending…</> : <><Send size={14} /> Send Request</>}
                </ActionButton>
              </div>
            </div>
          )}
        </form>

        <ResponsePanel result={selectedResult} isSending={isSending} validationError={validationError} />
      </div>

      <RequestHistory
        items={history}
        selectedId={selectedResult?.id ?? null}
        onSelect={inspectHistoryItem}
      />
      <footer className="discovery-page-footer">
        <span>API Testing · Session-only history · Mock provider</span>
        <span>DCC · API TESTING</span>
      </footer>
    </div>
  );
}
