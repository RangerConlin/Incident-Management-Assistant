import { useState } from "react";

interface AssignLeadDialogProps {
  leadLabel: string;
  initialValue?: string;
  onAssign: (name: string) => void;
  onCancel: () => void;
}

// Matches desktop's leads_tab.py's _assign_lead — a plain name prompt
// (QInputDialog.getText), not a full form.
export default function AssignLeadDialog({ leadLabel, initialValue, onAssign, onCancel }: AssignLeadDialogProps) {
  const [name, setName] = useState(initialValue ?? "");
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Assign Lead</h3>
        <div className="field">
          <label>Assign {leadLabel} to:</label>
          <input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button onClick={() => onAssign(name.trim())}>OK</button>
        </div>
      </div>
    </div>
  );
}
