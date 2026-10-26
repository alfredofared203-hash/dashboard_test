import { LockKeyhole, Unplug } from "lucide-react";
import type { DiscoveredEndpoint, DiscoveredService, HttpMethod } from "../types/discovery";

export interface EndpointListProps {
  endpoints: DiscoveredEndpoint[];
  services: DiscoveredService[];
  selectedEndpointId: string | null;
  onSelect: (endpointId: string) => void;
}

const methodOrder: Record<HttpMethod, number> = {
  GET: 0,
  POST: 1,
  PUT: 2,
  PATCH: 3,
  DELETE: 4,
};

export function EndpointList({
  endpoints,
  services,
  selectedEndpointId,
  onSelect,
}: EndpointListProps) {
  const serviceById = new Map(services.map((service) => [service.id, service]));
  const orderedEndpoints = [...endpoints].sort(
    (left, right) =>
      methodOrder[left.method] - methodOrder[right.method] ||
      left.path.localeCompare(right.path),
  );

  return (
    <section className="discovery-panel discovery-endpoints" aria-labelledby="discovery-endpoints-title">
      <header className="discovery-panel-heading">
        <div className="discovery-panel-title">
          <Unplug size={15} />
          <h2 id="discovery-endpoints-title">Endpoints</h2>
        </div>
        <span className="discovery-count">{endpoints.length}</span>
      </header>
      {orderedEndpoints.length > 0 ? (
        <ul className="discovery-endpoint-list" aria-label="Discovered endpoints">
          {orderedEndpoints.map((endpoint) => (
            <li key={endpoint.id}>
              <button
                className={`discovery-endpoint-item ${selectedEndpointId === endpoint.id ? "selected" : ""}`}
                type="button"
                aria-pressed={selectedEndpointId === endpoint.id}
                onClick={() => onSelect(endpoint.id)}
              >
                <span className="endpoint-item-topline">
                  <span className={`http-method method-${endpoint.method.toLowerCase()}`}>{endpoint.method}</span>
                  <code className="endpoint-path">{endpoint.path}</code>
                  {endpoint.authentication.required && (
                    <LockKeyhole className="endpoint-auth-icon" size={13} aria-label="Authentication required" />
                  )}
                </span>
                <span className="endpoint-item-name">{endpoint.name}</span>
                <span className="endpoint-item-description">{endpoint.description}</span>
                <span className="endpoint-service-name">{serviceById.get(endpoint.serviceId)?.name ?? "Unknown service"}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="discovery-empty discovery-list-empty" role="status">
          <Unplug size={21} />
          <strong>No matching endpoints</strong>
          <span>Try another search, method, or service.</span>
        </div>
      )}
      <footer className="discovery-panel-footer">ENDPOINT METADATA · READ ONLY</footer>
    </section>
  );
}
