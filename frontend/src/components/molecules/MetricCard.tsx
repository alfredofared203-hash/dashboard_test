import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export interface MetricCardProps {
  label: string;
  value: string;
  unit?: string;
  icon: LucideIcon;
  tone: "blue" | "violet" | "cyan" | "orange";
  range?: string;
  footer?: ReactNode;
  progress?: number;
  progressTone?: "cpu" | "memory";
}

export function MetricCard({
  label,
  value,
  unit,
  icon: Icon,
  tone,
  range,
  footer,
  progress,
  progressTone,
}: MetricCardProps) {
  return (
    <article className="summary-card">
      <div className="summary-top">
        <span className={`summary-icon ${tone}`}><Icon size={18} /></span>
        {range && <span className="summary-range">{range}</span>}
      </div>
      <div className="summary-label">{label}</div>
      <div className="summary-value">
        {value}
        {unit && <span className={unit === "%" ? "summary-percent" : "summary-unit"}>{unit}</span>}
      </div>
      {progress !== undefined ? (
        <div className="progress-track">
          <span
            className={`progress-fill ${progressTone ?? "cpu"}-fill`}
            style={{ width: `${progress}%` }}
          />
        </div>
      ) : footer ? (
        <div className="summary-foot">{footer}</div>
      ) : null}
    </article>
  );
}
