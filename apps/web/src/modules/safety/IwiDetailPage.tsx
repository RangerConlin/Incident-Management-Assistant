import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import { IWI_INCIDENT_TYPES, IWI_SEVERITIES } from "../../api/types";
import { useIwiReport, useSignoffIwiReport, useUpdateIwiReport } from "./iwiHooks";

type Row = Record<string, unknown>;
type FieldType = "text" | "textarea" | "checkbox" | "select";
interface FieldSpec {
  key: string;
  label: string;
  type: FieldType;
  options?: string[];
}

// Reused for every free-form nested list on the report (Persons Involved,
// Injury/Illness Detail, Sequence of Events, Notifications, Corrective
// Actions, Witness Statements) — these have no separate API, the whole
// report document is saved as one PUT, so this just edits local array
// state and hands the result back to the parent form.
function InlineListEditor({
  title,
  rows,
  fields,
  columns,
  onChange,
}: {
  title: string;
  rows: Row[];
  fields: FieldSpec[];
  columns: ColumnDef<Row & { _index: number }>[];
  onChange: (rows: Row[]) => void;
}) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [form, setForm] = useState<Row>({});

  const startAdd = () => {
    const initial: Row = {};
    fields.forEach((f) => (initial[f.key] = f.type === "checkbox" ? false : ""));
    setForm(initial);
    setEditingIndex(-1);
  };
  const startEdit = (idx: number) => {
    setForm({ ...rows[idx] });
    setEditingIndex(idx);
  };
  const cancel = () => setEditingIndex(null);
  const save = () => {
    if (editingIndex === -1) onChange([...rows, form]);
    else onChange(rows.map((r, i) => (i === editingIndex ? form : r)));
    cancel();
  };
  const remove = (idx: number) => onChange(rows.filter((_, i) => i !== idx));

  const indexedRows = rows.map((r, i) => ({ ...r, _index: i }));
  const allColumns: ColumnDef<Row & { _index: number }>[] = [
    ...columns,
    {
      key: "_actions",
      header: "",
      defaultWidth: 110,
      render: (r) => (
        <span style={{ display: "flex", gap: 6 }}>
          <button type="button" className="secondary" style={{ width: "auto", padding: "2px 8px" }} onClick={() => startEdit(r._index)}>
            Edit
          </button>
          <button type="button" className="secondary" style={{ width: "auto", padding: "2px 8px" }} onClick={() => remove(r._index)}>
            Remove
          </button>
        </span>
      ),
    },
  ];

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h4 style={{ margin: 0 }}>{title}</h4>
        <button type="button" className="secondary" style={{ width: "auto" }} onClick={startAdd}>
          + Add
        </button>
      </div>
      {editingIndex !== null && (
        <div className="detail-header" style={{ marginBottom: 10 }}>
          {fields.map((f) => (
            <div className="field" key={f.key}>
              <label>{f.label}</label>
              {f.type === "checkbox" ? (
                <input type="checkbox" checked={Boolean(form[f.key])} onChange={(e) => setForm((p) => ({ ...p, [f.key]: e.target.checked }))} />
              ) : f.type === "select" ? (
                <select value={String(form[f.key] ?? "")} onChange={(e) => setForm((p) => ({ ...p, [f.key]: e.target.value }))}>
                  <option value="" />
                  {f.options?.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : f.type === "textarea" ? (
                <textarea value={String(form[f.key] ?? "")} onChange={(e) => setForm((p) => ({ ...p, [f.key]: e.target.value }))} />
              ) : (
                <input value={String(form[f.key] ?? "")} onChange={(e) => setForm((p) => ({ ...p, [f.key]: e.target.value }))} />
              )}
            </div>
          ))}
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" style={{ width: "auto" }} onClick={save}>
              Save
            </button>
            <button type="button" className="secondary" style={{ width: "auto" }} onClick={cancel}>
              Cancel
            </button>
          </div>
        </div>
      )}
      <DataTable tableId={`iwi-list-${title}`} columns={allColumns} rows={indexedRows} rowKey={(r) => r._index} emptyMessage="None recorded yet." />
    </div>
  );
}

type Tab = "occurrence" | "classification" | "people" | "narrative" | "resolution";
const TABS: { key: Tab; label: string }[] = [
  { key: "occurrence", label: "Occurrence" },
  { key: "classification", label: "Classification" },
  { key: "people", label: "People & Events" },
  { key: "narrative", label: "Narrative & Analysis" },
  { key: "resolution", label: "Resolution" },
];

type FormState = {
  op_period: string;
  date_of_occurrence: string;
  day_of_event: string;
  time_of_occurrence: string;
  time_reported: string;
  reported_by: string;
  location_general: string;
  location_zone: string;
  location_sector: string;
  location_specific: string;
  incident_types: string[];
  incident_type_other: string;
  actual_outcome: string;
  actual_severity: string;
  activity_impact: string;
  activity_suspension_ref: string;
  conditions_weather: string;
  conditions_temp: string;
  conditions_wind: string;
  conditions_visibility: string;
  conditions_crowd_density: string;
  conditions_lighting: string;
  conditions_nws_warnings: string;
  conditions_other: string;
  persons_involved: Row[];
  injury_details: Row[];
  equipment_name: string;
  equipment_asset_id: string;
  equipment_owner: string;
  equipment_condition: string;
  sequence_of_events: Row[];
  narrative: string;
  factors_human: string;
  factors_environmental: string;
  factors_systems: string;
  factors_notes: string;
  immediate_actions: string;
  notifications: Row[];
  corrective_actions: Row[];
  escalation_decision: string;
  escalation_rationale: string;
  witnesses: Row[];
  prepared_by: string;
};

const EMPTY_FORM: FormState = {
  op_period: "",
  date_of_occurrence: "",
  day_of_event: "",
  time_of_occurrence: "",
  time_reported: "",
  reported_by: "",
  location_general: "",
  location_zone: "",
  location_sector: "",
  location_specific: "",
  incident_types: [],
  incident_type_other: "",
  actual_outcome: "",
  actual_severity: "",
  activity_impact: "",
  activity_suspension_ref: "",
  conditions_weather: "",
  conditions_temp: "",
  conditions_wind: "",
  conditions_visibility: "",
  conditions_crowd_density: "",
  conditions_lighting: "",
  conditions_nws_warnings: "",
  conditions_other: "",
  persons_involved: [],
  injury_details: [],
  equipment_name: "",
  equipment_asset_id: "",
  equipment_owner: "",
  equipment_condition: "",
  sequence_of_events: [],
  narrative: "",
  factors_human: "",
  factors_environmental: "",
  factors_systems: "",
  factors_notes: "",
  immediate_actions: "",
  notifications: [],
  corrective_actions: [],
  escalation_decision: "",
  escalation_rationale: "",
  witnesses: [],
  prepared_by: "",
};

const ACTUAL_OUTCOMES = [
  "No contact / no harm — hazard only",
  "First aid treated on scene",
  "Medical treatment required (beyond first aid)",
  "Hospitalization",
  "Fatality",
  "Property / equipment damage only",
  "Operational disruption (no injury)",
];
const ACTIVITY_IMPACTS = ["No operational impact", "Brief disruption", "Partial suspension", "Full suspension", "Event termination"];
const ESCALATION_DECISIONS = [
  "No escalation — monitor situation",
  "Increased monitoring required",
  "Activity suspension ref issued",
  "Partial suspension ordered",
  "Full suspension ordered",
];

export default function IwiDetailPage() {
  const { reportId } = useParams();
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("occurrence");
  const { data: report, isLoading, error } = useIwiReport(incidentId!, reportId!);
  const update = useUpdateIwiReport(incidentId!);
  const signoff = useSignoffIwiReport(incidentId!);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!report) return;
    const conditions = (report.conditions ?? {}) as Record<string, string>;
    const equipment = (report.equipment ?? {}) as Record<string, string>;
    const factors = (report.contributing_factors ?? {}) as { human?: string[]; environmental?: string[]; systems?: string[]; notes?: string };
    setForm({
      op_period: report.op_period != null ? String(report.op_period) : "",
      date_of_occurrence: report.date_of_occurrence ?? "",
      day_of_event: report.day_of_event != null ? String(report.day_of_event) : "",
      time_of_occurrence: report.time_of_occurrence ?? "",
      time_reported: report.time_reported ?? "",
      reported_by: report.reported_by ?? "",
      location_general: report.location_general ?? "",
      location_zone: report.location_zone ?? "",
      location_sector: report.location_sector ?? "",
      location_specific: report.location_specific ?? "",
      incident_types: report.incident_types ?? [],
      incident_type_other: report.incident_type_other ?? "",
      actual_outcome: report.actual_outcome ?? "",
      actual_severity: report.actual_severity ?? "",
      activity_impact: report.activity_impact ?? "",
      activity_suspension_ref: report.activity_suspension_ref ?? "",
      conditions_weather: conditions.weather ?? "",
      conditions_temp: conditions.temp_heat_index ?? "",
      conditions_wind: conditions.wind ?? "",
      conditions_visibility: conditions.visibility ?? "",
      conditions_crowd_density: conditions.crowd_density ?? "",
      conditions_lighting: conditions.lighting ?? "",
      conditions_nws_warnings: conditions.nws_warnings ?? "",
      conditions_other: conditions.other ?? "",
      persons_involved: report.persons_involved ?? [],
      injury_details: report.injury_details ?? [],
      equipment_name: equipment.name ?? "",
      equipment_asset_id: equipment.asset_id ?? "",
      equipment_owner: equipment.owner ?? "",
      equipment_condition: equipment.condition ?? "",
      sequence_of_events: report.sequence_of_events ?? [],
      narrative: report.narrative ?? "",
      factors_human: (factors.human ?? []).join(", "),
      factors_environmental: (factors.environmental ?? []).join(", "),
      factors_systems: (factors.systems ?? []).join(", "),
      factors_notes: factors.notes ?? "",
      immediate_actions: report.immediate_actions ?? "",
      notifications: report.notifications ?? [],
      corrective_actions: report.corrective_actions ?? [],
      escalation_decision: report.escalation_decision ?? "",
      escalation_rationale: report.escalation_rationale ?? "",
      witnesses: report.witnesses ?? [],
      prepared_by: report.prepared_by ?? "",
    });
    setSaved(false);
  }, [report]);

  if (!incidentId || !reportId) return null;
  if (isLoading) return <p>Loading…</p>;
  if (error || !report) return <p className="error">Could not load this IWI report.</p>;

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const toggleIncidentType = (type: string) => {
    set("incident_types", form.incident_types.includes(type) ? form.incident_types.filter((t) => t !== type) : [...form.incident_types, type]);
  };

  const onSave = () => {
    const body = {
      op_period: form.op_period ? Number(form.op_period) : null,
      date_of_occurrence: form.date_of_occurrence || null,
      day_of_event: form.day_of_event ? Number(form.day_of_event) : null,
      time_of_occurrence: form.time_of_occurrence || null,
      time_reported: form.time_reported || null,
      reported_by: form.reported_by || null,
      location_general: form.location_general || null,
      location_zone: form.location_zone || null,
      location_sector: form.location_sector || null,
      location_specific: form.location_specific || null,
      incident_types: form.incident_types,
      incident_type_other: form.incident_type_other || null,
      actual_outcome: form.actual_outcome || null,
      actual_severity: form.actual_severity || null,
      activity_impact: form.activity_impact || null,
      activity_suspension_ref: form.activity_suspension_ref || null,
      conditions: {
        weather: form.conditions_weather,
        temp_heat_index: form.conditions_temp,
        wind: form.conditions_wind,
        visibility: form.conditions_visibility,
        crowd_density: form.conditions_crowd_density,
        lighting: form.conditions_lighting,
        nws_warnings: form.conditions_nws_warnings,
        other: form.conditions_other,
      },
      persons_involved: form.persons_involved,
      injury_details: form.injury_details,
      equipment: { name: form.equipment_name, asset_id: form.equipment_asset_id, owner: form.equipment_owner, condition: form.equipment_condition },
      sequence_of_events: form.sequence_of_events,
      narrative: form.narrative || null,
      contributing_factors: {
        human: form.factors_human.split(",").map((s) => s.trim()).filter(Boolean),
        environmental: form.factors_environmental.split(",").map((s) => s.trim()).filter(Boolean),
        systems: form.factors_systems.split(",").map((s) => s.trim()).filter(Boolean),
        notes: form.factors_notes,
      },
      immediate_actions: form.immediate_actions || null,
      notifications: form.notifications,
      corrective_actions: form.corrective_actions,
      escalation_decision: form.escalation_decision || null,
      escalation_rationale: form.escalation_rationale || null,
      witnesses: form.witnesses,
      prepared_by: form.prepared_by || null,
    };
    update.mutate({ reportId, body }, { onSuccess: () => setSaved(true) });
  };

  const doSignoff = (role: string) => {
    signoff.mutate({ reportId, role, name: user?.display_name || user?.username || "" });
  };

  return (
    <div className="detail-page">
      <button className="secondary" style={{ width: "auto", marginBottom: 12 }} onClick={() => navigate("/safety/iwi")}>
        ← IWI Dashboard
      </button>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
        <h2 style={{ margin: 0 }}>
          IWI-{String(report.form_number).padStart(3, "0")} — Status: {report.status}
        </h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" style={{ width: "auto" }} disabled={update.isPending} onClick={onSave}>
            {update.isPending ? "Saving…" : "Save"}
          </button>
          {saved && <span className="muted">Saved.</span>}
        </div>
      </div>

      <div className="detail-tabs" style={{ marginTop: 12, marginBottom: 16 }}>
        {TABS.map((t) => (
          <button key={t.key} className={`detail-tab ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "occurrence" && (
        <div className="detail-header">
          <div className="field"><label>Op. Period</label><input type="number" min={1} value={form.op_period} onChange={(e) => set("op_period", e.target.value)} /></div>
          <div className="field"><label>Day of Event</label><input type="number" min={1} value={form.day_of_event} onChange={(e) => set("day_of_event", e.target.value)} /></div>
          <div className="field"><label>Date of Occurrence</label><input value={form.date_of_occurrence} onChange={(e) => set("date_of_occurrence", e.target.value)} /></div>
          <div className="field"><label>Time of Occurrence</label><input value={form.time_of_occurrence} onChange={(e) => set("time_of_occurrence", e.target.value)} /></div>
          <div className="field"><label>Time Reported</label><input value={form.time_reported} onChange={(e) => set("time_reported", e.target.value)} /></div>
          <div className="field"><label>Reported By</label><input value={form.reported_by} onChange={(e) => set("reported_by", e.target.value)} /></div>
          <div className="field"><label>General Location</label><input value={form.location_general} onChange={(e) => set("location_general", e.target.value)} /></div>
          <div className="field"><label>Zone / Division</label><input value={form.location_zone} onChange={(e) => set("location_zone", e.target.value)} /></div>
          <div className="field"><label>Sector / Post</label><input value={form.location_sector} onChange={(e) => set("location_sector", e.target.value)} /></div>
          <div className="field"><label>Specific Location</label><input value={form.location_specific} onChange={(e) => set("location_specific", e.target.value)} /></div>
        </div>
      )}

      {tab === "classification" && (
        <div>
          <h4>Incident Type</h4>
          {IWI_INCIDENT_TYPES.map((t) => (
            <label key={t} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <input type="checkbox" checked={form.incident_types.includes(t)} onChange={() => toggleIncidentType(t)} />
              {t}
            </label>
          ))}
          <div className="field"><label>Other</label><input value={form.incident_type_other} onChange={(e) => set("incident_type_other", e.target.value)} /></div>

          <div className="detail-header" style={{ marginTop: 14 }}>
            <div className="field">
              <label>Actual Outcome</label>
              <select value={form.actual_outcome} onChange={(e) => set("actual_outcome", e.target.value)}>
                <option value="" />
                {ACTUAL_OUTCOMES.map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Activity Impact</label>
              <select value={form.activity_impact} onChange={(e) => set("activity_impact", e.target.value)}>
                <option value="" />
                {ACTIVITY_IMPACTS.map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </div>
            <div className="field"><label>Activity Suspension Ref</label><input value={form.activity_suspension_ref} onChange={(e) => set("activity_suspension_ref", e.target.value)} /></div>
          </div>

          <div className="field">
            <label>Actual Severity</label>
            <div className="detail-tabs">
              {IWI_SEVERITIES.map((s) => (
                <button key={s} className={`detail-tab ${form.actual_severity === s ? "active" : ""}`} onClick={() => set("actual_severity", s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>

          <h4 style={{ marginTop: 14 }}>Conditions</h4>
          <div className="detail-header">
            <div className="field"><label>Weather</label><input value={form.conditions_weather} onChange={(e) => set("conditions_weather", e.target.value)} /></div>
            <div className="field"><label>Temp / Heat Index</label><input value={form.conditions_temp} onChange={(e) => set("conditions_temp", e.target.value)} /></div>
            <div className="field"><label>Wind Speed / Direction</label><input value={form.conditions_wind} onChange={(e) => set("conditions_wind", e.target.value)} /></div>
            <div className="field"><label>Visibility</label><input value={form.conditions_visibility} onChange={(e) => set("conditions_visibility", e.target.value)} /></div>
            <div className="field"><label>Crowd Density</label><input value={form.conditions_crowd_density} onChange={(e) => set("conditions_crowd_density", e.target.value)} /></div>
            <div className="field"><label>Lighting Conditions</label><input value={form.conditions_lighting} onChange={(e) => set("conditions_lighting", e.target.value)} /></div>
            <div className="field"><label>Active NWS Warnings</label><input value={form.conditions_nws_warnings} onChange={(e) => set("conditions_nws_warnings", e.target.value)} /></div>
            <div className="field"><label>Other Relevant Conditions</label><input value={form.conditions_other} onChange={(e) => set("conditions_other", e.target.value)} /></div>
          </div>
        </div>
      )}

      {tab === "people" && (
        <div>
          <InlineListEditor
            title="Persons Involved"
            rows={form.persons_involved}
            onChange={(rows) => set("persons_involved", rows)}
            fields={[
              { key: "name", label: "Name", type: "text" },
              { key: "role", label: "Role / ICS Position", type: "text" },
              { key: "agency", label: "Agency", type: "text" },
              { key: "contact", label: "Contact", type: "text" },
              { key: "injury_illness", label: "Injury / Illness", type: "checkbox" },
              { key: "disposition", label: "Disposition", type: "text" },
            ]}
            columns={[
              { key: "name", header: "Name", defaultWidth: 140 },
              { key: "role", header: "Role / ICS Position", defaultWidth: 160 },
              { key: "agency", header: "Agency", defaultWidth: 120 },
              { key: "contact", header: "Contact", defaultWidth: 120 },
              { key: "injury_illness", header: "Injury/Illness", defaultWidth: 100, render: (r) => (r.injury_illness ? "Yes" : "No") },
              { key: "disposition", header: "Disposition", defaultWidth: 160 },
            ]}
          />
          <InlineListEditor
            title="Injury / Illness Detail"
            rows={form.injury_details}
            onChange={(rows) => set("injury_details", rows)}
            fields={[
              { key: "person", label: "Person", type: "text" },
              { key: "nature", label: "Nature", type: "text" },
              { key: "body_part", label: "Body Part", type: "text" },
              { key: "treatment", label: "Treatment Rendered", type: "textarea" },
              { key: "ems_involved", label: "EMS/Hospital Involved", type: "checkbox" },
            ]}
            columns={[
              { key: "person", header: "Person", defaultWidth: 140 },
              { key: "nature", header: "Nature", defaultWidth: 160 },
              { key: "body_part", header: "Body Part", defaultWidth: 120 },
              { key: "treatment", header: "Treatment", defaultWidth: 200 },
              { key: "ems_involved", header: "EMS?", defaultWidth: 80, render: (r) => (r.ems_involved ? "Yes" : "No") },
            ]}
          />

          <h4>Equipment / Asset</h4>
          <div className="detail-header" style={{ marginBottom: 16 }}>
            <div className="field"><label>Equipment / Asset</label><input value={form.equipment_name} onChange={(e) => set("equipment_name", e.target.value)} /></div>
            <div className="field"><label>Asset ID / Tag #</label><input value={form.equipment_asset_id} onChange={(e) => set("equipment_asset_id", e.target.value)} /></div>
            <div className="field"><label>Owner / Operator</label><input value={form.equipment_owner} onChange={(e) => set("equipment_owner", e.target.value)} /></div>
            <div className="field"><label>Condition at Incident</label><input value={form.equipment_condition} onChange={(e) => set("equipment_condition", e.target.value)} /></div>
          </div>

          <InlineListEditor
            title="Sequence of Events"
            rows={form.sequence_of_events}
            onChange={(rows) => set("sequence_of_events", rows)}
            fields={[
              { key: "time", label: "Time", type: "text" },
              { key: "event", label: "Event / Action", type: "textarea" },
            ]}
            columns={[
              { key: "time", header: "Time", defaultWidth: 100 },
              { key: "event", header: "Event / Action", defaultWidth: 320 },
            ]}
          />
        </div>
      )}

      {tab === "narrative" && (
        <div>
          <div className="field">
            <label>Incident Narrative</label>
            <textarea rows={4} value={form.narrative} onChange={(e) => set("narrative", e.target.value)} />
          </div>

          <h4>Contributing Factors</h4>
          <div className="detail-header">
            <div className="field"><label>Human (comma-separated)</label><input value={form.factors_human} onChange={(e) => set("factors_human", e.target.value)} /></div>
            <div className="field"><label>Environmental / Physical (comma-separated)</label><input value={form.factors_environmental} onChange={(e) => set("factors_environmental", e.target.value)} /></div>
            <div className="field"><label>Systems / Organizational (comma-separated)</label><input value={form.factors_systems} onChange={(e) => set("factors_systems", e.target.value)} /></div>
            <div className="field" style={{ gridColumn: "1 / -1" }}><label>Factor Notes</label><textarea value={form.factors_notes} onChange={(e) => set("factors_notes", e.target.value)} /></div>
          </div>

          <div className="field">
            <label>Immediate Actions</label>
            <textarea rows={2} value={form.immediate_actions} onChange={(e) => set("immediate_actions", e.target.value)} />
          </div>

          <InlineListEditor
            title="Notifications"
            rows={form.notifications}
            onChange={(rows) => set("notifications", rows)}
            fields={[
              { key: "role", label: "Role", type: "text" },
              { key: "notified", label: "Notified", type: "checkbox" },
              { key: "time", label: "Time", type: "text" },
            ]}
            columns={[
              { key: "role", header: "Role", defaultWidth: 200 },
              { key: "notified", header: "Notified", defaultWidth: 100, render: (r) => (r.notified ? "Yes" : "No") },
              { key: "time", header: "Time", defaultWidth: 100 },
            ]}
          />

          <InlineListEditor
            title="Witness Statements"
            rows={form.witnesses}
            onChange={(rows) => set("witnesses", rows)}
            fields={[
              { key: "name", label: "Full Name", type: "text" },
              { key: "role", label: "Position / Role", type: "text" },
              { key: "agency", label: "Agency", type: "text" },
              { key: "contact", label: "Cell / Contact", type: "text" },
              { key: "statement", label: "Statement", type: "textarea" },
            ]}
            columns={[
              { key: "name", header: "Name", defaultWidth: 140 },
              { key: "role", header: "Role", defaultWidth: 140 },
              { key: "agency", header: "Agency", defaultWidth: 120 },
              { key: "statement", header: "Statement", defaultWidth: 280 },
            ]}
          />
        </div>
      )}

      {tab === "resolution" && (
        <div>
          <InlineListEditor
            title="Corrective Actions"
            rows={form.corrective_actions}
            onChange={(rows) => set("corrective_actions", rows)}
            fields={[
              { key: "action", label: "Recommended Action", type: "textarea" },
              { key: "assigned_to", label: "Assigned To", type: "text" },
              { key: "due_date", label: "Due Date", type: "text" },
              { key: "status", label: "Status", type: "select", options: ["Open", "Done"] },
            ]}
            columns={[
              { key: "action", header: "Recommended Action", defaultWidth: 260 },
              { key: "assigned_to", header: "Assigned To", defaultWidth: 160 },
              { key: "due_date", header: "Due Date", defaultWidth: 110 },
              { key: "status", header: "Status", defaultWidth: 90 },
            ]}
          />

          <div className="detail-header">
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <label>Escalation Decision</label>
              <select value={form.escalation_decision} onChange={(e) => set("escalation_decision", e.target.value)}>
                <option value="" />
                {ESCALATION_DECISIONS.map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </div>
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <label>Rationale</label>
              <textarea value={form.escalation_rationale} onChange={(e) => set("escalation_rationale", e.target.value)} />
            </div>
          </div>

          <h4>Command Review &amp; Sign-offs</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
            {(["reporter", "supervisor", "ops_chief", "ic", "safety_officer"] as const).map((role) => {
              const entry = report.signoffs?.[role];
              return (
                <div key={role} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <strong style={{ minWidth: 160, textTransform: "capitalize" }}>{role.replace("_", " ")}</strong>
                  {entry ? (
                    <span className="muted">{entry.name} — signed {entry.signed_at}</span>
                  ) : (
                    <button type="button" className="secondary" style={{ width: "auto" }} disabled={signoff.isPending} onClick={() => doSignoff(role)}>
                      Sign
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          <div className="field">
            <label>Prepared By</label>
            <input value={form.prepared_by} onChange={(e) => set("prepared_by", e.target.value)} />
          </div>
        </div>
      )}
    </div>
  );
}
