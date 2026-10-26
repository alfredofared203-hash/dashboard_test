import { Clock3, History } from "lucide-react";
import type { ApiTestHistoryItem } from "../types/apiTest";

interface RequestHistoryProps {
  items: ApiTestHistoryItem[];
  selectedId: string | null;
  onSelect: (item: ApiTestHistoryItem) => void;
}

export function RequestHistory({ items, selectedId, onSelect }: RequestHistoryProps) {
  return (
    <section className="api-test-panel api-test-history" aria-labelledby="api-history-title">
      <header className="api-test-panel-heading">
        <div className="api-test-panel-title"><History size={15} /><h2 id="api-history-title">Request history</h2></div>
        <span className="discovery-count">{items.length}</span>
      </header>
      {items.length === 0 ? (
        <div className="api-test-history-empty">
          <Clock3 size={19} />
          <span>Requests from this session will appear here.</span>
        </div>
      ) : (
        <ul className="api-test-history-list">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={`api-test-history-item ${selectedId === item.id ? "selected" : ""}`}
                aria-pressed={selectedId === item.id}
                onClick={() => onSelect(item)}
              >
                <span className={`api-test-history-dot ${item.success ? "success" : item.status === null ? "network" : "failure"}`} />
                <span className={`http-method method-${item.method.toLowerCase()}`}>{item.method}</span>
                <span className="api-test-history-copy">
                  <strong>{item.endpointName}</strong>
                  <code>{item.url}</code>
                </span>
                <span className={`api-test-history-status ${item.success ? "success" : item.status === null ? "network" : "failure"}`}>
                  {item.status ?? "ERR"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <footer className="discovery-panel-footer">IN-MEMORY · CLEARED WHEN YOU LEAVE</footer>
    </section>
  );
}
