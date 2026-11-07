import { useEffect, useState } from "react";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import type { CapOrmHazard, CapOrmRiskLevel } from "../../api/types";
import {
  useApproveCapOrmForm,
  useCapOrmForm,
  useCapOrmHazards,
  useCreateCapOrmHazard,
  useDeleteCapOrmHazard,
  useSaveCapOrmForm,
  useUpdateCapOrmHazard,
} from "./hooks";

const RISK_LABELS: Record<CapOrmRiskLevel, string> = { L: "Low", M: "Medium", H: "High", EH: "Extremely High" };
const RISK_LEVELS: CapOrmRiskLevel[] = ["L", "M", "H", "EH"];

type HazardRowForm = {
  sub_activity: string;
  hazard_outcome: string;
  initial_risk: CapOrmRiskLevel;
  control_text: string;
  residual_risk: CapOrmRiskLevel;
  implement_how: string;
  implement_who: string;
};

const EMPTY_ROW: HazardRowForm = {
  sub_activity: "",
  hazard_outcome: "",
  initial_risk: "L",
  control_text: "",
  residual_risk: "L",
  implement_how: "",
  implement_who: "",
};

function rowToForm(h: CapOrmHazard): HazardRowForm {
  return {
    sub_activity: h.sub_activity,
    hazard_outcome: h.hazard_outcome,
    initial_risk: h.initial_risk,
    control_text: h.control_text,
    residual_risk: h.residual_risk,
    implement_how: h.implement_how,
    implement_who: h.implement_who,
  };
}

// Matches routers/safety.py's CAP ORM compatibility surface (CAPF-160) —
// per your correction, this is the CAP-specific worksheet, distinct from
// the canonical SPE Hazard Register on Hazard Dashboard, which replaced it
// as the primary register. No desktop UI exists for this specific form
// shape, so this is built straight from the router's own request/response
// fields rather than a screen to match.
export default function CapOrmWorksheetPage() {
  const { incidentId, personnel } = useSession();
  const [op, setOp] = useState(1);
  const { data: form, isLoading: formLoading } = useCapOrmForm(incidentId!, op);
  const { data: hazards = [], isLoading: hazardsLoading } = useCapOrmHazards(incidentId!, op);
  const saveForm = useSaveCapOrmForm(incidentId!, op);
  const createHazard = useCreateCapOrmHazard(incidentId!, op);
  const updateHazard = useUpdateCapOrmHazard(incidentId!, op);
  const deleteHazard = useDeleteCapOrmHazard(incidentId!, op);
  const approve = useApproveCapOrmForm(incidentId!, op);

  const [activity, setActivity] = useState("");
  const [dateIso, setDateIso] = useState("");
  const [editing, setEditing] = useState<CapOrmHazard | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [rowForm, setRowForm] = useState<HazardRowForm>(EMPTY_ROW);

  useEffect(() => {
    setActivity(form?.activity ?? "");
    setDateIso(form?.date_iso ?? "");
  }, [form, op]);

  if (!incidentId) return null;

  const startAdd = () => {
    setRowForm(EMPTY_ROW);
    setIsNew(true);
    setEditing({} as CapOrmHazard);
  };
  const startEdit = (h: CapOrmHazard) => {
    setRowForm(rowToForm(h));
    setIsNew(false);
    setEditing(h);
  };
  const cancel = () => setEditing(null);
  const saveRow = () => {
    if (isNew) createHazard.mutate({ op_period: op, ...rowForm }, { onSuccess: cancel });
    else updateHazard.mutate({ hazardId: editing!.id, body: rowForm }, { onSuccess: cancel });
  };

  const saveHeader = () => {
    saveForm.mutate({ op_period: op, activity, prepared_by_id: personnel?.person_record ?? null, date_iso: dateIso });
  };

  const columns: ColumnDef<CapOrmHazard>[] = [
    { key: "sub_activity", header: "Sub-Activity", defaultWidth: 180 },
    { key: "hazard_outcome", header: "Hazard & Outcome", defaultWidth: 220 },
    { key: "initial_risk", header: "Initial Risk", defaultWidth: 100, render: (r) => RISK_LABELS[r.initial_risk] ?? r.initial_risk },
    { key: "control_text", header: "Control", defaultWidth: 220 },
    { key: "residual_risk", header: "Residual Risk", defaultWidth: 100, render: (r) => RISK_LABELS[r.residual_risk] ?? r.residual_risk },
    { key: "implement_how", header: "Implement How", defaultWidth: 180 },
    { key: "implement_who", header: "Implement Who", defaultWidth: 150 },
    {
      key: "_actions",
      header: "",
      defaultWidth: 110,
      render: (r) => (
        <span style={{ display: "flex", gap: 6 }}>
          <button type="button" className="secondary" style={{ width: "auto", padding: "2px 8px" }} onClick={() => startEdit(r)}>
            Edit
          </button>
          <button type="button" className="secondary" style={{ width: "auto", padding: "2px 8px" }} onClick={() => deleteHazard.mutate(r.id)}>
            Remove
          </button>
        </span>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
        <h2 style={{ margin: 0 }}>CAP ORM Worksheet</h2>
        <label className="field" style={{ margin: 0, flexDirection: "row", alignItems: "center", gap: 6 }}>
          Op. Period
          <input type="number" min={1} step={1} value={op} onChange={(e) => setOp(Math.max(1, Number(e.target.value) || 1))} style={{ width: 70 }} />
        </label>
      </div>
      <p className="muted" style={{ marginTop: -6 }}>
        CAPF 160-style view, synthesized from the same canonical hazard register as Hazard Dashboard — entries made here read/write the same
        underlying records through the legacy Sub-Activity / Hazard &amp; Outcome / Initial-Residual Risk form shape.
      </p>

      {formLoading ? (
        <p>Loading…</p>
      ) : (
        <>
          <div className="detail-header">
            <div className="field"><label>Activity</label><input value={activity} onChange={(e) => setActivity(e.target.value)} onBlur={saveHeader} /></div>
            <div className="field"><label>Prepared By</label><input readOnly value={personnel?.name ?? ""} /></div>
            <div className="field"><label>Date</label><input value={dateIso} onChange={(e) => setDateIso(e.target.value)} onBlur={saveHeader} placeholder="e.g. 2026-06-23T07:00" /></div>
            <div className="field"><label>Status</label><input readOnly value={form?.status ?? "draft"} /></div>
            <div className="field"><label>Highest Residual Risk</label><input readOnly value={form ? RISK_LABELS[form.highest_residual_risk] : ""} /></div>
          </div>

          {form?.approval_blocked && (
            <p className="error">Approval is blocked while the highest residual risk is High or Extremely High — lower every row's residual risk before submitting.</p>
          )}

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, marginTop: 10 }}>
            <h3 style={{ margin: 0 }}>Hazard Rows</h3>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="secondary" style={{ width: "auto" }} onClick={startAdd}>
                + Add Hazard Row
              </button>
              <button
                type="button"
                style={{ width: "auto" }}
                disabled={approve.isPending || form?.status === "approved"}
                onClick={() => approve.mutate()}
              >
                {form?.status === "approved" ? "Approved" : "Submit for Approval"}
              </button>
            </div>
          </div>
          {approve.isError && <p className="error">Approval failed — residual risk may still be too high.</p>}

          {editing !== null && (
            <div className="detail-header" style={{ marginBottom: 12 }}>
              <div className="field"><label>Sub-Activity</label><input value={rowForm.sub_activity} onChange={(e) => setRowForm({ ...rowForm, sub_activity: e.target.value })} /></div>
              <div className="field" style={{ gridColumn: "1 / -1" }}><label>Hazard &amp; Outcome</label><textarea value={rowForm.hazard_outcome} onChange={(e) => setRowForm({ ...rowForm, hazard_outcome: e.target.value })} /></div>
              <div className="field">
                <label>Initial Risk</label>
                <select value={rowForm.initial_risk} onChange={(e) => setRowForm({ ...rowForm, initial_risk: e.target.value as CapOrmRiskLevel })}>
                  {RISK_LEVELS.map((lvl) => (
                    <option key={lvl} value={lvl}>{RISK_LABELS[lvl]}</option>
                  ))}
                </select>
              </div>
              <div className="field" style={{ gridColumn: "1 / -1" }}><label>Control</label><textarea value={rowForm.control_text} onChange={(e) => setRowForm({ ...rowForm, control_text: e.target.value })} /></div>
              <div className="field">
                <label>Residual Risk</label>
                <select value={rowForm.residual_risk} onChange={(e) => setRowForm({ ...rowForm, residual_risk: e.target.value as CapOrmRiskLevel })}>
                  {RISK_LEVELS.map((lvl) => (
                    <option key={lvl} value={lvl}>{RISK_LABELS[lvl]}</option>
                  ))}
                </select>
              </div>
              <div className="field"><label>Implement How</label><input value={rowForm.implement_how} onChange={(e) => setRowForm({ ...rowForm, implement_how: e.target.value })} /></div>
              <div className="field"><label>Implement Who</label><input value={rowForm.implement_who} onChange={(e) => setRowForm({ ...rowForm, implement_who: e.target.value })} /></div>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" style={{ width: "auto" }} onClick={saveRow} disabled={!rowForm.sub_activity || !rowForm.hazard_outcome}>
                  Save
                </button>
                <button type="button" className="secondary" style={{ width: "auto" }} onClick={cancel}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          {hazardsLoading ? <p>Loading…</p> : <DataTable tableId="cap-orm-hazards" columns={columns} rows={hazards} rowKey={(r) => r.id} emptyMessage="No hazard rows yet." />}
        </>
      )}
    </div>
  );
}
