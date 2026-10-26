import { Check, LockKeyhole, ShieldCheck } from "lucide-react";
import type { DiscoveredEndpoint, DiscoveredService } from "../types/discovery";
import { SchemaViewer } from "./SchemaViewer";

export interface EndpointDetailsProps {
  endpoint: DiscoveredEndpoint | null;
  services: DiscoveredService[];
}

export function EndpointDetails({ endpoint, services }: EndpointDetailsProps) {
  if (!endpoint) {
    return (
      <section className="discovery-panel discovery-details discovery-details-empty" aria-labelledby="endpoint-details-title">
        <header className="discovery-panel-heading">
          <div className="discovery-panel-title"><ShieldCheck size={15} /><h2 id="endpoint-details-title">Endpoint details</h2></div>
        </header>
        <div className="discovery-empty detail-empty" role="status">
          <span className="detail-empty-icon"><ShieldCheck size={22} /></span>
          <strong>Select an endpoint</strong>
          <span>Choose an endpoint to inspect its discovered metadata and schemas.</span>
        </div>
      </section>
    );
  }

  const service = services.find((entry) => entry.id === endpoint.serviceId);

  return (
    <section className="discovery-panel discovery-details" aria-labelledby="endpoint-details-title">
      <header className="discovery-panel-heading">
        <div className="discovery-panel-title"><ShieldCheck size={15} /><h2 id="endpoint-details-title">Endpoint details</h2></div>
        <span className="metadata-readonly"><LockKeyhole size={11} /> DISCOVERY ONLY</span>
      </header>
      <div className="endpoint-details-content">
        <section className="endpoint-overview">
          <div className="endpoint-detail-title-row">
            <span className={`http-method method-${endpoint.method.toLowerCase()}`}>{endpoint.method}</span>
            <code className="detail-path">{endpoint.path}</code>
          </div>
          <h3>{endpoint.name}</h3>
          <p>{endpoint.description}</p>
          <dl className="endpoint-meta-grid">
            <div><dt>Service</dt><dd>{service?.name ?? "Unknown service"}</dd></div>
            <div><dt>Method</dt><dd><span className={`http-method method-${endpoint.method.toLowerCase()}`}>{endpoint.method}</span></dd></div>
            <div className="meta-path"><dt>Path</dt><dd><code>{endpoint.path}</code></dd></div>
          </dl>
        </section>

        <section className="detail-section">
          <div className="detail-section-heading"><h3>Parameters & headers</h3><span>{endpoint.parameters.length}</span></div>
          {endpoint.parameters.length > 0 ? (
            <div className="parameter-table-wrap">
              <table className="parameter-table">
                <thead><tr><th scope="col">NAME</th><th scope="col">LOCATION</th><th scope="col">TYPE</th><th scope="col">REQUIRED</th><th scope="col">DESCRIPTION</th></tr></thead>
                <tbody>
                  {endpoint.parameters.map((parameter) => (
                    <tr key={`${parameter.location}-${parameter.name}`}>
                      <td><code>{parameter.name}</code></td>
                      <td><span className={`parameter-location location-${parameter.location}`}>{parameter.location}</span></td>
                      <td><code>{parameter.type}</code></td>
                      <td>{parameter.required ? <span className="required-indicator"><Check size={11} /> Required</span> : <span className="optional-indicator">Optional</span>}</td>
                      <td className="parameter-description">{parameter.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="schema-empty">No parameters or headers are declared for this endpoint.</p>
          )}
        </section>

        <section className="detail-section auth-section">
          <div className="detail-section-heading"><h3>Authentication</h3></div>
          <div className={`auth-card ${endpoint.authentication.required ? "auth-required" : "auth-public"}`}>
            {endpoint.authentication.required ? <LockKeyhole size={15} /> : <ShieldCheck size={15} />}
            <div>
              <strong>{endpoint.authentication.required ? "Authentication required" : "No authentication required"}</strong>
              <p>{endpoint.authentication.description}</p>
              <div className="auth-meta">
                <span>Type: <strong>{endpoint.authentication.type}</strong></span>
                {endpoint.authentication.requiredHeaders.length > 0 && (
                  <span>Headers: <code>{endpoint.authentication.requiredHeaders.join(", ")}</code></span>
                )}
                {endpoint.authentication.scopes && endpoint.authentication.scopes.length > 0 && (
                  <span>Scopes: <code>{endpoint.authentication.scopes.join(", ")}</code></span>
                )}
              </div>
            </div>
          </div>
        </section>

        <SchemaViewer
          title="Request schema"
          schema={endpoint.requestSchema}
          emptyMessage="No request body schema is declared."
        />
        <section className="detail-section response-schemas">
          <div className="detail-section-heading"><h3>Response schemas</h3><span>{endpoint.responseSchemas.length}</span></div>
          {endpoint.responseSchemas.map((response) => (
            <div className="response-schema" key={response.statusCode}>
              <div className="response-schema-heading">
                <span className={`response-code ${response.statusCode < 400 ? "response-success" : "response-error"}`}>{response.statusCode}</span>
                <span>{response.description}</span>
              </div>
              <pre className="schema-code"><code>{JSON.stringify(response.schema, null, 2)}</code></pre>
            </div>
          ))}
        </section>
        <p className="discovery-safety-note"><LockKeyhole size={12} /> Metadata only. This page does not send requests or test endpoints.</p>
      </div>
    </section>
  );
}
