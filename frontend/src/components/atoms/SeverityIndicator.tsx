import type { EventSeverity } from "@/types/dashboard";

export interface SeverityIndicatorProps {
  severity: EventSeverity;
}

export function SeverityIndicator({ severity }: SeverityIndicatorProps) {
  return (
    <span
      className={`severity-mark ${severity}`}
      aria-label={`${severity} severity`}
    />
  );
}
