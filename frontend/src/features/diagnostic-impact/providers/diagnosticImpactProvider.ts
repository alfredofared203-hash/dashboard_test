import type { DiagnosticSession } from "@/types/diagnosticSession";
import type { DiagnosticImpactReport } from "../types/report";

export interface DiagnosticImpactProvider {
  /**
   * Returns the backend-generated, read-only report for the supplied session.
   */
  getReport(session: DiagnosticSession): Promise<DiagnosticImpactReport | null>;
}
