import { Layers } from "lucide-react";
import { NavLink } from "react-router-dom";
import { navigationItems } from "@/routes/navigation";

export interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {open && (
        <button
          className="mobile-backdrop"
          aria-label="Close navigation menu"
          onClick={onClose}
        />
      )}
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <NavLink className="brand" to="/" onClick={onClose}>
          <span className="brand-mark"><Layers size={21} /></span>
          <span className="brand-copy"><strong>DCC</strong><small>CONTROL CENTER</small></span>
        </NavLink>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Main navigation">
          {navigationItems.map(({ path, label, icon: Icon, badge }) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/"}
              className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
              onClick={onClose}
            >
              <Icon size={18} />
              <span>{label}</span>
              {badge && <span className="nav-new">{badge}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-status">
            <span className="live-dot" />
            <span>Demo environment</span>
            <span className="demo-tag">MOCK</span>
          </div>
        </div>
      </aside>
    </>
  );
}
