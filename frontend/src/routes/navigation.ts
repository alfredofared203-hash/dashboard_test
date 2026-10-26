import {
  Activity,
  Boxes,
  Container,
  Database,
  FileText,
  FlaskConical,
  LayoutDashboard,
  Radar,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavigationItem {
  path: string;
  label: string;
  icon: LucideIcon;
  badge?: string;
}

export const navigationItems: NavigationItem[] = [
  { path: "/", label: "System Overview", icon: LayoutDashboard },
  { path: "/ecs-resources", label: "ECS Resources", icon: Container },
  { path: "/resources", label: "Resource Metrics", icon: Activity },
  { path: "/logs", label: "Logs & Diagnostics", icon: FileText },
  { path: "/api-discovery", label: "API Discovery", icon: Radar },
  { path: "/api-testing", label: "API Testing", icon: FlaskConical },
  { path: "/tasks-resources", label: "Tasks & Resources Testing", icon: Boxes },
  { path: "/diagnostic-impact", label: "Diagnostic Impact Report", icon: FileText, badge: "NEW" },
  { path: "/dependencies", label: "Dependency Observability", icon: Database },
  { path: "/settings", label: "Settings & Integrations", icon: Settings },
];
