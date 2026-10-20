import { useState } from "react";
import { usePersonnelSearch } from "./hooks";

interface AssignStepControlProps {
  onAssign: (personRecord: number) => void;
  disabled?: boolean;
}

// Minimal inline person search, used to manually assign an approval step
// that has nobody resolved — either a flexible step by design, or a
// role-based step whose whole chain of command came up vacant.
export default function AssignStepControl({ onAssign, disabled }: AssignStepControlProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const { data: results = [] } = usePersonnelSearch(query);

  if (!open) {
    return (
      <button className="secondary" style={{ width: "auto" }} disabled={disabled} onClick={() => setOpen(true)}>
        Assign…
      </button>
    );
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4, position: "relative" }}>
      <input
        autoFocus
        placeholder="Search personnel…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        style={{ width: 180 }}
      />
      <button className="secondary" style={{ width: "auto" }} onClick={() => setOpen(false)}>
        Cancel
      </button>
      {query && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            zIndex: 10,
            background: "var(--surface, #1e1e1e)",
            border: "1px solid rgba(128,128,128,0.4)",
            maxHeight: 200,
            overflowY: "auto",
            minWidth: 220,
          }}
        >
          {results.length === 0 && <div style={{ padding: 6, opacity: 0.6 }}>No matches.</div>}
          {results.map((person) =>
            person.person_record == null ? null : (
              <div
                key={person.person_record}
                className="list-item"
                style={{ padding: 6, cursor: "pointer" }}
                onClick={() => {
                  onAssign(person.person_record!);
                  setOpen(false);
                  setQuery("");
                }}
              >
                {person.name}
                {person.primary_role ? ` — ${person.primary_role}` : ""}
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
