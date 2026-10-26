import { Bell, ChevronRight, Menu } from "lucide-react";
import { IconButton } from "@/components/atoms/IconButton";
import { EnvironmentBadge } from "@/components/molecules/EnvironmentBadge";

export interface TopHeaderProps {
  pageTitle: string;
  onMenuOpen: () => void;
}

export function TopHeader({ pageTitle, onMenuOpen }: TopHeaderProps) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <IconButton className="mobile-menu" label="Open navigation menu" onClick={onMenuOpen}>
          <Menu size={18} />
        </IconButton>
        <div className="breadcrumb">
          <span>Workspace</span>
          <ChevronRight size={14} />
          <strong>{pageTitle}</strong>
        </div>
      </div>
      <div className="topbar-right">
        <EnvironmentBadge />
        <IconButton className="notification-button" label="Notifications">
          <Bell size={18} />
          <span className="notification-dot" />
        </IconButton>
      </div>
    </header>
  );
}
