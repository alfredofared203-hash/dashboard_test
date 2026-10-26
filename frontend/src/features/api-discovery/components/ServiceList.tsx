import { Check, Layers, Server } from "lucide-react";
import type { DiscoveredService } from "../types/discovery";

export interface ServiceListProps {
  services: DiscoveredService[];
  selectedServiceId: string | null;
  totalEndpointCount: number;
  onSelect: (serviceId: string | null) => void;
}

export function ServiceList({
  services,
  selectedServiceId,
  totalEndpointCount,
  onSelect,
}: ServiceListProps) {
  return (
    <section className="discovery-panel discovery-services" aria-labelledby="discovery-services-title">
      <header className="discovery-panel-heading">
        <div className="discovery-panel-title">
          <Server size={15} />
          <h2 id="discovery-services-title">Services</h2>
        </div>
        <span className="discovery-count">{services.length}</span>
      </header>
      {services.length > 0 ? (
        <ul className="discovery-service-list" aria-label="Discovered services">
          <li>
            <button
              className={`discovery-service-item ${selectedServiceId === null ? "selected" : ""}`}
              type="button"
              aria-pressed={selectedServiceId === null}
              onClick={() => onSelect(null)}
            >
              <span className="service-item-icon"><Layers size={15} /></span>
              <span className="service-item-copy">
                <span className="service-item-name">All services</span>
                <span className="service-item-description">Browse the full catalog</span>
              </span>
              <span className="service-endpoint-count">{totalEndpointCount}</span>
            </button>
          </li>
          {services.map((service) => (
            <li key={service.id}>
              <button
                className={`discovery-service-item ${selectedServiceId === service.id ? "selected" : ""}`}
                type="button"
                aria-pressed={selectedServiceId === service.id}
                onClick={() => onSelect(service.id)}
              >
                <span className={`service-item-icon ${service.status}`}>
                  <Server size={15} />
                </span>
                <span className="service-item-copy">
                  <span className="service-item-name">{service.name}</span>
                  <span className="service-item-description">{service.description}</span>
                </span>
                <span className={`service-status-pill ${service.status}`}>{service.status}</span>
                <span className="service-endpoint-count" aria-label={`${service.endpointCount} endpoints`}>
                  {service.endpointCount}
                </span>
                {selectedServiceId === service.id && <Check className="service-selected-check" size={13} />}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="discovery-inline-empty">No services match this search.</p>
      )}
      <footer className="discovery-panel-footer">DEMO CATALOG · NOT CONNECTED</footer>
    </section>
  );
}
