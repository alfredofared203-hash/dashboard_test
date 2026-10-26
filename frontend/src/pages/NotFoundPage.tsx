import { CircleHelp } from "lucide-react";
import { EmptyState } from "@/components/molecules/EmptyState";

export function NotFoundPage() {
  return (
    <EmptyState
      title="Page not found"
      icon={CircleHelp}
      description="The page you requested does not exist."
    />
  );
}
