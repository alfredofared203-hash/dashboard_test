import type { LucideIcon } from "lucide-react";
import { EmptyState } from "@/components/molecules/EmptyState";

export interface ComingSoonPageProps {
  title: string;
  icon: LucideIcon;
}

export function ComingSoonPage({ title, icon }: ComingSoonPageProps) {
  return (
    <EmptyState
      title={title}
      icon={icon}
      description="This section is not part of the current milestone. It is reserved for a future DCC release."
    />
  );
}
