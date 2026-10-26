import type { ServiceStatus } from "@/types/dashboard";

export interface StatusBadgeProps {
  status: ServiceStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`status-badge ${status.toLowerCase()}`}>
      <span className="status-dot" />
      {status}
    </span>
  );
}
