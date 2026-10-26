import { Braces } from "lucide-react";
import type { ApiSchemaValue } from "../types/discovery";

export interface SchemaViewerProps {
  title: string;
  schema: ApiSchemaValue | null;
  emptyMessage: string;
}

export function SchemaViewer({ title, schema, emptyMessage }: SchemaViewerProps) {
  return (
    <section className="schema-section">
      <div className="schema-heading"><Braces size={14} /><h3>{title}</h3></div>
      {schema === null ? (
        <p className="schema-empty">{emptyMessage}</p>
      ) : (
        <pre className="schema-code"><code>{JSON.stringify(schema, null, 2)}</code></pre>
      )}
    </section>
  );
}
