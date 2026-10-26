import { CircleCheck, X } from "lucide-react";
import { IconButton } from "@/components/atoms/IconButton";

export interface ToastProps {
  message: string;
  onDismiss: () => void;
}

export function Toast({ message, onDismiss }: ToastProps) {
  return (
    <div className="toast" role="status">
      <span className="toast-check"><CircleCheck size={14} /></span>
      {message}
      <IconButton label="Dismiss notification" onClick={onDismiss}>
        <X size={15} />
      </IconButton>
    </div>
  );
}
