import { useState } from "react";
import { INFORMATION_CONFIDENCE_VALUES, LEAD_PRIORITIES, LEAD_SOURCE_CATEGORIES, SOURCE_RELIABILITY_VALUES } from "../../../api/endpoints";
import { CheckboxField, SelectField, TextField } from "../IntelFormFields";

interface NewLeadDialogProps {
  onCreate: (body: Record<string, unknown>) => void;
  onCancel: () => void;
  busy?: boolean;
}

// Matches desktop's leads_tab.py's _NewLeadDialog: common Title/Summary/
// Priority, a Source group whose Category select swaps between 5 stacked
// sub-forms (same fields the real dialog's _build_*_page methods create),
// Report Quality, then Location/Assign To/Notes.
export default function NewLeadDialog({ onCreate, onCancel, busy }: NewLeadDialogProps) {
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [priority, setPriority] = useState("Medium");
  const [category, setCategory] = useState(LEAD_SOURCE_CATEGORIES[0]);
  const [f, setF] = useState<Record<string, string>>({});
  const set = (key: string) => (value: string) => setF((prev) => ({ ...prev, [key]: value }));
  const [createContactSubject, setCreateContactSubject] = useState(false);
  const [location, setLocation] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [notes, setNotes] = useState("");

  const sourceTypeFor = (cat: string) =>
    ({ Team: "Team Report", Staff: "Team Report", "Agency / Liaison": "Liaison", "Public Tip": "Public Tip", Other: "Other" })[cat] ?? "Other";

  const buildBody = (): Record<string, unknown> => {
    let source_display: string | undefined;
    let reported_by: string | undefined;
    const base: Record<string, unknown> = {
      title: title.trim(),
      summary,
      priority,
      source_category: category,
      source_type: sourceTypeFor(category),
      source_reliability: f.reliability || undefined,
      information_confidence: f.confidence || undefined,
      location_text: location || undefined,
      assigned_to: assignedTo || undefined,
      notes: notes || undefined,
    };
    if (category === "Team") {
      source_display = f.team_name;
      reported_by = f.team_name;
      base.source_team_name = f.team_name;
      base.source_contact_name = f.team_member;
      base.source_contact_method = f.team_channel;
    } else if (category === "Staff") {
      source_display = f.staff_name;
      reported_by = f.staff_name;
      base.source_contact_name = f.staff_name;
      base.source_agency = f.staff_section;
      base.source_contact_method = f.staff_contact;
    } else if (category === "Agency / Liaison") {
      source_display = f.agency_contact ? `${f.agency_name} / ${f.agency_contact}` : f.agency_name;
      reported_by = f.agency_contact || f.agency_name;
      base.source_agency = f.agency_name;
      base.source_contact_name = f.agency_contact;
      base.source_role = f.agency_role;
      base.source_phone = f.agency_phone;
      base.source_email = f.agency_email;
      base.source_contact_method = f.agency_method;
      base.source_notes = f.agency_notes;
    } else if (category === "Public Tip") {
      source_display = f.tip_name || "Public Tip";
      reported_by = f.tip_name;
      base.source_contact_name = f.tip_name;
      base.source_phone = f.tip_phone;
      base.source_email = f.tip_email;
      base.source_address = f.tip_address;
      base.source_role = f.tip_relationship;
    } else {
      source_display = f.other_label || f.other_contact_name;
      reported_by = f.other_contact_name || f.other_label;
      base.source_agency = f.other_label;
      base.source_contact_name = f.other_contact_name;
      base.source_contact_method = f.other_contact_info;
      base.source_notes = f.other_notes;
    }
    base.source_display = source_display;
    base.reported_by = reported_by || "";
    return base;
  };

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" style={{ maxWidth: 580, maxHeight: "85vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <h3>New Lead</h3>

        <TextField label="Title" value={title} onChange={setTitle} required placeholder="Brief description" />
        <TextField label="Summary" value={summary} onChange={setSummary} textarea placeholder="Detailed summary" />
        <SelectField label="Priority" value={priority} onChange={setPriority} options={LEAD_PRIORITIES} />

        <fieldset>
          <legend>Source</legend>
          <SelectField label="Category" value={category} onChange={setCategory} options={LEAD_SOURCE_CATEGORIES} />

          {category === "Team" && (
            <>
              <TextField label="Team" value={f.team_name ?? ""} onChange={set("team_name")} placeholder="Team name or callsign" />
              <TextField label="Reporting Member" value={f.team_member ?? ""} onChange={set("team_member")} />
              <TextField label="Contact Channel" value={f.team_channel ?? ""} onChange={set("team_channel")} />
            </>
          )}
          {category === "Staff" && (
            <>
              <TextField label="Staff Member" value={f.staff_name ?? ""} onChange={set("staff_name")} placeholder="Name or role" />
              <TextField label="Section / Unit" value={f.staff_section ?? ""} onChange={set("staff_section")} />
              <TextField label="Contact Method" value={f.staff_contact ?? ""} onChange={set("staff_contact")} />
            </>
          )}
          {category === "Agency / Liaison" && (
            <>
              <TextField label="Agency" value={f.agency_name ?? ""} onChange={set("agency_name")} required placeholder="Agency or organization" />
              <TextField label="Representative" value={f.agency_contact ?? ""} onChange={set("agency_contact")} />
              <TextField label="Role / Title" value={f.agency_role ?? ""} onChange={set("agency_role")} />
              <TextField label="Phone" value={f.agency_phone ?? ""} onChange={set("agency_phone")} />
              <TextField label="Email" value={f.agency_email ?? ""} onChange={set("agency_email")} />
              <TextField label="Contact Method" value={f.agency_method ?? ""} onChange={set("agency_method")} />
              <TextField label="Source Notes" value={f.agency_notes ?? ""} onChange={set("agency_notes")} textarea />
            </>
          )}
          {category === "Public Tip" && (
            <>
              <TextField label="Name" value={f.tip_name ?? ""} onChange={set("tip_name")} required placeholder="Informant name" />
              <TextField label="Phone" value={f.tip_phone ?? ""} onChange={set("tip_phone")} />
              <TextField label="Email" value={f.tip_email ?? ""} onChange={set("tip_email")} />
              <TextField label="Address" value={f.tip_address ?? ""} onChange={set("tip_address")} />
              <TextField label="Relationship" value={f.tip_relationship ?? ""} onChange={set("tip_relationship")} />
              <p style={{ fontSize: "0.82rem", opacity: 0.6, fontStyle: "italic" }}>A Subject will be created for this informant.</p>
            </>
          )}
          {category === "Other" && (
            <>
              <TextField label="Source Label" value={f.other_label ?? ""} onChange={set("other_label")} />
              <TextField label="Contact Name" value={f.other_contact_name ?? ""} onChange={set("other_contact_name")} />
              <TextField label="Contact Info" value={f.other_contact_info ?? ""} onChange={set("other_contact_info")} />
              <TextField label="Source Notes" value={f.other_notes ?? ""} onChange={set("other_notes")} textarea />
              <CheckboxField label="Create Contact Subject for this contact" checked={createContactSubject} onChange={setCreateContactSubject} />
            </>
          )}
        </fieldset>

        <fieldset>
          <legend>Report Quality</legend>
          <SelectField label="Source Reliability" value={f.reliability ?? ""} onChange={set("reliability")} options={["", ...SOURCE_RELIABILITY_VALUES]} />
          <SelectField label="Information Confidence" value={f.confidence ?? ""} onChange={set("confidence")} options={["", ...INFORMATION_CONFIDENCE_VALUES]} />
        </fieldset>

        <TextField label="Location" value={location} onChange={setLocation} placeholder="Optional plain-text location or address" />
        <TextField label="Assign To" value={assignedTo} onChange={setAssignedTo} placeholder="Leave blank if unassigned" />
        <TextField label="Notes" value={notes} onChange={setNotes} textarea />

        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button disabled={!title.trim() || busy} onClick={() => onCreate(buildBody())}>
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
