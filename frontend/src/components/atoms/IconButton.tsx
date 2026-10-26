import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  children: ReactNode;
}

export function IconButton({ label, children, className, ...props }: IconButtonProps) {
  return (
    <button className={cn("icon-button", className)} aria-label={label} {...props}>
      {children}
    </button>
  );
}
