import { useState } from "react";

interface ReferenceListEditorProps {
  label: string;
  jsonValue: string;
  onSave: (nextJsonValue: string) => void;
}

function parseList(json: string): string[] {
  try {
    const parsed = JSON.parse(json || "[]");
    return Array.isArray(parsed) ? parsed.map((v) => String(v)) : [];
  } catch {
    return [];
  }
}

// Team member/vehicle/equipment/aircraft lists are stored server-side as a
// JSON-encoded array of plain strings (names/IDs) — this edits that array
// directly rather than pulling from the Personnel/Logistics master
// catalogs, which aren't wired up to the web client yet (see Team Detail
// scope note).
export default function ReferenceListEditor({ label, jsonValue, onSave }: ReferenceListEditorProps) {
  const items = parseList(jsonValue);
  const [draft, setDraft] = useState("");

  const commit = (next: string[]) => onSave(JSON.stringify(next));

  return (
    <div>
      <div className="field" style={{ flexDirection: "row", gap: 8 }}>
        <input
          placeholder={`Add ${label.toLowerCase()}…`}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && draft.trim()) {
              commit([...items, draft.trim()]);
              setDraft("");
            }
          }}
        />
        <button
          style={{ width: "auto" }}
          disabled={!draft.trim()}
          onClick={() => {
            commit([...items, draft.trim()]);
            setDraft("");
          }}
        >
          Add
        </button>
      </div>
      {items.length === 0 && <p style={{ opacity: 0.6 }}>None added.</p>}
      {items.map((item, idx) => (
        <div key={idx} className="list-item" style={{ cursor: "default" }}>
          <span>{item}</span>
          <button
            className="danger"
            style={{ width: "auto" }}
            onClick={() => commit(items.filter((_, i) => i !== idx))}
          >
            Remove
          </button>
        </div>
      ))}
    </div>
  );
}
