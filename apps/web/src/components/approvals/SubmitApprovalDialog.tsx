import { useMemo, useState } from "react";
import { usePersonnelSearch } from "./hooks";
import type { ApprovalPreviewRow } from "../../api/types";

interface SubmitApprovalDialogProps {
  title: string;
  rows: ApprovalPreviewRow[];
  onConfirm: (assignActors: Record<string, number>) => void;
  onCancel: () => void;
}

// Shows who each about-to-activate approval step would go to, with the
// option to change it, before the submitter commits to start/sign — the
// web counterpart of desktop's SubmitApprovalDialog.
export default function SubmitApprovalDialog({ title, rows, onConfirm, onCancel }: SubmitApprovalDialogProps) {
  const [choices, setChoices] = useState<Record<string, { id: number; name: string } | null>>(() =>
    Object.fromEntries(rows.map((r) => [r.step_id, r.resolved_actor_id != null ? { id: r.resolved_actor_id, name: r.resolved_actor_name ?? String(r.resolved_actor_id) } : null]))
  );
  const [editingStep, setEditingStep] = useState<string | null>(null);

  const canConfirm = useMemo(() => rows.every((r) => choices[r.step_id] != null), [rows, choices]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div style={{ background: "var(--surface, #1e1e1e)", padding: 20, borderRadius: 6, minWidth: 360, maxWidth: 480 }}>
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        {rows.map((row) => {
          const choice = choices[row.step_id];
          return (
            <div key={row.step_id} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: "1px solid rgba(128,128,128,0.3)" }}>
              <div style={{ fontWeight: 600 }}>{row.label}</div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                <span style={{ color: choice ? undefined : "#D97706" }}>
                  {choice ? `Will go to: ${choice.name}` : "Nobody resolved — a person must be picked"}
                </span>
                <button className="secondary" style={{ width: "auto" }} onClick={() => setEditingStep(editingStep === row.step_id ? null : row.step_id)}>
                  Change…
                </button>
              </div>
              {editingStep === row.step_id && (
                <PersonSearch
                  onPick={(id, name) => {
                    setChoices((prev) => ({ ...prev, [row.step_id]: { id, name } }));
                    setEditingStep(null);
                  }}
                />
              )}
            </div>
          );
        })}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
          <button className="secondary" style={{ width: "auto" }} onClick={onCancel}>
            Cancel
          </button>
          <button
            style={{ width: "auto" }}
            disabled={!canConfirm}
            onClick={() => {
              const assignActors: Record<string, number> = {};
              for (const row of rows) {
                const choice = choices[row.step_id];
                if (choice) assignActors[row.step_id] = choice.id;
              }
              onConfirm(assignActors);
            }}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}

function PersonSearch({ onPick }: { onPick: (id: number, name: string) => void }) {
  const [query, setQuery] = useState("");
  const { data: results = [] } = usePersonnelSearch(query);
  return (
    <div style={{ marginTop: 6 }}>
      <input autoFocus placeholder="Search personnel…" value={query} onChange={(e) => setQuery(e.target.value)} style={{ width: "100%" }} />
      {query && (
        <div style={{ maxHeight: 150, overflowY: "auto", border: "1px solid rgba(128,128,128,0.3)", marginTop: 4 }}>
          {results.length === 0 && <div style={{ padding: 6, opacity: 0.6 }}>No matches.</div>}
          {results.map((person) =>
            person.person_record == null ? null : (
              <div
                key={person.person_record}
                className="list-item"
                style={{ padding: 6, cursor: "pointer" }}
                onClick={() => onPick(person.person_record!, person.name)}
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
