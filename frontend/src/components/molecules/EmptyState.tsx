import type { LucideIcon } from "lucide-react";

export interface EmptyStateProps {
  title: string;
  description: string;
  icon: LucideIcon;
}

export function EmptyState({ title, description, icon: Icon }: EmptyStateProps) {
  return (
    <section className="coming-soon">
      <span className="coming-icon"><Icon size={27} /></span>
      <div className="eyebrow">WORKSPACE / {title.toUpperCase()}</div>
      <h1>{title}</h1>
      <p>{description}</p>
      <span className="coming-tag">COMING SOON</span>
    </section>
  );
}
