import { useMemo, useState } from "react";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import StatusPill from "../../components/table/StatusPill";
import type { MedicalPlanTable } from "../../api/types";
import {
  useAddMedicalAidStation,
  useAddMedicalPlanRow,
  useCreateMedicalPlanVersion,
  useDeleteMedicalAidStation,
  useDeleteMedicalPlanRow,
  useDuplicateMedicalPlanLastOp,
  useImportMedicalAidStations,
  useImportMedicalPlanTable,
  useMedicalAidStations,
  useMedicalPlan,
  useMedicalPlanVersions,
  useSaveMedicalPlanProcedures,
  useSubmitMedicalPlanForApproval,
  useUpdateMedicalAidStation,
  useUpdateMedicalPlanRow,
} from "./hooks";
import * as api from "../../api/endpoints";

type FieldType = "text" | "number" | "checkbox" | "select";
interface FieldSpec {
  key: string;
  label: string;
  type: FieldType;
  options?: string[];
}
type Row = Record<string, unknown>;

// One row-form + table, reused for the four plan tables (ambulance services,
// hospitals, air ambulance, medical comms) and aid stations — same shape as
// desktop's per-section Add/Edit dialogs in ics206_widget.py, just inline
// instead of a popup.
function PlanTableSection({
  title,
  rows,
  fields,
  columns,
  disabled,
  onAdd,
  onUpdate,
  onDelete,
  onImport,
  importLabel,
}: {
  title: string;
  rows: Row[];
  fields: FieldSpec[];
  columns: ColumnDef<Row>[];
  disabled: boolean;
  onAdd: (body: Row) => void;
  onUpdate: (id: number, body: Row) => void;
  onDelete: (id: number) => void;
  onImport?: () => void;
  importLabel?: string;
}) {
  const [editing, setEditing] = useState<Row | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState<Row>({});

  const startAdd = () => {
    const initial: Row = {};
    fields.forEach((f) => (initial[f.key] = f.type === "checkbox" ? false : ""));
    setForm(initial);
    setIsNew(true);
    setEditing({});
  };
  const startEdit = (row: Row) => {
    setForm({ ...row });
    setIsNew(false);
    setEditing(row);
  };
  const cancel = () => {
    setEditing(null);
    setForm({});
  };
  const save = () => {
    if (isNew) onAdd(form);
    else onUpdate(Number(editing!.id), form);
    cancel();
  };

  const actionColumn: ColumnDef<Row> = {
    key: "_actions",
    header: "",
    defaultWidth: 110,
    render: (row) =>
      disabled ? null : (
        <span style={{ display: "flex", gap: 6 }}>
          <button type="button" className="secondary" style={{ width: "auto", padding: "2px 8px" }} onClick={() => startEdit(row)}>
            Edit
          </button>
          <button type="button" className="secondary" style={{ width: "auto", padding: "2px 8px" }} onClick={() => onDelete(Number(row.id))}>
            Remove
          </button>
        </span>
      ),
  };

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        {!disabled && (
          <div style={{ display: "flex", gap: 8 }}>
            {onImport && (
              <button type="button" className="secondary" style={{ width: "auto" }} onClick={onImport}>
                {importLabel ?? "Import from Master"}
              </button>
            )}
            <button type="button" className="secondary" style={{ width: "auto" }} onClick={startAdd}>
              + Add
            </button>
          </div>
        )}
      </div>

      {editing !== null && (
        <div className="detail-header" style={{ marginBottom: 12 }}>
          {fields.map((f) => (
            <div className="field" key={f.key}>
              <label>{f.label}</label>
              {f.type === "checkbox" ? (
                <input
                  type="checkbox"
                  checked={Boolean(form[f.key])}
                  onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.checked }))}
                />
              ) : f.type === "select" ? (
                <select value={String(form[f.key] ?? "")} onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}>
                  <option value="" />
                  {f.options?.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type={f.type === "number" ? "number" : "text"}
                  value={String(form[f.key] ?? "")}
                  onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: f.type === "number" ? Number(e.target.value) : e.target.value }))}
                />
              )}
            </div>
          ))}
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
            <button type="button" style={{ width: "auto" }} onClick={save}>
              Save
            </button>
            <button type="button" className="secondary" style={{ width: "auto" }} onClick={cancel}>
              Cancel
            </button>
          </div>
        </div>
      )}

      <DataTable tableId={`ics206-${title}`} columns={disabled ? columns : [...columns, actionColumn]} rows={rows} rowKey={(r) => Number(r.id)} emptyMessage="None recorded yet." />
    </div>
  );
}

export default function Ics206BuilderPage() {
  const { incidentId, personnel } = useSession();
  const [op, setOp] = useState(1);
  const [version, setVersion] = useState<number | undefined>(undefined);
  const [changeNote, setChangeNote] = useState("");

  const { data: plan, isLoading, error } = useMedicalPlan(incidentId!, op, version);
  const { data: versions = [] } = useMedicalPlanVersions(incidentId!, op);
  const { data: aidStations = [] } = useMedicalAidStations(incidentId!, op, version);

  const addRow = useAddMedicalPlanRow(incidentId!);
  const updateRow = useUpdateMedicalPlanRow(incidentId!);
  const deleteRow = useDeleteMedicalPlanRow(incidentId!);
  const importTable = useImportMedicalPlanTable(incidentId!);
  const addAidStation = useAddMedicalAidStation(incidentId!);
  const updateAidStation = useUpdateMedicalAidStation(incidentId!);
  const deleteAidStation = useDeleteMedicalAidStation(incidentId!);
  const importAidStations = useImportMedicalAidStations(incidentId!);
  const createVersion = useCreateMedicalPlanVersion(incidentId!);
  const duplicateLastOp = useDuplicateMedicalPlanLastOp(incidentId!);
  const saveProcedures = useSaveMedicalPlanProcedures(incidentId!);
  const submitForApproval = useSubmitMedicalPlanForApproval(incidentId!);

  const person = useMemo(
    () => ({ name: personnel?.name ?? "", personnel_id: personnel?.person_record ?? null, position: personnel?.primary_role ?? "" }),
    [personnel]
  );

  if (!incidentId) return null;
  if (isLoading) return <p>Loading medical plan…</p>;
  if (error || !plan) return <p className="error">Could not load the medical plan for OP {op}.</p>;

  const locked = plan.approval_status !== "not_started";
  const effectiveVersion = version ?? plan.version;

  const approve = async (outcome: "approved" | "rejected") => {
    await api.applyMedicalPlanApproval(incidentId, op, effectiveVersion, outcome, person);
    window.location.reload();
  };

  const withTable = (table: MedicalPlanTable, body: Row) => addRow.mutate({ table, op, version: effectiveVersion, body });
  const withUpdate = (table: MedicalPlanTable, id: number, body: Row) => updateRow.mutate({ table, rowId: id, op, version: effectiveVersion, body });
  const withDelete = (table: MedicalPlanTable, id: number) => deleteRow.mutate({ table, rowId: id, op, version: effectiveVersion });

  return (
    <div className="detail-page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12, marginBottom: 12 }}>
        <div>
          <h2 style={{ margin: 0 }}>ICS 206 — Medical Plan</h2>
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 6 }}>
            <label className="field" style={{ margin: 0, flexDirection: "row", alignItems: "center", gap: 6 }}>
              Op. Period
              <input type="number" min={1} step={1} value={op} onChange={(e) => { setOp(Math.max(1, Number(e.target.value) || 1)); setVersion(undefined); }} style={{ width: 70 }} />
            </label>
            <select value={version ?? plan.version} onChange={(e) => setVersion(Number(e.target.value))}>
              {versions.map((v) => (
                <option key={v.version} value={v.version}>
                  v{v.version} — {v.approval_status}
                </option>
              ))}
            </select>
            <StatusPill domain="approval" statusKey={plan.approval_status} label={plan.approval_status} />
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input
            placeholder="Change note for new version…"
            value={changeNote}
            onChange={(e) => setChangeNote(e.target.value)}
            style={{ width: 200 }}
          />
          <button
            type="button"
            className="secondary"
            style={{ width: "auto" }}
            disabled={createVersion.isPending}
            onClick={() => createVersion.mutate({ op, version: effectiveVersion, changeNote, person }, { onSuccess: (r) => { setVersion(r.version); setChangeNote(""); } })}
          >
            New Version…
          </button>
          <button
            type="button"
            className="secondary"
            style={{ width: "auto" }}
            disabled={duplicateLastOp.isPending || locked}
            onClick={() => duplicateLastOp.mutate({ op, version: effectiveVersion, person })}
          >
            Copy from Previous OP
          </button>
          {!locked && (
            <button type="button" style={{ width: "auto" }} disabled={submitForApproval.isPending} onClick={() => submitForApproval.mutate({ op, version: effectiveVersion })}>
              Submit for Approval…
            </button>
          )}
          {plan.approval_status === "pending" && (
            <>
              <button type="button" style={{ width: "auto" }} onClick={() => approve("approved")}>
                Approve
              </button>
              <button type="button" className="secondary" style={{ width: "auto" }} onClick={() => approve("rejected")}>
                Reject
              </button>
            </>
          )}
        </div>
      </div>
      {locked && (
        <p className="muted" style={{ marginTop: -4 }}>
          Version {effectiveVersion} is {plan.approval_status} and locked — start a new version to make changes.
        </p>
      )}

      <PlanTableSection
        title="Aid Stations"
        disabled={locked}
        rows={aidStations as unknown as Row[]}
        fields={[
          { key: "name", label: "Name", type: "text" },
          { key: "type", label: "Type", type: "select", options: ["Medical Aid", "BLS", "ALS", "Paramedic", "Other"] },
          { key: "level", label: "Level", type: "text" },
          { key: "contact_frequency", label: "Contact / Frequency", type: "text" },
          { key: "is_24_7", label: "24/7", type: "checkbox" },
          { key: "location_text", label: "Location", type: "text" },
          { key: "manager_name", label: "Manager", type: "text" },
          { key: "notes", label: "Notes", type: "text" },
        ]}
        columns={[
          { key: "name", header: "Name", defaultWidth: 180 },
          { key: "location_text", header: "Facility / Location", defaultWidth: 180 },
          { key: "contact_frequency", header: "Contact / Frequency", defaultWidth: 140 },
          { key: "type", header: "Type", defaultWidth: 100 },
          { key: "level", header: "Level", defaultWidth: 80 },
          { key: "is_24_7", header: "24/7", defaultWidth: 60, render: (r) => (r.is_24_7 ? "Yes" : "No") },
          { key: "manager_name", header: "Manager", defaultWidth: 120 },
          { key: "notes", header: "Notes", defaultWidth: 160 },
        ]}
        onAdd={(body) => addAidStation.mutate({ op, version: effectiveVersion, body })}
        onUpdate={(id, body) => updateAidStation.mutate({ rowId: id, op, version: effectiveVersion, body })}
        onDelete={(id) => deleteAidStation.mutate({ rowId: id, op, version: effectiveVersion })}
        onImport={() => importAidStations.mutate({ op, version: effectiveVersion })}
      />

      <PlanTableSection
        title="Ambulance Services"
        disabled={locked}
        rows={plan.ambulance_services as unknown as Row[]}
        fields={[
          { key: "name", label: "Name", type: "text" },
          { key: "type", label: "Type", type: "select", options: ["Ground BLS", "Ground ALS", "Air", "Other"] },
          { key: "phone", label: "Phone", type: "text" },
          { key: "location", label: "Location", type: "text" },
          { key: "notes", label: "Notes", type: "text" },
        ]}
        columns={[
          { key: "name", header: "Name", defaultWidth: 180 },
          { key: "type", header: "Type", defaultWidth: 120 },
          { key: "phone", header: "Phone", defaultWidth: 120 },
          { key: "location", header: "Location", defaultWidth: 160 },
          { key: "notes", header: "Notes", defaultWidth: 160 },
        ]}
        onAdd={(body) => withTable("ambulance_services", body)}
        onUpdate={(id, body) => withUpdate("ambulance_services", id, body)}
        onDelete={(id) => withDelete("ambulance_services", id)}
        onImport={() => importTable.mutate({ table: "ambulance_services", op, version: effectiveVersion })}
      />

      <PlanTableSection
        title="Hospitals"
        disabled={locked}
        rows={plan.hospitals as unknown as Row[]}
        fields={[
          { key: "name", label: "Name", type: "text" },
          { key: "address", label: "Address", type: "text" },
          { key: "phone", label: "Phone", type: "text" },
          { key: "helipad", label: "Helipad", type: "checkbox" },
          { key: "burn_center", label: "Burn Center", type: "checkbox" },
          { key: "level", label: "Trauma Level", type: "select", options: ["I", "II", "III", "IV", "None"] },
          { key: "lat", label: "Latitude", type: "number" },
          { key: "lon", label: "Longitude", type: "number" },
          { key: "travel_time_ground_min", label: "Ground Travel (min)", type: "number" },
          { key: "travel_time_air_min", label: "Air Travel (min)", type: "number" },
          { key: "notes", label: "Notes", type: "text" },
        ]}
        columns={[
          { key: "name", header: "Name", defaultWidth: 180 },
          { key: "address", header: "Address", defaultWidth: 160 },
          { key: "phone", header: "Phone", defaultWidth: 120 },
          { key: "helipad", header: "Helipad", defaultWidth: 70, render: (r) => (r.helipad ? "Yes" : "No") },
          { key: "burn_center", header: "Burn Ctr", defaultWidth: 80, render: (r) => (r.burn_center ? "Yes" : "No") },
          { key: "level", header: "Trauma Level", defaultWidth: 100 },
          { key: "travel_time_ground_min", header: "Ground", defaultWidth: 80, render: (r) => (r.travel_time_ground_min != null ? `${r.travel_time_ground_min} min` : "—") },
          { key: "travel_time_air_min", header: "Air", defaultWidth: 80, render: (r) => (r.travel_time_air_min != null ? `${r.travel_time_air_min} min` : "—") },
          { key: "notes", header: "Notes", defaultWidth: 140 },
        ]}
        onAdd={(body) => withTable("hospitals", body)}
        onUpdate={(id, body) => withUpdate("hospitals", id, body)}
        onDelete={(id) => withDelete("hospitals", id)}
        onImport={() => importTable.mutate({ table: "hospitals", op, version: effectiveVersion })}
      />

      <PlanTableSection
        title="Air Ambulance / MedEvac"
        disabled={locked}
        rows={plan.air_ambulance as unknown as Row[]}
        fields={[
          { key: "name", label: "Name", type: "text" },
          { key: "phone", label: "Phone", type: "text" },
          { key: "base", label: "Base", type: "text" },
          { key: "contact", label: "Contact", type: "text" },
          { key: "notes", label: "Notes", type: "text" },
        ]}
        columns={[
          { key: "name", header: "Name", defaultWidth: 180 },
          { key: "phone", header: "Phone", defaultWidth: 120 },
          { key: "base", header: "Base", defaultWidth: 160 },
          { key: "contact", header: "Contact", defaultWidth: 140 },
          { key: "notes", header: "Notes", defaultWidth: 160 },
        ]}
        onAdd={(body) => withTable("air_ambulance", body)}
        onUpdate={(id, body) => withUpdate("air_ambulance", id, body)}
        onDelete={(id) => withDelete("air_ambulance", id)}
      />

      <PlanTableSection
        title="Medical Communications"
        disabled={locked}
        rows={plan.medical_comms as unknown as Row[]}
        fields={[
          { key: "channel", label: "Channel", type: "text" },
          { key: "function", label: "Function", type: "text" },
          { key: "frequency", label: "Frequency", type: "text" },
          { key: "mode", label: "Mode", type: "select", options: ["Analog", "Digital", "Mixed"] },
          { key: "notes", label: "Notes", type: "text" },
        ]}
        columns={[
          { key: "channel", header: "Channel", defaultWidth: 140 },
          { key: "function", header: "Function", defaultWidth: 140 },
          { key: "frequency", header: "Frequency", defaultWidth: 120 },
          { key: "mode", header: "Mode", defaultWidth: 100 },
          { key: "notes", header: "Notes", defaultWidth: 160 },
        ]}
        onAdd={(body) => withTable("medical_comms", body)}
        onUpdate={(id, body) => withUpdate("medical_comms", id, body)}
        onDelete={(id) => withDelete("medical_comms", id)}
      />

      <div style={{ marginBottom: 24 }}>
        <h3>Medical Emergency Procedures</h3>
        <textarea
          defaultValue={plan.procedures?.content ?? ""}
          disabled={locked}
          rows={5}
          style={{ width: "100%" }}
          onBlur={(e) => saveProcedures.mutate({ op, version: effectiveVersion, content: e.target.value })}
        />
      </div>

      <div style={{ marginBottom: 24 }}>
        <h3>Prepared By / Approved By</h3>
        <div className="detail-header">
          <div className="field"><label>Prepared By</label><input readOnly value={plan.signatures?.prepared_by || "—"} /></div>
          <div className="field"><label>Position</label><input readOnly value={plan.signatures?.position || "—"} /></div>
          <div className="field"><label>Prepared At</label><input readOnly value={plan.signatures?.prepared_at || "—"} /></div>
          <div className="field"><label>Approved By</label><input readOnly value={plan.signatures?.approved_by || "— pending —"} /></div>
          <div className="field"><label>Position</label><input readOnly value={plan.signatures?.approved_by_position || "—"} /></div>
          <div className="field"><label>Approved At</label><input readOnly value={plan.signatures?.approved_at || "—"} /></div>
        </div>
      </div>

      <div>
        <h3>Version History</h3>
        <DataTable
          tableId="ics206-versions"
          columns={[
            { key: "version", header: "Version", defaultWidth: 80, render: (v) => `v${v.version}` },
            { key: "approval_status", header: "Status", defaultWidth: 100 },
            { key: "prepared_by", header: "Prepared By", defaultWidth: 140 },
            { key: "prepared_at", header: "Prepared", defaultWidth: 140 },
            { key: "approved_by", header: "Approved By", defaultWidth: 140 },
            { key: "approved_at", header: "Approved", defaultWidth: 140 },
            { key: "change_note", header: "Change Note", defaultWidth: 220 },
          ]}
          rows={versions as unknown as Row[]}
          rowKey={(r) => Number(r.version)}
          onRowActivate={(r) => setVersion(Number(r.version))}
          emptyMessage="No versions yet."
        />
      </div>
    </div>
  );
}
