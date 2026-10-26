import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDownWideNarrow,
  ArrowUpWideNarrow,
  Clock3,
  FileSearch,
  RotateCw,
  Search,
  X,
} from "lucide-react";
import { ActionButton } from "@/components/atoms/ActionButton";
import { formatDuration } from "@/lib/time";
import { useDiagnosticLogs } from "../hooks/useDiagnosticLogs";
import { LogDetailsDialog } from "../components/LogDetailsDialog";
import type { DiagnosticLogEntry, LogSeverity } from "../types/logs";
import "../logs-diagnostics.css";

type SessionScope = "current" | "all";
type TimeRange = "all" | "5" | "15" | "30" | "60";
type SeverityFilter = "ALL" | LogSeverity;

const severityOptions: SeverityFilter[] = ["ALL", "DEBUG", "INFO", "WARN", "ERROR"];
const severityLabels: Record<SeverityFilter, string> = {
  ALL: "All",
  DEBUG: "Debug",
  INFO: "Info",
  WARN: "Warn",
  ERROR: "Error",
};
const sessionStatusLabels = {
  idle: "IDLE",
  starting: "STARTING",
  running: "RUNNING",
  completed: "COMPLETED",
  stopped: "STOPPED",
  failed: "FAILED",
} as const;
const timeRangeLabels: Record<TimeRange, string> = {
  all: "All time",
  "5": "Last 5 minutes",
  "15": "Last 15 minutes",
  "30": "Last 30 minutes",
  "60": "Last 1 hour",
};

const timestampFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

function logAccessibleName(entry: DiagnosticLogEntry): string {
  return `${entry.severity} log at ${timestampFormatter.format(new Date(entry.timestamp))}. ${entry.service}, task ${entry.taskId}, source ${entry.source}. ${entry.message}. Activate to view details.`;
}

export function LogsDiagnosticsWorkspace() {
  const { entries, status, error, generatedAt, diagnosticSession, reload } = useDiagnosticLogs();
  const [query, setQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("ALL");
  const [selectedService, setSelectedService] = useState("ALL");
  const [timeRange, setTimeRange] = useState<TimeRange>("all");
  const [sessionScope, setSessionScope] = useState<SessionScope>("current");
  const [newestFirst, setNewestFirst] = useState(true);
  const [selectedEntry, setSelectedEntry] = useState<DiagnosticLogEntry | null>(null);

  const hasSession = diagnosticSession.sessionId !== null;
  const effectiveSessionScope = hasSession ? sessionScope : "all";
  const availableServices = useMemo(
    () => [...new Set(entries.map((entry) => entry.service))].sort((left, right) => left.localeCompare(right)),
    [entries],
  );
  const normalizedQuery = query.trim().toLocaleLowerCase();

  const matchingEntries = useMemo(() => {
    const cutoff = timeRange === "all" ? null : Date.now() - Number(timeRange) * 60_000;
    const filtered = entries.filter((entry) => {
      const matchesSession = effectiveSessionScope === "all"
        || entry.diagnosticSessionId === diagnosticSession.sessionId;
      const matchesSeverity = severityFilter === "ALL" || entry.severity === severityFilter;
      const matchesService = selectedService === "ALL" || entry.service === selectedService;
      const matchesTime = cutoff === null || Date.parse(entry.timestamp) >= cutoff;
      const searchableText = `${entry.message} ${entry.service} ${entry.taskId} ${entry.source}`.toLocaleLowerCase();
      const matchesQuery = normalizedQuery.length === 0 || searchableText.includes(normalizedQuery);
      return matchesSession && matchesSeverity && matchesService && matchesTime && matchesQuery;
    });

    return filtered.sort((left, right) => {
      const difference = Date.parse(left.timestamp) - Date.parse(right.timestamp);
      return newestFirst ? -difference : difference;
    });
  }, [
    diagnosticSession.sessionId,
    effectiveSessionScope,
    entries,
    newestFirst,
    normalizedQuery,
    selectedService,
    severityFilter,
    timeRange,
  ]);

  const currentSessionEntries = useMemo(
    () => hasSession
      ? entries.filter((entry) => entry.diagnosticSessionId === diagnosticSession.sessionId)
      : [],
    [diagnosticSession.sessionId, entries, hasSession],
  );
  const errorCount = matchingEntries.filter((entry) => entry.severity === "ERROR").length;
  const warningCount = matchingEntries.filter((entry) => entry.severity === "WARN").length;
  const statusClass = diagnosticSession.status === "starting"
    ? "logs-session-starting"
    : `logs-session-${diagnosticSession.status}`;

  return (
    <div className="logs-page">
      <header className="logs-page-heading">
        <div>
          <div className="eyebrow">OBSERVABILITY / LOGS & DIAGNOSTICS</div>
          <h1>Logs & Diagnostics</h1>
          <p>Search and inspect diagnostic events returned by the DCC logs API.</p>
        </div>
        <span className="logs-mock-badge"><span /> DCC BACKEND LOGS</span>
      </header>

      <section className="logs-session-context" aria-labelledby="logs-session-heading">
        <div className="logs-session-context-heading">
          <div className="logs-panel-title">
            <FileSearch size={15} />
            <h2 id="logs-session-heading">Diagnostic session context</h2>
          </div>
          {hasSession && (
            <span className={`logs-session-state ${statusClass}`} role="status" aria-live="polite">
              <span />{sessionStatusLabels[diagnosticSession.status]}
            </span>
          )}
        </div>
        {hasSession ? (
          <div className="logs-session-details">
            <div className="logs-session-target">
              <strong>{diagnosticSession.targetScope?.displayName ?? "Diagnostic target unavailable"}</strong>
              <code>{diagnosticSession.sessionId}</code>
            </div>
            <dl>
              <div><dt>Started</dt><dd>{diagnosticSession.startedAt?.toLocaleString() ?? "Unavailable"}</dd></div>
              <div><dt>Elapsed</dt><dd>{formatDuration(diagnosticSession.elapsedSeconds, "compact")}</dd></div>
              <div><dt>Target scope</dt><dd>{diagnosticSession.targetScope?.type ?? "—"}</dd></div>
            </dl>
          </div>
        ) : (
          <div className="logs-no-session" role="status">
            <Clock3 size={16} />
            <div>
              <strong>No diagnostic session is available</strong>
              <span>You can still inspect all logs returned by the backend. Start a session only from System Overview.</span>
            </div>
          </div>
        )}
      </section>

      <div className="logs-toolbar">
        <label className="logs-search">
          <Search size={15} aria-hidden="true" />
          <span className="sr-only">Search log message, service, task, or source</span>
          <input
            type="search"
            value={query}
            placeholder="Search message, service, task, source…"
            onChange={(event) => setQuery(event.currentTarget.value)}
          />
          {query && (
            <button type="button" aria-label="Clear log search" onClick={() => setQuery("")}>
              <X size={14} />
            </button>
          )}
        </label>
        <label className="logs-filter">
          <span>SESSION</span>
          <select
            aria-label="Filter logs by diagnostic session"
            value={effectiveSessionScope}
            onChange={(event) => setSessionScope(event.currentTarget.value as SessionScope)}
          >
            <option value="current" disabled={!hasSession}>Current session</option>
            <option value="all">All sessions</option>
          </select>
        </label>
        <label className="logs-filter">
          <span>SERVICE</span>
          <select
            aria-label="Filter logs by service"
            value={selectedService}
            onChange={(event) => setSelectedService(event.currentTarget.value)}
          >
            <option value="ALL">All services</option>
            {availableServices.map((service) => <option key={service} value={service}>{service}</option>)}
          </select>
        </label>
        <label className="logs-filter">
          <span>TIME RANGE</span>
          <select
            aria-label="Filter logs by time range"
            value={timeRange}
            onChange={(event) => setTimeRange(event.currentTarget.value as TimeRange)}
          >
            {(Object.keys(timeRangeLabels) as TimeRange[]).map((range) => (
              <option key={range} value={range}>{timeRangeLabels[range]}</option>
            ))}
          </select>
        </label>
      </div>

      <section className="logs-severity-filter" aria-label="Filter logs by severity">
        <span className="logs-severity-filter-label">SEVERITY</span>
        <div role="group" aria-label="Severity filters">
          {severityOptions.map((severity) => (
            <button
              key={severity}
              type="button"
              className={`logs-severity-option ${severity === "ALL" ? "logs-severity-all" : `logs-severity-${severity.toLowerCase()}`} ${severityFilter === severity ? "active" : ""}`}
              aria-pressed={severityFilter === severity}
              onClick={() => setSeverityFilter(severity)}
            >
              {severityLabels[severity]}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="logs-sort-button"
          aria-label={`Sort by timestamp, currently ${newestFirst ? "newest first" : "oldest first"}`}
          onClick={() => setNewestFirst((current) => !current)}
        >
          {newestFirst ? <ArrowDownWideNarrow size={14} /> : <ArrowUpWideNarrow size={14} />}
          {newestFirst ? "Newest first" : "Oldest first"}
        </button>
      </section>

      {effectiveSessionScope === "current" && hasSession && (
        <section className="logs-current-summary" aria-label="Current diagnostic session log summary">
          <div><span>SESSION</span><strong>{diagnosticSession.sessionId}</strong></div>
          <div><span>LOGS</span><strong>{currentSessionEntries.length}</strong></div>
          <div><span>ERRORS</span><strong className="logs-count-error">{currentSessionEntries.filter((entry) => entry.severity === "ERROR").length}</strong></div>
          <div><span>WARNINGS</span><strong className="logs-count-warning">{currentSessionEntries.filter((entry) => entry.severity === "WARN").length}</strong></div>
        </section>
      )}

      <section className="logs-results-panel" aria-labelledby="logs-results-heading">
        <div className="logs-results-heading">
          <div>
            <h2 id="logs-results-heading">Diagnostic logs</h2>
            <p>
              <strong>{matchingEntries.length}</strong> matching {matchingEntries.length === 1 ? "entry" : "entries"}
              {generatedAt && <> · Logs fetched {new Date(generatedAt).toLocaleTimeString()}</>}
            </p>
          </div>
          <div className="logs-results-actions">
            <span className="logs-count-pill"><strong>{errorCount}</strong> errors</span>
            <span className="logs-count-pill"><strong>{warningCount}</strong> warnings</span>
            <ActionButton variant="outline" size="sm" onClick={reload} disabled={status === "loading"}>
              <RotateCw size={13} className={status === "loading" ? "logs-refresh-spinning" : ""} />
              Refresh
            </ActionButton>
          </div>
        </div>

        {status === "loading" && (
          <div className="logs-state-card" role="status">
            <span className="logs-spinner" />
            <strong>Loading diagnostic logs</strong>
            <span>Reading diagnostic logs from the DCC API…</span>
          </div>
        )}
        {status === "error" && (
          <div className="logs-state-card logs-state-error" role="alert">
            <AlertTriangle size={21} />
            <strong>Could not load diagnostic logs</strong>
            <span>{error ?? "The logs provider failed unexpectedly."}</span>
            <ActionButton variant="outline" size="sm" onClick={reload}><RotateCw size={13} /> Try again</ActionButton>
          </div>
        )}
        {status === "empty" && (
          <div className="logs-state-card" role="status">
            <FileSearch size={22} />
            <strong>No logs available</strong>
            <span>The backend returned no log entries. Refresh to try again.</span>
          </div>
        )}
        {status === "success" && matchingEntries.length === 0 && (
          <div className="logs-state-card" role="status">
            <Search size={21} />
            <strong>{normalizedQuery ? "No logs match your search" : "No logs match these filters"}</strong>
            <span>Try changing the search text, session, severity, service, or time range.</span>
          </div>
        )}
        {status === "success" && matchingEntries.length > 0 && (
          <div className="logs-list-wrap">
            <div className="logs-list-header" aria-hidden="true">
              <span>Timestamp</span><span>Severity</span><span>Service / Task</span><span>Source</span><span>Message</span>
            </div>
            <ol className="logs-list" aria-label="Matching diagnostic log entries">
              {matchingEntries.map((entry) => (
                <li key={entry.id}>
                  <button
                    type="button"
                    className="logs-list-row"
                    aria-label={logAccessibleName(entry)}
                    onClick={() => setSelectedEntry(entry)}
                  >
                    <time dateTime={entry.timestamp}>{timestampFormatter.format(new Date(entry.timestamp))}</time>
                    <span className={`logs-severity logs-severity-${entry.severity.toLowerCase()}`}>{entry.severity}</span>
                    <span className="logs-service-task"><strong>{entry.service}</strong><code>{entry.taskId}</code></span>
                    <span className="logs-source">{entry.source}</span>
                    <span className="logs-message">{entry.message}</span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        )}
      </section>

      <footer className="logs-page-footer">
        <span>DCC backend log entries · No live log streaming</span>
        <span>DCC · LOGS & DIAGNOSTICS</span>
      </footer>

      <LogDetailsDialog entry={selectedEntry} onClose={() => setSelectedEntry(null)} />
    </div>
  );
}
