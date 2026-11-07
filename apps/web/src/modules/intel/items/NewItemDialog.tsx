import { useState } from "react";
import { INFORMATION_CONFIDENCE_VALUES, ITEM_TYPES, LEAD_PRIORITIES } from "../../../api/endpoints";
import { CheckboxField, SelectField, TextField } from "../IntelFormFields";

interface NewItemDialogProps {
  onCreate: (body: Record<string, unknown>) => void;
  onCancel: () => void;
  busy?: boolean;
}

// Matches desktop's intel_items_tab.py's _NewItemDialog: Type/Description/
// Location/Priority/Confidence, the "Urgent response needed (SAR 135)"
// checkbox, and Notes. Desktop's file-attachment picker is a native OS
// dialog with no server endpoint behind it yet — omitted here rather than
// faking an upload control with nothing to receive it.
export default function NewItemDialog({ onCreate, onCancel, busy }: NewItemDialogProps) {
  const [itemType, setItemType] = useState(ITEM_TYPES[0]);
  const [title, setTitle] = useState("");
  const [location, setLocation] = useState("");
  const [priority, setPriority] = useState("Medium");
  const [confidence, setConfidence] = useState("Unconfirmed");
  const [urgent, setUrgent] = useState(false);
  const [notes, setNotes] = useState("");

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Intel Item</h3>
        <SelectField label="Type" value={itemType} onChange={setItemType} options={ITEM_TYPES} />
        <TextField label="Description" value={title} onChange={setTitle} required placeholder="Description (required)" />
        <TextField label="Location" value={location} onChange={setLocation} />
        <SelectField label="Priority" value={priority} onChange={setPriority} options={LEAD_PRIORITIES} />
        <SelectField label="Confidence" value={confidence} onChange={setConfidence} options={INFORMATION_CONFIDENCE_VALUES} />
        <CheckboxField label="Urgent response needed (SAR 135)" checked={urgent} onChange={setUrgent} />
        <TextField label="Notes" value={notes} onChange={setNotes} textarea />
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            disabled={!title.trim() || busy}
            onClick={() =>
              onCreate({
                item_type: itemType,
                title: title.trim(),
                location_text: location || undefined,
                priority,
                confidence,
                urgent_response_needed: urgent,
                notes: notes || undefined,
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
