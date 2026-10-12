import { useState } from "react";
import { OBJECTIVE_PRIORITIES } from "../../../api/endpoints";

interface NewObjectiveDialogProps {
  onCreate: (body: { text: string; priority: string; owner_section: string }) => void;
  onCancel: () => void;
  busy?: boolean;
}

export default function NewObjectiveDialog({ onCreate, onCancel, busy }: NewObjectiveDialogProps) {
  const [text, setText] = useState("");
  const [priority, setPriority] = useState("normal");
  const [ownerSection, setOwnerSection] = useState("");

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Objective</h3>
        <div className="field">
          <label htmlFor="objective-text">Objective</label>
          <textarea
            id="objective-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. Establish containment line along Ridge Trail by end of OP 3"
            autoFocus
          />
        </div>
        <div className="field">
          <label htmlFor="objective-priority">Priority</label>
          <select id="objective-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
            {OBJECTIVE_PRIORITIES.map((p) => (
              <option key={p.key} value={p.key}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="objective-owner">Owner Section</label>
          <input
            id="objective-owner"
            value={ownerSection}
            onChange={(e) => setOwnerSection(e.target.value)}
            placeholder="e.g. Operations"
          />
        </div>
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            disabled={!text.trim() || busy}
            onClick={() => onCreate({ text: text.trim(), priority, owner_section: ownerSection.trim() })}
          >
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
