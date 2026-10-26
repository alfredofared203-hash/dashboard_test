import { useEffect, useMemo, useState } from "react";
import { Search, Radio, RotateCw, X } from "lucide-react";
import { ActionButton } from "@/components/atoms/ActionButton";
import { useDiscoveryCatalog } from "../hooks/useDiscoveryCatalog";
import { EndpointDetails } from "../components/EndpointDetails";
import { EndpointList } from "../components/EndpointList";
import { ServiceList } from "../components/ServiceList";
import type { DiscoveredEndpoint, HttpMethod } from "../types/discovery";

const methodOptions: Array<"ALL" | HttpMethod> = ["ALL", "GET", "POST", "PUT", "PATCH", "DELETE"];

export function ApiDiscoveryPage() {
  const { catalog, status, error, reload } = useDiscoveryCatalog();
  const [query, setQuery] = useState("");
  const [methodFilter, setMethodFilter] = useState<"ALL" | HttpMethod>("ALL");
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(null);
  const [selectedEndpointId, setSelectedEndpointId] = useState<string | null>(null);

  const matchingEndpoints = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return catalog.endpoints.filter((endpoint) => {
      const service = catalog.services.find((entry) => entry.id === endpoint.serviceId);
      const matchesService = selectedServiceId === null || endpoint.serviceId === selectedServiceId;
      const matchesMethod = methodFilter === "ALL" || endpoint.method === methodFilter;
      const searchableText = [
        service?.name,
        service?.description,
        endpoint.name,
        endpoint.path,
        endpoint.method,
      ].join(" ").toLowerCase();

      return matchesService && matchesMethod && (!normalizedQuery || searchableText.includes(normalizedQuery));
    });
  }, [catalog, methodFilter, query, selectedServiceId]);

  const matchingServices = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return catalog.services.filter((service) => {
      const serviceMatches = `${service.name} ${service.description}`.toLowerCase().includes(normalizedQuery);
      const endpointMatches = matchingEndpoints.some((endpoint) => endpoint.serviceId === service.id);
      return !normalizedQuery || serviceMatches || endpointMatches || service.id === selectedServiceId;
    });
  }, [catalog.services, matchingEndpoints, query, selectedServiceId]);

  useEffect(() => {
    if (!matchingEndpoints.some((endpoint) => endpoint.id === selectedEndpointId)) {
      setSelectedEndpointId(matchingEndpoints[0]?.id ?? null);
    }
  }, [matchingEndpoints, selectedEndpointId]);

  const selectedEndpoint: DiscoveredEndpoint | null =
    matchingEndpoints.find((endpoint) => endpoint.id === selectedEndpointId) ?? null;
  const selectedService = catalog.services.find((service) => service.id === selectedServiceId);

  return (
    <div className="api-discovery-page">
      <header className="discovery-page-heading">
        <div>
          <div className="eyebrow">CATALOG / API DISCOVERY</div>
          <h1>API Discovery</h1>
          <p>Explore service endpoints, parameters, authentication, and schemas.</p>
        </div>
        <div className="discovery-page-badges">
          <span className="discovery-mode-badge"><span /> MOCK DISCOVERY</span>
          <span className="discovery-readonly-badge"><Radio size={12} /> READ ONLY</span>
        </div>
      </header>

      <div className="discovery-toolbar">
        <label className="discovery-search">
          <Search size={16} />
          <span className="sr-only">Search services and endpoints</span>
          <input
            type="search"
            value={query}
            placeholder="Search services, endpoints, paths, methods…"
            onChange={(event) => setQuery(event.target.value)}
          />
          {query && (
            <button type="button" aria-label="Clear search" onClick={() => setQuery("")}>
              <X size={14} />
            </button>
          )}
        </label>
        <label className="method-filter-label">
          <span>METHOD</span>
          <select
            aria-label="Filter endpoints by HTTP method"
            value={methodFilter}
            onChange={(event) => {
              const selectedMethod = methodOptions.find((method) => method === event.currentTarget.value);
              if (selectedMethod) setMethodFilter(selectedMethod);
            }}
          >
            {methodOptions.map((method) => <option key={method} value={method}>{method === "ALL" ? "All methods" : method}</option>)}
          </select>
        </label>
        <div className="discovery-result-summary" aria-live="polite">
          <strong>{matchingEndpoints.length}</strong> {matchingEndpoints.length === 1 ? "endpoint" : "endpoints"}
          {selectedService ? <> in <span>{selectedService.name}</span></> : " across all services"}
        </div>
      </div>

      {status === "loading" && (
        <div className="discovery-state-card" role="status">
          <span className="discovery-spinner" />
          <strong>Loading discovery catalog</strong>
          <span>Reading demonstration service metadata…</span>
        </div>
      )}

      {status === "error" && (
        <div className="discovery-state-card error" role="alert">
          <strong>Could not load API discovery metadata</strong>
          <span>{error ?? "The discovery provider returned an unknown error."}</span>
          <ActionButton variant="outline" size="sm" onClick={reload}><RotateCw size={14} /> Try again</ActionButton>
        </div>
      )}

      {status === "empty" && (
        <div className="discovery-state-card" role="status">
          <Radio size={24} />
          <strong>No APIs discovered yet</strong>
          <span>The demonstration provider returned no services or endpoints.</span>
        </div>
      )}

      {status === "success" && (
        <>
          <div className="discovery-catalog-note">
            <span className="catalog-note-dot" />
            Demonstration catalog only. These services and endpoints are examples and are not connected to production.
          </div>
          <div className="discovery-workspace">
            <ServiceList
              services={matchingServices}
              selectedServiceId={selectedServiceId}
              totalEndpointCount={catalog.endpoints.length}
              onSelect={setSelectedServiceId}
            />
            <EndpointList
              endpoints={matchingEndpoints}
              services={catalog.services}
              selectedEndpointId={selectedEndpointId}
              onSelect={setSelectedEndpointId}
            />
            <EndpointDetails endpoint={selectedEndpoint} services={catalog.services} />
          </div>
        </>
      )}
      <footer className="discovery-page-footer">
        <span>Discovery describes APIs only. Request execution and API testing are not available here.</span>
        <span>DCC · API DISCOVERY</span>
      </footer>
    </div>
  );
}
