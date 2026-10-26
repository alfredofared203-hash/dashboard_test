import {
  useDiagnosticSessionBusy,
  useDiagnosticSessionLoadError,
  useDiagnosticSessionActions,
  useDiagnosticSessionState,
} from "@/app/providers/DiagnosticSessionProvider";

export function useDiagnosticSession() {
  const session = useDiagnosticSessionState();
  const { start, stop } = useDiagnosticSessionActions();
  const isBusy = useDiagnosticSessionBusy();
  const loadError = useDiagnosticSessionLoadError();
  return { ...session, start, stop, isBusy, loadError };
}
