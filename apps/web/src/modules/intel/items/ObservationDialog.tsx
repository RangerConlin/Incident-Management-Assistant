import { useState } from "react";
import { INFORMATION_CONFIDENCE_VALUES, SEVERITY_VALUES } from "../../../api/endpoints";
import { SelectField, TextField } from "../IntelFormFields";

interface ObservationDialogProps {
  itemTitle: string;
  onCreate: (body: Record<string, unknown>) => void;
  onCancel: () => void;
  busy?: boolean;
}

// Matches desktop's widgets/observation_entry_dialog.py's
// ObservationEntryDialog.
export default function ObservationDialog({ itemTitle, onCreate, onCancel, busy }: ObservationDialogProps) {
  const [observer, setObserver] = useState("");
  const [observedAt, setObservedAt] = useState("");
  const [sourceTeam, setSourceTeam] = useState("");
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("Low");
  const [confidence, setConfidence] = useState("Unconfirmed");
  const [location, setLocation] = useState("");
  const [summary, setSummary] = useState("");
  const [notes, setNotes] = useState("");

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Add Observation</h3>
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          {itemTitle}
        </p>
        <TextField label="Observer" value={observer} onChange={setObserver} placeholder="Name or team designator" />
        <TextField label="Date / Time" value={observedAt} onChange={setObservedAt} placeholder="YYYY-MM-DD HH:MM — leave blank for now" />
        <TextField label="Source Team" value={sourceTeam} onChange={setSourceTeam} placeholder="Optional — field team, unit, etc." />
        <TextField label="Status" value={status} onChange={setStatus} placeholder="e.g. Closed, Worsening, Under Investigation" />
        <SelectField label="Severity" value={severity} onChange={setSeverity} options={SEVERITY_VALUES} />
        <SelectField label="Confidence" value={confidence} onChange={setConfidence} options={INFORMATION_CONFIDENCE_VALUES} />
        <TextField label="Location" value={location} onChange={setLocation} placeholder="Optional location description" />
        <TextField label="Summary" value={summary} onChange={setSummary} required placeholder="Brief summary of this observation (required)" />
        <TextField label="Detailed Notes" value={notes} onChange={setNotes} textarea />
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            disabled={!summary.trim() || busy}
            onClick={() =>
              onCreate({
                observer,
                observed_at: observedAt || undefined,
                source_team: sourceTeam || undefined,
                status,
                severity,
                confidence,
                location_text: location || undefined,
                summary: summary.trim(),
                detailed_notes: notes || undefined,
              })
            }
          >
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
