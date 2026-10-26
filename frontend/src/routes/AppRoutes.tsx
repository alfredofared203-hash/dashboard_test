import { Navigate, Route, Routes } from "react-router-dom";
import { DiagnosticSessionProvider } from "@/app/providers/DiagnosticSessionProvider";
import { DashboardLayout } from "@/components/templates/DashboardLayout";
import { DiagnosticImpactReportPage } from "@/pages/DiagnosticImpactReportPage";
import { DependenciesPage } from "@/pages/DependenciesPage";
import { LogsDiagnosticsPage } from "@/pages/LogsDiagnosticsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ResourceMetricsPage } from "@/pages/ResourceMetricsPage";
import { SettingsIntegrationsPage } from "@/pages/SettingsIntegrationsPage";
import { SystemOverviewPage } from "@/pages/SystemOverviewPage";
import { ApiDiscoveryPage } from "@/features/api-discovery/pages/ApiDiscoveryPage";
import { ApiTestingPage } from "@/features/api-testing/pages/ApiTestingPage";
import { TasksResourcesPage } from "@/features/tasks-resources-testing/pages/TasksResourcesPage";
import { EcsResourcesPage } from "@/features/ecs-resources/pages/EcsResourcesPage";
function DashboardRoutes() {
  return (
    <DiagnosticSessionProvider>
      <DashboardLayout />
    </DiagnosticSessionProvider>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<DashboardRoutes />}>
        <Route index element={<SystemOverviewPage />} />
        <Route path="ecs-resources" element={<EcsResourcesPage />} />
        <Route path="resources" element={<ResourceMetricsPage />} />
        <Route path="resource-metrics" element={<Navigate to="/resources" replace />} />
        <Route path="logs" element={<LogsDiagnosticsPage />} />
        <Route path="api-discovery" element={<ApiDiscoveryPage />} />
        <Route path="api-explorer" element={<Navigate to="/api-discovery" replace />} />
        <Route path="api-testing" element={<ApiTestingPage />} />
        <Route path="tasks-resources" element={<TasksResourcesPage />} />
        <Route path="diagnostic-impact" element={<DiagnosticImpactReportPage />} />
        <Route path="dependencies" element={<DependenciesPage />} />
        <Route path="settings" element={<SettingsIntegrationsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
