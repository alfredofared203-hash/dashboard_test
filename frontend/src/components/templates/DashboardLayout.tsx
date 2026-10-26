import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "@/components/organisms/Sidebar";
import { TopHeader } from "@/components/organisms/TopHeader";
import { navigationItems } from "@/routes/navigation";

export function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { pathname } = useLocation();
  const pageTitle =
    navigationItems.find((item) => item.path === pathname)?.label ?? "Page not found";

  return (
    <div className="app-shell">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="main-area">
        <TopHeader pageTitle={pageTitle} onMenuOpen={() => setSidebarOpen(true)} />
        <div className="content"><Outlet /></div>
      </main>
    </div>
  );
}
