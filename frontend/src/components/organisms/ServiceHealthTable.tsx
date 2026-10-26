import { ChevronRight } from "lucide-react";
import { StatusBadge } from "@/components/atoms/StatusBadge";
import { SectionHeader } from "@/components/molecules/SectionHeader";
import type { Service } from "@/types/dashboard";

export interface ServiceHealthTableProps {
  services: Service[];
  onViewAll: () => void;
  onViewDirectory: () => void;
  emptyMessage?: string;
}

export function ServiceHealthTable({
  services,
  onViewAll,
  onViewDirectory,
  emptyMessage = "No ECS services were discovered in the configured clusters.",
}: ServiceHealthTableProps) {
  return (
    <section className="panel services-panel">
      <SectionHeader
        title="Service health"
        description="Current status of your services"
        action={
          <button className="text-button" type="button" onClick={onViewAll}>
            View all <ChevronRight size={14} />
          </button>
        }
      />
      <div className="table-scroll">
        <table>
          <caption className="sr-only">Discovered ECS service status and task counts</caption>
          <thead>
            <tr>
              <th scope="col">SERVICE</th><th scope="col">STATUS</th><th scope="col">RUNNING TASKS</th>
              <th scope="col">CPU UTILIZATION</th><th scope="col">MEMORY UTILIZATION</th><th scope="col">LAST UPDATED</th>
            </tr>
          </thead>
          <tbody>
            {services.map((service) => (
              <tr key={service.name}>
                <td>
                  <div className="service-name">{service.name}</div>
                  <div className="service-detail">{service.detail}</div>
                </td>
                <td><StatusBadge status={service.status} /></td>
                <td className="task-cell">
                  {service.runningTasks === null || service.desiredTasks === null
                    ? "Unavailable"
                    : `${service.runningTasks} / ${service.desiredTasks}`}
                </td>
                <td>{service.cpu === null ? "—" : <span className={service.cpu >= 70 ? "metric-high" : ""}>{service.cpu}%</span>}</td>
                <td>{service.memory === null ? "—" : <span className={service.memory >= 80 ? "metric-high" : ""}>{service.memory}%</span>}</td>
                <td className="updated-cell">{service.updated}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {services.length === 0 && <p className="table-footer">{emptyMessage}</p>}
      <div className="table-footer">
        <span>Showing <strong>{services.length}</strong> discovered services</span>
        <button className="text-button" type="button" onClick={onViewDirectory}>
          View service directory <ChevronRight size={14} />
        </button>
      </div>
    </section>
  );
}
