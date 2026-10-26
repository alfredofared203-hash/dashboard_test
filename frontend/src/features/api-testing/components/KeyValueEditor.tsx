import { Plus, Trash2 } from "lucide-react";
import type { RequestParameter } from "../types/apiTest";

interface KeyValueEditorProps {
  title: string;
  rows: RequestParameter[];
  onChange: (rows: RequestParameter[]) => void;
  onAdd: () => void;
  emptyMessage: string;
  nameLabel: string;
  valueLabel: string;
}

export function KeyValueEditor({
  title,
  rows,
  onChange,
  onAdd,
  emptyMessage,
  nameLabel,
  valueLabel,
}: KeyValueEditorProps) {
  function updateRow(id: string, updates: Partial<RequestParameter>) {
    onChange(rows.map((row) => row.id === id ? { ...row, ...updates } : row));
  }

  return (
    <section className="api-test-subsection">
      <div className="api-test-subheading">
        <h3>{title}</h3>
        <button className="api-test-text-button" type="button" onClick={onAdd}>
          <Plus size={13} /> Add
        </button>
      </div>
      {rows.length === 0 ? (
        <p className="api-test-empty-inline">{emptyMessage}</p>
      ) : (
        <div className="api-test-rows">
          {rows.map((row, index) => (
            <div className="api-test-key-value-row" key={row.id}>
              <label className="api-test-enabled" title={row.enabled ? "Parameter enabled" : "Parameter disabled"}>
                <input
                  type="checkbox"
                  checked={row.enabled}
                  aria-label={`Enable ${title.toLowerCase()} row ${index + 1}`}
                  onChange={(event) => updateRow(row.id, { enabled: event.currentTarget.checked })}
                />
              </label>
              <label className="sr-only" htmlFor={`${row.id}-name`}>{nameLabel} {index + 1}</label>
              <input
                id={`${row.id}-name`}
                className="api-test-input"
                value={row.name}
                placeholder={nameLabel}
                aria-label={`${nameLabel} ${index + 1}`}
                onChange={(event) => updateRow(row.id, { name: event.currentTarget.value })}
              />
              <label className="sr-only" htmlFor={`${row.id}-value`}>{valueLabel} {index + 1}</label>
              <input
                id={`${row.id}-value`}
                className="api-test-input"
                type={/authorization|token|secret/i.test(row.name) ? "password" : "text"}
                value={row.value}
                placeholder={valueLabel}
                aria-label={`${valueLabel} ${index + 1}`}
                autoComplete="off"
                onChange={(event) => updateRow(row.id, { value: event.currentTarget.value })}
              />
              <button
                className="api-test-icon-button"
                type="button"
                aria-label={`Remove ${title.toLowerCase()} row ${index + 1}`}
                onClick={() => onChange(rows.filter((entry) => entry.id !== row.id))}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
