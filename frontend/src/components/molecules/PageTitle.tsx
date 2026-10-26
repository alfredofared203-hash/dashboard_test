import type { ReactNode } from "react";

export interface PageTitleProps {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}

export function PageTitle({ eyebrow, title, description, actions }: PageTitleProps) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="heading-actions">{actions}</div>}
    </div>
  );
}
